# VFX-Agent v2.0 项目信息

> 本文档记录 v2.0 codex OD 架构、工作流、测试结果与决策记录，用于后续开发对齐。

---

## 项目概述

**目标**：构建一个 AI Agent 驱动的系统，从 UX 视频/图片输入自动生成 Shadertoy 格式 GLSL 着色器代码，经隔离子 Agent 评分反馈迭代直至收敛。

**范围**：专注于 2D/2.5D 平面动效（涟漪、光晕、磨砂、流光等 UI 视效），支持移动端和 Web 平台。排除 3D raymarching/场景渲染/体渲染。

**技术栈**：
- Backend: Python 3.11+, FastAPI, codex CLI 0.144.1+
- Frontend: React 18, Vite, Three.js（复用 v1.0）
- 浏览器自动化: Playwright
- 视频处理: FFmpeg
- 状态持久化: JSON 文件

---

## v2.0 架构详解

### codex OD 动态编排

v2.0 用 **codex OD（Orchestrated Dispatch）模式**替代 v1.0 LangGraph 静态编排。核心思路：

```
Python Orchestrator (~270 行)
  ├── FFmpeg 提取关键帧
  ├── 创建 workdir + symlink skills/
  ├── spawn codex exec（主 agent）
  ├── 解析 JSONL 流 → 推前端
  ├── 提取 final_shader / evaluation
  └── 更新 PipelineState 持久化

codex exec（主 agent，按 SKILL.md 自主编排）
  ├── Phase 1: 分析关键帧 → visual_description.json
  ├── Phase 2: 生成 shader → shader.glsl
  ├── Phase 3: 验证编译 → validate_shader.py
  ├── Phase 4: 渲染截图 → render_shader.py + Playwright
  ├── Phase 5: 子 agent 评分 → spawn_agent (fork_turns="none")
  └── Phase 6: 迭代或收尾
```

### Orchestrator 职责边界

| 职责 | 归属 |
|------|------|
| 关键帧提取（FFmpeg） | Python orchestrator |
| Workdir 创建与清理 | Python orchestrator |
| Skill 资产 symlink | Python orchestrator |
| Spawn codex + 解析 JSONL | Python orchestrator |
| 状态持久化 + 前端推送 | Python orchestrator |
| 硬超时（600s） | Python orchestrator |
| 迭代控制（max_iterations） | codex agent（SKILL.md 约束） |
| 阶段路由/切换 | codex agent（自主决策） |
| 代码生成/验证 | codex agent |
| 渲染与截图 | codex agent（调用 script） |
| 评分 | Subagent（隔离上下文） |

### 6-Phase 工作流

| Phase | 名称 | 输入 | 输出 | 说明 |
|-------|------|------|------|------|
| **1** | Analyse | 关键帧图片 (`keyframes/*.png`) + 用户备注 | `visual_description.json` | 识别效果类型、颜色、动画特征 |
| **2** | Generate | `visual_description.json` + shader 模板 + few-shot | `shader.glsl` | 基于 Shadertoy 格式编写 GLSL |
| **3** | Validate | `shader.glsl` | 编译结果 | 调用 `validate_shader.py` 检查语法 |
| **4** | Render | `shader.glsl` | 截图 (`render_output.png`) | 调用 `render_shader.py` → Playwright WebGL 渲染 |
| **5** | Evaluate | 参考关键帧 + 渲染截图 + `visual_description.json` | `evaluation.json`（含 score） | **必须用 `spawn_agent`（`fork_turns="none"`）**，禁止自评 |
| **6** | Iterate/Finalize | 前轮 score + visual_issues | 修正的 `shader.glsl` 或 `final_shader.glsl` | score ≥ 0.85 则收尾，否则迭代 |

### Phase 5 Subagent 协议

```yaml
Protocol:
  spawn: spawn_agent with fork_turns: "none"
  input:
    - Reference keyframe path (via message)
    - Render screenshot path (via message)
    - visual_description.json (shared filesystem)
  output: evaluation.json (shared filesystem)
  
evaluation.json schema:
  {
    "overall_score": 0.0-1.0,
    "dimension_scores": {
      "color_accuracy": 0.0-1.0,
      "shape_fidelity": 0.0-1.0,
      "animation_match": 0.0-1.0,
      "overall_impression": 0.0-1.0
    },
    "visual_issues": [
      {"severity": "high|medium|low", "description": "...", "suggestion": "..."}
    ]
  }
```

