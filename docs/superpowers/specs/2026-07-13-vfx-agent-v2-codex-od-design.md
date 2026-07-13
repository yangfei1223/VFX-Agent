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
| codex `mcp` 子命令 MCP server 注册 | ✅ |
| codex `--json` JSONL 事件流 | ✅ |
| MCP server (fastmcp) 工具调用 | ✅ 5/5 成功 |
| codex 自主用 Bash+Python PIL 分析截图 | ✅（比 ViewImage 更精确，得到 RGB(0,255,235) 等真实像素值）|

**关键发现**：codex 在 v0.144.1 + GPT-5 默认模型下，能自主用 Bash+PIL 精确读图（不需要专门的 ViewImage 工具）。这比传统 ViewImage 更强 —— 能拿精确数值，反 hallucination。

---

## 2. 目标与非目标

### 2.1 目标

1. **架构哲学转换**: 静态编排（LangGraph）→ 动态编排（SKILL.md 驱动）
2. **codex 一次调用完成全流程**: 分析图 → 写码 → 验证 → 渲染 → 自评 → 迭代
3. **保留 Python 硬约束**: validate_shader / render_shader 通过 MCP 暴露给 codex
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
│  │  Pipeline Orchestrator (~150 行 Python)                   │   │
│  │                                                          │   │
│  │  1. extract_keyframes (FFmpeg，保留 v1.0)                │   │
│  │  2. 准备 workdir + AGENTS.md + 参考图                    │   │
│  │  3. 注册 MCP server（per-pipeline 独立进程）             │   │
│  │  4. spawn codex (1 次, --ephemeral, --yolo, --json)      │   │
│  │  5. JSONL 流式解析 + SSE 推前端                           │   │
│  │  6. 提取 final_shader.glsl + evaluation.json             │   │
│  └────────────────┬─────────────────────────────────────────┘   │
│                   │                                              │
│                   ▼                                              │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  codex exec (1 次, 自主完成全流程)                        │   │
│  │                                                          │   │
│  │  按 SKILL.md 工作流:                                      │   │
│  │  list_keyframes → Bash+PIL 看参考图                      │   │
│  │  → Write visual_description.json                         │   │
│  │  → Write shader.glsl                                     │   │
│  │  → MCP validate_shader → 修正 (最多 3 次)               │   │
│  │  → MCP render_shader → 拿截图                            │   │
│  │  → Bash+PIL 分析截图                                     │   │
│  │  → 自评 → 不满意回到 Write                               │   │
│  │  → 输出 final_shader.glsl + evaluation.json              │   │
│  └────────────────┬─────────────────────────────────────────┘   │
│                   │                                              │
│                   ▼                                              │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  MCP Server (vfx-tools, Python fastmcp)                   │   │
│  │                                                          │   │
│  │  - validate_shader(code) → {valid, errors}               │   │
│  │  - render_shader(code, time) → screenshot_path           │   │
│  │  - list_keyframes() → [paths]                            │   │
│  │  环境变量: PIPELINE_ID / VFX_OUTPUT_DIR / VFX_KEYFRAME_PATHS │
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

### 3.2 核心组件

