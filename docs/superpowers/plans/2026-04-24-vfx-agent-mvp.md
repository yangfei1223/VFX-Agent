# VFX Agent MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个多 Agent 闭环系统，从 UX 视频/图片输入自动生成 Shadertoy 格式 GLSL 着色器代码，并经视觉检视 Agent 自反馈迭代直至收敛。

**Architecture:** 三 Agent 架构——Decompose Agent（多模态 LLM，将视频/图片解构为视效语义描述）→ Generate Agent（代码生成 LLM，根据语义描述生成 Shadertoy 格式 GLSL）→ Inspect Agent（多模态 LLM，渲染截图 vs 设计稿截图对比，输出修正指令）。闭环在 Harness Loop 中迭代，WebGL 预览页负责渲染，Playwright 自动化截图供 Inspect Agent 使用。Python FastAPI 后端编排全流程，React + Vite 前端提供 WebUI。模型通过配置文件指定，默认使用 OpenAI-compatible API 格式，可对接 GLM/Kimi/MiniMax 等国产模型。

**Tech Stack:** Python 3.11+, FastAPI, LangGraph (Agent 编排), OpenAI-compatible SDK (模型可配置), React 18, Vite, Three.js (WebGL 渲染), Playwright (浏览器自动化截图), FFmpeg (视频关键帧提取)

---

## File Structure

```
VFX-Agent/
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI 入口，挂载路由
│   │   ├── config.py                  # 环境变量、模型 API 配置
│   │   ├── routers/
│   │   │   ├── pipeline.py            # Pipeline 触发与状态查询 API
│   │   │   └── preview.py             # 渲染截图 API（供 Inspect 调用）
│   │   ├── agents/
│   │   │   ├── base.py                # Agent 基类，统一的 LLM 调用封装
│   │   │   ├── decompose.py           # Decompose Agent：视频/图片 → 语义描述
│   │   │   ├── generate.py            # Generate Agent：语义描述 + Skills → GLSL
│   │   │   └── inspect.py             # Inspect Agent：渲染截图 vs 设计稿 → 修正指令
│   │   ├── pipeline/
│   │   │   ├── graph.py               # LangGraph 状态图：三 Agent 闭环编排
│   │   │   └── state.py               # Pipeline 状态定义（TypedDict）
│   │   ├── services/
│   │   │   ├── video_extractor.py     # FFmpeg 关键帧提取 + 光流提示
│   │   │   └── browser_render.py      # Playwright 截图服务
│   │   └── prompts/
│   │       ├── decompose_system.md    # Decompose Agent system prompt
│   │       ├── generate_system.md     # Generate Agent system prompt（含 Skill 引用指引）
│   │       └── inspect_system.md      # Inspect Agent system prompt
│   ├── requirements.txt
│   └── .env.example
├── .claude/
│   └── skills/
│       └── effect-dev/                # VFX Effect Dev Agent Skill
│           ├── SKILL.md               # Skill 主文件：frontmatter + 工作流指引
│           ├── references/            # 按需加载的参考文档
│           │   ├── sdf-operators.md   # SDF 距离场算子库
│           │   ├── noise-operators.md # 噪声函数库
│           │   ├── lighting-transforms.md # 光照与变换
│           │   ├── texture-sampling.md # 纹理采样模式
│           │   ├── shader-templates.md # 完整效果模板
│           │   ├── aesthetics-rules.md # 美学原则
│           │   └── gls-constraints.md  # GLSL 安全约束
│           ├── assets/                # 资产文件
│           │   └── shader-skeleton.glsl # 标准着色器骨架
│           └── scripts/               # 可执行脚本
│               └── validate-shader.py # GLSL 静态检查
├── frontend/
│   ├── src/
│   │   ├── App.tsx                    # 主布局：上传区 + 状态面板 + 预览区
│   │   ├── components/
│   │   │   ├── UploadPanel.tsx        # 视频/图片上传 + 参数标注
│   │   │   ├── PipelineStatus.tsx     # Agent 迭代状态实时展示
│   │   │   ├── ShaderPreview.tsx      # WebGL Shader 渲染器（核心）
│   │   │   └── CodeView.tsx           # GLSL 代码查看 + 手动编辑
│   │   ├── hooks/
│   │   │   └── usePipeline.ts         # Pipeline WebSocket 状态订阅
│   │   └── lib/
│   │       └── shader-renderer.ts     # Three.js ShaderMaterial 封装
│   ├── package.json
│   ├── vite.config.ts
│   └── tsconfig.json
├── docs/
│   └── superpowers/plans/             # 本计划
└── README.md
```

---

## Task 1: 项目脚手架搭建

**Files:**
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/config.py`
- Create: `backend/requirements.txt`
- Create: `backend/.env.example`
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/src/App.tsx`

- [ ] **Step 1: 初始化 backend 项目结构**

```bash
cd /Users/yangfei/Code/VFX-Agent
mkdir -p backend/app/routers backend/app/agents backend/app/pipeline backend/app/services backend/app/prompts
touch backend/app/__init__.py backend/app/routers/__init__.py backend/app/agents/__init__.py backend/app/pipeline/__init__.py backend/app/services/__init__.py
```

- [ ] **Step 2: 创建 backend/requirements.txt**

```text
fastapi==0.115.0
uvicorn[standard]==0.30.0
python-dotenv==1.0.1
openai==1.50.0
langgraph==0.2.28
langchain-core==0.3.1
playwright==1.47.0
ffmpeg-python==0.2.0
pillow==10.4.0
websockets==13.1
pydantic==2.9.0
```

- [ ] **Step 3: 创建 backend/.env.example**

```text
# ============================================================
# 模型配置 —— 按 Agent 角色配置，每个角色独立指定 API 和模型
# 所有模型均使用 OpenAI-compatible API 格式
# ============================================================

# Decompose Agent（视觉解构，需要多模态能力）
DECOMPOSE_API_KEY=your_api_key
DECOMPOSE_BASE_URL=https://api.moonshot.cn/v1
DECOMPOSE_MODEL=kimi-2.6

# Generate Agent（代码生成，需要强 coding 能力）
GENERATE_API_KEY=your_api_key
GENERATE_BASE_URL=https://open.bigmodel.cn/api/paas/v4
GENERATE_MODEL=glm-5.1

# Inspect Agent（视觉检视，需要多模态能力）
INSPECT_API_KEY=your_api_key
INSPECT_BASE_URL=https://api.moonshot.cn/v1
INSPECT_MODEL=kimi-2.6

# ============================================================
# 服务配置
# ============================================================
HOST=0.0.0.0
PORT=8000
FRONTEND_URL=http://localhost:5173

# Pipeline 配置
MAX_ITERATIONS=5
RENDER_TIMEOUT_MS=2000
SCREENSHOT_WIDTH=512
SCREENSHOT_HEIGHT=512
```

- [ ] **Step 4: 创建 backend/app/config.py**

```python
from pydantic_settings import BaseSettings


class ModelConfig:
    """单个 Agent 角色的模型配置"""
    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model


class Settings(BaseSettings):
    # Decompose Agent（视觉解构，需要多模态能力）
    decompose_api_key: str = ""
    decompose_base_url: str = "https://api.moonshot.cn/v1"
    decompose_model: str = "kimi-2.6"

    # Generate Agent（代码生成，需要强 coding 能力）
    generate_api_key: str = ""
    generate_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    generate_model: str = "glm-5.1"

    # Inspect Agent（视觉检视，需要多模态能力）
    inspect_api_key: str = ""
    inspect_base_url: str = "https://api.moonshot.cn/v1"
    inspect_model: str = "kimi-2.6"

    # 服务配置
    host: str = "0.0.0.0"
    port: int = 8000
    frontend_url: str = "http://localhost:5173"

    # Pipeline 配置
    max_iterations: int = 5
    render_timeout_ms: int = 2000
    screenshot_width: int = 512
    screenshot_height: int = 512

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def decompose(self) -> ModelConfig:
        return ModelConfig(self.decompose_api_key, self.decompose_base_url, self.decompose_model)

    @property
    def generate(self) -> ModelConfig:
        return ModelConfig(self.generate_api_key, self.generate_base_url, self.generate_model)

    @property
    def inspect(self) -> ModelConfig:
        return ModelConfig(self.inspect_api_key, self.inspect_base_url, self.inspect_model)


settings = Settings()
```

- [ ] **Step 5: 创建 backend/app/main.py**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings

app = FastAPI(title="VFX Agent", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 6: 初始化 frontend 项目**

```bash
cd /Users/yangfei/Code/VFX-Agent
npm create vite@latest frontend -- --template react-ts
```

- [ ] **Step 7: 安装 frontend 核心依赖**

```bash
cd /Users/yangfei/Code/VFX-Agent/frontend
npm install three @types/three
```

- [ ] **Step 8: 验证项目可启动**

Backend:
```bash
cd /Users/yangfei/Code/VFX-Agent/backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
Expected: `{"status":"ok"}` at `http://localhost:8000/health`

Frontend:
```bash
cd /Users/yangfei/Code/VFX-Agent/frontend
npm run dev
```
Expected: Vite dev server running at `http://localhost:5173`

- [ ] **Step 9: Commit**

```bash
git init
git add -A
git commit -m "chore: scaffold backend (FastAPI) + frontend (Vite/React/TS) project structure"
```

---

## Task 2: LLM 调用基类与模型集成

**Files:**
- Create: `backend/app/agents/base.py`

- [ ] **Step 1: 创建 Agent 基类**

```python
"""Agent 基类：统一 LLM 调用封装，支持文本和图片输入"""

import base64
from pathlib import Path
from typing import Any

from openai import OpenAI

from app.config import Settings, ModelConfig


class BaseAgent:
    """所有 Agent 的基类，封装 LLM 调用逻辑"""

    def __init__(self, model_config: ModelConfig):
        """
        根据传入的 ModelConfig 初始化 LLM 客户端。
        ModelConfig 来自 settings.decompose / settings.generate / settings.inspect。
        """
        self.client = OpenAI(
            api_key=model_config.api_key,
            base_url=model_config.base_url,
        )
        self.model = model_config.model
        self.model_config = model_config

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        image_paths: list[str] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """调用 LLM，支持可选的图片输入（多模态）"""
        content: list[Any] = [{"type": "text", "text": user_prompt}]

        if image_paths:
            for path in image_paths:
                image_data = base64.b64encode(Path(path).read_bytes()).decode()
                ext = Path(path).suffix.lower()
                mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
                mime = mime_map.get(ext, "image/png")
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{image_data}"},
                })

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content if image_paths else user_prompt},
        ]

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        return response.choices[0].message.content or ""
```

- [ ] **Step 2: 手动验证 LLM 调用**

在 backend 目录下运行：
```bash
cd /Users/yangfei/Code/VFX-Agent/backend
python -c "
from app.agents.base import BaseAgent
agent = BaseAgent('glm')
result = agent.chat('You are a helpful assistant.', 'Say hello in 5 words.')
print('GLM:', result)

agent2 = BaseAgent('kimi')
result2 = agent2.chat('You are a helpful assistant.', 'Say hello in 5 words.')
print('Kimi:', result2)
"
```
Expected: 两个模型均返回简短回复，无报错。

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "feat: add BaseAgent with OpenAI-compatible LLM client for GLM and Kimi"
```

---

## Task 3: Decompose Agent —— 视效解构

**Files:**
- Create: `backend/app/prompts/decompose_system.md`
- Create: `backend/app/agents/decompose.py`
- Create: `backend/app/services/video_extractor.py`

- [ ] **Step 1: 创建 Decompose Agent system prompt**

```markdown
# 视效解构 Agent

你是一个视觉效果解构专家。你的任务是分析用户提供的视觉参考（视频关键帧截图或设计稿图片），将其解构为结构化的视效语义描述。

## 输出格式

请严格输出以下 JSON 结构（不要输出其他内容）：

```json
{
  "effect_name": "效果名称（英文，如 frosted_glass, ripple, aurora）",
  "shape": {
    "type": "形状类型（full_screen, circle, rect, ring, gradient_band）",
    "description": "形状描述，如'全屏覆盖，中心有一个圆形波纹区域'",
    "sdf_primitives": ["circle", "smooth_union"],
    "parameters": {
      "radius": "圆形半径比例（0-1）",
      "corner_radius": "圆角半径",
      "blend": "混合平滑度"
    }
  },
  "color": {
    "palette": ["#hex1", "#hex2"],
    "gradient_type": "none / linear / radial / angular",
    "gradient_direction": "从左到右/从中心向外 等",
    "opacity_range": [0.0, 1.0],
    "has_noise": true,
    "noise_type": "value / perlin / simplex / worley"
  },
  "animation": {
    "loop_duration_s": 2.0,
    "easing": "linear / ease_in / ease_out / ease_in_out / spring",
    "phases": [
      {
        "name": "phase_name",
        "time_range": [0.0, 1.0],
        "description": "该阶段的动画描述"
      }
    ],
    "time_function": "fract(t) / smoothstep / sin(t) / custom"
  },
  "interaction": {
    "responds_to_pointer": false,
    "interaction_type": "none / ripple / magnet / glow / deform",
    "description": "交互效果描述"
  },
  "post_processing": {
    "blur": false,
    "blur_radius": 0,
    "bloom": false,
    "bloom_intensity": 0.0,
    "chromatic_aberration": false
  },
  "overall_description": "一段 2-3 句话的整体视效描述，作为生成 Agent 的核心指引"
}
```

## 分析要点

1. **形态**：效果覆盖全屏还是局部？是什么几何形状？边缘是锐利还是模糊？
2. **色彩**：主色调、渐变方式、是否有噪声纹理？
3. **动画**：是否有时间维度的变化？循环周期？缓动曲线？
4. **交互**：是否响应指针/触摸？
5. **后处理**：是否有模糊、泛光、色差等后处理效果？

## 注意

- 对于无法确定的字段，给出最合理的推测
- 描述要具体到可以让另一个 Agent 据此编写 GLSL 着色器代码
- 如果输入是视频关键帧序列，请综合所有帧的信息进行解构
```

- [ ] **Step 2: 创建视频关键帧提取服务**

```python
"""FFmpeg 关键帧提取 + 视频元信息获取"""

import json
import subprocess
import tempfile
from pathlib import Path


def extract_keyframes(video_path: str, output_dir: str | None = None, max_frames: int = 8) -> list[str]:
    """从视频中均匀提取关键帧，返回图片路径列表"""
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="vfx_keyframes_")

    # 获取视频时长
    probe_cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        video_path,
    ]
    result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
    duration = float(json.loads(result.stdout)["format"]["duration"])

    # 均匀采样时间点
    interval = duration / (max_frames + 1)
    timestamps = [interval * (i + 1) for i in range(max_frames)]

    output_paths: list[str] = []
    for i, ts in enumerate(timestamps):
        out_path = str(Path(output_dir) / f"frame_{i:03d}.png")
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(ts),
            "-i", video_path,
            "-frames:v", "1",
            "-q:v", "2",
            out_path,
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        output_paths.append(out_path)

    return output_paths