**为什么用 subagent**：主 agent 自评有正偏差，隔离 agent 更客观。v1.0 经验证明自评评分偏高 10-15%。

### Skill 体系

```
backend/app/skills/
├── AGENTS.md                   # codex 主指令（~470 行）
└── vfx-shader/
    ├── SKILL.md (~415 行)      # 6-phase 工作流
    └── reference/
        ├── shader_templates.md (~1230 行)  # 9 个模板 + SDF/噪声/光效
        ├── few_shot_examples.md (~540 行)  # 9 个端到端示例
        └── scripts/
            ├── validate_shader.py          # GLSL 编译检查
            ├── render_shader.py            # Playwright 渲染
            └── analyze_pixels.py           # 像素级分析
```

v2.0 将 v1.0 的 7 个 prompt 文件（4521 行）浓缩到 3 个 skill 文件 + 3 个脚本。

---

## 已实现功能

### v2.0 核心

| 功能 | 说明 |
|------|------|
| codex OD 动态编排 | 单次 `codex exec` 按 SKILL.md 自主完成全流程 |
| 6-phase 工作流 | Analyse → Generate → Validate → Render → Evaluate → Iterate |
| Subagent 隔离评分 | `spawn_agent` + `fork_turns="none"` 上下文隔离 |
| Python orchestrator | ~270 行最小编排，不做路由/评分/迭代控制 |
| JSON 状态持久化 | `pipeline_states/<id>.json`，无数据库依赖 |
| Standalone 渲染 | `shader_render_page.html` 独立 HTML，无前端 chrome 干扰 |
| 编译验证脚本 | `validate_shader.py` |
| 像素分析脚本 | `analyze_pixels.py` |
| 迭代预算控制 | `max_iterations` 由 SKILL.md 约束 |
| 硬超时保护 | 600s，orchestrator 级终止 |
| JSONL 流式推前端 | orchestrator 解析 codex stdout 实时推送 |

### 复用 v1.0

| 组件 | 说明 |
|------|------|
| WebUI（React/Three.js） | 三栏布局、Shader 预览、GLSL 编辑器 |
| 输入支持 | 图片/视频上传、文本描述 |
| Playwright 渲染 | `browser_render.py` |
| FFmpeg 关键帧提取 | `video_extractor.py` |
| GLSL 编译检查 | `shader_validator.py` |
| Session 日志 | `session_logger.py` |
| API 路由 | FastAPI routers（pipeline + config） |

---

## 关键决策记录

| 决策 | 原因 |
|------|------|
| v1.0 LangGraph 静态编排 → v2.0 codex OD 动态编排 | LangGraph 路由僵化，codex 自主决策更灵活 |
| 取消 MCP（plan revision 2） | CLI 工具直接 Bash 调用更简单，MCP 对 CLI 友好工具是过度工程 |
| Phase 5 用 subagent 而非主 agent 自评 | 主 agent 自评有正偏差，subagent fork_turns="none" 隔离上下文 |
| Render pipeline 用 standalone HTML（非前端 dev server） | 前端 UI 截图包含 chrome，污染像素对比 |
| Workdir 用 symlinks 暴露 skills/ | 单一来源，workdir 是临时的 |
| Orchestrator 不做迭代控制（max_iterations 由 SKILL.md 约束） | codex 自主判断，Python 只做超时和状态记录 |
| PipelineState 4 区 → JSON 单文件 | 简化，v2.0 codex 自管理文件 |
| v1.0 prompt 资产（7 文件 4521 行）→ 3 skill 文件 | 合并冗余，减少维护负担 |

---

## 测试规范

> 基线标准：`backend/test_results/2026-07-13_v2-codex-od-19samples/`

### 测试脚本

| 脚本 | 用途 | 运行方式 |
|------|------|---------|
| `backend/tests/e2e/run_v2_samples.py` | 运行指定样本 | `cd backend && python tests/e2e/run_v2_samples.py <sample>` |
| `backend/tests/e2e/collect_v2_results.py` | 收集结果到 test_results | `python tests/e2e/collect_v2_results.py` |
| `backend/tests/e2e/generate_v2_report.py` | 生成 HTML 报告 | `python tests/e2e/generate_v2_report.py` |
| `backend/tests/unit/` | 单元测试 | `cd backend && python -m pytest tests/unit/ -v` |