| 组件 | 位置 | 行数估算 | 责任 |
|------|------|---------|------|
| **Pipeline Orchestrator** | `backend/app/orchestrator.py` | ~150 | spawn codex + JSONL 解析 + 状态更新 |
| **MCP Server** | `backend/app/mcp_server/__init__.py` | ~80 | 3 个工具（validate/render/list_keyframes） |
| **State Store** | `backend/app/state_store.py` | ~60 | JSON 文件持久化 per pipeline_id |
| **SKILL.md** | `backend/app/prompts/SKILL_vfx.md` | ~900 | 工作流 + 评分 rubric + 效果目录 |
| **AGENTS.md** | `backend/app/prompts/AGENTS.md` | ~500 | 角色 + 工具概览 + VFX 术语库 |
| **reference/** | `backend/app/prompts/reference/` | ~2000 | shader_templates + few_shot（codex 按需 Read） |
| **SSE Router** | `backend/app/routers/pipeline.py` | ~100 | 替代 v1.0 的 polling |

### 3.3 数据流

```
用户上传视频/图片 + notes
   ↓
[Orchestrator] FFmpeg 提关键帧 → 4-6 张 PNG
   ↓
[Orchestrator] 创建 workdir (/tmp/vfx_pipelines/<uuid>/)
   ↓
[Orchestrator] 写 .codex/AGENTS.md + symlink SKILL.md + 准备 reference/
   ↓
[Orchestrator] 启动 MCP server 子进程（环境变量传 pipeline 上下文）
   ↓
[Orchestrator] 注册 MCP 到 codex: codex mcp add vfx-tools -- python -m app.mcp_server
   ↓
[Orchestrator] spawn codex exec（stdin 传 user prompt）
   ↓
[codex] 按 SKILL.md 自主完成 6 phases
   ├── Phase 1: list_keyframes → Bash+PIL 分析参考图 → Write visual_description.json
   ├── Phase 2: Read reference/* (按需) → Write shader.glsl
   ├── Phase 3: MCP validate_shader → Edit 修正（最多 3 次）
   ├── Phase 4: MCP render_shader → 拿截图路径
   ├── Phase 5: Bash+PIL 分析截图 → 写 evaluation.json（含 pixel evidence）
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
2. spawn codex（1 次）
3. JSONL 解析 + 状态更新 + SSE 推送
4. 提取最终产物（final_shader.glsl + evaluation.json）

**Python 编排器不做**:
- ❌ 阶段切换（交给 SKILL.md）
- ❌ 迭代次数控制（交给 SKILL.md）
- ❌ 评分比较 / 阈值判断（交给 SKILL.md）
- ❌ Checkpoint 回滚（取消这个概念，codex 自己维护 best）

**MCP 工具只暴露客观能力**:
- ✅ validate_shader（GLSL 编译检查 - 客观）
- ✅ render_shader（Playwright 渲染 - 物理）
- ✅ list_keyframes（路径查询 - 数据）
- ❌ 不暴露 evaluate_shader（评分主观，由 codex 在对话中做）
- ❌ 不暴露 save_state / load_state（编排器管）

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
- 使用 list_keyframes MCP 获取参考图路径
- 使用 Bash+PIL 采样关键位置 RGB（4 corners + center + 4 edge midpoints）
- 识别 effect_type（9 种之一）
- 写 visual_description.json

### Phase 2: Code Generation
- 按 effect_type 选模板（Read reference/shader_templates.md）
- 写 shader.glsl，遵守 Shadertoy 约定

### Phase 3: Validation (HARD CONSTRAINT)
- 必须先调 validate_shader MCP
- 失败用 Edit 修正，最多 3 次
- 3 次仍失败 → 写 STOP reason 到 evaluation.json，停止

### Phase 4: Rendering (HARD CONSTRAINT)
- 必须用 render_shader MCP（禁止自己生成截图）
- 时间采样 [0.0, 0.5, 1.0, 1.5, 2.0]

### Phase 5: Self-Evaluation
- 必须 Bash+PIL 算像素 evidence（反 hallucination）
- 8 维评分：composition / geometry / color / animation / background / lighting / texture / vfx_details
- 写 evaluation.json（含 pixel_evidence 字段）

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
- NEVER 自己生成截图
- NEVER exceed 3 iterations
- NEVER 用 3D raymarching / volume rendering
- ALWAYS 含 pixel evidence
- MCP 工具不可用 → STOP，禁止 hallucinate
```

**关键设计决策**:
- **Phase 5 pixel evidence 是反 hallucination 的关键**：评分必须基于真实像素 diff，不是凭感觉
- **Phase 6 取消 checkpoint 概念**：codex 自己决定 best shader，Python 不再管
- **Few-shot 不嵌入主 SKILL.md**：放 reference/，codex 按需 Read（节省 ~12K token）

### 4.2 AGENTS.md（角色 + 术语，~500 行）

```markdown
# VFX Shader Agent

[角色 + 工具概览 + 输出文件约定]

## Available Tools
- MCP vfx-tools: validate_shader, render_shader, list_keyframes
- System: Read, Write, Edit, Bash, Glob, Grep
- Image analysis: Bash + Python PIL (ImageMagick not available by default)

## Output Files (in workdir)
- visual_description.json (Phase 1)
- shader.glsl (current, Phase 2)
- final_shader.glsl (best, Phase 6)
- evaluation.json (Phase 5)

## VFX Terminology
[嵌入 shared_vfx_terminology.md 351 行]
```

### 4.3 MCP Server

**位置**: `backend/app/mcp_server/__init__.py`

```python
from fastmcp import FastMCP
from app.services.shader_validator import validate_shader as _validate
from app.services.browser_render import render_and_screenshot
import os, asyncio

mcp = FastMCP("vfx-tools")

@mcp.tool(description="Validate GLSL shader code for Shadertoy compatibility.")
def validate_shader(shader_code: str) -> dict:
    """Returns {valid: bool, errors: [str], warnings: [str], can_attempt_render: bool}"""
    result = _validate(shader_code)
    return {
        "valid": result["valid"],
        "errors": result["errors"],
        "warnings": result["warnings"],
        "can_attempt_render": result.get("can_attempt_render", result["valid"]),
    }

@mcp.tool(description="Render GLSL shader at given time. Returns absolute screenshot path.")
def render_shader(shader_code: str, time_seconds: float = 1.0) -> dict:
    """Returns {screenshot_path: str (absolute), success: bool, error: str | None}"""
    output_dir = os.environ["VFX_OUTPUT_DIR"]
    try:
        path = asyncio.run(render_and_screenshot(shader_code, time_seconds=time_seconds))
        return {"screenshot_path": str(path), "success": True, "error": None}
    except Exception as e:
        return {"screenshot_path": "", "success": False, "error": str(e)}

@mcp.tool(description="List all reference keyframe image paths for the current pipeline.")
def list_keyframes() -> dict:
    """Returns {count: int, paths: [str (absolute)]}"""
    paths = [p for p in os.environ["VFX_KEYFRAME_PATHS"].split(":") if p]
    return {"count": len(paths), "paths": paths}

if __name__ == "__main__":
    mcp.run()  # stdio mode
```

**MCP 启动方式**（每个 pipeline 独立进程）:
```bash
codex mcp add vfx-tools \
  --env PIPELINE_ID=$PIPELINE_ID \
  --env VFX_OUTPUT_DIR=$WORKDIR/output \
  --env VFX_KEYFRAME_PATHS=$KEYFRAME_PATHS_COLON_SEPARATED \
  -- python -m app.mcp_server
```

**关键设计**: MCP server 无状态，pipeline 上下文通过环境变量注入。并发 pipeline 各起各的 MCP 进程，无冲突。

### 4.4 Python 编排器

**位置**: `backend/app/orchestrator.py`（~150 行）

```python
class PipelineOrchestrator:
    async def run(self, pipeline_id: str, video_path: str | None,
                  images: list[str], notes: str, max_iterations: int = 3):
        workdir = Path(f"/tmp/vfx_pipelines/{pipeline_id}")
        (workdir / "output").mkdir(parents=True)

        # 1. FFmpeg 提关键帧
        keyframes = extract_keyframes(video_path) if video_path else images

        # 2. 准备 codex 工作区
        self._setup_codex_workspace(workdir)

        # 3. 注册 MCP server
        self._register_mcp(pipeline_id, workdir, keyframes)

        # 4. spawn codex + 流式解析
        await self._spawn_codex(pipeline_id, workdir, keyframes, notes, max_iterations)

        # 5. 提取产物
        final_shader = self._read_file_if_exists(workdir / "final_shader.glsl")
        evaluation = self._read_json_if_exists(workdir / "evaluation.json")

        # 6. 更新 StateStore
        record = StateStore.load(pipeline_id)
        record.final_shader = final_shader
        record.evaluation = evaluation
        record.status = self._compute_status(evaluation)
        StateStore.save(record)

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
| MCP server 启动失败 | spawn codex 前测一次 `python -m app.mcp_server --help` | status="failed"，error 含 traceback |
| MCP 工具调用超时 | MCP server 内部 asyncio.run 加 timeout（render 30s） | 工具返回 success=false, error="timeout"，codex 决定是否重试 |
| shader 连续编译失败 | SKILL.md 已限制最多 3 次验证 | codex 写 STOP reason，编排器照常提取 |
| 缺 final_shader.glsl | codex 退出后检查文件 | 降级用 shader.glsl，status="max_iterations" |
| 缺 evaluation.json | 同上 | score=0.0，status="failed" |
| codex 输出空响应 | proc.stdout 全空 | status="failed"，error="empty_codex_response" |
| codex 违反 SKILL.md（跳过 validate） | JSONL 事件分析 | MVP 阶段观察，决定是否加 Python 强制门禁 |
| 网络问题 | codex stderr 含 "WebSocket timed out" | 重试 1 次，仍失败 status="failed" |

---

## 5. 测试策略

### 5.1 MVP 5 步渐进

| Step | 测试内容 | 成功标准 | 失败处理 |
|------|---------|---------|---------|
| **0** | ✅ 已完成：codex 0.144.1 + Bash+PIL 看图验证 | 通过 | — |
| **1** | heart-2d 单样本：SKILL.md + MCP + codex 跑通完整流程 | final_shader.glsl + evaluation.json 非空 | 调 SKILL.md 措辞，重跑（最多 3 次） |
| **2** | heart-2d 评分对比：codex 自评 vs v1.0 InspectAgent 离线评估 | 差距 < 0.10 | 加 pixel evidence 强约束 |
| **3** | heart-2d 多轮迭代验证：max_iterations=3 | 第 N 轮评分 > 第 1 轮 | 调 Phase 6 指令 |
| **4** | 3 simple 样本（heart-2d / 4-col-grad / shiny-circle） | 平均分 ≥ v1.0 基线 (0.90) | 分类问题（prompt/模型/MCP） |
| **5** | 19 全量样本 | 平均分 ≥ v1.0 V2 baseline (0.71) | 部分失败可接受，分析 pattern |

### 5.2 A/B 对比测试方法

```python
# backend/tests/e2e/test_ab_codex_vs_v1.py
async def test_ab_heart_2d():
    # A: v2.0 codex OD 模式
    codex_shader, codex_eval = await run_codex_pipeline("heart-2d")

    # B: 用 v1.0 InspectAgent（独立 LLM 调用）评估 v2.0 输出
    v1_score = await v1_inspect_agent.evaluate(
        reference=keyframes,
        render=render_shader(codex_shader, time=1.0),
        dsl=parse_visual_description(codex_eval),
    )

    # codex 自评 vs v1.0 独立评分
    assert abs(codex_eval["overall_score"] - v1_score["overall_score"]) < 0.10
```

**关键**: 保留 `backend/app/agents/inspect.py` 作为离线评估器（不参与新 pipeline），用于 A/B 测试。Step 5 通过后删除。

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

### 7.1 Phase A-E 时间线

```
Phase A: 基础设施搭建 (1-2 天)
    ↓
Phase B: MVP Step 1 - heart-2d 跑通 (1-2 天) ← 关键决策点
    ↓
Phase C: MVP Step 2-3 - A/B + 多轮迭代 (1-2 天) ← 关键决策点
    ↓
Phase D: MVP Step 4-5 - 3 样本 → 19 样本 (5-7 天) ← 关键决策点
    ↓
Phase E: 删除旧代码 + 文档收尾 (1 天)
```

每个 Phase 后用 @oracle 做风险评估，决定继续/调整/中止。

### 7.2 各 Phase 任务分解

#### Phase A: 基础设施搭建（1-2 天）

| 任务 | 负责 | 产出 |
|------|------|------|
| 在 v2.0 worktree 中保留 services/ + frontend/，删除 pipeline/ 和 agents/ | @fixer | v2.0 干净起点（仅保留可复用代码） |
| 实现 MCP server | @fixer | `backend/app/mcp_server/__init__.py` |
| 实现 state_store.py | @fixer | `backend/app/state_store.py` |
| 实现 orchestrator.py 骨架 | @fixer | `backend/app/orchestrator.py` |
| 重写 routers/pipeline.py（SSE） | @fixer | `backend/app/routers/pipeline.py` |
| 梳理 7 个 prompt md → AGENTS/SKILL/reference 映射 | @explorer | 拆分映射表 + token 估算 |
| 查 codex `--enable`/`--disable` 完整 feature | @librarian | codex 调用参数清单 |
| 前端 usePipeline.ts: polling → SSE | @fixer | `frontend/src/hooks/usePipeline.ts` |

**Phase A 验收**: backend 启动无报错 + codex 调通 MCP server + SSE 端点返回状态

#### Phase B: MVP Step 1 - heart-2d 跑通（1-2 天）

| 任务 | 负责 |
|------|------|
| 写 v2.0 SKILL.md（~900 行） | @fixer + 我审查 |
| 写 v2.0 AGENTS.md（~500 行） | @fixer + 我审查 |
| 重组 reference/ | @fixer |
| 跑 heart-2d 单样本 | @fixer |
| **风险审查** | @oracle |

**Phase B 决策点**:
- ✅ codex 输出非空 → Phase C
- ⚠️ codex 跳过 validate 或不迭代 → 调 SKILL.md 重跑 1 次
- ❌ codex 完全不工作 → 中止，回 brainstorming

#### Phase C: MVP Step 2-3 - A/B + 多轮迭代（1-2 天）

| 任务 | 负责 |
|------|------|
| 临时保留 v1.0 的 InspectAgent 作离线评估器 | @fixer |
| 写 A/B 测试脚本 | @fixer |
| heart-2d 跑 max_iterations=3 | @fixer |
| **风险审查** | @oracle |

**Phase C 决策点**:
- ✅ 自评 vs 独立评分差距 < 0.10 → Phase D
- ⚠️ 差距 0.10-0.20 → 加 pixel evidence，重测
- ❌ 差距 > 0.20 → 中止

#### Phase D: 扩展验证（5-7 天）

| 任务 | 负责 |
|------|------|
| 3 simple 样本 | @fixer |
| **风险审查** | @oracle |
| 19 全量样本 | @fixer |
| HTML 报告生成（对比 v1.0 V2 baseline） | @fixer |
| **最终风险审查** | @oracle |

**Phase D 决策点**:
- ✅ 平均分 ≥ 0.71 → Phase E
- ⚠️ 0.60-0.71 → 调 SKILL.md 或保留双轨
- ❌ < 0.60 → 归档 v2.0/codex-od 分支

#### Phase E: 清理（1 天）

| 任务 | 负责 |
|------|------|
| 删除 graph.py / state.py / context_assembler / BaseAgent / 3 Agent | @fixer |
| 删除 v1.0 配置项 | @fixer |
| 更新 README / AGENTS.md | 我 |
| 打 tag `v2.0.0` + master 打 tag `v1.0.0` | 我 |

### 7.3 工作分配原则

| Agent | 主要承担 |
|-------|---------|
| **@fixer** | 80% 代码实施（Phase A 可并行多实例） |
| **@oracle** | 每个 Phase 后风险评估 + 关键设计审查 |
| **@explorer** | Phase A 的 prompt 资产 mapping |
| **@librarian** | Phase A 的 codex 高级特性查询 |
| **@designer** | 不需要（前端改动小，@fixer 直接处理） |
| **orchestrator** | 设计审查、SKILL.md 撰写指导、跨 phase 协调、用户沟通 |

### 7.4 可并行任务（@fixer 多实例）

Phase A 内可并行:
- **fixer-A1**: MCP server + state_store（后端基础设施）
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
| **R1** | codex 跳过 validate 直接 render（违反 SKILL.md） | Phase B 观察遵守度。<50% 则加 Python 强制门禁（render_shader MCP 内部先调 validate） |
| **R2** | codex 自评虚高（bias） | Phase C A/B 对比验证。差距 > 0.10 则加强 pixel evidence 要求 |
| **R3** | codex 卡在无限迭代 | asyncio.wait_for(600s) 硬超时 + SKILL.md "max 3 iterations" |
| **R4** | GPT-5 GLSL 质量 < v1.0 Generate Agent 模型 | Phase D 严格 A/B。若显著差，归档 v2.0 分支 |

### 8.2 P1 风险

| ID | 风险 | Mitigation |
|----|------|-----------|
| R5 | 上下文超限（4521 行 prompt + 9 few-shot + 多图） | 分层加载，主 SKILL.md ~12K token，reference 按需 Read |
| R6 | 网络抖动（codex 调 OpenAI API） | spawn 时设 HTTP_PROXY + 失败重试 1 次 |
| R7 | 可观测性下降（codex 黑盒） | JSONL 全量保存到 record.events，session_logger 保留 |
| R8 | 并发 pipeline MCP 冲突 | 每个 pipeline 起独立 MCP 进程，环境变量隔离 |

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
│   └── inspect.py        ❌ Phase E 删除（Phase C/D 暂留作 A/B 评估器）
├── services/
│   └── context_assembler.py  ❌ 删除（347 行，被 SKILL.md 替代）
```

### 9.2 保留（v1.0 工具层 + UI）

```
backend/app/services/
├── video_extractor.py    ✅ 保留（FFmpeg）
├── browser_render.py     ✅ 保留（被 MCP server 调用）
├── shader_validator.py   ✅ 保留（被 MCP server 调用）
├── validators.py         ✅ 保留（DSL 校验）
└── session_logger.py     ✅ 保留（记 codex JSONL）

frontend/src/             ✅ 全保留
└── hooks/usePipeline.ts  ⚠️ 改: HTTP polling → EventSource
```

### 9.3 新建

```
backend/app/
├── orchestrator.py       🆕 ~150 行
├── mcp_server/
│   └── __init__.py       🆕 ~80 行
├── state_store.py        🆕 ~60 行
├── pipeline_states/      🆕 运行时目录（gitignored）
├── prompts/              ✏️ 重组
│   ├── AGENTS.md         🆕 ~500 行
│   ├── SKILL_vfx.md      🆕 ~900 行
│   └── reference/        🆕 按需 Read
│       ├── shader_templates.md       (~1200 行)
│       └── few_shot_examples.md      (~800 行压缩版)
└── routers/pipeline.py   ✏️ 改写
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
# backend/requirements.txt 新增
fastmcp>=0.8.0
```

---

## 10. 相关调研引用

本设计文档基于以下 background 调研结果：

| 调研 | Session ID | 关键发现 |
|------|-----------|---------|
| **lib-1**: nexu-io/open-design 项目研究 | ses_0a6b3a5b1ffeLHS1oC5I8POOcx | OD 是 Claude Design 开源替代，77K+ stars，Apache-2.0，Skills + DESIGN.md 架构 |
| **exp-1**: VFX-Agent v1.0 架构调研 | ses_0a6a7f309ffeuMt64Wdrle0OK4 | 唯一模型 API 调用点 base.py:157，4 区状态，6 节点 LangGraph |
| **lib-2**: codex CLI 协议 | ses_0a6a78e61ffe1mWuIXrnb5yjHN | codex exec 非交互模式，JSONL 事件流，MCP 完整支持 |
| **ora-1**: 重构可行性分析 | ses_0a6a2f3daffeQRhpdFHxIxUE49 | 基于 OD 实际源码的方案 Y 设计（预处理外包 + 全委托） |
| **fix-1**: Step 0 codex MCP+ViewImage 验证 | ses_0a68fba04ffe844gJ64oPNmA8M | fix-1 用 codex 0.140 失败；后续升级到 0.144.1 后 Bash+PIL 看图成功 |

---

## 11. 决策记录

### 11.1 关键决策

| # | 决策 | 选择 | 理由 |
|---|------|------|------|
| 1 | codex 调用模式 | 1 次自主调用（方案 B） | 纯 OD 哲学，让 codex 用工具能力 + GPT-5 代码能力 |
| 2 | Session 模式 | `--ephemeral` | 上下文隔离，避免上一 pipeline 残留 |
| 3 | 看图机制 | codex 自主 Bash+PIL | Step 0 已验证（codex 0.144.1），比 ViewImage 更精确 |
| 4 | 硬约束 | Python MCP server | GLSL 验证、渲染必须确定，不能 LLM 主观 |
| 5 | 状态持久化 | JSON 文件 per pipeline_id | 简单优先，无 SQL 依赖 |
| 6 | 前端协议 | SSE 替代 500ms polling | 实时性 + FastAPI 原生支持 |
| 7 | 仓库策略 | 当前仓 + 分支隔离 | 重用 v1.0 服务层/前端/测试基础设施 |
| 8 | 版本命名 | v1.0 = master / v2.0 = v2.0/codex-od | 双版本并列对照 |
| 9 | 多轮人工迭代 | 重新 spawn codex（不用 --resume） | --ephemeral 模式下无 session 可续 |
| 10 | Checkpoint 概念 | 取消 | codex 自己决定 best，Python 不镜像状态 |

### 11.2 已拒绝的替代方案

| 方案 | 拒绝理由 |
|------|---------|
| 方案 A: 3 次独立 codex exec | 等于"用 codex 当 dumb LLM caller"，没拿到 OD 真正好处（oracle 第一次批评） |
| 方案 C: 阶段切换 + Generate 自主迭代 | 折中方案，但失去纯 OD 哲学的清晰性 |
| 新建独立仓库 vfx-codex | 失去 v1.0 8000+ 行服务层/前端/测试基础设施复用 |
| 保留 LangGraph 作 fallback | 双轨维护成本高，违背"全量重构"决策 |

### 11.3 已 A/B 测试 / 验证的子决策

| 子决策 | 验证方式 | 结果 |
|--------|---------|------|
| codex 0.144.1 + GPT-5 能精确看图 | Step 0 测试 | ✅ 通过（RGB(0,255,235) 等精确像素值） |
| MCP server 工具调用稳定 | Step 0 测试（5 次 render_shader） | ✅ 5/5 成功 |
| codex `--disable plugins` 避免 superpowers 干扰 | Step 0 测试 | ✅ 必需 |

---

## 12. 后续行动

本文档是 **brainstorming 阶段产出**。User review 通过后，下一步:

1. **Transition to writing-plans skill**: 把本设计转化为可执行的 implementation plan（含具体文件、行号、依赖关系）
2. **实施**: 按 Phase A-E 执行
3. **每个 Phase 后用 @oracle 风险评估**

---

*本设计基于 2026-07-13 的 OD 实际源码调研 + codex CLI 协议调研 + VFX-Agent v1.0 架构调研 + Step 0 验证结果。如环境发生重大变化（codex 版本升级、OD 架构演进、OpenAI API 变更），需重新评估。*