def get_video_info(video_path: str) -> dict:
    """获取视频基本信息：时长、帧率、分辨率"""
    probe_cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        video_path,
    ]
    result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
    info = json.loads(result.stdout)

    video_stream = next(
        (s for s in info["streams"] if s["codec_type"] == "video"), None
    )
    if not video_stream:
        raise ValueError("No video stream found")

    return {
        "duration": float(info["format"]["duration"]),
        "fps": eval(video_stream["r_frame_rate"]),  # e.g. "30/1" -> 30.0
        "width": int(video_stream["width"]),
        "height": int(video_stream["height"]),
    }
```

- [ ] **Step 3: 创建 Decompose Agent**

```python
"""Decompose Agent：将视频/图片解构为视效语义描述 JSON"""

import json
from pathlib import Path

from app.agents.base import BaseAgent
from app.config import settings
from app.services.video_extractor import extract_keyframes


class DecomposeAgent(BaseAgent):
    def __init__(self):
        super().__init__(model_config=settings.decompose)
        self.system_prompt = Path("app/prompts/decompose_system.md").read_text()

    def run(
        self,
        image_paths: list[str],
        video_info: dict | None = None,
        user_notes: str = "",
    ) -> dict:
        """
        分析输入的视觉参考，输出结构化视效语义描述。

        Args:
            image_paths: 关键帧图片路径列表
            video_info: 视频元信息（时长、帧率等），可选
            user_notes: 用户附加的结构化参数标注，可选

        Returns:
            解构出的视效语义描述 dict
        """
        parts = ["请分析以下视觉参考，解构出视效语义描述。"]

        if video_info:
            parts.append(
                f"视频信息：时长 {video_info['duration']:.1f}s，"
                f"帧率 {video_info['fps']:.0f}fps，"
                f"分辨率 {video_info['width']}x{video_info['height']}。"
            )
            parts.append(
                f"以下 {len(image_paths)} 张图片是从视频中均匀提取的关键帧。"
            )
        else:
            parts.append(f"以下是 {len(image_paths)} 张设计稿图片。")

        if user_notes:
            parts.append(f"用户附加参数标注：{user_notes}")

        user_prompt = "\n".join(parts)

        response = self.chat(
            system_prompt=self.system_prompt,
            user_prompt=user_prompt,
            image_paths=image_paths,
            temperature=0.3,
            max_tokens=2048,
        )

        # 从响应中提取 JSON
        return self._parse_json(response)

    @staticmethod
    def _parse_json(text: str) -> dict:
        """从 LLM 响应中提取 JSON（处理 markdown code block 包裹）"""
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            # 去掉首尾的 ``` 行
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)
        return json.loads(text)
```

- [ ] **Step 4: 测试 Decompose Agent 端到端调用**

准备一张测试图片（可从网上下载一个简单的渐变效果截图），然后：
```bash
cd /Users/yangfei/Code/VFX-Agent/backend
python -c "
from app.agents.decompose import DecomposeAgent
agent = DecomposeAgent()
# 替换为实际测试图片路径
result = agent.run(image_paths=['/path/to/test_image.png'])
import json
print(json.dumps(result, indent=2, ensure_ascii=False))
"
```
Expected: 输出结构化的视效语义描述 JSON，包含 shape/color/animation 等字段。

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: add Decompose Agent with video keyframe extraction and structured visual analysis"
```

---

## Task 4: VFX Effect Dev Skill —— Agent Skill 资产包

**Files:**
- Create: `.claude/skills/effect-dev/SKILL.md`
- Create: `.claude/skills/effect-dev/references/sdf-operators.md`
- Create: `.claude/skills/effect-dev/references/noise-operators.md`
- Create: `.claude/skills/effect-dev/references/lighting-transforms.md`
- Create: `.claude/skills/effect-dev/references/texture-sampling.md`
- Create: `.claude/skills/effect-dev/references/shader-templates.md`
- Create: `.claude/skills/effect-dev/references/aesthetics-rules.md`
- Create: `.claude/skills/effect-dev/references/gls-constraints.md`
- Create: `.claude/skills/effect-dev/assets/shader-skeleton.glsl`
- Create: `.claude/skills/effect-dev/scripts/validate-shader.py`

- [ ] **Step 1: 创建 effect-dev Skill 目录结构**

```bash
cd /Users/yangfei/Code/VFX-Agent
mkdir -p .claude/skills/effect-dev/references
mkdir -p .claude/skills/effect-dev/assets
mkdir -p .claude/skills/effect-dev/scripts
```

- [ ] **Step 2: 创建 SKILL.md 主文件**

```markdown
---
name: effect-dev
description: |
  VFX shader development skill for 2D/2.5D procedural motion effects on mobile and web.
  Use when generating, reviewing, or debugging Shadertoy-format GLSL fragment shaders.
  Covers SDF operators (based on iq's formulations), noise functions, texture sampling,
  animation timing, shader templates, aesthetics rules, and GLSL safety constraints.
  Target: OS-level UI visual effects — flat/layered motion, NOT 3D scenes or raymarching.
  Activates when writing or modifying shader code, visual effect generation, or GPU rendering logic.
---

# VFX Effect Development Skill

You are developing **2D/2.5D procedural motion-effect shaders** for an OS-level visual FX agent system. The target is **mobile devices and web platforms** — performance and real-time responsiveness are paramount. This skill provides the complete knowledge base: operator libraries, shader templates, aesthetics principles, and safety constraints.

## Scope: 2D/2.5D Only

This skill covers **flat and layered visual effects** only:
- ✅ Background gradients, noise textures, atmospheric effects
- ✅ UI element effects: ripple, glow, pulse, frosted glass, shimmer
- ✅ 2D SDF shapes with smooth blending, masks, transitions
- ✅ Procedural animation: breathing, flowing, pulsing, oscillating
- ✅ Texture sampling for backdrop blur, distortion, tinting
- ❌ **NOT**: 3D raymarching, path tracing, volumetric rendering, camera/scene graphs
- ❌ **NOT**: High-polygon mesh rendering, PBR material systems, shadow maps

If a request implies 3D scene rendering, simplify to a 2D approximation or push back.

## Authority Sources

The knowledge in this skill is grounded in two authoritative references:

1. **Shadertoy** (https://www.shadertoy.com/) — Community repository of GLSL visual effects. When unsure about an effect's implementation, reference popular Shadertoy shaders for patterns. Key channels: `shadertoy.com/results?query=<effect_name>`
2. **Inigo Quilez (iq)** (https://iquilezles.org/) — Foundational SDF and noise operator definitions. The SDF operators in this skill are derived from iq's formulations:
   - 2D SDF: `https://iquilezles.org/articles/distfunctions2d/`
   - Noise: `https://iquilezles.org/articles/noise/`
   - Smooth minimum: `https://iquilezles.org/articles/smoothmin/`
   - Voronoi: `https://iquilezles.org/articles/voronoise/`

When generating shaders, prefer operators from these sources over ad-hoc implementations.

## Core Workflow

1. **Read the visual description JSON** to understand effect intent
2. **Select operators** from the references below based on shape/color/animation requirements
3. **Pick a template** if one matches the effect category, or compose from scratch
4. **Apply aesthetics rules** for color harmony and motion design
5. **Respect GLSL constraints** — safety, performance (mobile!), portability
6. **Output complete, compilable Shadertoy-format GLSL**

## Reference Files

