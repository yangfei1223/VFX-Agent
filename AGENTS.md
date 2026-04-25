# VFX-Agent 项目信息

> 本文档记录项目架构、开发进度、与设计方案的差距分析，便于后续开发对齐。

---

## 项目概述

**目标**：构建一个多 Agent 闭环系统，从 UX 视频/图片输入自动生成 Shadertoy 格式 GLSL 着色器代码，并经视觉检视 Agent 自反馈迭代直至收敛。

**范围**：专注于 2D/2.5D 平面动效（涟漪、光晕、磨砂、流光等 UI 视效），支持移动端和 Web 平台。排除 3D raymarching/场景渲染/体渲染。

**技术栈**：
- Backend: Python 3.11+, FastAPI, LangGraph, OpenAI-compatible SDK
- Frontend: React 18, Vite, Three.js
- 浏览器自动化: Playwright
- 视频处理: FFmpeg

---

## 架构设计

### 三 Agent 闭环架构

```
[输入] 视频/图片/文本描述
   │
   ▼
┌─────────────────────────────────────────────────────────┐
│  Pipeline Orchestrator (LangGraph)                      │
│                                                         │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐ │
│  │ Decompose    │ → │ Generate     │ → │ Inspect      │ │
│  │ Agent        │   │ Agent        │   │ Agent        │ │
│  │ (多模态)     │   │ (代码生成)   │   │ (多模态)     │ │
│  └──────────────┘   └──────────────┘   └──────────────┘ │
│         │                  │                  │        │
│         ▼                  ▼                  ▼        │
│  visual_description    GLSL shader      对比评分       │
│  (JSON DSL)           (Shadertoy)      + 反馈指令      │
│                                                         │
│  ←←←←←←←←←←←←←←←← 反馈迭代 ←←←←←←←←←←←←←←←←←←←←←←←←←←←←│
└─────────────────────────────────────────────────────────┘
   │
   ▼
[输出] 最终 GLSL Shader + WebGL 预览
```

### Agent 角色分工

| Agent | 输入 | 输出 | 模型要求 |
|-------|------|------|----------|
| **Decompose** | 关键帧图片 + 视频元信息 + 用户标注 | visual_description (JSON DSL) | 多模态 LLM |
| **Generate** | visual_description + effect-dev Skill + 前轮代码 + 反馈 | GLSL Shader (Shadertoy 格式) | 强 coding 能力 |
| **Inspect** | 渲染截图 + 设计参考截图 + visual_description | 对比评分 + 修正指令 | 多模态 LLM |

### Pipeline 阶段流程

1. **Extract Keyframes** - FFmpeg 从视频提取关键帧（4-6 帧）
2. **Decompose** - 多模态 LLM 分析关键帧，输出结构化视效描述
3. **Generate** - 根据 DSL + Skill 知识库生成 GLSL 代码
4. **Render** - Playwright 在 WebGL 预览页渲染 shader 并截图
5. **Inspect** - 对比渲染截图与设计参考，输出评分和修正指令
6. **Loop** - 若未通过则迭代生成修正代码，直至收敛或达到最大迭代次数

---

## 已实现功能

### ✅ 核心功能 (MVP)

| 功能模块 | 状态 | 文件位置 |
|----------|------|----------|
| **Backend 服务** | ✅ | `backend/app/main.py` |
| **Pipeline 编排** | ✅ | `backend/app/pipeline/graph.py`, `state.py` |
| **Decompose Agent** | ✅ | `backend/app/agents/decompose.py` |
| **Generate Agent** | ✅ | `backend/app/agents/generate.py` |
| **Inspect Agent** | ✅ | `backend/app/agents/inspect.py` |
| **BaseAgent (多 API 支持)** | ✅ | `backend/app/agents/base.py` |
| **视频关键帧提取** | ✅ | `backend/app/services/video_extractor.py` |
| **浏览器截图服务** | ✅ | `backend/app/services/browser_render.py` |
| **effect-dev Skill** | ✅ | `.claude/skills/effect-dev/SKILL.md` + 7 references |
| **WebGL Shader 渲染** | ✅ | `frontend/src/lib/shader-renderer.ts` |
| **WebUI 三栏布局** | ✅ | `frontend/src/App.tsx` |
| **Agent Process Log** | ✅ | `frontend/src/components/AgentLog.tsx` |
| **GLSL Editor** | ✅ | `frontend/src/components/ShaderEditor.tsx` |
| **Parameter Panel** | ✅ | `frontend/src/components/ParameterPanel.tsx` |
| **Shader Preview** | ✅ | `frontend/src/components/ShaderPreview.tsx` |
| **代理支持** | ✅ | `backend/.env` PROXY 配置 |
| **启动脚本** | ✅ | `start.sh` |

