# VFX-Agent v2.0: Codex OD 模式重构设计

> **日期**: 2026-07-13
> **作者**: yangfei
> **状态**: Draft（待 user review）
> **目标分支**: `v2.0/codex-od`
> **目标 tag**: `v2.0.0`
> **基线对照**: VFX-Agent v1.0 (master, tag `v1.0.0`)，V2 测试基线 0.71（19 samples）

---

## 1. 背景

### 1.1 v1.0 现状（master 分支）

VFX-Agent v1.0 采用 **LangGraph 静态编排 + 3 Agent 独立调用** 架构：

```
extract_keyframes → decompose → generate → validate_shader → render_and_screenshot → inspect
                       ↑__________________________________________________________________|
                                       (LangGraph 反馈迭代)
```

- **PipelineState 4 区**: baseline / snapshot / gradient_window / checkpoint
- **3 Agent**: DecomposeAgent (多模态) / GenerateAgent (代码) / InspectAgent (评分)
- **BaseAgent**: 通过 OpenAI-compatible SDK 调模型 API（`base.py:157`）
- **V2 baseline**: 19 samples，平均 0.71，5/19 通过 (26.3%)

### 1.2 痛点

V2 baseline 测试显示 shader 生成质量差距巨大（0.00 ~ 0.95）。已优化方向：
- ✅ 9 个 few-shot 示例（消除 crash）
- ✅ Checkpoint.best_shader 回滚机制
- ❌ CV 特征提取（A/B 测试为负效果，已回退）
- ❌ 软标签效果分类（实现复杂，已回退）

**核心瓶颈**：shader 质量瓶颈不在编排层（LangGraph 状态机已完善），而在 LLM 的"思维僵化"。静态编排无法根据样本复杂度调整流程。

### 1.3 重构动机