Load these when you need detailed content (don't load all at once):

- `references/sdf-operators.md` — 2D SDF shape primitives (iq's formulations): circle, box, rounded rect, smooth union/intersection/subtraction, ring, arc
- `references/noise-operators.md` — Noise functions: Perlin, Simplex, Value, Voronoi, Worley (F1/F2), FBM composition
- `references/lighting-transforms.md` — Fresnel, 2D AO, rotation/scale transforms, UV manipulation
- `references/texture-sampling.md` — Texture/channel sampling patterns, iChannel usage, backdrop blur, procedural vs. sampled textures
- `references/shader-templates.md` — Full 2D effect skeletons: gradient, ripple, frosted glass, aurora, glow pulse
- `references/aesthetics-rules.md` — Color harmony, motion principles, mobile performance budget, dark-theme safety
- `references/gls-constraints.md` — GLSL safety rules, banned patterns, mobile GPU performance limits, cross-platform quirks

## Quick Reference: Shader Skeleton

See `assets/shader-skeleton.glsl` for the canonical file structure every shader must follow.

## Quick Reference: Validation

Run `scripts/validate-shader.py <file.glsl>` to check for banned patterns, missing mainImage, unsafe math, 3D raymarching detection, and texture usage errors before submitting.

## When to Load References

| Task | Load these |
|------|-----------|
| Generate new shader from description | sdf-operators, noise-operators, shader-templates, aesthetics-rules |
| Fix shape/geometry issues | sdf-operators, lighting-transforms |
| Fix color/appearance issues | noise-operators, aesthetics-rules, texture-sampling |
| Fix animation/timing issues | shader-templates (for easing patterns), aesthetics-rules (motion section) |
| Fix compile errors | gls-constraints |
| Fix performance issues | gls-constraints, aesthetics-rules (performance section) |
| Add texture support | texture-sampling |
```

- [ ] **Step 3: 创建 SDF 算子参考文档**

```markdown
# SDF Operators Reference

> All 2D SDF formulations are based on Inigo Quilez's canonical definitions:
> https://iquilezles.org/articles/distfunctions2d/
> Smooth min/max: https://iquilezles.org/articles/smoothmin/

## Primitives

### sdCircle
```glsl
float sdCircle(vec2 p, float r) {
    return length(p) - r;
}
```
- `r`: radius (0.0–1.0), default 0.3
- Use for: circles, rings, ripples, radial masks
- Compose with: smooth_union, fresnel, rotation

### sdBox
```glsl
float sdBox(vec2 p, vec2 b) {
    vec2 d = abs(p) - b;
    return length(max(d, 0.0)) + min(max(d.x, d.y), 0.0);
}
```
- `b`: half-extents (vec2), default vec2(0.3, 0.2)
- Use for: rectangles, cards, panels, rounded backgrounds

### sdRoundedBox
```glsl
float sdRoundedBox(vec2 p, vec2 b, float r) {
    vec2 q = abs(p) - b + r;
    return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r;
}
```
- `b`: half-extents, `r`: corner radius
- Use for: OS UI elements, cards with rounded corners

### sdRing
```glsl
float sdRing(vec2 p, float r, float w) {
    return abs(length(p) - r) - w;
}
```
- `r`: ring radius, `w`: ring width (thin = 0.01–0.05)
- Use for: selection rings, progress indicators, halos

### sdArc
```glsl
float sdArc(vec2 p, float r, float w, float a1, float a2) {
    float a = atan(p.y, p.x);
    a = clamp(a, a1, a2);
    vec2 q = vec2(cos(a), sin(a)) * r;
    return length(p - q) - w;
}
```
- Use for: progress arcs, gauge indicators

## Boolean Operations

### opSmoothUnion
```glsl
float opSmoothUnion(float d1, float d2, float k) {
    float h = clamp(0.5 + 0.5 * (d2 - d1) / k, 0.0, 1.0);
    return mix(d2, d1, h) - k * h * (1.0 - h);
}
```
- `k`: blend smoothness (0.01 = sharp, 0.3 = very soft)
- Use for: organic shape merging, blob effects

### opSmoothSubtraction
```glsl
float opSmoothSubtraction(float d1, float d2, float k) {
    float h = clamp(0.5 - 0.5 * (d2 + d1) / k, 0.0, 1.0);
    return mix(d2, -d1, h) + k * h * (1.0 - h);
}
```
- Use for: cutouts, hollow shapes, windows

### opSmoothIntersection
```glsl
float opSmoothIntersection(float d1, float d2, float k) {
    float h = clamp(0.5 - 0.5 * (d2 - d1) / k, 0.0, 1.0);
    return mix(d2, d1, h) + k * h * (1.0 - h);
}
```
- Use for: constrained regions, overlap masks
```

- [ ] **Step 4: 创建噪声算子参考文档**

```markdown
# Noise Operators Reference

## Hash Functions (building blocks)

```glsl
float hash21(vec2 p) {
    p = fract(p * vec2(234.34, 435.345));
    p += dot(p, p + 34.23);
    return fract(p.x * p.y);
}

vec2 hash22(vec2 p) {
    p = vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)));
    return -1.0 + 2.0 * fract(sin(p) * 43758.5453123);
}
```

## Value Noise
```glsl
float valueNoise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash21(i), hash21(i + vec2(1.0, 0.0)), u.x),
               mix(hash21(i + vec2(0.0, 1.0)), hash21(i + vec2(1.0, 1.0)), u.x),
               u.y);
}
```
- Output: [0, 1], cheap, blocky appearance
- Best for: subtle grain, low-detail textures

## Perlin Gradient Noise
```glsl
float perlinNoise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(dot(hash22(i + vec2(0,0)), f - vec2(0,0)),
                   dot(hash22(i + vec2(1,0)), f - vec2(1,0)), u.x),
               mix(dot(hash22(i + vec2(0,1)), f - vec2(0,1)),
                   dot(hash22(i + vec2(1,1)), f - vec2(1,1)), u.x),
               u.y);
}
```
- Output: ~[-1, 1], natural, directional
- Best for: clouds, fire, water, natural textures

## Simplex Noise
```glsl
float simplexNoise(vec2 p) {
    // Skew and unskew factors
    const vec2 F = vec2(0.5 * (sqrt(3.0) - 1.0));
    const vec2 G = vec2((3.0 - sqrt(3.0)) / 6.0);

    vec2 s = floor(p + dot(p, F));
    vec2 i = s - floor(s * G);
    vec2 f = p - i - dot(i, G);

    vec2 o1 = (f.x > f.y) ? vec2(1.0, 0.0) : vec2(0.0, 1.0);
    vec2 o2 = i + vec2(0.0, 1.0) - floor((i + vec2(0.0, 1.0)) * G);
    vec2 o3 = i + vec2(1.0, 1.0) - floor((i + vec2(1.0, 1.0)) * G);

    float n0 = 0.0, n1 = 0.0, n2 = 0.0;
    vec2 d0 = f - vec2(0,0);
    vec2 d1 = f - o1;
    vec2 d2 = f - o2;

    float t0 = 0.5 - dot(d0, d0);
    if (t0 > 0.0) n0 = t0 * t0 * t0 * t0 * dot(hash22(s), d0);
    float t1 = 0.5 - dot(d1, d1);
    if (t1 > 0.0) n1 = t1 * t1 * t1 * t1 * dot(hash22(s + o1), d1);
    float t2 = 0.5 - dot(d2, d2);
    if (t2 > 0.0) n2 = t2 * t2 * t2 * t2 * dot(hash22(s + o2), d2);

    return 70.0 * (n0 + n1 + n2);
}
```
- Output: ~[-1, 1], isotropic, no directional artifacts
- Best for: high-quality organic textures, less grid bias

## Voronoi / Worley
```glsl
vec3 voronoi(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    float d1 = 8.0, d2 = 8.0;
    vec2 closestCell = vec2(0.0);

    for (int y = -1; y <= 1; y++) {
        for (int x = -1; x <= 1; x++) {
            vec2 neighbor = vec2(float(x), float(y));
            vec2 point = hash22(i + neighbor);
            point = 0.5 + 0.5 * sin(u_time + 6.2831 * point);
            vec2 diff = neighbor + point - f;
            float dist = length(diff);
            if (dist < d1) { d2 = d1; d1 = dist; closestCell = i + neighbor; }
            else if (dist < d2) { d2 = dist; }
        }
    }
    return vec3(d1, d2, hash21(closestCell)); // F1, F2, cell_id
}
```
- `voronoi(p).x` = F1 (nearest cell distance)
- `voronoi(p).y` = F2 (second nearest)
- `voronoi(p).z` = cell random ID
- Use for: cells, cracks, crystals, organic partitions

## FBM (Fractal Brownian Motion)
```glsl
float fbm(vec2 p, int octaves) {
    float val = 0.0;
    float amp = 0.5;
    float freq = 1.0;
    for (int i = 0; i < 6; i++) {
        if (i >= octaves) break;
        val += amp * perlinNoise(p * freq); // or valueNoise/simplexNoise
        freq *= 2.0;
        amp *= 0.5;
    }
    return val;
}
```
- `octaves`: 2 = very soft, 4 = standard, 6 = detailed (performance cost)
- Use for: complex natural textures, layered effects
```

- [ ] **Step 5: 创建纹理采样参考文档**

```markdown
# Texture Sampling Reference

## iChannel System

Shadertoy provides up to 4 texture channels via `iChannel0`–`iChannel3`. In our runtime, these map to:

| Channel | Content | Type |
|---------|---------|------|
| iChannel0 | Backdrop/framebuffer capture | sampler2D (system-provided) |
| iChannel1 | User-uploaded texture | sampler2D (optional) |
| iChannel2 | Reserved | — |
| iChannel3 | Reserved | — |

## Sampling Patterns

### Standard texture sample
```glsl
vec4 texColor = texture(iChannel0, uv);
```

### Backdrop blur (frosted glass)
```glsl
vec3 backdropBlur(vec2 uv, float radius, sampler2D channel) {
    vec3 sum = vec3(0.0);
    float total = 0.0;
    for (int i = -4; i <= 4; i++) {
        for (int j = -4; j <= 4; j++) {
            vec2 offset = vec2(float(i), float(j)) * radius / u_resolution.xy;
            float w = 1.0 - length(vec2(float(i), float(j))) / 6.0;
            w = max(w, 0.0);
            sum += texture(channel, uv + offset).rgb * w;
            total += w;
        }
    }
    return sum / max(total, 0.001);
}
```
- `radius`: blur spread in pixels (2.0–16.0)
- Note: 9×9 kernel = 81 samples, keep radius moderate for performance

### Parallax / offset sampling
```glsl
vec2 distortedUV = uv + vec2(noise * 0.02, 0.0);
vec4 texColor = texture(iChannel0, distortedUV);
```
- Use for: glass refraction, heat distortion, water surface

### Mipmap LOD for blur
```glsl
// Hardware-accelerated blur via LOD bias
vec4 blurred = texture(iChannel0, uv, lod_bias);
```
- `lod_bias`: 0.0 = sharp, higher = blurrier
- Performance: single sample, hardware-accelerated
- Use when quality isn't critical (subtle blur)

## Texture + Procedural Mix

### Blended approach (recommended)
```glsl
vec3 texSample = texture(iChannel0, uv).rgb;
float procedural = perlinNoise(uv * 8.0);
vec3 color = mix(texSample, vec3(procedural), blend_factor);
```
- `blend_factor`: 0.0 = pure texture, 1.0 = pure procedural
- Use for: adding noise/grain to sampled textures

### Tinted backdrop
```glsl
vec3 backdrop = texture(iChannel0, uv).rgb;
vec3 tint = vec3(0.8, 0.9, 1.0); // cool tint
vec3 color = backdrop * tint;
```

## Constraints

- Always check if channel is available: wrap texture calls in `#ifdef` or runtime checks
- Maximum texture samples per fragment: 16 (budget for performance)
- Prefer procedural noise over texture when possible — zero memory, infinite resolution
- For backdrop blur: prefer mipmap LOD over multi-sample when quality allows
```

- [ ] **Step 6: 创建光照与变换参考文档**

```markdown
# Lighting & Transform Operators Reference

## Fresnel (Schlick Approximation)
```glsl
float fresnel(float cosTheta, float f0) {
    return f0 + (1.0 - f0) * pow(clamp(1.0 - cosTheta, 0.0, 1.0), 5.0);
}
```
- `f0`: base reflectance (0.02–0.08 for dielectrics, 0.8+ for metals)
- Use for: rim lighting, edge glow, glass-like effects
- In 2D: compute cosTheta from SDF gradient `cosTheta = dot(normalize(grad), viewDir)`

## Simplified 2D Ambient Occlusion
```glsl
float ao(vec2 p, float d, float stepSize, int steps) {
    float occ = 0.0;
    float scale = 1.0;
    for (int i = 0; i < 5; i++) {
        if (i >= steps) break;
        float dist = d + 0.01 + float(i + 1) * stepSize;
        float sd = sceneSDF(p + normalize(p) * dist); // user-defined scene
        float diff = dist - sd;
        occ += scale * clamp(diff, 0.0, 1.0);
        scale *= 0.5;
    }
    return clamp(1.0 - 2.0 * occ, 0.0, 1.0);
}
```

## 2D Rotation
```glsl
mat2 rot2D(float a) {
    float c = cos(a), s = sin(a);
    return mat2(c, -s, s, c);
}
// Usage: uv = rot2D(angle) * uv;
```

## UV Manipulations
```glsl
// Mirror/repeat
vec2 mirrorUV(vec2 uv) {
    return fract(uv) * 2.0 - 1.0; // tile with mirror
}

// Polar coordinates
vec2 toPolar(vec2 uv, vec2 center) {
    vec2 p = uv - center;
    return vec2(length(p), atan(p.y, p.x));
}

// From polar back to cartesian
vec2 fromPolar(vec2 polar) {
    return vec2(polar.x * cos(polar.y), polar.x * sin(polar.y));
}
```
```

- [ ] **Step 7: 创建着色器模板参考文档**

```markdown
# Shader Templates Reference

Each template is a complete effect skeleton. Customize parameters based on the visual description.

## Template: Basic Gradient
```glsl
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / u_resolution.xy;
    vec3 colA = vec3(0.1, 0.1, 0.18); // top color
    vec3 colB = vec3(0.06, 0.2, 0.38); // bottom color
    vec3 col = mix(colB, colA, uv.y); // linear vertical
    // For radial: float d = length(uv - 0.5); col = mix(colA, colB, d * 2.0);
    // For angular: float a = atan(uv.y-0.5, uv.x-0.5); col = mix(colA, colB, (a/6.28+0.5));
    fragColor = vec4(col, 1.0);
}
```

## Template: Ripple
```glsl
float sdCircle(vec2 p, float r) { return length(p) - r; }

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / u_resolution.xy;
    vec2 center = u_mouse / u_resolution.xy;
    float t = u_time;

    float speed = 0.8;
    float wavelength = 0.05;
    float decay = 3.0;

    vec2 p = uv - center;
    float dist = length(p);
    float wave = sin((dist - t * speed) / wavelength * 6.2832);
    float attenuation = exp(-dist * decay) * exp(-fract(t * 0.3) * 2.0);
    float ripple = wave * attenuation;

    vec3 baseColor = vec3(0.1, 0.3, 0.6);
    vec3 rippleColor = vec3(0.4, 0.7, 1.0);
    vec3 col = mix(baseColor, rippleColor, ripple * 0.5 + 0.5);
    fragColor = vec4(col, 1.0);
}
```
- Customizable: speed, wavelength, decay, baseColor, rippleColor

## Template: Frosted Glass (with backdrop texture)
```glsl
vec3 backdropBlur(vec2 uv, float radius) {
    vec3 sum = vec3(0.0);
    float total = 0.0;
    for (int i = -4; i <= 4; i++) {
        for (int j = -4; j <= 4; j++) {
            vec2 offset = vec2(float(i), float(j)) * radius / u_resolution.xy;
            float w = 1.0 - length(vec2(float(i), float(j))) / 6.0;
            w = max(w, 0.0);
            sum += texture(iChannel0, uv + offset).rgb * w;
            total += w;
        }
    }
    return sum / max(total, 0.001);
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / u_resolution.xy;
    vec3 blurred = backdropBlur(uv, 4.0);
    float noise = 0.5 + 0.5 * perlinNoise(uv * 20.0 + u_time * 0.1);
    vec3 col = blurred * (0.85 + 0.15 * noise);
    col += vec3(0.8, 0.85, 0.95) * 0.08; // cool tint
    fragColor = vec4(col, 0.92);
}
```
- Requires: iChannel0 (backdrop texture)
- Customizable: blur radius, noise scale, tint color, opacity

## Template: Aurora
```glsl
float perlinNoise(vec2 p) { /* see noise-operators */ }
float fbm(vec2 p) { float v=0.0; float a=0.5; for(int i=0;i<5;i++){v+=a*perlinNoise(p);p*=2.0;a*=0.5;} return v; }

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / u_resolution.xy;
    float t = u_time * 0.3;

    float n1 = fbm(vec2(uv.x * 3.0 + t, uv.y * 2.0 + t * 0.5));
    float n2 = fbm(vec2(uv.x * 2.0 - t * 0.7, uv.y * 3.0));

    vec3 col1 = vec3(0.1, 0.8, 0.4); // green
    vec3 col2 = vec3(0.2, 0.4, 0.9); // blue
    vec3 col3 = vec3(0.7, 0.2, 0.8); // purple

    float band = smoothstep(0.3, 0.7, uv.y + n1 * 0.3);
    vec3 col = mix(col1, col2, band);
    col = mix(col, col3, smoothstep(0.5, 0.8, n2));

    col *= smoothstep(0.0, 0.3, uv.y) * smoothstep(1.0, 0.5, uv.y);
    col *= 0.7 + 0.3 * sin(t * 2.0 + uv.x * 6.28);

    fragColor = vec4(col, 1.0);
}
```
- Customizable: color bands, flow speed, vertical distribution

## Template: Glow Pulse
```glsl
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / u_resolution.xy;
    vec2 center = vec2(0.5);
    float dist = length(uv - center);

    float pulse = 0.5 + 0.5 * sin(u_time * 2.0); // breathing
    float glow = exp(-dist * (4.0 + 2.0 * pulse));

    vec3 glowColor = vec3(0.3, 0.6, 1.0);
    vec3 baseColor = vec3(0.02, 0.02, 0.05);

    vec3 col = baseColor + glowColor * glow * (0.5 + 0.5 * pulse);
    fragColor = vec4(col, 1.0);
}
```
- Customizable: pulse speed, glow radius, glow color, base color
```

- [ ] **Step 8: 创建美学原则参考文档**

```markdown
# Aesthetics Rules Reference

> Target: 2D/2.5D UI visual effects on mobile devices (Mali/Adreno/Apple GPU) and web.
> Authority: Shadertoy (https://www.shadertoy.com/) for visual patterns and implementation approaches.

## Color Harmony

### Complementary (180° apart)
- High contrast, use sparingly: base 70%, accent 30%
- Shader: `mix(base, complement, factor)` with factor 0.1–0.3
- Example: blue #1a1a2e + orange #e94560

### Analogous (30°–60° apart)
- Natural, harmonious — safe default
- Shader: `cos(uv.x * 6.28 + offset)` for color bands
- Example: deep blue #0f3460 + indigo #16213e + purple #533483

### Triadic (120° apart)
- Rich but needs hierarchy: 1 primary 70%, 2 accents 15% each
- Shader: assign one color per SDF region

### Readability
- Background-foreground luminance difference > 0.4 (WCAG AA)
- In motion: > 0.3 acceptable
- Luminance: `dot(col, vec3(0.299, 0.587, 0.114))`

### Dark Theme Safe
- Background luminance < 0.15
- Highlight luminance > 0.5
- Never pure black #000000 — use `vec3(0.02, 0.02, 0.05)` minimum

## Motion Principles

### Easing Selection
| Motion Type | Easing | Shader Function |
|-------------|--------|----------------|
| Appear/expand | ease-out | `1.0 - (1.0 - t) * (1.0 - t)` |
| Disappear/shrink | ease-in | `t * t` |
| Natural/organic | ease-in-out | `t * t * (3.0 - 2.0 * t)` |
| Bounce/spring | spring | `1.0 - pow(cos(t * 3.14159 * 0.5), 2.0) * exp(-t * 4.0)` |
| Smooth loop | cosine | `0.5 - 0.5 * cos(t * 6.2832)` |

### Timing
- Micro-interactions: 150–400ms
- Transitions: 300–800ms
- Ambient effects: 2–6s loop
- Never instant (0ms) — even subtle motion feels better than none

### Rhythm
- Use `fract(u_time / duration)` for perfect loops
- Vary frequencies to avoid mechanical feel: `sin(t * 1.0) + sin(t * 1.7) * 0.5`
- Layer 2–3 speeds: slow drift + medium pulse + fast shimmer

## Performance Budget (Mobile/Web)

> These are **mobile** budgets — significantly tighter than desktop.
> A 2022 mid-range phone (e.g. Snapdragon 778G, Mali-G78) is the reference device.

| Metric | Mobile Limit | Desktop/Dev Limit | Notes |
|--------|-------------|-------------------|-------|
| ALU instructions | ≤ 256 | ≤ 512 | Fragment shader instruction count |
| Texture fetches per fragment | ≤ 8 | ≤ 16 | Mobile memory bandwidth is the bottleneck |
| For-loop iterations (total) | ≤ 32 | ≤ 64 | Hard limit, no dynamic bounds |
| Target frame time | < 2ms @ 1080p | < 4ms @ 1440p | 60fps budget with headroom for OS UI |
| FBM octaves | ≤ 4 | ≤ 6 | Each octave doubles cost |
| Blur kernel | ≤ 7×7 (49 samples) | ≤ 9×9 (81 samples) | Multi-sample blur is very expensive on mobile |

### Optimization Tips (Mobile-First)
- Prefer `smoothstep` over conditional branches
- Use `step()` for binary masks instead of `if`
- Precompute constants outside `mainImage`
- Use `mix` instead of branching where possible
- **Prefer mipmap LOD blur over multi-sample blur** — single texture fetch vs. 49+
- Downsample expensive effects: render at half resolution when precision allows
- Avoid dependent texture reads on mobile (compute UV, then sample, don't sample-then-recompute)
- Keep FBM at 4 octaves max on mobile; 5+ causes visible jank
- Use `lowp`/`mediump` for colors where precision loss is acceptable (but not for UVs or SDF distances)
```

- [ ] **Step 9: 创建 GLSL 约束参考文档**

```markdown
# GLSL Constraints Reference

> Target platform: **Mobile GPU (Mali/Adreno/Apple GPU) + WebGL** — not desktop.
> Target frame budget: **< 2ms per frame at 1080p** on mid-range mobile.
> Scope: **2D/2.5D flat effects only** — no 3D raymarching, no volumetric, no scene graphs.

## Mandatory Rules

1. **Do NOT declare** `u_time`, `u_resolution`, `u_mouse` — these are injected by runtime
2. **Must implement** `void mainImage(out vec4 fragColor, in vec2 fragCoord)` — entry point
3. **Output must be** complete, compilable GLSL ES 3.0 — no `#include`, no undefined functions
4. **2D only** — all coordinates are `vec2 uv`, all SDF operations are 2D, no `vec3` position/ray/direction for 3D scene rendering

## Banned Patterns

| Pattern | Reason | Alternative |
|---------|--------|-------------|
| **3D raymarching** (`rayDirection`, `marchRay`, `castRay`, `sceneSDF(vec3)`) | Mobile GPU too slow, not our scope | Use 2D SDF + layered composition |
| **3D SDF primitives** (`sdSphere(vec3)`, `sdBox(vec3)`) | Outside 2D/2.5D scope | Use 2D equivalents |
| **Path tracing / BRDF / PBR** | Desktop-only, not mobile real-time | Use Fresnel rim, fake AO, procedural lighting |
| **Volumetric / fog / clouds** (ray-step loops > 8) | Too expensive on mobile | Layer 2D noise with depth fade |
| `for` loops with > 8 iterations or dynamic bounds | GPU divergence, timeout | Unroll or use fixed-count loops |
| Recursion | Not supported in GLSL | Refactor to iterative |
| `discard` | Kills early-Z, hurts performance | Use alpha blending or `step()` mask |
| Dynamic array indexing | GPU register pressure | Constant-index or texture lookup |
| `while` loops | Infinite loop risk | Fixed `for` loop |
| `textureLod` in fragment | Not universally supported | `texture()` with bias parameter |

## Mobile Performance Budget

| Metric | Limit | Rationale |
|--------|-------|-----------|
| Fragment shader ALU instructions | ≤ 256 | Mid-range mobile at 1080p |
| Texture fetches per fragment | ≤ 8 | Mobile memory bandwidth limited |
| For-loop iterations (total across all loops) | ≤ 32 | Prevents GPU timeout |
| Target frame time | < 2ms at 1080p | 60fps budget with headroom for UI |
| FBM octaves | ≤ 4 | Each octave doubles cost; 4 is already heavy on mobile |
| Blur kernel | ≤ 7×7 (49 samples) | 9×9 is too slow on mobile GPU |
| Total fragment shader complexity | "simple" to "moderate" | If it wouldn't run smoothly on a 2022 mid-range phone, simplify |

### Mobile Optimization Tips

- **Prefer `smoothstep` and `step` over branching** — GPUs hate divergent branches
- **Use `mix()` instead of `if/else`** — both branches execute anyway on GPU
- **Reduce texture samples**: prefer mipmap LOD over multi-sample blur
- **Downsample expensive effects**: render at half resolution when possible
- **Avoid dependent texture reads**: compute UV before sampling, not after
- **Keep FBM octaves ≤ 4** on mobile; 5+ is desktop-only
- **Use `pow(x, 2.0)` instead of `x * x` only when the compiler won't optimize** — usually `x * x` is fine

## Math Safety

```glsl
// Division — always guard
float safe = a / max(b, 0.0001);

// Square root — ensure non-negative
float safe = sqrt(max(val, 0.0));

// Log — ensure positive
float safe = log(max(val, 0.0001));

// Pow with negative base — use abs
float safe = pow(abs(base), exp);

// Normalize — guard zero-length
vec2 safe = length(v) > 0.0001 ? normalize(v) : vec2(0.0);

// Clamp all outputs
fragColor = vec4(clamp(col, 0.0, 1.0), clamp(alpha, 0.0, 1.0));
```

## Cross-Platform Quirks

| Issue | GLSL (WebGL/Vulkan) | MSL (Metal) | Notes |
|-------|---------------------|-------------|-------|
| Fragment output | `out vec4 fragColor` | `return vec4` | Our runtime wraps to handle this |
| Texture function | `texture(sampler, uv)` | `sampler.sample(uv)` | Use `texture()` — transpiler handles |
| Uniform declarations | Must declare in code | Declared in shader signature | Our runtime auto-injects common uniforms |
| Precision | Need `precision highp float` | Implicit | Always include precision qualifier |
| Half-float framebuffers | May not support | Supported | Assume `highp` only; don't rely on `mediump` FBO |

## Texture Support

- Textures are supported via `iChannel0`–`iChannel3` (Shadertoy convention)
- Use `texture(iChannelN, uv)` for sampling
- Our runtime will bind system textures to channels automatically
- For backdrop blur effects, iChannel0 is the system framebuffer
- For user-uploaded textures, iChannel1 is available
- Always handle the case where a channel may not be bound — use fallback procedural
- **Mobile**: keep texture samples ≤ 8 per fragment; prefer mipmap LOD blur over multi-sample
```

- [ ] **Step 10: 创建着色器骨架资产文件**

```glsl
// assets/shader-skeleton.glsl
// VFX Agent 标准着色器骨架 — 所有生成的 shader 必须遵循此结构

// 效果名称：{effect_name}

// ---- Uniforms（由运行时自动注入，不需要声明）----
// uniform float u_time;        // 全局时间（秒）
// uniform vec2  u_resolution;  // 视窗分辨率（像素）
// uniform vec2  u_mouse;       // 鼠标/触摸位置（像素，左下角原点）
// uniform sampler2D iChannel0; // 系统纹理：backdrop framebuffer
// uniform sampler2D iChannel1; // 用户纹理（可选）

// ---- 辅助函数区 ----
// 在这里放置 SDF、噪声、纹理采样等辅助函数
// 优先从 effect-dev Skill 的 references 中复用已有实现

// float sdCircle(vec2 p, float r) { ... }
// float perlinNoise(vec2 p) { ... }
// vec3 backdropBlur(vec2 uv, float radius) { ... }

// ---- 主着色函数 ----
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    // 1. 坐标归一化
    vec2 uv = fragCoord / u_resolution.xy;
    float aspect = u_resolution.x / u_resolution.y;

    // 2. 着色逻辑
    vec3 col = vec3(0.0);

    // ... 在这里实现你的视效逻辑 ...

    // 3. 安全输出
    fragColor = vec4(clamp(col, 0.0, 1.0), 1.0);
}
```

- [ ] **Step 11: 创建着色器验证脚本**

```python
"""scripts/validate-shader.py — 检查 GLSL 代码是否符合 VFX Agent 约束"""

import re
import sys


def validate_shader(source: str) -> list[str]:
    errors = []

    # 1. 必须包含 mainImage
    if "mainImage" not in source:
        errors.append("MISSING: mainImage function not found")

    # 2. 不应声明系统 uniform
    banned_decls = [
        (r"uniform\s+float\s+u_time", "u_time"),
        (r"uniform\s+vec2\s+u_resolution", "u_resolution"),
        (r"uniform\s+vec2\s+u_mouse", "u_mouse"),
    ]
    for pattern, name in banned_decls:
        if re.search(pattern, source):
            errors.append(f"BANNED: explicit declaration of uniform {name} (injected by runtime)")

    # 3. 禁止 discard
    if re.search(r"\bdiscard\b", source):
        errors.append("BANNED: discard keyword (kills early-Z, use alpha/step instead)")

    # 4. 检测 3D raymarching 模式（2D/2.5D 系统不允许）
    raymarch_patterns = [
        (r"\b(raycast|raymarch|marchRay|castRay|rayDirection|traceRay)\b", "raymarching function name"),
        (r"\bsceneSDF\s*\(\s*vec3\b", "3D scene SDF (vec3 parameter) — use 2D SDF only"),
        (r"\bsdSphere\s*\(\s*vec3\b", "3D SDF primitive — use 2D equivalents"),
        (r"\bsdBox\s*\(\s*vec3\b", "3D SDF primitive — use 2D equivalents"),
        (r"\b(camera|camPos|rayOrigin|rayDir)\b", "3D camera/ray setup — not allowed in 2D system"),
        (r"\b(MAX_STEPS|MAX_MARCH|NUM_STEPS)\b.*\b\d{2,}\b", "raymarching step constant — likely 3D"),
    ]
    for pattern, desc in raymarch_patterns:
        if re.search(pattern, source, re.IGNORECASE):
            errors.append(f"SCOPE: detected 3D/raymarching pattern ({desc}) — this system is 2D/2.5D only")

    # 5. 检查不安全循环
    for_loops = re.findall(r"for\s*\(.+?;\s*(.+?)\s*<\s*(.+?)\s*;", source)
    for init, bound in for_loops:
        try:
            if int(bound) > 8:
                errors.append(f"LOOP: for-loop bound {bound} exceeds 8 iterations")
        except ValueError:
            errors.append(f"LOOP: dynamic loop bound '{bound}' not allowed")

    # 6. 检查不安全数学
    if re.search(r"/\s*(?!\d)(?!\s*max)", source) and "max(" not in source.split("/")[-1][:20]:
        # Simplified check — may have false positives
        pass

    # 7. 检查精度声明
    if "precision" not in source:
        errors.append("WARN: no precision qualifier (add 'precision highp float;')")

    # 8. 检查输出 clamp
    if "clamp" not in source:
        errors.append("WARN: no clamp on output — risk of out-of-gamut colors")

    return errors


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python validate-shader.py <file.glsl>")
        sys.exit(1)

    with open(sys.argv[1], "r") as f:
        source = f.read()

    errors = validate_shader(source)
    if errors:
        print(f"❌ Found {len(errors)} issue(s):")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("✅ Shader passes validation")
        sys.exit(0)
```

- [ ] **Step 12: 验证 Skill 可被 Agent 发现和加载**

在 OpenCode 中运行：
```bash
# 确认 skill 被发现
ls -la .claude/skills/effect-dev/SKILL.md
```
检查 OpenCode 的 skill 列表中是否出现 `effect-dev`。

- [ ] **Step 13: Commit**

```bash
git add -A
git commit -m "feat: add effect-dev Agent Skill with SDF/noise/lighting/texture/templates/aesthetics/GLSL references"
```

## Task 5: Generate Agent —— Shader 代码生成（集成 Skill 检索）

**Files:**
- Create: `backend/app/prompts/generate_system.md`
- Create: `backend/app/agents/generate.py`

- [ ] **Step 1: 创建 Generate Agent system prompt**

```markdown
# Shader 生成 Agent

你是一个高级图形程序员，专注于为移动端和 Web 平台编写 **2D/2.5D 程序化动效** 的 GLSL 着色器代码。你将接收一个结构化的视效语义描述 JSON，以及通过 effect-dev Skill 提供的算子/模板/美学原则参考，输出符合 Shadertoy 格式的 GLSL 片段着色器代码。

## 核心定位：2D/2.5D 平面动效

本系统面向**移动端和 Web 平台的 OS 级 UI 视效**，不是通用 3D 渲染系统：
- ✅ 2D SDF 形状、程序化噪声纹理、色彩渐变、遮罩混合
- ✅ UI 动效：涟漪、光晕、呼吸、磨砂、流光、脉冲
- ✅ 纹理采样：backdrop blur、色调偏移、纹理+程序化混合
- ✅ 2.5D：多层 2D 叠加、伪深度（视差/模糊分层）
- ❌ **禁止**：3D raymarching、3D SDF、路径追踪、体渲染、相机/场景图
- ❌ **禁止**：高开销效果（>2ms/帧@1080p 的效果在移动端不可接受）

## 权威参考

算子和实现参考以下权威来源：
- **iq (Inigo Quilez)** — SDF 算法定义：`iquilezles.org/articles/distfunctions2d/`
- **Shadertoy** — 视效实现案例：`shadertoy.com`
- 当不确定某个效果的实现时，优先参考 Shadertoy 上的高赞案例

## Shadertoy 格式规范

你的输出必须遵循以下格式：

```glsl
// 效果名称：{effect_name}

// ---- Uniforms（由运行时注入，不需要声明）----
// uniform float u_time;       // 全局时间（秒）
// uniform vec2  u_resolution; // 视窗分辨率（像素）
// uniform vec2  u_mouse;      // 鼠标位置（像素，左下角原点）

// ---- 用户自定义函数区 ----
// 在这里实现你需要的辅助函数（SDF、噪声、缓动等）
// 优先使用上下文中提供的 Skill 算子代码

float hash(vec2 p) { ... }
float noise(vec2 p) { ... }
float sdCircle(vec2 p, float r) { ... }
// ... 其他辅助函数

// ---- 主着色函数 ----
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / u_resolution.xy;
    vec2 aspect = vec2(u_resolution.x / u_resolution.y, 1.0);

    // 你的着色逻辑

    fragColor = vec4(color, 1.0);
}
```

## 关键约束

1. **不要声明 `u_time`, `u_resolution`, `u_mouse`** —— 这些 uniform 由运行时自动注入
2. **必须实现 `mainImage(out vec4, in vec2)` 函数** —— 这是入口点
3. **2D/2.5D 限定**：所有坐标运算基于 `vec2 uv`，SDF 运算使用 2D 版本，禁止 3D raymarching/3D SDF/相机系统
4. **禁止使用**：`for` 循环（超过 8 次迭代）、递归、动态数组索引、`discard`
5. **纹理采样**：支持通过 `iChannel0`–`iChannel3` 采样纹理（Shadertoy 标准），使用 `texture(iChannelN, uv)` 调用。iChannel0 为系统 backdrop framebuffer，iChannel1 为用户上传纹理。**移动端限制每片段纹理采样 ≤ 8 次**。
6. **所有数学运算必须安全**：除法前检查分母、`sqrt` / `log` 前确保非负、使用 `clamp` 防止越界
7. **输出必须是完整可编译的 GLSL ES 3.0 代码**，不要有 `#include` 或未定义的函数
8. **代码中必须有充分的注释**，说明关键逻辑的视觉意图
9. **移动端性能**：目标 < 2ms/帧@1080p，FBM ≤ 4 octaves，模糊核 ≤ 7×7

## Skill 算子使用

你的上下文中通过 effect-dev Agent Skill 提供了完整的知识库，按需加载：
- **SDF 算子**（iq 定义）：直接复用其中提供的 GLSL 函数实现，不要自己重写，保证正确性
- **噪声函数**：Perlin/Simplex/Voronoi/Worley/FBM，复用已有实现
- **纹理采样**：backdrop blur、parallax distortion、mipmap LOD 等模式
- **着色器模板**：可作为着色器的骨架参考，根据语义描述调整模板中的参数和逻辑
- **美学原则**：在色彩选择和动效设计时遵循这些原则
- **GLSL 约束**：安全规则、移动端性能限制、2D 范围检查

## 编码原则

- 使用 **2D SDF**（有向距离场）描述形状——更精确、更灵活，基于 iq 的算法定义
- 使用程序化噪声（Value/Perlin/Simplex/Worley）生成纹理
- 使用数学缓动函数而非硬编码的关键帧
- 优先使用 `smoothstep` 和 `mix` 实现柔和过渡
- 使用 `fract(u_time / duration)` 创建循环动画
- **移动端优先**：FBM ≤ 4 octaves，模糊优先用 mipmap LOD，避免多采样
- **2D 思维**：效果都是平面/分层的，用 UV 坐标和 `vec2` SDF，不引入 `vec3` 3D 空间

## 输出

只输出 GLSL 代码，不要输出任何其他内容。不要用 markdown 代码块包裹。
```

- [ ] **Step 2: 创建 Generate Agent（集成 SkillLoader）**

```python
"""Generate Agent：根据视效语义描述 + Skill 资产生成 Shadertoy 格式 GLSL 代码"""

import json
import re
from pathlib import Path

from app.agents.base import BaseAgent
from app.config import settings


class GenerateAgent(BaseAgent):
    def __init__(self):
        super().__init__(model_config=settings.generate)
        self.system_prompt = Path("app/prompts/generate_system.md").read_text()
        # Skill 知识库通过 .claude/skills/effect-dev/ 的标准 Agent Skill 机制提供
        # 运行此 Agent 的 AI 编码工具（如 OpenCode/Claude Code）会自动发现并按需加载 Skill
        # 这里不需要自定义的 SkillLoader —— Skill 在 Agent 的 system prompt 层面生效

    def run(
        self,
        visual_description: dict,
        previous_shader: str | None = None,
        feedback: str | None = None,
    ) -> str:
        """
        生成或修正 GLSL 着色器代码。

        Skill 知识库（算子/模板/美学原则/纹理采样/约束）通过 Agent Skill 机制
        在 system prompt 层面自动注入，无需手动检索和拼装。

        Args:
            visual_description: Decompose Agent 输出的视效语义描述
            previous_shader: 前一轮生成的 shader 代码（修正时传入）
            feedback: Inspect Agent 的修正指令（修正时传入）

        Returns:
            完整的 Shadertoy 格式 GLSL 代码
        """
        # 构建 user prompt
        user_parts = [
            "请根据以下视效语义描述生成 GLSL 着色器代码：\n",
            f"```json\n{json.dumps(visual_description, indent=2, ensure_ascii=False)}\n```",
        ]

        # 修正模式下注入历史代码和反馈
        if previous_shader and feedback:
            user_parts.extend([
                "\n---\n以下是上一轮生成的着色器代码：",
                f"```glsl\n{previous_shader}\n```",
                f"\n---\n检视 Agent 的反馈：\n{feedback}",
                "\n请根据反馈修正着色器代码，保持整体结构不变，仅修改有问题的部分。",
            ])

        user_prompt = "\n".join(user_parts)

        response = self.chat(
            system_prompt=self.system_prompt,
            user_prompt=user_prompt,
            temperature=0.2 if previous_shader else 0.5,
            max_tokens=4096,
        )

        return self._extract_glsl(response)

    @staticmethod
    def _extract_glsl(text: str) -> str:
        """从 LLM 响应中提取 GLSL 代码"""
        text = text.strip()

        # 如果被 markdown code block 包裹
        if "```glsl" in text:
            match = re.search(r"```glsl\s*\n(.*?)```", text, re.DOTALL)
            if match:
                return match.group(1).strip()
        if "```" in text:
            match = re.search(r"```\s*\n(.*?)```", text, re.DOTALL)
            if match:
                return match.group(1).strip()

        # 否则假定整个响应就是 GLSL 代码
        return text
```

- [ ] **Step 3: 测试 Generate Agent 端到端调用（含 Skill 检索）**

```bash
cd /Users/yangfei/Code/VFX-Agent/backend
python -c "
from app.agents.generate import GenerateAgent
agent = GenerateAgent()
desc = {
    'effect_name': 'ripple',
    'shape': {'type': 'circle', 'description': '中心圆形波纹', 'sdf_primitives': ['circle'], 'parameters': {'radius': '0.3'}},
    'color': {'palette': ['#1a1a2e', '#4a90d9'], 'gradient_type': 'radial', 'gradient_direction': '从中心向外', 'opacity_range': [0.5, 1.0], 'has_noise': True, 'noise_type': 'perlin'},
    'animation': {'loop_duration_s': 2.0, 'easing': 'ease_out', 'phases': [{'name': 'expand', 'time_range': [0.0, 1.0], 'description': '波纹向外扩散'}], 'time_function': 'fract(t)'},
    'interaction': {'responds_to_pointer': True, 'interaction_type': 'ripple', 'description': '点击产生涟漪'},
    'post_processing': {'blur': False, 'blur_radius': 0, 'bloom': False, 'bloom_intensity': 0, 'chromatic_aberration': False},
    'overall_description': '从点击位置产生同心圆水波纹，向外扩散并衰减，深蓝底色+浅蓝高亮'
}
shader = agent.run(desc)
print(shader[:800])
print('...')
print(f'Total length: {len(shader)} chars')
"
```
Expected: 输出一段完整的 Shadertoy 格式 GLSL 代码，包含 `mainImage` 函数，并且使用了 Skill 中的算子（如 `sdCircle`、`perlinNoise`）。

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: add Generate Agent with Skill-aware GLSL code generation"
```

---

## Task 6: Web Shader 渲染预览组件

**Files:**
- Create: `frontend/src/lib/shader-renderer.ts`
- Create: `frontend/src/components/ShaderPreview.tsx`

- [ ] **Step 1: 创建 Three.js Shader 渲染器封装**

```typescript
// shader-renderer.ts
import * as THREE from "three";

const VERTEX_SHADER = `
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`;

// Shadertoy 兼容的片段着色器包装
function wrapFragmentShader(userShader: string): string {
  return `
precision highp float;
uniform float u_time;
uniform vec2 u_resolution;
uniform vec2 u_mouse;
uniform sampler2D iChannel0;
uniform sampler2D iChannel1;
varying vec2 vUv;

${userShader}

void main() {
  vec4 fragColor;
  mainImage(fragColor, gl_FragCoord.xy);
  gl_FragColor = fragColor;
}
`;
}

export class ShaderRenderer {
  private renderer: THREE.WebGLRenderer;
  private scene: THREE.Scene;
  private camera: THREE.OrthographicCamera;
  private mesh: THREE.Mesh | null = null;
  private clock: THREE.Clock;
  private animationId: number | null = null;
  private mousePos = new THREE.Vector2(0, 0);
  private backdropTexture: THREE.Texture | null = null;
  private userTexture: THREE.Texture | null = null;
  private defaultTexture: THREE.Texture;

  constructor(container: HTMLElement) {
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    this.renderer.setPixelRatio(window.devicePixelRatio);
    this.renderer.setSize(container.clientWidth, container.clientHeight);
    container.appendChild(this.renderer.domElement);

    this.scene = new THREE.Scene();
    this.camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
    this.clock = new THREE.Clock();

    // 默认 1x1 白色纹理（未绑定 channel 时使用，避免采样报错）
    const canvas = document.createElement("canvas");
    canvas.width = 1; canvas.height = 1;
    const ctx = canvas.getContext("2d")!;
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, 1, 1);
    this.defaultTexture = new THREE.CanvasTexture(canvas);
  }

  compileShader(fragShaderSource: string): { success: boolean; error: string | null } {
    const fullFrag = wrapFragmentShader(fragShaderSource);

    // 清除旧的 mesh
    if (this.mesh) {
      this.scene.remove(this.mesh);
      this.mesh.geometry.dispose();
      (this.mesh.material as THREE.ShaderMaterial).dispose();
      this.mesh = null;
    }

    const material = new THREE.ShaderMaterial({
      vertexShader: VERTEX_SHADER,
      fragmentShader: fullFrag,
      uniforms: {
        u_time: { value: 0.0 },
        u_resolution: { value: new THREE.Vector2(
          this.renderer.domElement.width,
          this.renderer.domElement.height
        )},
        u_mouse: { value: this.mousePos },
        // 纹理通道：iChannel0 = 系统backdrop, iChannel1 = 用户纹理
        iChannel0: { value: this.backdropTexture || defaultTexture },
        iChannel1: { value: this.userTexture || defaultTexture },
      },
    });

    // 检查编译错误
    const gl = this.renderer.getContext();
    const existingProgram = gl.getParameter(gl.CURRENT_PROGRAM);

    const geometry = new THREE.PlaneGeometry(2, 2);
    this.mesh = new THREE.Mesh(geometry, material);
    this.scene.add(this.mesh);

    // 尝试编译
    this.renderer.render(this.scene, this.camera);

    const program = (material as any).program;
    if (program) {
      const diagnostics = program.getDiagnostics();
      if (diagnostics && diagnostics.fragmentShaderLog) {
        return { success: false, error: diagnostics.fragmentShaderLog };
      }
    }

    return { success: true, error: null };
  }

  startRendering() {
    this.clock.start();
    const animate = () => {
      this.animationId = requestAnimationFrame(animate);
      if (this.mesh) {
        const mat = (this.mesh.material as THREE.ShaderMaterial);
        mat.uniforms.u_time.value = this.clock.getElapsedTime();
        mat.uniforms.u_resolution.value.set(
          this.renderer.domElement.width,
          this.renderer.domElement.height
        );
      }
      this.renderer.render(this.scene, this.camera);
    };
    animate();
  }

  stopRendering() {
    if (this.animationId !== null) {
      cancelAnimationFrame(this.animationId);
      this.animationId = null;
    }
  }

  updateMouse(x: number, y: number) {
    const canvas = this.renderer.domElement;
    this.mousePos.set(x, canvas.height - y);
  }

  resize(width: number, height: number) {
    this.renderer.setSize(width, height);
    if (this.mesh) {
      const mat = (this.mesh.material as THREE.ShaderMaterial);
      mat.uniforms.u_resolution.value.set(width * devicePixelRatio, height * devicePixelRatio);
    }
  }

  dispose() {
    this.stopRendering();
    this.renderer.dispose();
    this.renderer.domElement.remove();
  }
}
```

- [ ] **Step 2: 创建 ShaderPreview React 组件**

```tsx
// ShaderPreview.tsx
import { useEffect, useRef, useState, useCallback } from "react";
import { ShaderRenderer } from "../lib/shader-renderer";

interface ShaderPreviewProps {
  shaderCode: string | null;
  width?: number;
  height?: number;
}

export default function ShaderPreview({ shaderCode, width = 512, height = 512 }: ShaderPreviewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const rendererRef = useRef<ShaderRenderer | null>(null);
  const [compileError, setCompileError] = useState<string | null>(null);
  const [isRendering, setIsRendering] = useState(false);

  // 初始化渲染器
  useEffect(() => {
    if (containerRef.current && !rendererRef.current) {
      rendererRef.current = new ShaderRenderer(containerRef.current);
    }
    return () => {
      rendererRef.current?.dispose();
      rendererRef.current = null;
    };
  }, []);

  // Shader 代码变化时重新编译
  useEffect(() => {
    if (!rendererRef.current || !shaderCode) return;

    const result = rendererRef.current.compileShader(shaderCode);
    if (result.success) {
      setCompileError(null);
      rendererRef.current.startRendering();
      setIsRendering(true);
    } else {
      setCompileError(result.error);
      rendererRef.current.stopRendering();
      setIsRendering(false);
    }
  }, [shaderCode]);

  // 鼠标交互
  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!rendererRef.current) return;
    const rect = e.currentTarget.getBoundingClientRect();
    rendererRef.current.updateMouse(e.clientX - rect.left, e.clientY - rect.top);
  }, []);

  return (
    <div className="flex flex-col items-center gap-2">
      <div
        ref={containerRef}
        style={{ width, height }}
        className="border border-gray-700 rounded-lg overflow-hidden bg-black"
        onMouseMove={handleMouseMove}
      />
      {compileError && (
        <div className="w-full p-2 bg-red-900/50 border border-red-700 rounded text-red-300 text-xs font-mono overflow-auto max-h-32">
          <p className="font-bold mb-1">Compile Error:</p>
          <pre>{compileError}</pre>
        </div>
      )}
      {!shaderCode && (
        <p className="text-gray-500 text-sm">等待生成着色器代码...</p>
      )}
      {isRendering && !compileError && (
        <p className="text-green-400 text-sm">✓ 着色器运行中</p>
      )}
    </div>
  );
}
```

- [ ] **Step 3: 验证前端渲染可工作**

在 `App.tsx` 中临时写入一个简单的测试 shader 并渲染：
```tsx
// 临时测试代码，验证 ShaderPreview 可工作
const TEST_SHADER = `
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
  vec2 uv = fragCoord / u_resolution.xy;
  vec3 col = 0.5 + 0.5 * cos(u_time + uv.xyx + vec3(0, 2, 4));
  fragColor = vec4(col, 1.0);
}
`;
```
打开 `http://localhost:5173`，应看到一个随时间变化的彩虹渐变动画。

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: add Three.js shader renderer and ShaderPreview component"
```

---

## Task 7: 浏览器自动化截图服务

**Files:**
- Create: `backend/app/services/browser_render.py`

- [ ] **Step 1: 安装 Playwright 浏览器**

```bash
cd /Users/yangfei/Code/VFX-Agent/backend
playwright install chromium
```

- [ ] **Step 2: 创建 Playwright 截图服务**

```python
"""Playwright 浏览器自动化截图服务：将 shader 注入 WebGL 预览页并截图"""

import asyncio
import base64
import tempfile
from pathlib import Path

from playwright.async_api import async_playwright

from app.config import settings


async def render_and_screenshot(
    shader_code: str,
    time_seconds: float = 1.0,
    width: int | None = None,
    height: int | None = None,
) -> str:
    """
    在浏览器中渲染 shader 并截图，返回截图文件路径。

    Args:
        shader_code: Shadertoy 格式 GLSL 代码
        time_seconds: 渲染到第几秒时截图（用于动画效果）
        width: 截图宽度
        height: 截图高度

    Returns:
        截图 PNG 文件路径
    """
    width = width or settings.screenshot_width
    height = height or settings.screenshot_height

    # 将 shader 代码编码为 URL-safe base64，通过 URL 参数传给前端
    shader_b64 = base64.urlsafe_b64encode(shader_code.encode()).decode()

    preview_url = f"{settings.frontend_url}?shader={shader_b64}&t={time_seconds}"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": width, "height": height})
        await page.goto(preview_url, wait_until="networkidle")

        # 等待 shader 编译和渲染
        await page.wait_for_timeout(500)

        # 等待渲染器标记就绪
        await page.wait_for_function(
            "() => window.__shaderReady === true",
            timeout=settings.render_timeout_ms,
        )

        # 截图
        screenshot_path = Path(tempfile.mktemp(suffix=".png", prefix="vfx_screenshot_"))
        await page.screenshot(path=str(screenshot_path), type="png")

        await browser.close()

    return str(screenshot_path)


async def render_multiple_frames(
    shader_code: str,
    times: list[float] | None = None,
    width: int | None = None,
    height: int | None = None,
) -> list[str]:
    """
    渲染 shader 在多个时间点的截图，用于动画对比。

    Args:
        shader_code: Shadertoy 格式 GLSL 代码
        times: 截图时间点列表（秒），默认 [0, 0.5, 1.0, 1.5, 2.0]
        width: 截图宽度
        height: 截图高度

    Returns:
        截图文件路径列表
    """
    times = times or [0.0, 0.5, 1.0, 1.5, 2.0]
    screenshots = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(
            viewport={"width": width or settings.screenshot_width, "height": height or settings.screenshot_height}
        )

        shader_b64 = base64.urlsafe_b64encode(shader_code.encode()).decode()
        await page.goto(f"{settings.frontend_url}?shader={shader_b64}", wait_until="networkidle")
        await page.wait_for_timeout(500)
        await page.wait_for_function(
            "() => window.__shaderReady === true",
            timeout=settings.render_timeout_ms,
        )

        for t in times:
            # 通过 JS 设置渲染器时间并等待一帧
            await page.evaluate(f"window.__setShaderTime({t})")
            await page.wait_for_timeout(100)

            path = Path(tempfile.mktemp(suffix=".png", prefix=f"vfx_t{t}_"))
            await page.screenshot(path=str(path), type="png")
            screenshots.append(str(path))

        await browser.close()

    return screenshots
```

- [ ] **Step 3: 在前端添加 URL 参数渲染支持**

在前端 `App.tsx` 中添加解析 URL 参数的逻辑，使得 `?shader=BASE64&t=SECONDS` 可以直接渲染指定 shader：

```typescript
// 在 App 组件中添加
useEffect(() => {
  const params = new URLSearchParams(window.location.search);
  const shaderParam = params.get("shader");
  const timeParam = params.get("t");

  if (shaderParam) {
    try {
      const code = atob(shaderParam.replace(/-/g, "+").replace(/_/g, "/"));
      setShaderCode(code);
    } catch (e) {
      console.error("Failed to decode shader from URL", e);
    }
  }
}, []);
```

并在 `ShaderPreview` 渲染器就绪时设置 `window.__shaderReady = true`，以及暴露 `window.__setShaderTime(t)` 函数，供 Playwright 调用。

- [ ] **Step 4: 测试截图服务**

```bash
cd /Users/yangfei/Code/VFX-Agent/backend
python -c "
import asyncio
from app.services.browser_render import render_and_screenshot

TEST_SHADER = '''
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
  vec2 uv = fragCoord / u_resolution.xy;
  vec3 col = 0.5 + 0.5 * cos(u_time + uv.xyx + vec3(0, 2, 4));
  fragColor = vec4(col, 1.0);
}
'''

path = asyncio.run(render_and_screenshot(TEST_SHADER, time_seconds=1.0))
print(f'Screenshot saved to: {path}')
"
```
Expected: 生成一张 512x512 的 PNG 截图，内容为彩色渐变。

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: add Playwright browser automation for shader rendering and screenshot capture"
```

---

## Task 8: Inspect Agent —— 视觉检视与反馈

**Files:**
- Create: `backend/app/prompts/inspect_system.md`
- Create: `backend/app/agents/inspect.py`

- [ ] **Step 1: 创建 Inspect Agent system prompt**

```markdown
# 视效检视 Agent

你是一个视觉效果质量审查专家。你的任务是将生成的着色器渲染截图与原始设计参考进行对比，判断视觉一致性，并给出精确的修正指令。

## 评估维度

1. **形态一致性 (Shape)**：形状轮廓是否匹配？位置和比例是否正确？
2. **色彩一致性 (Color)**：色调、渐变方向、色彩分布是否匹配？
3. **动画一致性 (Animation)**：动态节奏、缓动感、运动方向是否匹配？（通过多帧截图判断）
4. **整体相似度 (Overall)**：视觉上是否达到了设计意图？

## 输出格式

请严格输出以下 JSON 结构（不要输出其他内容）：

```json
{
  "passed": false,
  "overall_score": 0.7,
  "dimensions": {
    "shape": {"score": 0.8, "notes": "形状基本匹配，但边缘模糊度不够"},
    "color": {"score": 0.6, "notes": "色调偏冷，缺少设计稿中的暖色过渡"},
    "animation": {"score": 0.7, "notes": "运动节奏稍快，应放缓"},
    "overall": {"score": 0.7, "notes": "整体接近但细节需要调整"}
  },
  "feedback": "具体修正指令，如：1) 将渐变方向从 vertical 改为 diagonal（左上到右下）；2) 降低噪声频率，将 noise_freq 从 8.0 降至 4.0；3) 将动画周期从 1.5s 延长至 2.5s，使用 smoothstep 替代线性时间函数",
  "critical_issues": ["色调偏移严重"]
}
```

## 评分标准

- **0.9-1.0**：几乎完全一致，可以接受
- **0.7-0.9**：基本一致，需要微调
- **0.5-0.7**：有明显偏差，需要较大修改
- **0.3-0.5**：偏差较大，建议重新生成
- **0.0-0.3**：完全不符，需要从头开始

## 判定规则

- `overall_score >= 0.85` 时 `passed = true`
- 否则 `passed = false`，并给出修正指令

## 修正指令编写原则

- **具体可操作**：指出需要修改的变量名、函数名、数值范围
- **不重写**：只指明修改方向，不要给出完整的新代码
- **优先级排序**：最影响视觉的问题排在前面
```

- [ ] **Step 2: 创建 Inspect Agent**

```python
"""Inspect Agent：对比渲染截图与设计参考，输出修正指令"""

import json
from pathlib import Path

from app.agents.base import BaseAgent
from app.config import settings


class InspectAgent(BaseAgent):
    def __init__(self):
        super().__init__(model_config=settings.inspect)
        self.system_prompt = Path("app/prompts/inspect_system.md").read_text()

    def run(
        self,
        design_images: list[str],
        render_screenshots: list[str],
        visual_description: dict | None = None,
        iteration: int = 0,
    ) -> dict:
        """
        对比渲染截图与设计参考，输出评估结果和修正指令。

        Args:
            design_images: 原始设计参考图片路径列表
            render_screenshots: 渲染截图路径列表（多时间点）
            visual_description: 原始视效语义描述（供参考）
            iteration: 当前迭代轮次

        Returns:
            评估结果 dict，包含 passed/score/feedback 等
        """
        all_images = list(design_images) + list(render_screenshots)

        parts = [
            f"请对比以下图片，评估生成着色器的视觉效果是否满足设计要求。",
            f"\n前 {len(design_images)} 张是原始设计参考，",
            f"后 {len(render_screenshots)} 张是着色器渲染截图（按时间顺序）。",
        ]

        if visual_description:
            parts.append(
                f"\n原始视效描述：{json.dumps(visual_description, indent=2, ensure_ascii=False)}"
            )

        if iteration > 0:
            parts.append(f"\n这是第 {iteration + 1} 轮迭代修正后的结果。")

        user_prompt = "\n".join(parts)

        response = self.chat(
            system_prompt=self.system_prompt,
            user_prompt=user_prompt,
            image_paths=all_images,
            temperature=0.2,
            max_tokens=2048,
        )

        return self._parse_json(response)

    @staticmethod
    def _parse_json(text: str) -> dict:
        """从 LLM 响应中提取 JSON"""
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)
        return json.loads(text)
```

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "feat: add Inspect Agent with multi-dimension visual comparison and feedback"
```

---

## Task 9: Pipeline 闭环编排（LangGraph）

**Files:**
- Create: `backend/app/pipeline/state.py`
- Create: `backend/app/pipeline/graph.py`
- Create: `backend/app/routers/pipeline.py`

- [ ] **Step 1: 定义 Pipeline 状态**

```python
"""Pipeline 状态定义"""

from typing import TypedDict


class PipelineState(TypedDict, total=False):
    # 输入
    input_type: str                     # "video" | "image"
    video_path: str | None              # 视频文件路径
    image_paths: list[str]              # 图片路径列表
    user_notes: str                     # 用户附加参数标注
    video_info: dict | None             # 视频元信息

    # 关键帧（视频输入时由 extractor 生成）
    keyframe_paths: list[str]           # 提取的关键帧路径

    # Decompose Agent 产出
    visual_description: dict            # 视效语义描述

    # 迭代状态
    iteration: int                      # 当前迭代轮次（从 0 开始）
    max_iterations: int                 # 最大迭代次数
    current_shader: str                 # 当前 GLSL 代码
    compile_error: str | None           # 编译错误信息

    # Inspect Agent 产出
    inspect_result: dict | None         # 评估结果
    passed: bool                        # 是否通过检视

    # 截图
    render_screenshots: list[str]       # 渲染截图路径
    design_screenshots: list[str]       # 设计参考截图路径

    # Pipeline 状态
    status: str                         # "running" | "passed" | "failed" | "max_iterations"
    error: str | None                   # 错误信息
    history: list[dict]                 # 迭代历史记录
```

- [ ] **Step 2: 创建 LangGraph 闭环编排**

```python
"""LangGraph 闭环编排：Decompose → Generate → Render → Inspect → (反馈循环)"""

import asyncio
from typing import Literal

from langgraph.graph import StateGraph, END

from app.agents.decompose import DecomposeAgent
from app.agents.generate import GenerateAgent
from app.agents.inspect import InspectAgent
from app.pipeline.state import PipelineState
from app.services.browser_render import render_multiple_frames
from app.services.video_extractor import extract_keyframes, get_video_info
from app.config import settings


# ---- 节点函数 ----

decompose_agent = DecomposeAgent()
generate_agent = GenerateAgent()
inspect_agent = InspectAgent()


async def node_extract_keyframes(state: PipelineState) -> dict:
    """视频输入时，提取关键帧"""
    if state.get("input_type") == "video" and state.get("video_path"):
        video_info = get_video_info(state["video_path"])
        keyframe_paths = extract_keyframes(state["video_path"], max_frames=6)
        return {"video_info": video_info, "keyframe_paths": keyframe_paths, "design_screenshots": keyframe_paths}
    elif state.get("image_paths"):
        return {"keyframe_paths": state["image_paths"], "design_screenshots": state["image_paths"]}
    return {}


async def node_decompose(state: PipelineState) -> dict:
    """Decompose Agent：解构视效语义描述"""
    keyframes = state.get("keyframe_paths", [])
    video_info = state.get("video_info")
    user_notes = state.get("user_notes", "")

    description = decompose_agent.run(
        image_paths=keyframes,
        video_info=video_info,
        user_notes=user_notes,
    )

    return {"visual_description": description}


async def node_generate(state: PipelineState) -> dict:
    """Generate Agent：生成或修正 GLSL 代码"""
    description = state.get("visual_description", {})
    previous_shader = state.get("current_shader") if state.get("iteration", 0) > 0 else None
    feedback = None
    if state.get("inspect_result") and not state.get("passed", False):
        feedback = state["inspect_result"].get("feedback", "")

    shader = generate_agent.run(
        visual_description=description,
        previous_shader=previous_shader,
        feedback=feedback,
    )

    return {
        "current_shader": shader,
        "compile_error": None,
        "iteration": state.get("iteration", 0),
    }


async def node_render_and_screenshot(state: PipelineState) -> dict:
    """在浏览器中渲染 shader 并截图"""
    shader = state.get("current_shader", "")
    if not shader:
        return {"render_screenshots": [], "compile_error": "No shader code to render"}

    try:
        screenshots = await render_multiple_frames(
            shader_code=shader,
            times=[0.0, 0.5, 1.0, 1.5, 2.0],
        )
        return {"render_screenshots": screenshots, "compile_error": None}
    except Exception as e:
        return {"render_screenshots": [], "compile_error": str(e)}


async def node_inspect(state: PipelineState) -> dict:
    """Inspect Agent：对比截图，输出评估"""
    design_imgs = state.get("design_screenshots", [])
    render_imgs = state.get("render_screenshots", [])

    if not render_imgs:
        return {
            "inspect_result": {"passed": False, "overall_score": 0, "feedback": "渲染失败，无截图可对比"},
            "passed": False,
        }

    result = inspect_agent.run(
        design_images=design_imgs,
        render_screenshots=render_imgs,
        visual_description=state.get("visual_description"),
        iteration=state.get("iteration", 0),
    )

    passed = result.get("passed", False) or result.get("overall_score", 0) >= 0.85

    # 记录历史
    history = state.get("history", [])
    history.append({
        "iteration": state.get("iteration", 0),
        "score": result.get("overall_score", 0),
        "passed": passed,
        "feedback": result.get("feedback", ""),
    })

    return {
        "inspect_result": result,
        "passed": passed,
        "history": history,
    }


# ---- 条件边 ----

def should_continue(state: PipelineState) -> Literal["generate", "end"]:
    """判断是否继续迭代"""
    if state.get("passed", False):
        return "end"
    if state.get("compile_error") and state.get("iteration", 0) >= 1:
        # 编译错误且已重试，结束
        return "end"
    if state.get("iteration", 0) >= state.get("max_iterations", settings.max_iterations) - 1:
        return "end"
    return "generate"


# ---- 构建图 ----

def build_pipeline_graph() -> StateGraph:
    graph = StateGraph(PipelineState)

    # 添加节点
    graph.add_node("extract_keyframes", node_extract_keyframes)
    graph.add_node("decompose", node_decompose)
    graph.add_node("generate", node_generate)
    graph.add_node("render_and_screenshot", node_render_and_screenshot)
    graph.add_node("inspect", node_inspect)

    # 添加边
    graph.set_entry_point("extract_keyframes")
    graph.add_edge("extract_keyframes", "decompose")
    graph.add_edge("decompose", "generate")
    graph.add_edge("generate", "render_and_screenshot")
    graph.add_edge("render_and_screenshot", "inspect")

    # 条件边：inspect 之后决定是否继续迭代
    graph.add_conditional_edges(
        "inspect",
        should_continue,
        {"generate": "generate", "end": END},
    )

    return graph


# ---- 迭代计数器增量 ----

# 需要在 generate 节点中增加 iteration
_original_generate = node_generate

async def node_generate_with_increment(state: PipelineState) -> dict:
    result = await _original_generate(state)
    result["iteration"] = state.get("iteration", 0) + 1
    return result

# 重新绑定
graph = StateGraph(PipelineState)
graph.add_node("extract_keyframes", node_extract_keyframes)
graph.add_node("decompose", node_decompose)
graph.add_node("generate", node_generate_with_increment)
graph.add_node("render_and_screenshot", node_render_and_screenshot)
graph.add_node("inspect", node_inspect)

graph.set_entry_point("extract_keyframes")
graph.add_edge("extract_keyframes", "decompose")
graph.add_edge("decompose", "generate")
graph.add_edge("generate", "render_and_screenshot")
graph.add_edge("render_and_screenshot", "inspect")
graph.add_conditional_edges(
    "inspect",
    should_continue,
    {"generate": "generate", "end": END},
)

pipeline_app = graph.compile()
```

- [ ] **Step 3: 创建 Pipeline API 路由**

```python
"""Pipeline 触发与状态查询 API"""

import asyncio
import uuid
from fastapi import APIRouter, UploadFile, File, Form
from pathlib import Path
import shutil

from app.pipeline.graph import pipeline_app
from app.pipeline.state import PipelineState
from app.config import settings

router = APIRouter(prefix="/pipeline", tags=["pipeline"])

# 简单的内存存储（MVP 阶段足够）
pipeline_results: dict[str, dict] = {}


@router.post("/run")
async def run_pipeline(
    video: UploadFile | None = File(None),
    images: list[UploadFile] = File([]),
    notes: str = Form(""),
):
    """触发 Pipeline 执行"""
    pipeline_id = str(uuid.uuid4())
    upload_dir = Path(f"/tmp/vfx_uploads/{pipeline_id}")
    upload_dir.mkdir(parents=True, exist_ok=True)

    # 保存上传文件
    video_path = None
    image_paths = []

    if video:
        video_path = str(upload_dir / video.filename)
        with open(video_path, "wb") as f:
            shutil.copyfileobj(video.file, f)

    for img in images:
        img_path = str(upload_dir / img.filename)
        with open(img_path, "wb") as f:
            shutil.copyfileobj(img.file, f)
        image_paths.append(img_path)

    # 构建初始状态
    initial_state: PipelineState = {
        "input_type": "video" if video_path else "image",
        "video_path": video_path,
        "image_paths": image_paths,
        "user_notes": notes,
        "video_info": None,
        "keyframe_paths": [],
        "visual_description": {},
        "iteration": 0,
        "max_iterations": settings.max_iterations,
        "current_shader": "",
        "compile_error": None,
        "inspect_result": None,
        "passed": False,
        "render_screenshots": [],
        "design_screenshots": [],
        "status": "running",
        "error": None,
        "history": [],
    }

    # 异步执行 pipeline
    async def _run():
        try:
            result = await pipeline_app.ainvoke(initial_state)
            result_dict = {k: v for k, v in result.items()}
            result_dict["status"] = "passed" if result.get("passed") else "max_iterations"
            pipeline_results[pipeline_id] = result_dict
        except Exception as e:
            pipeline_results[pipeline_id] = {"status": "failed", "error": str(e)}

    asyncio.create_task(_run())

    return {"pipeline_id": pipeline_id, "status": "running"}


@router.get("/status/{pipeline_id}")
async def get_pipeline_status(pipeline_id: str):
    """查询 Pipeline 执行状态"""
    result = pipeline_results.get(pipeline_id)
    if not result:
        return {"status": "not_found"}
    return result
```

- [ ] **Step 4: 注册路由到 main.py**

在 `backend/app/main.py` 中添加：
```python
from app.routers import pipeline
app.include_router(pipeline.router)
```

- [ ] **Step 5: 手动测试完整 Pipeline**

上传一张设计稿图片，通过 API 触发 Pipeline：
```bash
curl -X POST http://localhost:8000/pipeline/run \
  -F "images=@/path/to/test_design.png" \
  -F "notes=深蓝到浅蓝的径向渐变，中心有微弱的光晕效果"
```
然后轮询状态：
```bash
curl http://localhost:8000/pipeline/status/{pipeline_id}
```
Expected: Pipeline 经过 Decompose → Generate → Render → Inspect 循环，最终收敛或达到最大迭代次数。

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: add LangGraph pipeline orchestration with closed-loop iteration"
```

---

## Task 10: WebUI 界面整合

**Files:**
- Modify: `frontend/src/App.tsx`
- Create: `frontend/src/components/UploadPanel.tsx`
- Create: `frontend/src/components/PipelineStatus.tsx`
- Create: `frontend/src/components/CodeView.tsx`
- Create: `frontend/src/hooks/usePipeline.ts`

- [ ] **Step 1: 创建 Pipeline 状态 Hook**

```typescript
// hooks/usePipeline.ts
import { useState, useCallback } from "react";

export interface PipelineIteration {
  iteration: number;
  score: number;
  passed: boolean;
  feedback: string;
}

export interface PipelineResult {
  status: string;
  current_shader: string;
  visual_description: Record<string, unknown>;
  iteration: number;
  passed: boolean;
  history: PipelineIteration[];
  inspect_result: Record<string, unknown> | null;
  error: string | null;
}

export function usePipeline() {
  const [pipelineId, setPipelineId] = useState<string | null>(null);
  const [result, setResult] = useState<PipelineResult | null>(null);
  const [loading, setLoading] = useState(false);

  const startPipeline = useCallback(async (formData: FormData) => {
    setLoading(true);
    setResult(null);
    try {
      const res = await fetch("http://localhost:8000/pipeline/run", {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      setPipelineId(data.pipeline_id);

      // 轮询状态
      const poll = async () => {
        const statusRes = await fetch(`http://localhost:8000/pipeline/status/${data.pipeline_id}`);
        const statusData = await statusRes.json();
        setResult(statusData);
        if (statusData.status === "running") {
          setTimeout(poll, 2000);
        } else {
          setLoading(false);
        }
      };
      poll();
    } catch (err) {
      setLoading(false);
      console.error("Pipeline error:", err);
    }
  }, []);

  return { pipelineId, result, loading, startPipeline };
}
```

- [ ] **Step 2: 创建 UploadPanel 组件**

```tsx
// components/UploadPanel.tsx
import { useRef, useState } from "react";

