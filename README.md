# VFX-Agent

<div align="center">

**基于 AI Agent 的视效代码自动生成系统**

从 UX 视频/图片输入自动生成 Shadertoy 格式 GLSL 着色器代码

[English](#english) | [中文文档](#中文文档)

</div>

---

## 中文文档

### 项目简介

VFX-Agent 是一个 AI Agent 驱动的自动化系统，从 UX 视频/图片输入生成 Shadertoy 格式 GLSL 着色器代码。v2.0 采用 **codex OD（动态编排）架构**，单次 `codex exec` 调用自主完成全流程：分析关键帧 → 生成 visual_description → 编写 GLSL → 验证编译 → 渲染截图 → 子 Agent 评分 → 迭代优化。

**核心能力**：
- 🎨 多模态输入：支持图片、视频、纯文本描述
- 🤖 单 Agent 自主编排：codex exec 按 SKILL.md 6-phase 工作流执行
- 🔄 自动迭代优化：子 Agent 隔离评分 + 语义反馈修正
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
快速生成常见 UI 视效：涟漪（Ripple）、光晕（Glow）、磨砂玻璃（Frosted Glass）、流光（Shimmer）、渐变动画（Gradient Animation）、波纹（Wave）等。

---

### v2.0 架构设计

```
[输入] 视频/图片/文本描述
   │
   ▼
┌──────────────────────────────────────────────────────────────┐
│  Python Orchestrator (~270 行)                                │
│  FFmpeg 提关键帧 → symlink skills → spawn codex → 解析 JSONL │
│  不做迭代控制 / 评分 / 路由（全部委托给 codex）                │
└──────────────────────────────────────────────────────────────┘
   │
   ▼
┌──────────────────────────────────────────────────────────────┐
│  codex exec 自主编排（按 SKILL.md）                           │
│                                                              │
│  Phase 1  Analyse  ──→  visual_description.json              │
│  Phase 2  Generate ──→  shader.glsl                          │
│  Phase 3  Validate ──→  compile check                        │
│  Phase 4  Render   ──→  Playwright screenshot                │
│  Phase 5  Evaluate ──→  subagent (spawn_agent, fork_turns=n) │
│  Phase 6  Iterate  ──→  loop or finalize                     │
│                                                              │
│  ←── 迭代（max_iterations 由 SKILL.md 约束）──→              │
└──────────────────────────────────────────────────────────────┘
   │
   ▼
[输出] 最终 GLSL Shader + WebGL 预览 + 评分报告
```

**架构要点**：

| 组件 | 职责 |
|------|------|
| **Python Orchestrator** | FFmpeg 关键帧提取、workdir 创建、symlink skills、spawn codex、解析 JSONL、状态持久化。不做路由/评分/迭代控制。 |
| **codex Agent（主）** | 按 `skills/vfx-shader/SKILL.md` 6-phase 自主工作流执行全流程。 |
| **Subagent（Phase 5）** | 通过 `spawn_agent`（`fork_turns="none"` 上下文隔离）评估渲染结果，输出结构化评分。 |
| **Skill 资产** | SKILL.md（6-phase 工作流）+ shader_templates.md（1200 行参考）+ few_shot_examples.md（9 个端到端示例）+ 脚本（验证/渲染/像素分析）。 |

---

### 技术栈

| 组件 | v2.0 技术 |
|------|-----------|
| Backend | Python 3.11+, FastAPI, codex CLI 0.144.1+ |
| LLM 编排 | codex OD 动态编排（非 LangGraph） |
| Frontend | React 18, Vite, TypeScript |
| 渲染 | Three.js, WebGL（复用 v1.0） |
| 浏览器自动化 | Playwright |
| 视频处理 | FFmpeg |
| 状态持久化 | JSON 文件 |

---

### 快速开始

#### 环境要求

- Python 3.11+
- Node.js 18+
- FFmpeg（视频处理）
- codex CLI 0.144.1+（`npm install -g @openai/codex`）
- 现代浏览器（支持 WebGL）

#### 安装与启动

```bash
# 1. 克隆项目
git clone https://github.com/your-repo/VFX-Agent.git
cd VFX-Agent

# 2. 配置 API Keys
cd backend
cp .env.example .env
# 编辑 .env 文件，填入 codex 模型配置

# 3. 启动服务（自动安装依赖）
./start.sh start
```

#### 访问地址

| 服务 | 地址 |
|------|------|
| **Frontend (WebUI)** | http://localhost:5173 |
| **Backend (API)** | http://localhost:8000 |
| **API Docs** | http://localhost:8000/docs |

#### CLI 直接运行（不需要前端）

```bash
cd backend
python tests/e2e/run_v2_samples.py heart-2d

# 批量运行
python tests/e2e/run_v2_samples.py 4-col-grad heart-2d shiny-circle
```

---

### 项目结构

```
VFX-Agent/
├── backend/
│   ├── app/
│   │   ├── main.py                   # FastAPI 入口
│   │   ├── config.py                 # v2.0 配置
│   │   ├── orchestrator.py (~270 行) # v2.0 核心编排器
│   │   ├── state_store.py (~65 行)   # JSON 状态持久化
│   │   ├── pipeline_states/          # 运行时状态 (.json)
│   │   ├── routers/                  # API 路由
│   │   │   ├── pipeline.py           # POST /run + GET /status
│   │   │   └── config.py
│   │   ├── services/                 # 复用 v1.0 服务
│   │   │   ├── browser_render.py
│   │   │   ├── shader_render_page.html # v2.0 standalone HTML
│   │   │   ├── shader_validator.py
│   │   │   ├── video_extractor.py
│   │   │   └── session_logger.py
│   │   └── skills/                   # v2.0 codex skill 资产
│   │       ├── AGENTS.md (~470 行)   # codex 主指令
│   │       └── vfx-shader/
│   │           ├── SKILL.md (~415 行) # 6-phase 工作流
│   │           └── reference/
│   │               ├── shader_templates.md
│   │               ├── few_shot_examples.md
│   │               └── scripts/
│   │                   ├── validate_shader.py
│   │                   ├── render_shader.py
│   │                   └── analyze_pixels.py
│   ├── tests/
│   │   ├── unit/                     # 单元测试（5 个文件，18 tests pass）
│   │   └── e2e/                      # v2.0 E2E runner + report
│   ├── test_results/                 # 测试结果归档
│   ├── requirements.txt
│   └── .env.example
├── frontend/                         # 复用 v1.0（最小改动）
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/               # InputPanel, ShaderEditor 等
│   │   └── hooks/usePipeline.ts
│   └── package.json
├── test-samples/                     # 19 baseline 样本 (.gitignored)
├── docs/
├── start.sh
└── README.md
```

---

### 测试结果

> 📊 **完整 50-sample benchmark 详情**（每 sample 含 reference vs render 对比、UI 截图、codex 关键事件时间线、8 维 dimension 评分、shader 源码）见 [**GitHub Release v2.0.1**](https://github.com/yangfei1223/VFX-Agent/releases/tag/v2.0.1)（95MB tar.gz 归档）。

#### v2.0 vs v1.0（50 samples + retry）

| 指标 | v1.0 LangGraph (19 sample) | v2.0 codex OD (50 sample, 含 retry) | Delta |
|------|---------------------------|-------------------------------------|-------|
| 平均分 | 0.715 | **0.770** | **+0.055** |
| 中位分 | 0.710 | 0.766 | +0.056 |
| 通过 (≥0.85) | 5/19 (26.3%) | **16/50 (32.0%)** | +5.7% |
| 可接受 (0.80-0.85) | 4/19 (21.1%) | 5/50 (10.0%) | − |
| 失败 (<0.80) | 10/19 (52.6%) | 29/50 (58.0%) | − |

> **关键发现**：v2.0 在 50-sample 上以 +0.055 反超 v1.0（v2.0 首次系统性超越 v1.0）。第一轮 9 个 0 分/低分样本经 retry 后全部大幅好转（4 个黑屏 → 0.6+，2 个直接 PASS），证明 codex 非确定性对瞬时编译失败有效。

#### 历次 benchmark

| 版本 | 日期 | 样本数 | 平均分 | 详情 |
|------|------|--------|--------|------|
| **v2.0.1** | 2026-07-16 | 50 (+ retry) | **0.770** | [Release v2.0.1](https://github.com/yangfei1223/VFX-Agent/releases/tag/v2.0.1) |
| v2.0.0 | 2026-07-15 | 20 | 0.762 | [Release v2.0.0](https://github.com/yangfei1223/VFX-Agent/releases/tag/v2.0.0) |
| v1.0 baseline | 2026-05-18 | 19 | 0.715 | `backend/test_results/2026-05-18_e2e-v2-baseline-19samples/` |

#### 本地查看报告

```bash
# 解压 release 里的 tar.gz 到 backend/test_results/
cd backend
tar xzf /path/to/v2.0.1-baseline-50samples.tar.gz
open test_results/2026-07-16_v2-codex-od-50samples/index.html

# 自己跑 benchmark + 生成报告
python tests/e2e/run_v2_samples_via_ui.py <sample1> <sample2> ...  # 显式列表
python tests/e2e/collect_v2_results.py
python tests/e2e/generate_v2_report.py
```

---

### 已知问题

| 问题 | 说明 | 优先级 |
|------|------|--------|
| 部分样本 shader 编译失败 | 渲染全黑，subagent score ≈ 0 | P0 |
| 复杂样本 600s timeout | hypnotic-ripples、moon-distance-2d 等超时 | P0 |
| 平均分落后 v1.0 | 迭代质量不足，3 iter 用满仍不收敛 | P1 |
| Subagent 评分偏差 | A/B cross-validation delta 0.111，borderline bias | P1 |

### Roadmap

- **Phase F**：提高 Generate Agent few-shot 覆盖面，降低编译失败率
- **Phase G**：优化迭代策略，约束 codex 的时间分配
- **Phase H**：v1.0 prompt 资产移植到 v2.0 skill 体系

---

### v1.0 历史版本

v1.0（LangGraph 三 Agent 架构）已废弃。如需查看旧版代码，请 checkout `v1.0.0` tag。

---

### 配置说明

模型配置通过 `backend/.env` 指定：

```env
# codex 模型配置
CODEX_MODEL=gemini-2.5-flash
CODEX_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
CODEX_API_KEY=your_api_key

# 代理（海外 API）
PROXY=http://127.0.0.1:7890
```

**支持的所有 OpenAI-compatible API**：Gemini 2.x、OpenAI GPT-4o、Anthropic Claude 等。

---

### 参考文档

- **设计文档**：`docs/superpowers/specs/2026-07-13-vfx-agent-v2-codex-od-design.md`
- **codex Agent 指令**：`backend/app/skills/AGENTS.md`
- **6-phase 工作流**：`backend/app/skills/vfx-shader/SKILL.md`
- **Shader 模板库**：`backend/app/skills/vfx-shader/reference/shader_templates.md`
- **Few-shot 示例**：`backend/app/skills/vfx-shader/reference/few_shot_examples.md`
- **iq SDF 算子**：https://iquilezles.org/articles/distfunctions2d/
- **Shadertoy 案例**：https://www.shadertoy.com/

---

### 开源协议

MIT License

---

## English

### Project Overview

VFX-Agent is an AI Agent-driven system that automatically generates Shadertoy-format GLSL shader code from UX video/image inputs. v2.0 uses a **codex OD (Orchestrated Dispatch)** architecture — a single `codex exec` call autonomously completes the full pipeline.

**Key Features**:
- 🎨 Multimodal input: images, videos, text descriptions
- 🤖 Autonomous single-Agent pipeline via codex exec + SKILL.md
- 🔄 Self-iteration with isolated subagent evaluation
- ⚡ Real-time WebGL shader preview + live editing

### Quick Start

```bash
# Clone and setup
git clone https://github.com/your-repo/VFX-Agent.git
cd VFX-Agent
cd backend && cp .env.example .env

# Start services
../start.sh start

# CLI direct run
python tests/e2e/run_v2_samples.py heart-2d

# Access WebUI at http://localhost:5173
```

### Architecture (v2.0)

```
[Input] → Python Orchestrator (FFmpeg + spawn codex)
         → codex exec (autonomous 6-phase workflow)
           Phase 1: Analyse → visual_description.json
           Phase 2: Generate → shader.glsl
           Phase 3: Validate → compile check
           Phase 4: Render → screenshot
           Phase 5: Evaluate → subagent (spawn_agent, fork_turns=none)
           Phase 6: Iterate / Finalize
         → Output: GLSL Shader + Score Report
```

### Test Results Summary

📊 **Full 50-sample benchmark report** (per-sample reference vs render comparison, UI screenshots, codex event timeline, dimension scores, shader source): see [**GitHub Release v2.0.1**](https://github.com/yangfei1223/VFX-Agent/releases/tag/v2.0.1).

| Metric | v1.0 LangGraph (19) | v2.0 codex OD (50 + retry) | Delta |
|--------|---------------------|----------------------------|-------|
| Average Score | 0.715 | **0.770** | **+0.055** |
| Median Score | 0.710 | 0.766 | +0.056 |
| Pass (≥0.85) | 5/19 (26.3%) | **16/50 (32.0%)** | +5.7% |

v2.0 surpasses v1.0 on the 50-sample benchmark. 9 zero/low-score samples in round 1 recovered significantly after retry (4 black-screen → 0.6+, 2 PASS) — codex non-determinism effectively rescues transient compile failures.

### License

MIT License