### 测试参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `max_iterations` | **3** | SKILL.md 约束，codex agent 自主遵守 |
| `passing_threshold` | **0.85** | ≥0.85 即为通过 |
| `timeout` | **600s** | orchestrator 级硬超时 |

**评分标准**：
- **≥0.85**: ✅ PASS
- **0.80-0.85**: ⚠️ ACCEPTABLE
- **<0.80**: ❌ FAIL

### 测试结果目录结构

```
backend/test_results/<YYYY-MM-DD_描述>/
├── index.html                 # 主报告（v1.0 vs v2.0 对比）
├── test_results.json          # 汇总
└── <sample_name>/
    ├── pipeline_state.json    # 状态快照
    ├── reference_frame.png    # 参考帧
    ├── render_0.png ~ render_N.png  # 各迭代渲染
    ├── shader.glsl            # 最终 shader
    └── visual_description.json
```

### test_results.json 结构

```json
{
  "<sample_name>": {
    "sample_name": "4-col-grad",
    "pipeline_id": "v2-4-col-grad-xxx",
    "status": "passed|failed|timeout",
    "elapsed_seconds": 133.0,
    "score": 0.997,
    "iteration": 1,
    "effect_type": "{effect.gradient}",
    "shader_lines": 14,
    "issues": [...],
    "timestamp": "2026-07-13T20:40:00"
  }
}
```

**Issue Severity**：
- **P0**: 关键问题（pipeline 失败、超时、无 shader）
- **P1**: 重要问题（编译错误、渲染失败）
- **P2**: 次要问题（字段缺失、格式问题）

### 测试样本列表

19 个基线样本（存放于 `test-samples/`）：

| 样本名 | 效果类型 | 预期难度 |
|--------|---------|---------|
| 4-col-grad | gradient | simple |
| auroras | flow | complex |
| buffer-bloom | glow | simple |
| cool-s-distance | shape/warp | medium |
| electron | particle | complex |
| happy-diwali-2019 | particle | medium |
| heart-2d | shape | simple |
| hypnotic-ripples | ripple | simple |
| liquid-galss-test | liquid | medium |
| liquid-glass-ui | liquid/special | medium |
| moon-distance-2d | warp | medium |
| plasma-waves | flow/glow | medium |
| shiny-circle | glow | simple |
| sparks-drifting | particle | complex |
| supah-frosted-glass | gradient/liquid | simple |
| twitter-blue-check | shape | simple |
| vortex-street | liquid | medium |
| warp-speed2 | particle/space | medium |
| water-color-blending | liquid | medium |

---

## v2.0 测试结果（2026-07-13，19 样本）

### 完整结果

| 样本 | v1.0 基线 | v2.0 score | Delta | 状态 | 迭代 | 行数 | 耗时 |
|------|-----------|-----------|-------|------|------|------|------|
| 4-col-grad | 0.950 | **0.997** | +0.047 | ✅ PASS | 1 | 14 | 133s |
| twitter-blue-check | 0.870 | **0.992** | +0.122 | ✅ PASS | 2 | 37 | 370s |
| heart-2d | 0.780 | **0.901** | +0.121 | ✅ PASS | 0 | 47 | 0s |
| shiny-circle | 0.880 | **0.860** | −0.020 | ✅ PASS | 3 | 54 | 550s |
| liquid-galss-test | 0.520 | **0.802** | +0.282 | ⚠️ ACCEPT | 3 | 76 | 525s |
| buffer-bloom | 0.740 | 0.758 | +0.018 | ❌ FAIL | 3 | 88 | 476s |
| auroras | 0.420 | 0.720 | +0.300 | ❌ FAIL | 3 | 126 | 579s |
| water-color-blending | 0.860 | 0.720 | −0.140 | ❌ FAIL | 3 | 101 | 536s |
| warp-speed2 | 0.810 | 0.702 | −0.108 | ❌ FAIL | 2 | 90 | 600s |
| happy-diwali-2019 | 0.780 | 0.698 | −0.082 | ❌ FAIL | 4 | 69 | 564s |
| cool-s-distance | 0.520 | 0.682 | +0.162 | ❌ FAIL | 3 | 79 | 523s |
| electron | 0.680 | 0.677 | −0.003 | ❌ FAIL | 3 | 97 | 462s |
| plasma-waves | 0.830 | 0.641 | −0.189 | ❌ FAIL | 3 | 65 | 545s |
| liquid-glass-ui | 0.730 | 0.500 | −0.230 | ❌ FAIL | 3 | 105 | 513s |
| vortex-street | 0.810 | 0.498 | −0.312 | ❌ FAIL | 3 | 88 | 600s |
| sparks-drifting | 0.000 | 0.491 | +0.491 | ❌ FAIL | 2 | 90 | 600s |
| hypnotic-ripples | 0.860 | 0.460 | −0.400 | ❌ FAIL | 3 | 38 | 600s |
| moon-distance-2d | 0.720 | 0.020 | −0.700 | ❌ FAIL | 3 | 67 | 600s |
| supah-frosted-glass | 0.820 | 0.070 | −0.750 | ❌ FAIL | 1 | 56 | 600s |