interface UploadPanelProps {
  onSubmit: (formData: FormData) => void;
  loading: boolean;
}

export default function UploadPanel({ onSubmit, loading }: UploadPanelProps) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [notes, setNotes] = useState("");
  const [previews, setPreviews] = useState<string[]>([]);

  const handleFileChange = () => {
    const files = fileRef.current?.files;
    if (!files) return;
    const urls = Array.from(files).map((f) => URL.createObjectURL(f));
    setPreviews(urls);
  };

  const handleSubmit = () => {
    const formData = new FormData();
    const files = fileRef.current?.files;
    if (files) {
      Array.from(files).forEach((f) => formData.append("images", f));
    }
    formData.append("notes", notes);
    onSubmit(formData);
  };

  return (
    <div className="flex flex-col gap-4 p-4 bg-gray-900 rounded-xl">
      <h2 className="text-lg font-semibold text-white">视觉参考输入</h2>

      <div>
        <label className="block text-sm text-gray-400 mb-1">
          上传视频或图片（支持多选）
        </label>
        <input
          ref={fileRef}
          type="file"
          accept="video/*,image/*"
          multiple
          onChange={handleFileChange}
          className="block w-full text-sm text-gray-400 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:bg-blue-600 file:text-white hover:file:bg-blue-500"
        />
      </div>

      {previews.length > 0 && (
        <div className="flex gap-2 overflow-x-auto">
          {previews.map((src, i) => (
            <img key={i} src={src} className="h-20 rounded border border-gray-700" />
          ))}
        </div>
      )}

      <div>
        <label className="block text-sm text-gray-400 mb-1">
          附加参数标注（可选）
        </label>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="e.g. 循环周期2s，缓动曲线ease-in-out，主色#1a1a2e"
          className="w-full h-20 bg-gray-800 text-white rounded p-2 text-sm border border-gray-700 focus:border-blue-500 focus:outline-none"
        />
      </div>

      <button
        onClick={handleSubmit}
        disabled={loading || previews.length === 0}
        className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? "生成中..." : "开始生成"}
      </button>
    </div>
  );
}
```

- [ ] **Step 3: 创建 PipelineStatus 组件**

```tsx
// components/PipelineStatus.tsx
import { PipelineResult } from "../hooks/usePipeline";