### ✅ 输入支持

| 输入类型 | 状态 | 说明 |
|----------|------|------|
| **纯文本描述** | ✅ | 直接输入效果描述，auto-pass 模式 |
| **图片上传** | ✅ | 支持 PNG/JPG/WebP，单图或多图 |
| **视频上传** | ⚠️ | 支持 MP4/WebM，但 Pipeline 执行耗时较长 |

### ✅ 日志与进度追踪

| 功能 | 状态 | 说明 |
|------|------|------|
| **5 阶段时间线** | ✅ | Extract → Decompose → Generate → Render → Inspect |
| **实时进度消息** | ✅ | 每阶段显示 started/completed/failed |
| **持续时间统计** | ✅ | 每阶段显示 duration (ms/s) |
| **阶段详情展开** | ✅ | 点击展开查看详细信息 |
| **迭代次数显示** | ✅ | 每条日志显示 Iteration N |
| **500ms polling** | ✅ | 实时状态更新 |
| **日志窗口最大化** | ✅ | Maximize 按钮展开全屏显示 |

---

## 已知问题与待优化

### 当前已知问题

| 问题 | 状态 | 说明 |
|------|------|------|
| **视频输入 Pipeline 慢** | ⚠️ | 关键帧提取 + 多图多模态分析耗时 2-3 分钟 |
| **Inspect 评分简化** | ⚠️ | 纯文本模式 auto-pass，缺少量化指标 |
| **参数面板未同步** | ⚠️ | Parameter Panel 提取 #define/uniform 但未实时联动 |

### 待优化项（P1）

1. **增强 Inspect Agent 多维度评估**
   - 实现 IoU 计算（渲染截图 vs 设计参考 mask）
   - 实现 MSE 光流对比
   - 输出结构化修正指令

2. **特征提取增强**
   - 关键帧 SDF Mask 提取（形态场）
   - 光流场计算（动态特征）
   - 色彩频域分析

3. **参数面板实时联动**
   - 滑块修改 #define 常量实时更新 shader
   - uniform 变量实时传递到预览

---

## 与设计方案的差距分析

### 设计方案核心要求

根据 `基于 AI Agent 的操作系统级自定义视效生成管线设计方案.md`：

| 设计要求 | 当前状态 | 差距说明 |
|----------|----------|----------|
| **三 Agent 架构** | ✅ 完成 | Decompose → Generate → Inspect 已实现 |
| **Harness Loop 约束系统** | ❌ 未实现 | 缺少形态收敛(IoU)、动态拟合(MSE)、性能剪枝(AST审计) |
| **DSL 中间表示** | ⚠️ 部分 | 当前 visual_description 是简化 DSL，缺少算子拓扑描述 |
| **光流场提取** | ❌ 未实现 | 仅提取关键帧，缺少 Optical Flow 分析 |
| **形态场(SDF Mask)** | ❌ 未实现 | 缺少关键帧 SDF 轮廓提取 |
| **色彩频域分析** | ❌ 未实现 | 缺少色彩直方图及空间频率分布分析 |
| **算子抽象库** | ✅ 完成 | effect-dev Skill 包含 SDF/噪声/光照算子 |
| **多维特征评估** | ⚠️ 简化版 | Inspect 仅做视觉对比，缺少 IoU/MSE 计算 |
| **性能剪枝(AST审计)** | ⚠️ 部分 | validate-shader.py 有静态检查，但缺少算力统计 |

### 运行态差距（不在当前 MVP 范围）