### 统计

| 指标 | 数值 |
|------|------|
| Passed (≥0.85) | **4/19 (21.1%)** |
| Acceptable (0.80-0.85) | **1/19 (5.3%)** |
| Failed (<0.80) | **14/19 (73.7%)** |
| **Average Score** | **0.642** |
| v1.0 baseline 平均 | 0.715 |
| v2.0 vs v1.0 delta | **−0.073** |

### 显著变化

| 样本 | Delta | 分析 |
|------|-------|------|
| sparks-drifting | **+0.49** | v1.0 timeout → v2.0 生成可用 shader（score 0.49 仍 fail） |
| auroras | **+0.30** | v1.0 严重失败 → v2.0 逼近 acceptable |
| liquid-galss-test | **+0.28** | v1.0 低分 → v2.0 刚好可接受 |
| supah-frosted-glass | **−0.75** | v1.0 acceptable → v2.0 编译失败 / 全黑 |
| moon-distance-2d | **−0.70** | 600s timeout + 编译失败 |
| hypnotic-ripples | **−0.40** | 600s timeout + 渲染失败 |

### Subagent Cross-validation

Subagent A/B cross-validation delta: **0.111**（borderline bias 嫌疑，需进一步分析）。

---

## 已知问题与改进方向

### 问题

1. **编译失败**：部分样本 codex 生成的 shader 语法错误或语义错误，渲染全黑（score ≈ 0）。原因是 GLSL 模板匹配不足。
2. **600s 超时**：复杂样本（hypnotic-ripples、moon-distance-2d）在 Phase 2/5 耗时过长，触发 orchestrator 硬超时。
3. **迭代质量差**：即使 3 次迭代用满，部分样本仍然不收敛。codex 的语义反馈利用率不足。
4. **Subagent 评分偏差**：cross-validation delta 0.111，评分一致性待验证。
5. **平均分落后 v1.0**：v2.0 avg 0.642 vs v1.0 0.715。v1.0 的 LangGraph 路由 + 专业 prompt 仍有优势。

### 改进方向

- **Few-shot 增强**：增加编译失败样本的 few-shot 示例
- **时间预算管理**：SKILL.md 增加 phase 级时间约束
- **评分配准**：优化 Phase 5 subagent prompt，降低评分方差
- **Prompt 资产移植**：v1.0 中已验证有效的 prompt 内容逐步移植到 v2.0 skill 体系

---

## 文件结构