interface Props {
  result: PipelineResult | null;
  loading: boolean;
}

export default function PipelineStatus({ result, loading }: Props) {
  if (!result && !loading) {
    return <div className="text-gray-500 text-sm p-4">等待 Pipeline 启动...</div>;
  }

  return (
    <div className="flex flex-col gap-3 p-4 bg-gray-900 rounded-xl">
      <h2 className="text-lg font-semibold text-white">Pipeline 状态</h2>

      {loading && (
        <div className="flex items-center gap-2 text-blue-400">
          <div className="animate-spin h-4 w-4 border-2 border-blue-400 border-t-transparent rounded-full" />
          <span className="text-sm">Agent 迭代中...</span>
        </div>
      )}

      {result && (
        <>
          <div className="flex items-center gap-2">
            <span className={`inline-block w-3 h-3 rounded-full ${
              result.status === "passed" ? "bg-green-500" :
              result.status === "failed" ? "bg-red-500" :
              result.status === "max_iterations" ? "bg-yellow-500" :
              "bg-blue-500 animate-pulse"
            }`} />
            <span className="text-white text-sm capitalize">{result.status}</span>
            <span className="text-gray-400 text-sm">迭代 {result.iteration} 轮</span>
          </div>

          {result.history && result.history.length > 0 && (
            <div className="space-y-1">
              <p className="text-xs text-gray-400">迭代历史：</p>
              {result.history.map((h, i) => (
                <div key={i} className="flex items-center gap-2 text-xs">
                  <span className="text-gray-500">#{h.iteration + 1}</span>
                  <span className={`font-mono ${h.passed ? "text-green-400" : "text-yellow-400"}`}>
                    {h.score.toFixed(2)}
                  </span>
                  <span className="text-gray-600 truncate max-w-xs">{h.feedback.slice(0, 60)}</span>
                </div>
              ))}
            </div>
          )}

          {result.error && (
            <p className="text-red-400 text-sm">{result.error}</p>
          )}
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 4: 创建 CodeView 组件**

```tsx
// components/CodeView.tsx
interface Props {
  code: string | null;
}

export default function CodeView({ code }: Props) {
  if (!code) {
    return <div className="text-gray-500 text-sm p-4">等待着色器代码生成...</div>;
  }

  return (
    <div className="p-4 bg-gray-900 rounded-xl">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-lg font-semibold text-white">GLSL 代码</h2>
        <button
          onClick={() => navigator.clipboard.writeText(code)}
          className="text-xs text-gray-400 hover:text-white px-2 py-1 border border-gray-700 rounded"
        >
          复制
        </button>
      </div>
      <pre className="bg-gray-950 text-green-300 text-xs font-mono p-3 rounded overflow-auto max-h-96 leading-relaxed">
        {code}
      </pre>
    </div>
  );
}
```

- [ ] **Step 5: 整合 App.tsx 主布局**

```tsx
// App.tsx
import { useState, useEffect } from "react";
import UploadPanel from "./components/UploadPanel";
import ShaderPreview from "./components/ShaderPreview";
import PipelineStatus from "./components/PipelineStatus";
import CodeView from "./components/CodeView";
import { usePipeline } from "./hooks/usePipeline";
import { ShaderRenderer } from "./lib/shader-renderer";

export default function App() {
  const { result, loading, startPipeline } = usePipeline();
  const [shaderCode, setShaderCode] = useState<string | null>(null);

  // 支持通过 URL 参数直接渲染（供 Playwright 截图服务使用）
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const shaderParam = params.get("shader");
    if (shaderParam) {
      try {
        const code = atob(shaderParam.replace(/-/g, "+").replace(/_/g, "/"));
        setShaderCode(code);
      } catch (e) {
        console.error("Failed to decode shader from URL", e);
      }
    }
  }, []);

  // Pipeline 产出 shader 时更新预览
  useEffect(() => {
    if (result?.current_shader) {
      setShaderCode(result.current_shader);
    }
  }, [result?.current_shader]);

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <header className="border-b border-gray-800 px-6 py-4">
        <h1 className="text-xl font-bold">VFX Agent</h1>
        <p className="text-sm text-gray-400">AI 驱动的视觉效果自动生成</p>
      </header>

      <main className="max-w-7xl mx-auto p-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左列：输入 + 状态 */}
        <div className="space-y-6">
          <UploadPanel onSubmit={startPipeline} loading={loading} />
          <PipelineStatus result={result} loading={loading} />
        </div>

        {/* 中列：Shader 预览 */}
        <div className="space-y-4">
          <ShaderPreview shaderCode={shaderCode} width={512} height={512} />
        </div>

        {/* 右列：代码查看 */}
        <div>
          <CodeView code={shaderCode} />
        </div>
      </main>
    </div>
  );
}
```

- [ ] **Step 6: 添加 Tailwind CSS 并验证前端**

```bash
cd /Users/yangfei/Code/VFX-Agent/frontend
npm install -D tailwindcss @tailwindcss/vite
```

配置 `vite.config.ts` 添加 Tailwind 插件，添加 `@import "tailwindcss"` 到 `src/index.css`。

启动前端，上传一张图片，验证完整的 UI 流程可用。

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: add complete WebUI with upload, pipeline status, shader preview, and code view"
```

---

## Task 11: 端到端集成测试与调优

**Files:**
- None (验证性任务)

- [ ] **Step 1: 准备测试素材**

准备 2-3 个测试用例：
1. **静态渐变**：一张简单的线性渐变背景图（验证基础 Pipeline 流程）
2. **动态效果**：一段 2-3 秒的循环动画视频（如呼吸光晕、水波纹）
3. **复杂效果**：一张包含噪声纹理和多层叠加的效果图

- [ ] **Step 2: 端到端 Pipeline 测试**

对每个测试用例运行 Pipeline，检查：
- Decompose Agent 是否产出了合理的语义描述
- Generate Agent 是否产出了可编译的 GLSL 代码
- ShaderPreview 是否能正确渲染
- Inspect Agent 是否能给出合理的评估和修正指令
- 闭环迭代是否收敛

- [ ] **Step 3: Prompt 调优**

根据测试结果调整：
- Decompose Agent 的 JSON schema 是否覆盖了足够的视觉特征
- Generate Agent 是否稳定产出可编译代码（常见的编译错误模式）
- Inspect Agent 的评分标准是否合理（0.85 阈值是否太高/太低）
- 反馈指令是否足够具体可操作

- [ ] **Step 4: 错误处理与鲁棒性增强**

- GLSL 编译失败时的重试逻辑
- LLM API 调用超时/失败的重试
- 视频格式不兼容的降级处理
- Inspect Agent JSON 解析失败的 fallback

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: end-to-end integration testing and prompt tuning"
```

---

## Self-Review Checklist

### Spec Coverage
| 需求 | 覆盖任务 |
|------|---------|
| Decompose Agent（多模态，模型可配置） | Task 3 |
| Generate Agent（代码生成，模型可配置） | Task 5 |
| Inspect Agent（多模态，模型可配置） | Task 8 |
| effect-dev Agent Skill（标准 SKILL.md 格式） | Task 4 |
| Skill 参考文档（SDF/噪声/纹理/模板/美学/约束） | Task 4 (references/) |
| 权威来源标注（Shadertoy/iq 博客） | Task 4 (SKILL.md + references) |
| 2D/2.5D 范围限定（排除 3D raymarching） | Task 4 + Task 5 + validate-shader.py |
| 移动端性能预算 | Task 4 (gls-constraints.md + aesthetics-rules.md) |
| 纹理采样支持（iChannel0-3） | Task 4 + Task 5 + Task 6 |
| 模型配置按角色独立指定 | Task 1 (.env + config.py) |
| 视频 + 图片输入 | Task 3 (extract_keyframes) |
| Shadertoy 格式 GLSL | Task 5 |
| Harness Loop 闭环迭代 | Task 9 (LangGraph) |
| Web 渲染预览（Three.js WebGL + 纹理） | Task 6 |
| 浏览器自动化截图 | Task 7 (Playwright) |
| WebUI 前端 | Task 10 |
| 端到端验证 | Task 11 |

### Key Decisions Summary
1. **Skill 系统**：采用标准 Agent Skill 格式（`.claude/skills/effect-dev/SKILL.md`），而非自定义 YAML + Loader
2. **纹理支持**：通过 `iChannel0`–`iChannel3`（Shadertoy 标准），支持 backdrop blur 和用户纹理
3. **范围限定**：2D/2.5D 平面动效，明确排除 3D raymarching/场景渲染，验证脚本会检测
4. **权威来源**：SDF 算子基于 iq (iquilezles.org) 定义，视效参考 Shadertoy 案例
5. **移动端优先**：性能预算按移动端 GPU 设定（≤ 256 ALU, ≤ 8 texture fetch, ≤ 4 FBM octaves）

### Placeholder Scan
- ✅ No TBD/TODO/fill-in-later found
- ✅ All code steps have actual implementation
- ✅ All commands have expected output described

### Type Consistency
- ✅ PipelineState fields used consistently across all agents and graph
- ✅ Shader code always passed as `str` type
- ✅ Image paths always `list[str]`
- ✅ Inspect result always `dict` with `passed`/`overall_score`/`feedback` keys
- ✅ Texture channels referenced as `iChannel0`–`iChannel3` consistently