| 运行态设计要求 | 状态 | 说明 |
|----------|----------|----------|
| **运行时沙盒** | 📋 待单独实现 | 算力熔断器、受限计算图 |
| **DSL 转译器** | 📋 待单独实现 | GLSL → MSL/SPIR-V |
| **系统级集成** | 📋 待单独实现 | OS Framebuffer 注入 |

### 关键差距详解

#### 1. Harness Loop 约束系统

设计方案要求三层约束迭代：

```
形态收敛 (Shape Phase)
  → 计算 IoU (交并比)，若 < 0.95 则反馈修正 SDF 参数

动态拟合 (Motion Phase)
  → 计算光流 MSE，修正时间驱动函数

性能剪枝 (Performance Phase)
  → AST 指令复杂度审计，算子降级
```

**当前实现**：Inspect Agent 仅做视觉对比评分，缺少量化指标。

**需要补充**：
- `backend/app/services/mask_extractor.py` - 关键帧 SDF 轮廓提取
- `backend/app/services/optical_flow.py` - 光流场计算
- `backend/app/services/performance_audit.py` - AST 指令复杂度审计
- 修改 Inspect Agent 输出为结构化反馈：`{shape_iou, motion_mse, performance_score, feedback_commands}`

#### 2. DSL 中间表示增强

当前 visual_description JSON 结构：

```json
{
  "effect_name": "...",
  "shape": {"type": "...", "sdf_primitives": [], "parameters": {}},
  "color": {...},
  "animation": {...}
}
```

设计方案要求更完整的 DSL：

```json
{
  "operators": [
    {"type": "SDF_Box", "params": {"size": [0.5, 0.3], "blend": "smooth_union"}},
    {"type": "Fractal_Noise", "params": {"octaves": 4, "frequency": 2.0}}
  ],
  "topology": "compose(add(mask, noise), multiply(fresnel, gradient))",
  "uniforms": {"u_time": "fract(t)", "u_pointer": "vec2"},
  "constraints": {"max_alu": 256, "max_texture_fetch": 8}
}
```

**需要补充**：
- 增强 Decompose Agent system prompt，输出算子拓扑描述
- 设计 DSL Schema 并验证

#### 3. 特征提取增强

设计方案要求三维度特征：

| 特征维度 | 设计要求 | 当前实现 |
|----------|----------|----------|
| **形态场** | 关键帧 SDF Mask | ❌ 未实现 |
| **光流场** | Optical Flow 矢量 | ❌ 未实现 |
| **色彩频域** | 直方图 + 频率分布 | ❌ 未实现 |

**需要补充**：
- `backend/app/services/perception.py` - 多维度特征提取模块
- 关键帧 SDF 轮廓提取 (使用 OpenCV 或 skimage)
- 光流计算 (OpenCV `calcOpticalFlowFarneback`)
- 色彩频域分析 (FFT 或 直方图)

#### 4. 运行时沙盒

设计方案要求：

```
运行态沙盒
  ├─ DSL 转译器 (DSL → GLSL/MSL/Warp)
  ├─ 系统上下文注入 (u_time, u_resolution, u_pointer, u_sysTheme)
  ├─ 受限计算图 (禁止无界内存读写)
  └─ 算力熔断器 (单帧 < 2ms)
```

**当前实现**：仅 WebGL 预览，无安全隔离。

**需要补充**：
- Shader 执行时间监控 (WebGL `getQuery` 或估算)
- 禁止危险操作的静态检查
- 目标平台转译器 (GLSL → MSL for iOS, GLSL → Vulkan SPIR-V for Android)

---

## 范围界定

**当前 MVP 范围**：专注于**开发态（编辑态）** Agent 系统，实现从 UX 设计稿到 GLSL Shader 的自动化生成闭环。

**不在当前范围**（后续单独实现）：
- 运行态沙盒（算力熔断器、受限计算图）
- 系统级集成（OS Framebuffer 注入）
- 目标平台转译（GLSL → MSL/SPIR-V）

---

## 后续开发优先级（开发态）

### P0 (关键功能，影响核心闭环质量)