参考 [nexu-io/open-design](https://github.com/nexu-io/open-design) 项目（77K+ stars，Claude Design 开源替代）的实际源码调研发现：**OD 的核心模式是"委托式编排"——一次 spawn Agent，让 Agent 自主完成全流程**。

| OD 实际模式（基于源码 fact-check） | VFX-Agent v1.0 |
|----------------------------------|----------------|
| 一次请求 → 一次 spawn | 6 节点状态机串行 |
| OD 自己不编排，Agent 自主决定顺序 | LangGraph 严格路由 |
| 多轮靠 codex session resume | Python 管理 generate_history |
| Agent 用内置工具（Read/Write/Edit/Bash）完成 | Python service 层显式调用 |
| Skills 注入 prompt，一次一个 | context_assembler 层叠拼接 |

**v2.0 核心转换**：从 Python 编排 Agent → Agent 编排 Python 工具。

### 1.4 Step 0 验证（已完成）

在重构启动前，已验证关键依赖：

| 检查项 | 结果 |
|--------|------|
| codex CLI 安装（v0.144.1） | ✅ |
| codex `exec` 子命令非交互模式 | ✅ |
| codex `--json` JSONL 事件流 | ✅ |
| codex `multi_agent` feature（stable + true）| ✅ features list 确认可用（用于评分阶段 spawn subagent）|
| Skill reference 脚本通过 Bash 调用 | ✅ codex 默认 Bash 工具可用 |
| codex 自主用 Bash+Python PIL 分析截图 | ✅（比 ViewImage 更精确，得到 RGB(0,255,235) 等真实像素值）|

**关键发现**:
1. codex 在 v0.144.1 + GPT-5 默认模型下，能自主用 Bash+PIL 精确读图（不需要专门的 ViewImage 工具）。比传统 ViewImage 更强 —— 能拿精确数值，反 hallucination
2. codex `multi_agent` feature 支持 spawn subagent，可在主 agent 内 fork 独立上下文的子任务（解决"自评偏见"问题的关键能力）
3. 简单工具（validate/render）不需要 MCP，直接写 Python 脚本放 skill reference/scripts/，codex 用 Bash 调用即可 —— 比 MCP 更简洁、更易调试

---

## 2. 目标与非目标

### 2.1 目标

1. **架构哲学转换**: 静态编排（LangGraph）→ 动态编排（SKILL.md 驱动）
2. **codex 一次调用完成全流程**: 分析图 → 写码 → 验证 → 渲染 → 自评 → 迭代
3. **保留 Python 硬约束**: validate_shader / render_shader 通过 skill reference scripts（Bash 调用）暴露给 codex
4. **架构简化**: 删除 graph.py / state.py / context_assembler.py / BaseAgent / 3 个 Agent 子类
5. **不破坏 v1.0**: master 保留作 V2 baseline 参照

### 2.2 非目标

- ❌ 不重写前端（仅 usePipeline.ts: polling → SSE）
- ❌ 不替换服务层（FFmpeg/Playwright/glslangValidator 保留）
- ❌ 不改 V2 baseline 测试规范（19 samples + 评分标准 + HTML 报告）
- ❌ 不实现 multi-skill 编排（一次只触发 vfx-shader-generation skill）
- ❌ 不实现 codex session resume（人工迭代用重新 spawn）

---

## 3. 架构设计

### 3.1 高层架构

```
┌──────────────────────────────────────────────────────────────────┐
│                    FastAPI Backend (v2.0)                         │
│                                                                  │
│  POST /pipeline/run ─────┐                                       │
│                          ▼                                       │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Pipeline Orchestrator (~120 行 Python)                   │   │
│  │                                                          │   │
│  │  1. extract_keyframes (FFmpeg，保留 v1.0)                │   │
│  │  2. 准备 workdir + symlink AGENTS.md + skill/ + 参考图   │   │
│  │  3. spawn codex (1 次, --ephemeral, --yolo, --json)      │   │
│  │  4. JSONL 流式解析 + SSE 推前端                           │   │
│  │  5. 提取 final_shader.glsl + evaluation.json             │   │
│  └────────────────┬─────────────────────────────────────────┘   │
│                   │                                              │
│                   ▼                                              │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  codex exec (1 次, 自主完成全流程)                        │   │
│  │                                                          │   │
│  │  按 skill/SKILL.md 工作流:                                │   │
│  │  Bash+PIL 看参考图 → Write visual_description.json       │   │
│  │  → Write shader.glsl                                     │   │
│  │  → Bash 调 reference/scripts/validate_shader.py          │   │
│  │    → 失败用 Edit 修正 (最多 3 次)                        │   │
│  │  → Bash 调 reference/scripts/render_shader.py            │   │
│  │    → 拿截图路径                                          │   │
│  │  → spawn subagent 独立评分（multi_agent, 上下文隔离）    │   │
│  │    └ subagent: 只看参考图+渲染图，输出 evaluation.json   │   │
│  │  → 主 agent 读 evaluation.json，不满意回 Write shader    │   │
│  │  → 输出 final_shader.glsl                                │   │
│  └────────────────┬─────────────────────────────────────────┘   │
│                   │                                              │
│                   ▼                                              │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Skill 资产 (workdir/.codex/skills/vfx-shader/)           │   │
│  │                                                          │   │
│  │  SKILL.md          — 工作流 + 评分 rubric + 效果目录     │   │
│  │  reference/                                              │   │
│  │    shader_templates.md    — 9 种效果模板                 │   │
│  │    few_shot_examples.md   — 压缩 few-shot                │   │
│  │    scripts/                                             │   │
│  │      validate_shader.py  — Bash 调用，stdout JSON        │   │
│  │      render_shader.py    — Bash 调用，stdout JSON        │   │
│  │      analyze_pixels.py   — 像素采样/对比工具             │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌────────────────┐  ┌────────────────┐                         │
│  │  State Store   │  │  SSE Emitter   │                         │
│  │  (JSON 文件)   │  │  (替代 polling) │                         │
│  └────────────────┘  └────────────────┘                         │
└──────────────────────────────────────────────────────────────────┘
       ▲ SSE (300ms 间隔推送)
       │
┌──────┴───────────────────────────────────────────────────┐
│  React Frontend (保留 v1.0，仅改 usePipeline.ts)         │
└──────────────────────────────────────────────────────────┘
```

**关键架构改动（相比 MCP 方案）**:
- ❌ 去掉 MCP server（不需要 fastmcp 依赖、不需要单独进程、不需要环境变量传上下文）
- ✅ validate/render 实现为 Python CLI 脚本，放在 skill reference/scripts/，codex 用 Bash 调用，参数走 argv，结果走 stdout JSON
- ✅ 评分阶段用 codex `multi_agent` feature spawn subagent，实现上下文隔离（解决自评偏见）

### 3.2 核心组件

| 组件 | 位置 | 行数估算 | 责任 |
|------|------|---------|------|
| **Pipeline Orchestrator** | `backend/app/orchestrator.py` | ~120 | spawn codex + JSONL 解析 + 状态更新（无 MCP 注册） |
| **Skill Package** | `backend/app/skills/vfx-shader/` | (整个目录) | codex 自主执行的全部资产 |
| ├─ SKILL.md | `SKILL.md` | ~700 | 工作流 + 评分 rubric + 效果目录 |
| ├─ reference/shader_templates.md | `reference/` | ~1200 | 9 种效果模板（codex 按需 Read） |
| ├─ reference/few_shot_examples.md | `reference/` | ~800 | 压缩 few-shot（codex 按需 Read） |
| ├─ reference/scripts/validate_shader.py | `reference/scripts/` | ~80 | Bash 调用，stdout JSON，调 v1.0 shader_validator |
| ├─ reference/scripts/render_shader.py | `reference/scripts/` | ~60 | Bash 调用，stdout JSON，调 v1.0 browser_render |
| └─ reference/scripts/analyze_pixels.py | `reference/scripts/` | ~50 | Bash 调用，像素采样/对比工具 |
| **AGENTS.md** | `backend/app/skills/AGENTS.md` | ~500 | 角色 + 工具概览 + VFX 术语库 |
| **State Store** | `backend/app/state_store.py` | ~60 | JSON 文件持久化 per pipeline_id |
| **SSE Router** | `backend/app/routers/pipeline.py` | ~100 | 替代 v1.0 的 polling |

### 3.3 数据流

```
用户上传视频/图片 + notes
   ↓
[Orchestrator] FFmpeg 提关键帧 → 4-6 张 PNG
   ↓
[Orchestrator] 创建 workdir (/tmp/vfx_pipelines/<uuid>/)
   ↓
[Orchestrator] symlink .codex/AGENTS.md + .codex/skills/vfx-shader/ + 拷贝参考图
   ↓
[Orchestrator] spawn codex exec（stdin 传 user prompt）
   ↓
[codex 主 agent] 按 SKILL.md 自主完成 6 phases
   ├── Phase 1: Bash+PIL 看参考图 → Write visual_description.json
   ├── Phase 2: Read reference/* (按需) → Write shader.glsl
   ├── Phase 3: Bash 调 reference/scripts/validate_shader.py shader.glsl
   │            → 失败 Edit 修正（最多 3 次）
   ├── Phase 4: Bash 调 reference/scripts/render_shader.py shader.glsl 1.0
   │            → 拿截图绝对路径
   ├── Phase 5: spawn subagent（multi_agent feature，独立上下文）
   │            └ subagent: 看参考图+渲染图+visual_description.json
   │                       → 写 evaluation.json（8 维评分 + pixel evidence）
   │            主 agent 读 evaluation.json
   └── Phase 6: 决定迭代 / 停止 → Write final_shader.glsl
   ↓ (JSONL 流式输出)
[Orchestrator] 解析每个 event → 更新 StateStore + SSE 推前端
   ↓
[Orchestrator] codex 退出后 → 读 final_shader.glsl + evaluation.json
   ↓
[State Store] 持久化 PipelineRecord（status / score / usage）
   ↓
[Frontend] SSE 收到 status=passed/failed → 停止订阅
```

### 3.4 关键边界（最重要的设计原则）

**Python 编排器只做 4 件事**:
1. FFmpeg 提关键帧（同步工具调用）
2. symlink skill 资产到 workdir
3. spawn codex（1 次）
4. JSONL 解析 + 状态更新 + SSE 推送 + 提取最终产物

**Python 编排器不做**:
- ❌ 阶段切换（交给 SKILL.md）
- ❌ 迭代次数控制（交给 SKILL.md）
- ❌ 评分比较 / 阈值判断（交给 SKILL.md + subagent）
- ❌ Checkpoint 回滚（取消这个概念，codex 自己维护 best）
- ❌ MCP server 启动/注册（取消 MCP，用 reference scripts 替代）

**Skill reference/scripts 只提供客观能力（Bash CLI 调用）**:
- ✅ validate_shader.py（GLSL 编译检查 - 客观，调 v1.0 shader_validator）
- ✅ render_shader.py（Playwright 渲染 - 物理，调 v1.0 browser_render）
- ✅ analyze_pixels.py（像素采样/对比 - 数据，给 subagent 评分用）
- ❌ 不提供 evaluate_shader（评分主观，由 codex subagent 在独立上下文中做）
- ❌ 不提供 list_keyframes（codex 直接 ls workdir/keyframes/）

**多 Agent 协作（codex multi_agent feature）**:
- ✅ 评分阶段强制 spawn subagent（独立 LLM context，避免主 agent "心软"）
- ✅ subagent 只看参考图+渲染图+visual_description.json，输出 evaluation.json
- ✅ 主 agent 读 evaluation.json 决定迭代（不直接参与评分）
- ❌ Decompose / Generate 不分 subagent（共享参考图上下文是优势）

---

## 4. 详细设计

### 4.1 SKILL.md（核心资产，~900 行）

**结构**:

```markdown
---
name: vfx-shader-generation
description: Generate Shadertoy GLSL shaders from reference images through self-directed iteration. Trigger: any visual effect / shader / GLSL task.
---

# VFX Shader Generation

[角色定义 + 平台约束]

## Workflow (MANDATORY — follow phases in order)

### Phase 1: Visual Analysis
- ls workdir/keyframes/ 获取参考图列表
- 使用 Bash+PIL 采样关键位置 RGB（4 corners + center + 4 edge midpoints）
- 识别 effect_type（9 种之一）
- 写 visual_description.json

### Phase 2: Code Generation
- 按 effect_type 选模板（Read reference/shader_templates.md）
- 写 shader.glsl，遵守 Shadertoy 约定

### Phase 3: Validation (HARD CONSTRAINT)
- 必须先调 reference/scripts/validate_shader.py shader.glsl
- 失败用 Edit 修正，最多 3 次
- 3 次仍失败 → 写 STOP reason 到 evaluation.json，停止

### Phase 4: Rendering (HARD CONSTRAINT)
- 必须用 reference/scripts/render_shader.py（禁止自己生成截图）
- 时间采样 [0.0, 0.5, 1.0, 1.5, 2.0]

### Phase 5: Independent Evaluation (subagent — 上下文隔离)
- **MUST spawn subagent**（codex multi_agent feature）做评分，禁止主 agent 自评
- subagent 任务输入：
  - 参考图路径列表（workdir/keyframes/）
  - 渲染截图路径列表（workdir/output/）
  - visual_description.json 内容
- subagent 工作流：
  - 用 reference/scripts/analyze_pixels.py 算 pixel evidence（参考 vs 渲染）
  - 按 8 维 rubric 评分（必须引用 pixel evidence）
  - 写 evaluation.json（含 pixel_evidence + dimension_scores + overall_score）
- 主 agent 读 evaluation.json 决定迭代

### Phase 6: Iteration Decision (NO LangGraph)
- overall_score >= 0.85 → DONE
- iteration < 3 AND 改善 → 回 Phase 2
- 否则写 best shader 到 final_shader.glsl

## Effect Catalog
[嵌入 vfx_effect_catalog.md 282 行]

## GLSL Platform Constraints
[嵌入 shared_vfx_constraints.md 69 行]

## Critical Rules (NON-NEGOTIABLE)
- NEVER skip Phase 3
- NEVER 自己生成截图（必须用 render_shader.py）
- NEVER exceed 3 iterations
- NEVER 用 3D raymarching / volume rendering
- NEVER 主 agent 自评（Phase 5 必须 spawn subagent）
- ALWAYS evaluation.json 含 pixel evidence
- reference scripts 不可用 → STOP，禁止 hallucinate
```

**关键设计决策**:
- **Phase 5 subagent 是反自评偏见的关键**：评分在独立 LLM context 中完成，主 agent 不能影响 subagent 判断。subagent 只看"参考+渲染+DSL"三件客观输入，不知道 shader 是怎么写的
- **Phase 5 pixel evidence 是反 hallucination 的关键**：评分必须基于真实像素 diff，subagent 用 analyze_pixels.py 算出客观数据
- **Phase 6 取消 checkpoint 概念**：codex 自己决定 best shader，Python 不再管
- **Few-shot 不嵌入主 SKILL.md**：放 reference/，codex 按需 Read（节省 ~12K token）
- **Scripts 与 prompt 同居 skill/reference/**：脚本作为 skill 的"可执行资产"，与 markdown 资产平级

### 4.2 AGENTS.md（角色 + 术语，~500 行）

```markdown
# VFX Shader Agent

[角色 + 工具概览 + 输出文件约定]

## Available Tools
- Skill scripts (Bash 调用): 
  - reference/scripts/validate_shader.py
  - reference/scripts/render_shader.py
  - reference/scripts/analyze_pixels.py
- System: Read, Write, Edit, Bash, Glob, Grep
- Multi-agent: 可 spawn subagent（用于评分阶段）
- Image analysis: Bash + Python PIL (ImageMagick not available by default)

## Output Files (in workdir)
- visual_description.json (Phase 1)
- shader.glsl (current, Phase 2)
- final_shader.glsl (best, Phase 6)
- evaluation.json (Phase 5 subagent 输出)

## VFX Terminology
[嵌入 shared_vfx_terminology.md 351 行]
```

### 4.3 Skill Scripts（reference/scripts/，替代 MCP）

**位置**: `backend/app/skills/vfx-shader/reference/scripts/`

**设计哲学**: 简单工具（validate/render）不需要 MCP，直接写 Python CLI 脚本，codex 用 Bash 调用即可。相比 MCP 方案：
- ❌ 无需 fastmcp 依赖
- ❌ 无需独立进程
- ❌ 无需环境变量传上下文（参数走 argv，结果走 stdout）
- ❌ 无需 mcp 注册步骤
- ✅ 更易调试（直接 python script.py 跑）
- ✅ 与 SKILL.md 同居一个 skill 目录，自然打包分发

**`validate_shader.py`** (~80 行):
```python
#!/usr/bin/env python3
"""Validate GLSL shader code for Shadertoy compatibility.
Usage: validate_shader.py <shader_file>
Output: JSON to stdout
"""
import sys, json
from pathlib import Path
# 从 v1.0 复用 shader_validator（sys.path 加 backend）
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / "backend"))
from app.services.shader_validator import validate_shader

shader_code = Path(sys.argv[1]).read_text()
result = validate_shader(shader_code)
print(json.dumps({
    "valid": result["valid"],
    "errors": result["errors"],
    "warnings": result["warnings"],
    "can_attempt_render": result.get("can_attempt_render", result["valid"]),
}, indent=2))
```

**`render_shader.py`** (~60 行):
```python
#!/usr/bin/env python3
"""Render GLSL shader at given time. Returns absolute screenshot path.
Usage: render_shader.py <shader_file> [time_seconds]
Output: JSON to stdout
"""
import sys, json, asyncio
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / "backend"))
from app.services.browser_render import render_and_screenshot

shader_code = Path(sys.argv[1]).read_text()
time_seconds = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
try:
    path = asyncio.run(render_and_screenshot(shader_code, time_seconds=time_seconds))
    print(json.dumps({"screenshot_path": str(path), "success": True, "error": None}))
except Exception as e:
    print(json.dumps({"screenshot_path": "", "success": False, "error": str(e)}))
```

**`analyze_pixels.py`** (~50 行):
```python
#!/usr/bin/env python3
"""Sample/compare pixels between reference and rendered images.
Usage: analyze_pixels.py <reference.png> <render.png> [--positions tl,tr,bl,br,center]
Output: JSON with pixel values + average color distance
"""
from PIL import Image
import json, sys, math

ref = Image.open(sys.argv[1]).convert("RGB")
render = Image.open(sys.argv[2]).convert("RGB")
# Resize render to match ref if different
if ref.size != render.size:
    render = render.resize(ref.size)

w, h = ref.size
positions = {
    "tl": (0, 0), "tr": (w-1, 0),
    "bl": (0, h-1), "br": (w-1, h-1),
    "center": (w//2, h//2),
}

result = {}
total_diff = 0
for name, (x, y) in positions.items():
    r, g, b = ref.getpixel((x, y))
    rr, rg, rb = render.getpixel((x, y))
    diff = (abs(r-rr) + abs(g-rg) + abs(b-rb)) / 3
    total_diff += diff
    result[name] = {
        "reference": [r, g, b],
        "render": [rr, rg, rb],
        "diff": round(diff, 2),
    }

result["avg_color_distance"] = round(total_diff / len(positions), 2)
print(json.dumps(result, indent=2))
```

**调用示例**（codex 用 Bash）:
```bash
# Phase 3 验证
python3 reference/scripts/validate_shader.py shader.glsl

# Phase 4 渲染
python3 reference/scripts/render_shader.py shader.glsl 1.0

# Phase 5 subagent 像素对比
python3 reference/scripts/analyze_pixels.py keyframes/001.png output/render_1.0.png
```

**为什么不用 MCP（重新评估）**:

| 维度 | MCP server | Skill reference scripts |
|------|-----------|------------------------|
| 依赖 | fastmcp + 独立进程 | 仅 Python 标准库 |
| 注册步骤 | `codex mcp add ...` | 无（codex 自动用 Bash） |
| 上下文传递 | 环境变量 | argv 参数 |
| 输出格式 | MCP 协议响应 | stdout JSON |
| 调试 | 难（黑盒） | 易（直接 python script.py） |
| 与 skill 打包 | 跨包（MCP 在外） | 同包（reference/scripts/） |
| 适合场景 | GUI / 不能 CLI 的工具 | **所有能用 CLI 的工具** |

VFX-Agent 的 validate/render/analyze_pixels 都是 CLI 友好的 Python 工具，**完全不需要 MCP**。

### 4.4 Python 编排器

**位置**: `backend/app/orchestrator.py`（~120 行，去 MCP 注册）

```python
class PipelineOrchestrator:
    async def run(self, pipeline_id: str, video_path: str | None,
                  images: list[str], notes: str, max_iterations: int = 3):
        workdir = Path(f"/tmp/vfx_pipelines/{pipeline_id}")
        (workdir / "keyframes").mkdir(parents=True)
        (workdir / "output").mkdir(parents=True)

        # 1. FFmpeg 提关键帧
        keyframes = extract_keyframes(video_path, output_dir=workdir/"keyframes") \
                    if video_path else self._copy_images(images, workdir/"keyframes")

        # 2. 准备 codex 工作区（symlink skill 资产，无 MCP 注册）
        self._setup_codex_workspace(workdir)

        # 3. spawn codex + 流式解析（无 MCP 启动步骤）
        await self._spawn_codex(pipeline_id, workdir, keyframes, notes, max_iterations)

        # 4. 提取产物
        final_shader = self._read_file_if_exists(workdir / "final_shader.glsl")
        evaluation = self._read_json_if_exists(workdir / "evaluation.json")

        # 5. 更新 StateStore
        record = StateStore.load(pipeline_id)
        record.final_shader = final_shader
        record.evaluation = evaluation
        record.status = self._compute_status(evaluation)
        StateStore.save(record)

    def _setup_codex_workspace(self, workdir: Path):
        """symlink skill 资产到 workdir/.codex/"""
        codex_dir = workdir / ".codex"
        codex_dir.mkdir(exist_ok=True)
        skills_src = Path("app/skills")  # 仓库内 skill 源
        # symlink 整个 skills/ 到 .codex/skills/
        (codex_dir / "skills").symlink_to(skills_src.absolute())
        # symlink AGENTS.md
        (codex_dir / "AGENTS.md").symlink_to(skills_src / "AGENTS.md").absolute()

    async def _spawn_codex(self, ...):
        user_prompt = self._build_user_prompt(keyframes, notes, max_iter)
        cmd = [
            "codex", "exec",
            "--json", "--yolo",
            "--skip-git-repo-check",
            "--ephemeral",
            "--disable", "plugins",  # 避免 superpowers 干扰
            "-C", str(workdir),
        ]
        for img in keyframes:
            cmd.extend(["-i", img])
        cmd.append("-")  # stdin prompt

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={
                **os.environ,
                "HTTP_PROXY": "http://127.0.0.1:7890",
                "HTTPS_PROXY": "http://127.0.0.1:7890",
            },
        )
        proc.stdin.write(user_prompt.encode())
        await proc.stdin.drain()
        proc.stdin.close()

        # 流式解析 JSONL → 更新 state + SSE 推前端
        async for line in proc.stdout:
            event = json.loads(line)
            await self._process_event(pipeline_id, event)

        await proc.wait()
```

### 4.5 状态持久化（JSON 文件，替代 PipelineState 4 区）

**位置**: `backend/app/pipeline_states/{pipeline_id}.json`

```python
@dataclass
class PipelineRecord:
    pipeline_id: str
    status: str  # running | passed | failed | timeout | max_iterations
    workdir: str
    keyframe_paths: list[str]
    final_shader: str = ""
    final_score: float = 0.0
    evaluation: dict | None = None
    codex_usage: dict | None = None  # token 统计
    duration_ms: int = 0
    error: str | None = None
    events: list[dict] = field(default_factory=list)  # JSONL 关键事件


class StateStore:
    STORE_DIR = Path("app/pipeline_states")

    @classmethod
    def save(cls, record: PipelineRecord):
        cls.STORE_DIR.mkdir(exist_ok=True)
        (cls.STORE_DIR / f"{record.pipeline_id}.json").write_text(
            json.dumps(asdict(record), indent=2, default=str)
        )

    @classmethod
    def load(cls, pipeline_id: str) -> PipelineRecord | None:
        path = cls.STORE_DIR / f"{pipeline_id}.json"
        if path.exists():
            return PipelineRecord(**json.loads(path.read_text()))
        return None
```

**取消 PipelineState 4 区**: codex 在 workdir 里通过文件管理（visual_description.json / shader.glsl / evaluation.json / final_shader.glsl），Python 不需要镜像。

### 4.6 前端协议（SSE 替代 polling）

**位置**: `backend/app/routers/pipeline.py`

```python
@router.post("/run")
async def run(...):
    # 同 v1.0，触发 BackgroundTasks
    pipeline_id = str(uuid.uuid4())
    background_tasks.add_task(_execute_pipeline, pipeline_id, ...)
    return {"pipeline_id": pipeline_id, "status": "running"}


@router.get("/stream/{pipeline_id}")
async def stream(pipeline_id: str):
    """SSE 替代 v1.0 的 500ms polling"""
    async def gen():
        last_event_id = 0
        while True:
            events = EventStore.get_after(pipeline_id, last_event_id)
            for e in events:
                yield f"data: {json.dumps(e)}\n\n"
                last_event_id = e["id"]
            record = StateStore.load(pipeline_id)
            if record and record.status in ("passed", "failed", "timeout", "max_iterations"):
                break
            await asyncio.sleep(0.3)  # 300ms 间隔（比 v1.0 的 500ms 更快）

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

**前端改动**: `frontend/src/hooks/usePipeline.ts`
- 把 `setInterval` 500ms polling → `EventSource` 订阅
- 状态数据格式保持一致
- **除 usePipeline.ts 外其他前端组件不改**（InputPanel / ShaderEditor / ShaderPreview / AgentLog / ParameterPanel / SettingsPanel / FeedbackPanel / PipelineStatus / VFXDiscoveryForm / CodeView / UploadPanel 全部保留）

### 4.7 错误处理

| 错误类型 | 检测方式 | 处理策略 |
|---------|---------|---------|
| codex 子进程超时 | `asyncio.wait_for(timeout=600)` | SIGTERM → 10s → SIGKILL，status="timeout"，提取已有的 best shader |
| codex 卡死（无新事件） | 监听 stdout，10 分钟无新事件 | 同上 |
| JSONL 解析失败 | `json.loads()` 抛异常 | 跳过该行，warning 到 record.events，继续 |
| skill script 调用失败（validate/render） | script 退出码 != 0 或 stdout 不是 JSON | codex 读 stderr，决定是否重试（最多 3 次） |
| subagent spawn 失败 | JSONL 无 `subagent` 相关事件 | 主 agent 降级为自评（加 warning），或停止 |
| subagent 输出无效 evaluation.json | schema 校验失败 | 主 agent 重 spawn 1 次；仍失败 → 用 analyze_pixels.py 的客观数据降级评分 |
| shader 连续编译失败 | SKILL.md 已限制最多 3 次验证 | codex 写 STOP reason，编排器照常提取 |
| 缺 final_shader.glsl | codex 退出后检查文件 | 降级用 shader.glsl，status="max_iterations" |
| 缺 evaluation.json | 同上 | score=0.0，status="failed" |
| codex 输出空响应 | proc.stdout 全空 | status="failed"，error="empty_codex_response" |
| codex 违反 SKILL.md（跳过 validate / 主 agent 自评） | JSONL 事件分析 | MVP 阶段观察，决定是否加 Python 强制门禁 |
| 网络问题 | codex stderr 含 "WebSocket timed out" | 重试 1 次，仍失败 status="failed" |

---

## 5. 测试策略

### 5.1 MVP 5 步渐进

| Step | 测试内容 | 成功标准 | 失败处理 |
|------|---------|---------|---------|
| **0** | ✅ 已完成：codex 0.144.1 + Bash+PIL 看图 + multi_agent feature | 通过 | — |
| **1** | heart-2d 单样本：SKILL.md + skill scripts + codex 跑通完整流程（含 subagent 评分） | final_shader.glsl + evaluation.json 非空，subagent 事件存在 | 调 SKILL.md 措辞，重跑（最多 3 次） |
| **2** | heart-2d 评分对比：codex subagent 评分 vs v1.0 InspectAgent 离线评估 | 差距 < 0.10（验证 subagent 真做了上下文隔离） | 加强 Phase 5 subagent 指令，重测 |
| **3** | heart-2d 多轮迭代验证：max_iterations=3 | 第 N 轮评分 > 第 1 轮 | 调 Phase 6 指令 |
| **4** | 3 simple 样本（heart-2d / 4-col-grad / shiny-circle） | 平均分 ≥ v1.0 基线 (0.90) | 分类问题（prompt/模型/scripts） |
| **5** | 19 全量样本 | 平均分 ≥ v1.0 V2 baseline (0.71) | 部分失败可接受，分析 pattern |

### 5.2 A/B 对比测试方法

```python
# backend/tests/e2e/test_ab_codex_vs_v1.py
async def test_ab_heart_2d():
    # A: v2.0 codex OD 模式（subagent 评分）
    codex_shader, codex_eval = await run_codex_pipeline("heart-2d")

    # B: 用 v1.0 InspectAgent（独立 LLM 调用）二次评估 v2.0 输出
    # （仅作 cross-validation，不参与新 pipeline）
    v1_score = await v1_inspect_agent.evaluate(
        reference=keyframes,
        render=render_shader(codex_shader, time=1.0),
        dsl=parse_visual_description(codex_eval),
    )

    # codex subagent 评分 vs v1.0 独立评分
    assert abs(codex_eval["overall_score"] - v1_score["overall_score"]) < 0.10
```

**关键**:
- v2.0 内部的"subagent 评分"本身就是上下文隔离的（解决自评偏见），不需要外部评估器
- 保留 v1.0 `backend/app/agents/inspect.py` 仅作 A/B cross-validation 用，**不参与 v2.0 pipeline**
- Step 5 通过后删除 v1.0 InspectAgent

### 5.3 性能基准（容许退化范围）

| 指标 | v1.0 baseline | v2.0 目标 | 容许退化 |
|------|--------------|----------|---------|
| 单 pipeline 延迟（cold） | 30-60s | 60-120s | 2x |
| 单 pipeline 延迟（warm） | 20-40s | 40-80s | 2x |
| Token 消耗 / pipeline | ~30K | ~60-90K | 3x |
| 19 样本平均分 | 0.71 | ≥ 0.71 | 0% |
| 19 样本通过率 | 26.3% | ≥ 26.3% | 0% |

---

## 6. 仓库策略

### 6.1 版本命名约定

| 版本 | 分支 | tag | 架构 | 测试基线 |
|------|------|-----|------|---------|
| **VFX-Agent v1.0** | master | `v1.0.0` | LangGraph + 3 Agent | V2 baseline 0.71 (19 samples) |
| **VFX-Agent v2.0** | v2.0/codex-od | `v2.0.0`（待打） | codex OD 模式 | 待 MVP 验证 |

> **歧义澄清**: "V2 baseline" 是测试系列号（V1/V2 测试），"v1.0/v2.0 架构" 是架构版本号 —— 两个维度独立。

### 6.2 分支策略

- **master**（v1.0）: 保留作 V2 baseline 参照，只接受 bug fix，不再开发新功能
- **v2.0/codex-od**: 重构主开发分支，所有 v2.0 工作 commit 到此
- worktree 隔离: `.worktrees/v2.0-codex-od`（已创建）

### 6.3 v2.0 完成后的处理

- v2.0 通过 Step 5 验证后：
  - 在 master 上打 tag `v1.0.0`，README 加一行 "已废弃，看 v2.0/codex-od 分支"
  - 在 v2.0/codex-od 上打 tag `v2.0.0`
  - **不立即 merge v2.0 → master**，让两个分支并存一段时间观察
  - 长期：v2.0 稳定后可考虑替换 master，或永久双轨

---

## 7. 实施计划

> **时间估算原则**: 用户使用 AI agent（opencode + GLM）辅助开发 + codex 迭代以小时为单位，**不再以"天"为单位估算**。每个 Phase 内的子任务以"会话"（session，~30-90 分钟）计量。

### 7.1 Phase A-E 时间线（压缩版）

```
Phase A: 基础设施搭建 (1 个长会话，~3-4 小时)
    ↓
Phase B: MVP Step 1 - heart-2d 跑通 (1-2 个迭代会话，~2-3 小时) ← 关键决策点
    ↓
Phase C: MVP Step 2-3 - A/B + 多轮迭代 (1 个会话，~1-2 小时) ← 关键决策点
    ↓
Phase D: MVP Step 4-5 - 3 样本 → 19 样本 (2-3 个迭代会话，~3-5 小时) ← 关键决策点
    ↓
Phase E: 删除旧代码 + 文档收尾 (1 个会话，~1 小时)
```

**总计 ~10-15 小时**（约 2-3 个工作日，含调试 buffer），相比 v1.0 风格的"5-7 天"压缩 ~60%。

每个 Phase 后用 @oracle 做风险评估，决定继续/调整/中止。

### 7.2 各 Phase 任务分解（AI 辅助开发节奏）

#### Phase A: 基础设施搭建（~3-4 小时，1 个长会话）

| 任务 | 负责 | 产出 |
|------|------|------|
| 在 v2.0 worktree 中保留 services/ + frontend/，删除 pipeline/ 和 agents/ | @fixer | v2.0 干净起点（仅保留可复用代码） |
| 写 skill scripts（validate_shader.py / render_shader.py / analyze_pixels.py） | @fixer | `backend/app/skills/vfx-shader/reference/scripts/*.py` |
| 实现 state_store.py | @fixer | `backend/app/state_store.py` |
| 实现 orchestrator.py 骨架（symlink skill + spawn codex + JSONL 解析） | @fixer | `backend/app/orchestrator.py` |
| 重写 routers/pipeline.py（SSE） | @fixer | `backend/app/routers/pipeline.py` |
| 梳理 7 个 prompt md → AGENTS/SKILL/reference 映射 | @explorer | 拆分映射表 + token 估算 |
| 查 codex multi_agent subagent 调用方式（spawn 语法、上下文隔离边界） | @librarian | subagent 调用示例 |
| 前端 usePipeline.ts: polling → SSE | @fixer | `frontend/src/hooks/usePipeline.ts` |

**Phase A 验收**: backend 启动无报错 + codex 能 Bash 调通 skill scripts + SSE 端点返回状态变化

**Phase A 并行**: fixer-A1（scripts + state_store）/ fixer-A2（orchestrator + router）/ fixer-A3（前端）三实例并行

#### Phase B: MVP Step 1 - heart-2d 跑通（~2-3 小时，1-2 个迭代会话）

| 任务 | 负责 |
|------|------|
| 写 v2.0 SKILL.md（~700 行，含 subagent Phase 5 指令） | @fixer + 我审查 |
| 写 v2.0 AGENTS.md（~500 行） | @fixer + 我审查 |
| 重组 reference/（shader_templates + few_shot 压缩） | @fixer |
| 跑 heart-2d 单样本 | @fixer |
| **风险审查**（codex 是否遵守 SKILL.md？subagent 评分正常 spawn 吗？） | @oracle |

**Phase B 决策点**:
- ✅ codex 输出非空 + subagent 事件存在 → Phase C
- ⚠️ codex 跳过 validate 或不 spawn subagent → 调 SKILL.md 措辞，重跑 1 次（~30 分钟）
- ❌ codex 完全不工作 → 中止，回 brainstorming

#### Phase C: MVP Step 2-3 - A/B + 多轮迭代（~1-2 小时，1 个会话）

| 任务 | 负责 |
|------|------|
| 临时保留 v1.0 InspectAgent 作 cross-validation 评估器 | @fixer |
| 写 A/B 测试脚本（subagent 评分 vs v1.0 评分） | @fixer |
| heart-2d 跑 max_iterations=3 | @fixer |
| **风险审查** | @oracle |

**Phase C 决策点**:
- ✅ subagent 评分 vs v1.0 独立评分差距 < 0.10 → Phase D
- ⚠️ 差距 0.10-0.20 → 加强 subagent 上下文隔离 + pixel evidence，重测
- ❌ 差距 > 0.20 → 中止

#### Phase D: 扩展验证（~3-5 小时，2-3 个迭代会话）

| 任务 | 负责 |
|------|------|
| 3 simple 样本 | @fixer |
| **风险审查**（通过率 vs v1.0 基线 0.90） | @oracle |
| 19 全量样本（codex 并发跑 3-4 个，缩短总时长） | @fixer |
| HTML 报告生成（对比 v1.0 V2 baseline） | @fixer |
| **最终风险审查** | @oracle |

**Phase D 决策点**:
- ✅ 平均分 ≥ 0.71 → Phase E
- ⚠️ 0.60-0.71 → 调 SKILL.md 或保留双轨
- ❌ < 0.60 → 归档 v2.0/codex-od 分支

#### Phase E: 清理（~1 小时，1 个会话）

| 任务 | 负责 |
|------|------|
| 删除 graph.py / state.py / context_assembler / BaseAgent / 3 Agent | @fixer |
| 删除 v1.0 配置项 | @fixer |
| 更新 README / AGENTS.md | 我 |
| 打 tag `v2.0.0` + master 打 tag `v1.0.0` | 我 |

### 7.3 工作分配原则

| Agent | 主要承担 |
|-------|---------|
| **@fixer** | 80% 代码实施（Phase A 三实例并行） |
| **@oracle** | 每个 Phase 后风险评估 + 关键设计审查 |
| **@explorer** | Phase A 的 prompt 资产 mapping |
| **@librarian** | Phase A 的 codex multi_agent subagent 调用方式查询 |
| **@designer** | 不需要（前端改动小，@fixer 直接处理） |
| **orchestrator** | 设计审查、SKILL.md 撰写指导、跨 phase 协调、用户沟通 |

### 7.4 可并行任务（@fixer 多实例）

Phase A 内可并行:
- **fixer-A1**: skill scripts + state_store（后端基础设施）
- **fixer-A2**: orchestrator + routers/pipeline（编排层 + SSE）
- **fixer-A3**: 前端 usePipeline.ts 改造

并行前提: 写 ownership 隔离，无文件冲突。

### 7.5 失败回退策略

任何 Phase 失败:
1. 立即停止后续 phase
2. 保留当前 worktree 状态作 debug 材料
3. 派 @oracle 做 root cause 分析
4. 决定: 调设计重试 / 退回上一 phase / 完全放弃 v2.0

---

## 8. 风险评估

### 8.1 P0 风险

| ID | 风险 | Mitigation |
|----|------|-----------|
| **R1** | codex 跳过 validate 直接 render（违反 SKILL.md） | Phase B 观察遵守度。<50% 则加 Python 强制门禁（render_shader.py 内部先调 validate） |
| **R2** | codex 主 agent 自评（不 spawn subagent，违反 SKILL.md Phase 5） | Phase B 强制观察 subagent 事件。若 codex 不 spawn subagent → 加 prompt 强约束 + 重 spawn |
| **R3** | subagent 评分仍有偏见（与主 agent 共享底模） | Phase C A/B vs v1.0 InspectAgent。差距 > 0.10 则加强 pixel evidence + 上下文隔离 |
| **R4** | codex 卡在无限迭代 | asyncio.wait_for(600s) 硬超时 + SKILL.md "max 3 iterations" |
| **R5** | GPT-5 GLSL 质量 < v1.0 Generate Agent 模型 | Phase D 严格 A/B。若显著差，归档 v2.0 分支 |

### 8.2 P1 风险

| ID | 风险 | Mitigation |
|----|------|-----------|
| R6 | 上下文超限（4521 行 prompt + 9 few-shot + 多图 + subagent fork） | 分层加载，主 SKILL.md ~12K token，reference 按需 Read |
| R7 | 网络抖动（codex 调 OpenAI API） | spawn 时设 HTTP_PROXY + 失败重试 1 次 |
| R8 | 可观测性下降（codex + subagent 黑盒） | JSONL 全量保存到 record.events（含 subagent 事件），session_logger 保留 |
| R9 | subagent spawn 失败 / 不返回 evaluation.json | 主 agent 降级用 analyze_pixels.py 客观数据，加 warning |

---

## 9. 删除/保留/新建清单

### 9.1 删除（Phase E，全量验证通过后）

```
backend/app/
├── pipeline/
│   ├── graph.py          ❌ 删除（1166 行 LangGraph 编排）
│   └── state.py          ❌ 删除（520 行 PipelineState 4 区）
├── agents/
│   ├── base.py           ❌ 删除（195 行 BaseAgent）
│   ├── decompose.py      ❌ 删除（198 行）
│   ├── generate.py       ❌ 删除（272 行）
│   └── inspect.py        ❌ Phase E 删除（Phase C/D 暂留作 A/B cross-validation）
├── services/
│   └── context_assembler.py  ❌ 删除（347 行，被 SKILL.md 替代）
```

### 9.2 保留（v1.0 工具层 + UI）

```
backend/app/services/
├── video_extractor.py    ✅ 保留（FFmpeg，编排器直接调）
├── browser_render.py     ✅ 保留（被 skill scripts/render_shader.py 调用）
├── shader_validator.py   ✅ 保留（被 skill scripts/validate_shader.py 调用）
├── validators.py         ✅ 保留（DSL 校验）
└── session_logger.py     ✅ 保留（记 codex JSONL）

frontend/src/             ✅ 全保留
└── hooks/usePipeline.ts  ⚠️ 改: HTTP polling → EventSource
```

### 9.3 新建

```
backend/app/
├── orchestrator.py                        🆕 ~120 行
├── state_store.py                         🆕 ~60 行
├── pipeline_states/                       🆕 运行时目录（gitignored）
├── skills/                                🆕 skill 包根目录
│   ├── AGENTS.md                          🆕 ~500 行（角色 + 术语）
│   └── vfx-shader/                        🆕 主 skill 包
│       ├── SKILL.md                       🆕 ~700 行（工作流 + 评分 + 效果目录）
│       └── reference/
│           ├── shader_templates.md        (~1200 行)
│           ├── few_shot_examples.md       (~800 行压缩版)
│           └── scripts/
│               ├── validate_shader.py     🆕 ~80 行（Bash 调用 v1.0 shader_validator）
│               ├── render_shader.py       🆕 ~60 行（Bash 调用 v1.0 browser_render）
│               └── analyze_pixels.py      🆕 ~50 行（像素采样/对比工具）
└── routers/pipeline.py                    ✏️ 改写（SSE 替代 polling）
```

### 9.4 配置改动

```env
# backend/.env 新增
CODEX_PROXY=http://127.0.0.1:7890
CODEX_TIMEOUT=600
CODEX_MAX_ITERATIONS=3

# 删除（Phase E 后）
# DECOMPOSE_API_KEY / DECOMPOSE_BASE_URL / DECOMPOSE_MODEL
# GENERATE_API_KEY / GENERATE_BASE_URL / GENERATE_MODEL
# INSPECT_API_KEY / INSPECT_BASE_URL / INSPECT_MODEL
# PROXY
```

```txt
# backend/requirements.txt
# 无新增依赖（取消了 fastmcp，scripts 只用 Python 标准库 + v1.0 已有依赖）
```

---

## 10. 相关调研引用

本设计文档基于以下 background 调研结果：

| 调研 | Session ID | 关键发现 |
|------|-----------|---------|
| **lib-1**: nexu-io/open-design 项目研究 | ses_0a6b3a5b1ffeLHS1oC5I8POOcx | OD 是 Claude Design 开源替代，77K+ stars，Apache-2.0，Skills + DESIGN.md 架构 |
| **exp-1**: VFX-Agent v1.0 架构调研 | ses_0a6a7f309ffeuMt64Wdrle0OK4 | 唯一模型 API 调用点 base.py:157，4 区状态，6 节点 LangGraph |
| **lib-2**: codex CLI 协议 | ses_0a6a78e61ffe1mWuIXrnb5yjHN | codex exec 非交互模式，JSONL 事件流，multi_agent feature |
| **ora-1**: 重构可行性分析 | ses_0a6a2f3daffeQRhpdFHxIxUE49 | 基于 OD 实际源码的方案 Y 设计（预处理外包 + 全委托） |
| **fix-1**: Step 0 codex Bash+PIL 看图验证 | ses_0a68fba04ffe844gJ64oPNmA8M | fix-1 用 codex 0.140 失败；后续升级到 0.144.1 后 Bash+PIL 看图成功 |

---

## 11. 决策记录

### 11.1 关键决策

| # | 决策 | 选择 | 理由 |
|---|------|------|------|
| 1 | codex 调用模式 | 1 次自主调用（方案 B） | 纯 OD 哲学，让 codex 用工具能力 + GPT-5 代码能力 |
| 2 | Session 模式 | `--ephemeral` | 上下文隔离，避免上一 pipeline 残留 |
| 3 | 看图机制 | codex 自主 Bash+PIL | Step 0 已验证（codex 0.144.1），比 ViewImage 更精确 |
| 4 | **客观工具实现方式** | **Skill reference scripts（Bash 调用）** | 比 MCP 更简洁，无需 fastmcp/独立进程/环境变量；与 SKILL.md 同居 skill 包，自然打包分发 |
| 5 | **评分机制** | **codex subagent（multi_agent feature）独立评分** | 上下文隔离避免主 agent 自评偏见；比保留 v1.0 InspectAgent 更纯 OD |
| 6 | 状态持久化 | JSON 文件 per pipeline_id | 简单优先，无 SQL 依赖 |
| 7 | 前端协议 | SSE 替代 500ms polling | 实时性 + FastAPI 原生支持 |
| 8 | 仓库策略 | 当前仓 + 分支隔离 | 重用 v1.0 服务层/前端/测试基础设施 |
| 9 | 版本命名 | v1.0 = master / v2.0 = v2.0/codex-od | 双版本并列对照 |
| 10 | 多轮人工迭代 | 重新 spawn codex（不用 --resume） | --ephemeral 模式下无 session 可续 |
| 11 | Checkpoint 概念 | 取消 | codex 自己决定 best，Python 不镜像状态 |

### 11.2 已拒绝的替代方案

| 方案 | 拒绝理由 |
|------|---------|
| 方案 A: 3 次独立 codex exec | 等于"用 codex 当 dumb LLM caller"，没拿到 OD 真正好处（oracle 第一次批评） |
| 方案 C: 阶段切换 + Generate 自主迭代 | 折中方案，但失去纯 OD 哲学的清晰性 |
| 新建独立仓库 vfx-codex | 失去 v1.0 8000+ 行服务层/前端/测试基础设施复用 |
| 保留 LangGraph 作 fallback | 双轨维护成本高，违背"全量重构"决策 |
| **MCP server 实现 validate/render** | **过度工程**：能用 CLI 脚本完成的工具不需要 MCP 协议；MCP 适合"GUI / 不能 CLI 的工具"，VFX-Agent 场景不匹配 |
| **保留 v1.0 InspectAgent 作主评分器** | **违背 OD 哲学**：评分应交给 codex subagent 在统一架构内完成，而非保留 v1.0 旧组件；subagent 已实现上下文隔离，无需外部评估器 |

### 11.3 已 A/B 测试 / 验证的子决策

| 子决策 | 验证方式 | 结果 |
|--------|---------|------|
| codex 0.144.1 + GPT-5 能精确看图 | Step 0 测试 | ✅ 通过（RGB(0,255,235) 等精确像素值） |
| codex Bash 工具调用稳定 | Step 0 测试（自主用 PIL 分析） | ✅ codex 自主选 PIL 而非 ImageMagick |
| codex `multi_agent` feature 可用 | `codex features list` | ✅ stable + true |
| codex `--disable plugins` 避免 superpowers 干扰 | Step 0 测试 | ✅ 必需 |

---

## 12. 后续行动

本文档是 **brainstorming 阶段产出**。User review 通过后，下一步:

1. **Transition to writing-plans skill**: 把本设计转化为可执行的 implementation plan（含具体文件、行号、依赖关系）
2. **实施**: 按 Phase A-E 执行
3. **每个 Phase 后用 @oracle 风险评估**

---

*本设计基于 2026-07-13 的 OD 实际源码调研 + codex CLI 协议调研 + VFX-Agent v1.0 架构调研 + Step 0 验证结果。如环境发生重大变化（codex 版本升级、OD 架构演进、OpenAI API 变更），需重新评估。*
