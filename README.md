# VFX-Agent

基于 AI Agent 的操作系统级自定义视效生成管线系统。

## 目标

从 UX 视频/图片输入，经多 Agent 闭环迭代，自动生成 Shadertoy 格式的 GLSL 着色器代码。

专注于 2D/2.5D 平面动效（涟漪、光晕、磨砂、流光等 UI 视效），支持移动端和 Web。

## 架构

三 Agent 闭环系统：
- **Decompose Agent**：多模态 LLM，将视频/图片解构为视效语义描述
- **Generate Agent**：代码生成 LLM，根据语义描述生成 Shadertoy 格式 GLSL
- **Inspect Agent**：多模态 LLM，渲染截图 vs 设计稿对比，输出修正指令

## 技术栈

- Backend: Python 3.11+, FastAPI, LangGraph, OpenAI-compatible SDK
- Frontend: React 18, Vite, Three.js
- 浏览器自动化: Playwright
- 视频处理: FFmpeg

## 快速启动

### Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env  # 编辑配置
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## 模型配置

通过 `.env` 文件按 Agent 角色配置模型（OpenAI-compatible API 格式）：

- `DECOMPOSE_*` - Decompose Agent 配置（需要多模态能力）
- `GENERATE_*` - Generate Agent 配置（需要强 coding 能力）
- `INSPECT_*` - Inspect Agent 配置（需要多模态能力）

## 文档

详细实现计划见 `docs/superpowers/plans/2026-04-24-vfx-agent-mvp.md`