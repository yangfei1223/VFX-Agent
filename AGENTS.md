# VFX-Agent 项目信息

> 本文档记录项目架构、已实现功能、测试结果与优化决策，便于后续开发对齐。

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
   |
   v
+-----------------------------------------------------------+
|  Pipeline Orchestrator (LangGraph)                        |
|                                                           |
|  +--------------+   +--------------+   +--------------+  |
|  | Decompose    | ->| Generate     | ->| Inspect      |  |
|  | Agent        |   | Agent        |   | Agent        |  |
|  | (多模态)     |   | (代码生成)   |   | (多模态)     |  |
|  +--------------+   +--------------+   +--------------+  |
|        |                  |                  |            |
|        v                  v                  v            |
|  visual_description    GLSL shader      对比评分         |
|  (JSON DSL)           (Shadertoy)      + 反馈指令        |
|                                                           |
|  <--- 反馈迭代 (若评分 < threshold) ---                   |
+-----------------------------------------------------------+
   |
   v
[输出] 最终 GLSL Shader + WebGL 预览
```

### Agent 角色分工

| Agent | Role (职业定位) | 输入 | 输出 | 模型要求 |
|-------|----------------|------|------|----------|
| **Decompose** | 视觉分析专家 | 关键帧图片 + 视频元信息 + 用户标注 | visual_description (JSON) | 多模态 LLM |
| **Generate** | 图形程序开发专家 | visual_description + 算子知识库 + 前轮代码 + 反馈 | GLSL Shader (Shadertoy 格式) | 强 coding 能力 |
| **Inspect** | 视效技术总监 | 渲染截图 + 设计参考截图 + visual_description | 对比评分 + 语义反馈 | 多模态 LLM |

**System Prompt 架构**（参考 Google GenerativeUI 论文 arXiv:2604.09577）：
```
Role -> Philosophy -> Common Info -> Planning Instructions -> Skill -> Failure Examples
```

### Pipeline 阶段流程

1. **Extract Keyframes** - FFmpeg 从视频提取关键帧（4-6 帧）
2. **Decompose** - 多模态 LLM 分析关键帧，输出结构化视效描述
3. **Generate** - 根据 DSL + 算子知识库生成 GLSL 代码
4. **Render** - Playwright 在 WebGL 预览页渲染 shader 并截图
5. **Inspect** - 对比渲染截图与设计参考，输出评分和修正指令
6. **Loop** - 若未通过则迭代生成修正代码，直至收敛或达到最大迭代次数

---

## 已实现功能

### 核心管道

| 功能 | 说明 |
|------|------|
| 三 Agent 闭环 | Decompose -> Generate -> Inspect 反馈迭代 |
| 流式处理 | `astream()` 实时状态更新 |
| 编译重试限制 | `compile_retry_count` 防止无限循环 |
| Agent 上下文历史 | generate_history, inspect_history 注入 prompt |
| 运行时配置 API | GET/PUT `/config` 动态调整参数 |
| Session 日志 | `session_logger.py` 记录 Agent 完整输入/输出 |

### Prompt 系统优化

| 功能 | 说明 |
|------|------|
| 9 种效果类型 | Plasma, Noise, Gradient, Ripple, Glow/Bloom, Liquid Glass, Particle Field, Domain Warp, Solid Shape |
| 分类决策树 | Decompose Agent 内置效果分类树，提高识别准确率 |
| Glow/Bloom 强度标准 | 统一 glow 效果的 intensity 评估基准 |
| 9 个 Few-shot 示例 | generate_system.md 包含 visual_description JSON -> 完整 GLSL shader 的端到端示例 |
| 9 个 Shader 模板 | shader_skill_reference.md 包含 Liquid Glass, Particle Field, Domain Warp, Solid Shape 等 9 个模板 |
| VFX 术语库 | 351 行术语定义，三 Agent 共享 |
| 效果算子目录 | 282 行算子参考（SDF/噪声/光照/UV 变换） |

### WebUI

| 功能 | 说明 |
|------|------|
| 三栏布局 | 输入面板 + 中间预览/编辑 + 参数/日志面板 |
| 实时 Shader 预览 | Three.js WebGL 渲染 |
| GLSL 编辑器 | 语法高亮 + 实时编辑 |
| Pipeline 进度日志 | 5 阶段时间线 + Agent Reasoning 展示 + 全屏模式 |
| VFX Discovery Form | 结构化效果描述输入 |
| Feedback Panel | 人工迭代反馈 |
| Pipeline Status | 管道状态可视化 |
| 设置面板 | max_iterations / passing_threshold / compile_retry_limit |
| 参数面板 | #define / uniform 提取与滑块 |

### 输入支持

| 类型 | 说明 |
|------|------|
| 纯文本描述 | 直接输入效果描述 |
| 图片上传 | PNG/JPG/WebP，单图或多图 |
| 视频上传 | MP4/WebM（耗时较长） |

### 服务层

| 服务 | 文件 | 说明 |
|------|------|------|
| 关键帧提取 | `video_extractor.py` | FFmpeg 提取 4-6 帧关键帧 |
| 浏览器渲染截图 | `browser_render.py` | Playwright WebGL 渲染 + 截图 |
| Prompt 构建 | `context_assembler.py` | 组装 system/user prompt + 历史上下文 |
| Session 日志 | `session_logger.py` | 记录 Agent 会话完整 IO |
| Shader 验证 | `shader_validator.py` | GLSL 编译检查 |
| 输入验证 | `validators.py` | API 输入参数校验 |

---

## 测试结果与优化决策

### V2 基线测试 (19 samples, max_iter=3)

| 指标 | 数值 |
|------|------|
| >=0.8 通过率 | 9/19 (47%) |
| 平均分 | 0.73 |
| 最高 | 4-col-grad 0.95, shiny-circle 0.88, twitter-blue-check 0.87 |
| 最低 | sparks-drifting 0.00, auroras 0.42 |

### CV 特征提取 A/B 测试 (19 samples, max_iter=1)

| 指标 | 数值 |
|------|------|
| 平均分变化 (delta) | -0.02 (CV hurt) |
| CV 帮助的样本 | 5/16 |
| CV 损害的样本 | 9/16 |

**结论**: CV 特征提取（SDF Mask、光流场、色彩频域）**不是瓶颈**。分支 `feat/cv-feature-extraction` 已测试并回退到 master。

### Few-shot Smoke Test (3 samples, max_iter=1)

| 样本 | 无 few-shot | 有 few-shot | Delta |
|------|-------------|-------------|-------|
| vortex-street | 0.00 (crash) | 0.65 | +0.65 |
| plasma-waves | 0.18 (crash) | 0.78 | +0.60 |
| heart-2d | 0.74 | 0.84 | +0.10 |

**结论**: Few-shot 示例显著提高 Generate Agent 稳定性，消除 crash 问题。当前优化方向：**增强 Generate Agent 的 few-shot 覆盖面**。

### 关键决策记录

| 决策 | 原因 |
|------|------|
| CV 特征提取已放弃 | A/B 测试证明无效，平均 delta 为负 |
| DSL 结构化字段已推迟 | Prompt channel 已满载，结构化字段挤占有限上下文 |
| Few-shot 是当前重点 | Smoke test 证明 few-shot 显著提升 Generate 稳定性 |

---

## 文件结构

```
VFX-Agent/
+-- backend/
|   +-- app/
|   |   +-- main.py                    # FastAPI 入口
|   |   +-- config.py                  # 环境变量 + 模型配置
|   |   +-- routers/
|   |   |   +-- pipeline.py            # Pipeline API
|   |   |   +-- config.py              # 配置 API (GET/PUT)
|   |   +-- agents/
|   |   |   +-- base.py                # Agent 基类 (多 API 支持 + 代理)
|   |   |   +-- decompose.py           # Decompose Agent
|   |   |   +-- generate.py            # Generate Agent
|   |   |   +-- inspect.py             # Inspect Agent
|   |   +-- pipeline/
|   |   |   +-- graph.py               # LangGraph 编排 + 阶段日志 + 路由函数
|   |   |   +-- state.py               # PipelineState TypedDict
|   |   +-- services/
|   |   |   +-- video_extractor.py     # FFmpeg 关键帧提取
|   |   |   +-- browser_render.py      # Playwright 截图
|   |   |   +-- context_assembler.py   # Prompt 构建器
|   |   |   +-- session_logger.py      # Agent 会话日志
|   |   |   +-- shader_validator.py    # GLSL 编译检查
|   |   |   +-- validators.py          # API 输入校验
|   |   +-- prompts/                   # System Prompts (核心资产)
|   |   |   +-- decompose_system.md    # 624 lines, 含分类决策树
|   |   |   +-- generate_system.md     # 1238 lines, 含 9 few-shot 示例
|   |   |   +-- inspect_system.md      # 724 lines, 含 Lighting rubric
|   |   |   +-- shader_skill_reference.md  # 1233 lines, 9 个 shader 模板
|   |   |   +-- shared_vfx_constraints.md  # 69 lines, 平台约束
|   |   |   +-- shared_vfx_terminology.md  # 351 lines, VFX 术语库
|   |   |   +-- vfx_effect_catalog.md      # 282 lines, 9 种效果算子
|   +-- tests/
|   |   +-- unit/                      # 单元测试（无需后端）
|   |   +-- e2e/                       # 端到端 Pipeline 测试
|   +-- test_results/                  # 测试结果归档（gitignored）
|   +-- requirements.txt
|   +-- .env                           # 实际配置 (不提交)
|   +-- .env.example                   # 配置模板
+-- frontend/
|   +-- src/
|   |   +-- App.tsx                    # 主布局 (三栏)
|   |   +-- components/
|   |   |   +-- InputPanel.tsx         # 上传 + 文本输入
|   |   |   +-- UploadPanel.tsx        # 文件上传组件
|   |   |   +-- VFXDiscoveryForm.tsx   # 结构化效果描述
|   |   |   +-- AgentLog.tsx           # Pipeline 进度日志
|   |   |   +-- ShaderEditor.tsx       # GLSL 编辑器 + 语法高亮
|   |   |   +-- CodeView.tsx           # 代码查看组件
|   |   |   +-- ShaderPreview.tsx      # WebGL 渲染预览
|   |   |   +-- ParameterPanel.tsx     # 参数提取 + 滑块
|   |   |   +-- SettingsPanel.tsx      # 设置面板
|   |   |   +-- FeedbackPanel.tsx      # 人工反馈面板
|   |   |   +-- PipelineStatus.tsx     # 管道状态组件
|   |   +-- hooks/
|   |   |   +-- usePipeline.ts         # Pipeline 状态订阅 (500ms polling)
|   |   +-- lib/
|   |   |   +-- shader-renderer.ts     # Three.js ShaderMaterial 封装
|   |   |   +-- glsl-parser.ts         # GLSL 参数提取
+-- test-samples/                      # 测试样本视频/图片（gitignored）
+-- example/
|   +-- demo.webm                      # 测试视频
|   +-- description.txt                # 测试描述
+-- docs/
|   +-- superpowers/plans/             # 实施计划文档
+-- AGENTS.md                          # 本文档
+-- README.md
+-- start.sh                           # 启动脚本
+-- .gitignore
```

---

## 测试规范

### 测试脚本组织

| 目录 | 用途 | 运行方式 |
|------|------|---------|
| `backend/tests/unit/` | 单元测试，验证 prompt/schema/catalog 完整性 | `cd backend && python -m pytest tests/unit/ -v` |
| `backend/tests/e2e/` | 端到端 Pipeline 测试，需后端运行 | 见下方命令 |

### E2E 测试用法

```bash
# 单样本测试（生成详细 HTML 报告）
cd backend && python tests/e2e/test_e2e_single.py --sample vortex-street --max-iter 3