1. **完善 Inspect Agent 多维度评估**
   - 实现 IoU 计算 (渲染截图 vs 设计参考 mask)
   - 实现 MSE 光流对比
   - 输出结构化修正指令而非简单评分

2. **增强 DSL 中间表示**
   - 设计完整 DSL Schema（算子拓扑描述）
   - Decompose Agent 输出算子组合关系
   - Generate Agent 解析 DSL 生成 GLSL

3. **特征提取增强**
   - 关键帧 SDF Mask 提取（形态场）
   - 光流场计算（动态特征）
   - 色彩频域分析（直方图 + FFT）

### P1 (重要功能，提升迭代效率)

4. **性能剪枝（AST审计）**
   - GLSL 指令复杂度静态分析
   - Texture Fetch/ALU 计数
   - 超阈值时算子自动降级建议

5. **视频输入优化**
   - 提升 Pipeline 执行速度（关键帧并行处理）
   - 关键帧预览缩略图显示
   - 进度百分比实时显示

### P2 (体验优化)

6. **WebUI 交互增强**
   - 参数滑块实时联动预览
   - Shader 编辑器智能补全
   - 历史版本对比切换

7. **效果模板库**
   - 预置常用效果模板（涟漪、光晕、磨砂）
   - 模板参数化快速生成
   - 用户自定义模板保存

---

## 文件结构

```
VFX-Agent/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI 入口
│   │   ├── config.py               # 环境变量 + 模型配置
│   │   ├── routers/
│   │   │   ├── pipeline.py         # Pipeline API
│   │   │   └── __init__.py
│   │   ├── agents/
│   │   │   ├── base.py             # Agent 基类 (多 API 支持 + 代理)
│   │   │   ├── decompose.py        # Decompose Agent
│   │   │   ├── generate.py         # Generate Agent
│   │   │   ├── inspect.py          # Inspect Agent
│   │   │   └── __init__.py
│   │   ├── pipeline/
│   │   │   ├── graph.py            # LangGraph 编排 + 阶段日志
│   │   │   ├── state.py            # PipelineState TypedDict
│   │   │   └── __init__.py
│   │   ├── services/
│   │   │   ├── video_extractor.py  # FFmpeg 关键帧提取
│   │   │   ├── browser_render.py   # Playwright 截图
│   │   │   └ __init__.py
│   │   ├── prompts/
│   │   │   ├── decompose_system.md # Decompose system prompt
│   │   │   ├── generate_system.md  # Generate system prompt
│   │   │   └ inspect_system.md    # Inspect system prompt
│   │   └── __init__.py
│   ├── requirements.txt
│   ├── .env                        # 实际配置 (不提交)
│   ├── .env.example                # 配置模板
│   ├── test_agents.py              # Agent 逐步调试脚本
│   └── debug_output/               # 调试输出目录
├── .claude/
│   └── skills/
│       └── effect-dev/
│           ├── SKILL.md            # Skill 主文件
│           ├── references/
│           │   ├── sdf-operators.md
│           │   ├── noise-operators.md
│           │   ├── lighting-transforms.md
│           │   ├── texture-sampling.md
│           │   ├── shader-templates.md
│           │   ├── aesthetics-rules.md
│           │   ├── gls-constraints.md
│           ├── assets/
│           │   └ shader-skeleton.glsl
│           └── scripts/
│               └ validate-shader.py
├── frontend/
│   ├── src/
│   │   ├── App.tsx                 # 主布局 (三栏)
│   │   ├── components/
│   │   │   ├── InputPanel.tsx      # 上传 + 文本输入
│   │   │   ├── AgentLog.tsx        # Pipeline 进度日志 (增强版)
│   │   │   ├── ShaderEditor.tsx    # GLSL 编辑器 + 语法高亮
│   │   │   ├── ParameterPanel.tsx  # 参数提取 + 滑块
│   │   │   └ ShaderPreview.tsx     # WebGL 渲染预览
│   │   ├── hooks/
│   │   │   └ usePipeline.ts        # Pipeline 状态订阅 (500ms polling)
│   │   ├── lib/
│   │   │   ├── shader-renderer.ts  # Three.js ShaderMaterial 封装
│   │   │   ├── glsl-parser.ts      # GLSL 参数提取
│   │   ├── index.css               # Tailwind CSS
│   │   └ main.tsx
│   ├── package.json
│   ├── vite.config.ts
│   └ tsconfig.json
├── example/
│   ├── demo.webm                   # 测试视频 (Windows 图标动画)
│   └ description.txt               # 测试描述
├── docs/
│   └── superpowers/plans/
│       └ 2026-04-24-vfx-agent-mvp.md  # MVP 实施计划
├── AGENTS.md                       # 本文档
├── README.md
├── start.sh                        # 启动脚本
└── .gitignore
```