```
VFX-Agent/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                       # FastAPI 入口
│   │   ├── config.py                     # v2.0 配置
│   │   ├── orchestrator.py (~304 行)     # v2.0 核心编排器
│   │   ├── state_store.py (~65 行)       # JSON 持久化
│   │   ├── pipeline_states/              # 运行时状态文件
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── pipeline.py (~95 行)      # POST /run + GET /status
│   │   │   └── config.py
│   │   ├── services/
│   │   │   ├── browser_render.py         # Playwright 渲染复用
│   │   │   ├── shader_render_page.html   # v2.0 standalone HTML (128 行)
│   │   │   ├── shader_validator.py       # GLSL 编译检查
│   │   │   ├── video_extractor.py        # FFmpeg 关键帧
│   │   │   ├── session_logger.py         # Agent 会话日志
│   │   │   └── validators.py             # API 校验
│   │   └── skills/                       # v2.0 codex skill 资产
│   │       ├── AGENTS.md (~471 行)       # codex 主指令
│   │       └── vfx-shader/
│   │           ├── SKILL.md (~414 行)    # 6-phase 工作流
│   │           └── reference/
│   │               ├── shader_templates.md (~1230 行)  # shader 模板
│   │               ├── few_shot_examples.md (~540 行)  # 9 个 few-shot
│   │               └── scripts/
│   │                   ├── validate_shader.py
│   │                   ├── render_shader.py
│   │                   └── analyze_pixels.py
│   ├── tests/
│   │   ├── unit/                         # 5 文件，18 tests pass
│   │   └── e2e/
│   │       ├── run_v2_samples.py         # 批量运行器
│   │       ├── collect_v2_results.py     # 结果收集
│   │       └── generate_v2_report.py     # HTML 报告生成
│   ├── test_results/                     # 测试归档 (.gitignore)
│   ├── requirements.txt
│   └── .env.example
├── frontend/                             # 复用 v1.0
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── InputPanel.tsx
│   │   │   ├── UploadPanel.tsx
│   │   │   ├── VFXDiscoveryForm.tsx
│   │   │   ├── ShaderEditor.tsx
│   │   │   ├── ShaderPreview.tsx
│   │   │   ├── ParameterPanel.tsx
│   │   │   ├── AgentLog.tsx
│   │   │   ├── SettingsPanel.tsx
│   │   │   └── PipelineStatus.tsx
│   │   ├── hooks/
│   │   │   └── usePipeline.ts
│   │   └── lib/
│   │       ├── shader-renderer.ts
│   │       └── glsl-parser.ts
│   └── package.json
├── test-samples/                         # 19 基线样本 (.gitignored)
├── docs/
├── start.sh
├── AGENTS.md
├── README.md
└── .gitignore
```

---

## 配置说明

模型配置通过 `backend/.env` 指定：

```env
# codex 模型配置
CODEX_MODEL=gemini-2.5-flash
CODEX_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
CODEX_API_KEY=your_api_key

# 代理（海外 API）
PROXY=http://127.0.0.1:7890
codex_proxy=http://127.0.0.1:7890

# Pipeline 参数
codex_timeout=600          # codex 调用超时（秒）
max_iterations=5           # SKILL.md 中配置的迭代上限（硬 cap）
passing_score=0.85         # 通过阈值
render_timeout_ms=2000     # 渲染超时
screenshot_width=1280
screenshot_height=720
workdir_root=/tmp/vfx_workdirs  # 运行 workdir 根目录
```

---

## 代码统计

| 指标 | 数值 |
|------|------|
| Python 文件 (backend/app) | ~12 |
| TSX/TS 文件 (frontend/src) | ~16 |
| Skill 文件 | 3（AGENTS.md + SKILL.md + shader_templates.md） |
| 脚本文件 | 3（validate/render/analyze） |
| Python 核心代码行数 | ~1,000（orchestrator 304 + state_store 65 + routers + services） |
| Skill 资产行数 | ~2,185（AGENTS 471 + SKILL 414 + templates 1230 + few-shot 540 + scripts） |
| 总代码行数 | ~8,000（缩减 35%） |
| Git Commits | ~110+ |

---

## 参考文档

- **设计文档**：`docs/superpowers/specs/2026-07-13-vfx-agent-v2-codex-od-design.md`
- **codex Agent 主指令**：`backend/app/skills/AGENTS.md`
- **6-phase 工作流**：`backend/app/skills/vfx-shader/SKILL.md`
- **Shader 模板库**：`backend/app/skills/vfx-shader/reference/shader_templates.md`
- **Few-shot 示例**：`backend/app/skills/vfx-shader/reference/few_shot_examples.md`
- **Orchestrator 源码**：`backend/app/orchestrator.py`
- **设计文档（原始）**：`基于 AI Agent 的操作系统级自定义视效生成管线设计方案.md`
- **iq SDF 算子**：https://iquilezles.org/articles/distfunctions2d/
- **Shadertoy 案例**：https://www.shadertoy.com/

---

*最后更新: 2026-07-14*