# 批量测试（运行多个样本）
cd backend && python tests/e2e/test_e2e_batch.py --samples vortex-street plasma-waves heart-2d --max-iter 3 --timeout 480

# 生成批量 HTML 报告（从已保存结果）
cd backend && python tests/e2e/test_e2e_report.py --report-only
```

### 测试结果归档

测试结果统一存放在 `backend/test_results/`（已 gitignored），目录命名格式：

```
backend/test_results/
+-- 2026-05-18_e2e-v2-baseline-19samples/       # V2 基线测试
+-- 2026-05-19_e2e-v3-cv-debug-5samples/        # CV 特征调试
+-- 2026-05-20_e2e-v4-cv-semantic-5samples/     # 语义级 CV 对比
+-- 2026-05-20_e2e-v1-batch-19samples/          # V1 批量测试
+-- 2026-05-20_ab-cv-toggle-19samples/          # CV 开关 A/B 测试
+-- 2026-05-20_fewshot-smoke-3samples/          # Few-shot 冒烟测试
```

**命名规则**: `YYYY-MM-DD_描述-样本数samples/`

每次跑完 E2E 测试后，手动将结果移入对应目录：

```bash
# 示例：归档批量测试结果
mv backend/test_e2e_results backend/test_results/2026-05-21_e2e-fewshot-19samples/
```

### 测试样本

50 个测试样本在 `test-samples/`（gitignored），每个包含 `.webm` 视频和 `.json` 元数据。基线测试使用的 19 个样本：

```
4-col-grad, auroras, buffer-bloom, cool-s-distance, electron,
happy-diwali-2019, heart-2d, hypnotic-ripples, liquid-galss-test,
liquid-glass-ui, moon-distance-2d, plasma-waves, shiny-circle,
sparks-drifting, supah-frosted-glass, twitter-blue-check,
vortex-street, warp-speed2, water-color-blending
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

## 代码统计

| 指标 | 数值 |
|------|------|
| Python 文件 (backend/app) | 22 |
| TSX/TS 文件 (frontend/src) | 16 |
| Prompt Markdown 文件 | 7 |
| Python 代码行数 | ~3,973 |
| TSX/TS 代码行数 | ~3,796 |
| Prompt 行数 | 4,521 (decompose 624 + generate 1238 + inspect 724 + skill 1233 + constraints 69 + terminology 351 + catalog 282) |
| 总代码行数 | ~12,290 |
| Git Commits | 104 |

---

## 参考文档

- **设计方案**: `基于 AI Agent 的操作系统级自定义视效生成管线设计方案.md`
- **MVP 实施计划**: `docs/superpowers/plans/2026-04-24-vfx-agent-mvp.md`
- **System Prompts**: `backend/app/prompts/` (7 个 markdown 文件，共 4521 行)
- **iq SDF 算子**: https://iquilezles.org/articles/distfunctions2d/
- **Shadertoy 案例**: https://www.shadertoy.com/

---

*最后更新: 2026-05-20*