---

## Git Commits (29)

```
69b41b4 fix: duration tracking in all pipeline nodes
b4dc435 fix: add missing isFullscreen state to AgentLog
c0cf6bd feat: add fullscreen toggle to AgentLog component
d8fbcec docs: clarify scope - focus on development state, runtime deferred
6ea9697 docs: add AGENTS.md with project overview and gap analysis
52f4c79 fix: initialize phase_start_time for duration tracking
d8fa034 chore: remove demo screenshot
f46012a fix: screenshot size 1024x1024 to avoid mobile warning
754610a chore: remove test screenshots
a902c5e fix: WebUI complete fixes
51631d7 fix: usePipeline stale closure bug with refs
6550dd8 fix: pipeline graph for text-only input mode
e6c24d7 fix: Decompose Agent text-only input mode
bbf3f9a feat: redesign WebUI with professional three-column layout
aaac772 fix: increase Generate Agent max_tokens to 16384
3325783 fix: increase max_tokens for Decompose and Generate Agents
f170a41 fix: improve JSON parsing and add Playwright integration
6bec888 feat: add proxy support for Gemini and other APIs
13e42ac fix: update requirements.txt for openai and python-multipart
43d8e07 fix: add python-multipart for FastAPI form data support
b21f2f9 fix: upgrade openai package to fix proxies argument error
33bb9b0 feat: add start.sh script for launching backend and frontend
9f1dcf0 feat: add Pipeline orchestration and complete WebUI
c26d6cd feat: add Generate Agent, Inspect Agent, Web Shader Renderer
9ae40b0 feat: add effect-dev Agent Skill with complete references
30a03b6 feat: add Decompose Agent with video keyframe extraction
3f8a0ad feat: add BaseAgent with OpenAI-compatible LLM client
62b1a1b chore: scaffold backend + frontend project structure
```

---

## 快速启动

```bash
# 启动服务
./start.sh start

# 状态查看
./start.sh status

# 停止服务
./start.sh stop

# 测试 Agent
cd backend && python test_agents.py
```

---

## 配置文件

模型配置通过 `backend/.env` 按角色指定：

```env
# Decompose Agent (多模态)
DECOMPOSE_API_KEY=xxx
DECOMPOSE_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
DECOMPOSE_MODEL=gemini-2.5-flash

# Generate Agent (代码生成)
GENERATE_API_KEY=xxx
GENERATE_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
GENERATE_MODEL=gemini-2.5-flash

# Inspect Agent (多模态)
INSPECT_API_KEY=xxx
INSPECT_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
INSPECT_MODEL=gemini-2.5-flash

# 代理 (海外 API)
PROXY=http://127.0.0.1:7890
```

---

## 参考文档

- **设计方案**: `基于 AI Agent 的操作系统级自定义视效生成管线设计方案.md`
- **MVP 实施计划**: `docs/superpowers/plans/2026-04-24-vfx-agent-mvp.md`
- **effect-dev Skill**: `.claude/skills/effect-dev/SKILL.md`
- **iq SDF 算子**: https://iquilezles.org/articles/distfunctions2d/
- **Shadertoy 案例**: https://www.shadertoy.com/

---

## 代码统计

| 指标 | 数值 |
|------|------|
| **总代码文件** | ~40 个核心文件 |
| **代码行数** | ~4071 行 |
| **Git Commits** | 29 条 |
| **已实现功能** | 25+ 项 ✅ |
| **设计方案差距** | 6 项待补充（开发态） |

---

*最后更新: 2026-04-25*