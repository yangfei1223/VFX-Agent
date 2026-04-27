# VFX-Agent

<div align="center">

**基于 AI Agent 的视效代码自动生成系统**

从 UX 视频/图片输入自动生成 Shadertoy 格式 GLSL 着色器代码

[English](#english) | [中文文档](#中文文档)

</div>

---

## 中文文档

### 项目简介

VFX-Agent 是一个多 Agent 闭环系统，从 UX 视频/图片输入自动生成 Shadertoy 格式 GLSL 着色器代码，并经视觉检视 Agent 自反馈迭代直至收敛。

**核心能力**：
- 🎨 多模态输入：支持图片、视频、纯文本描述
- 🤖 三 Agent 协作：Decompose → Generate → Inspect
- 🔄 自动迭代优化：视觉对比评分 + 反馈修正
- ⚡ 实时预览：WebGL Shader 渲染 + 实时编辑

**范围界定**：
- ✅ 2D/2.5D 平面动效（涟漪、光晕、磨砂、流光等 UI 视效）
- ✅ 移动端和 Web 平台
- ❌ 3D raymarching/场景渲染/体渲染（不在当前范围）

---

### 使用场景

#### 🎨 UX 设计师快速生成 Shader 原型
上传设计稿或动效参考，自动生成可运行的 GLSL 代码，无需手写 Shader。

#### 🎬 动效设计验证
将 UX 视频转换为 Shader 代码，验证动效逻辑是否符合预期。

#### ✨ UI 视效生成
快速生成常见 UI 视效：
- 涟漪（Ripple）
- 光晕（Glow）
- 磨砂玻璃（Frosted Glass）
- 流光（Shimmer）
- 渐变动画（Gradient Animation）
- 波纹（Wave）

#### 📱 跨平台预览
生成 Shadertoy 格式 Shader，可直接移植到：
- Web（Three.js / WebGL）
- iOS（Metal Shader Language）
- Android（Vulkan SPIR-V）

---

### 架构设计

#### 三 Agent 闭环架构

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

#### Agent 角色分工

| Agent | 输入 | 输出 | 职责 |
|-------|------|------|------|
| **Decompose** | 关键帧图片 + 视频元信息 | visual_description (JSON DSL) | 分析视觉元素，提取形态、色彩、动画特征 |
| **Generate** | visual_description + Skill | GLSL Shader (Shadertoy 格式) | 根据特征描述生成 Shader 代码 |
| **Inspect** | 渲染截图 + 设计参考截图 | 对比评分 + 修正指令 | 视觉对比，输出改进建议 |

#### 技术特性

- **LangGraph 编排**：使用 LangGraph 实现有向图状态机，支持条件路由和循环迭代
- **流式状态更新**：后端使用 `astream()` 实现实时进度推送，前端 500ms polling 获取状态
- **Agent 上下文历史**：每个 Agent 保留历史工作记录，避免重复错误
- **编译重试限制**：`compile_retry_count` 计数器防止无限循环

#### 技术栈

| 组件 | 技术 |
|------|------|
| Backend | Python 3.11+, FastAPI, LangGraph |
| LLM SDK | OpenAI-compatible API |
| Frontend | React 18, Vite, TypeScript |
| 渲染 | Three.js, WebGL |
| 浏览器自动化 | Playwright |
| 视频处理 | FFmpeg |

---

### 快速开始

#### 环境要求

- Python 3.11+
- Node.js 18+
- FFmpeg（视频处理）
- 现代浏览器（支持 WebGL）

#### 安装步骤

```bash
# 1. 克隆项目
git clone https://github.com/your-repo/VFX-Agent.git
cd VFX-Agent

# 2. 配置 API Keys
cd backend
cp .env.example .env
# 编辑 .env 文件，填入你的 API keys

# 3. 安装依赖（启动脚本会自动安装）
./start.sh start
```

#### 启动服务

```bash
# 启动服务（自动安装依赖）
./start.sh start

# 查看状态
./start.sh status

# 查看日志
./start.sh logs

# 停止服务
./start.sh stop

# 重启服务
./start.sh restart
```

#### 访问地址

| 服务 | 地址 |
|------|------|
| **Frontend (WebUI)** | http://localhost:5173 |
| **Backend (API)** | http://localhost:8000 |
| **API Docs** | http://localhost:8000/docs |

---

### 使用方法

#### 1. 上传图片/视频

在左侧 **Input Panel** 中：
- 📷 点击上传图片（支持 PNG/JPG/WebP，单图或多图）
- 🎬 点击上传视频（支持 MP4/WebM）
- ✏️ 或直接输入文本描述

#### 2. 启动 Pipeline

点击 **"Start Pipeline"** 按钮，系统将自动执行：
1. **Extract** - 提取关键帧
2. **Decompose** - 分析视效特征
3. **Generate** - 生成 Shader 代码
4. **Render** - WebGL 渲染预览
5. **Inspect** - 视觉对比评分

#### 3. 查看进度

在中间 **Agent Process Log** 面板中：
- 查看每个阶段的执行状态（started/completed/failed）
- 查看阶段执行时间
- 点击展开查看详细信息
- 点击 "Maximize" 展开全屏查看

#### 4. 编辑 Shader

在右侧 **Shader Editor** 中：
- 查看生成的 GLSL 代码
- 编辑代码并实时预览
- 语法高亮 + 行号显示

#### 5. 调整参数

在 **Parameter Panel** 中：
- 查看提取的 `#define` 常量
- 查看提取的 `uniform` 变量
- 滑块调整参数（开发中）

#### 6. 预览效果

在 **Shader Preview** 中：
- WebGL 实时渲染
- 鼠标交互（部分效果支持）
- 时间动画自动播放

#### 7. 调整设置

点击右上角 **Settings (⚙️)** 按钮配置：
| 参数 | 说明 | 默认值 |
|------|------|--------|
| `max_iterations` | 最大迭代次数 | 2 |
| `passing_threshold` | 通过阈值（0-100） | 80 |
| `compile_retry_limit` | 编译重试限制 | 3 |

---

### 配置说明

#### 模型配置

在 `backend/.env` 文件中按 Agent 角色配置模型：

```env
# Decompose Agent（视觉解构，需要多模态能力）
DECOMPOSE_API_KEY=your_api_key
DECOMPOSE_BASE_URL=https://api.openai.com/v1
DECOMPOSE_MODEL=gpt-4o

# Generate Agent（代码生成，需要强 coding 能力）
GENERATE_API_KEY=your_api_key
GENERATE_BASE_URL=https://api.openai.com/v1
GENERATE_MODEL=gpt-4o

# Inspect Agent（视觉检视，需要多模态能力）
INSPECT_API_KEY=your_api_key
INSPECT_BASE_URL=https://api.openai.com/v1
INSPECT_MODEL=gpt-4o
```

**支持的所有 OpenAI-compatible API**：
- OpenAI GPT-4o / GPT-4 Vision
- Google Gemini 2.x
- Anthropic Claude (via proxy)
- Moonshot Kimi
- Zhipu GLM
- 其他兼容 API

#### 系统参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `MAX_ITERATIONS` | Pipeline 最大迭代次数 | 2 |
| `RENDER_TIMEOUT_MS` | 渲染超时时间（毫秒） | 2000 |
| `SCREENSHOT_WIDTH` | 截图宽度 | 1024 |
| `SCREENSHOT_HEIGHT` | 截图高度 | 1024 |

#### 代理配置

访问海外 API（如 Gemini）需要配置代理：

```env
# HTTP 代理
PROXY=http://127.0.0.1:7890

# SOCKS5 代理
PROXY=socks5://127.0.0.1:1080

# 不使用代理
# PROXY=
```

---

### 更新日志

#### v0.2.0 (2026-04-25)

**新增功能**：
- ✨ 流式处理：使用 `astream()` 实现实时状态更新
- ⚙️ 设置面板：可配置 max_iterations/passing_threshold/compile_retry_limit
- 📜 Agent 上下文历史：每个 Agent 保留工作记录，避免重复错误
- 🔄 路由修复：修复 generate → validate_shader → generate 无限循环
- 🛡️ 编译重试限制：`compile_retry_count` 计数和终止条件
- 📊 节点日志输出：Backend 日志添加 `[Pipeline ID] Node XXX completed`

**WebUI 增强**：
- 🖼️ 日志窗口最大化：Maximize 按钮展开全屏显示
- 📝 Agent Reasoning 显示：点击日志条目展开显示原始响应
- ⏱️ 持续时间统计：每阶段显示 duration (ms/s)
- 🔢 迭代次数显示：每条日志显示 Iteration N

#### v0.1.0 (2026-04-24)

**核心功能**：
- 🤖 三 Agent 架构：Decompose → Generate → Inspect
- 🎨 多模态输入：图片/视频/文本描述
- 🔄 自动迭代优化：视觉对比 + 反馈修正
- ⚡ LangGraph 编排：有向图状态机
- 🌐 WebGL 渲染：Three.js ShaderMaterial
- 📊 Agent Process Log：5 阶段时间线 + 实时进度

**Agent 实现**：
- Decompose Agent：关键帧分析 + 视效特征提取
- Generate Agent：GLSL 代码生成 + effect-dev Skill
- Inspect Agent：渲染截图对比 + 评分反馈

**WebUI 实现**：
- 三栏布局：Input / Agent Log / Editor+Preview
- GLSL Editor：语法高亮 + 实时编辑
- Shader Preview：WebGL 实时渲染
- Parameter Panel：参数提取 + 滑块

---

### 项目结构

```
VFX-Agent/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI 入口
│   │   ├── config.py               # 环境变量 + 模型配置
│   │   ├── agents/                 # Agent 实现
│   │   │   ├── base.py             # Agent 基类 (多 API 支持 + 代理)
│   │   │   ├── decompose.py        # Decompose Agent
│   │   │   ├── generate.py         # Generate Agent
│   │   │   └── inspect.py          # Inspect Agent
│   │   ├── pipeline/               # Pipeline 编排
│   │   │   ├── graph.py            # LangGraph 状态机
│   │   │   └── state.py            # PipelineState TypedDict
│   │   ├── services/               # 服务层
│   │   │   ├── video_extractor.py  # FFmpeg 关键帧提取
│   │   │   └── browser_render.py   # Playwright 截图
│   │   └── prompts/                # Agent System Prompts
│   │       ├── decompose_system.md
│   │       ├── generate_system.md
│   │       └── inspect_system.md
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx                 # 主布局 (三栏)
│   │   ├── components/
│   │   │   ├── InputPanel.tsx      # 上传 + 文本输入
│   │   │   ├── AgentLog.tsx        # Pipeline 进度日志
│   │   │   ├── ShaderEditor.tsx    # GLSL 编辑器
│   │   │   ├── ParameterPanel.tsx  # 参数提取 + 滑块
│   │   │   └── ShaderPreview.tsx    # WebGL 渲染预览
│   │   └── lib/
│   │       └── shader-renderer.ts  # Three.js ShaderMaterial 封装
│   └── package.json
├── .claude/
│   └── skills/
│       └── effect-dev/             # Generate Agent Skill
│           ├── SKILL.md            # Skill 主文件
│           └── references/         # 技术参考文档
│               ├── sdf-operators.md
│               ├── noise-operators.md
│               ├── lighting-transforms.md
│               └── ...
├── start.sh                        # 启动脚本
└── README.md
```

---

### 参考文档

- **设计方案**：`基于 AI Agent 的操作系统级自定义视效生成管线设计方案.md`
- **MVP 实施计划**：`docs/superpowers/plans/2026-04-24-vfx-agent-mvp.md`
- **effect-dev Skill**：`.claude/skills/effect-dev/SKILL.md`
- **iq SDF 算子**：https://iquilezles.org/articles/distfunctions2d/
- **Shadertoy 案例**：https://www.shadertoy.com/

---

### 开源协议

MIT License

---

## English

### Project Overview

VFX-Agent is a multi-Agent closed-loop system that automatically generates Shadertoy-format GLSL shader code from UX video/image inputs, with visual inspection Agent self-feedback iteration until convergence.

**Key Features**:
- 🎨 Multimodal input: images, videos, text descriptions
- 🤖 Three-Agent collaboration: Decompose → Generate → Inspect
- 🔄 Auto iteration: visual comparison + feedback refinement
- ⚡ Real-time preview: WebGL shader rendering + live editing

**Scope**:
- ✅ 2D/2.5D UI visual effects (ripple, glow, frosted glass, shimmer, etc.)
- ✅ Mobile and Web platforms
- ❌ 3D raymarching/scene rendering/volumetric rendering (out of scope)

### Quick Start

```bash
# Clone and setup
git clone https://github.com/your-repo/VFX-Agent.git
cd VFX-Agent

# Configure API keys
cd backend
cp .env.example .env
# Edit .env with your API keys

# Start services
./start.sh start

# Access WebUI
# http://localhost:5173
```

### License

MIT License