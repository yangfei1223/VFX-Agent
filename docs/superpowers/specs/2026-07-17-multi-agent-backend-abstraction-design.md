# Multi-Agent Backend Abstraction Design

**Date**: 2026-07-17
**Branch**: `feat/backend-ext` (base: `v2.0/codex-od` @ `ce470e6`)
**Scope**: L3-revised — codex refactor + Claude Code adapter (OpenCode reserved)

---

## 1. Goals

把当前 v2.0 orchestrator 硬编码的 codex CLI 调用抽象为统一的 `AgentBackend` interface，让多个 agent runtime 可插拔。**兑现 README 承诺的"后端可插拔：当前 MVP 用 codex CLI，架构上可替换为其他支持 agent skills 标准的流行多 agent 后端"**。

### In scope

- 定义 `AgentBackend` ABC + 统一 `AgentEvent` schema
- 把现有 `orchestrator.py` 的 codex-specific 私有方法 refactor 为 `CodexBackend` 类（行为 100% 保持）
- 新增 `ClaudeCodeBackend` 适配器（接 DeepSeek-v4-pro 主模型 + 智谱 zai-mcp-server 多模态）
- Backend 选择支持 **per-pipeline**（POST /run body 字段），同时 SettingsPanel 提供 **全局默认值**
- Capability Discovery Protocol：让 agent 自发现多模态能力（不写死 backend 分支）
- SettingsPanel 扩展为完整配置面板（Backend / Pipeline / Render / System 四组）
- E2E 验收：codex 抽样回归（delta <0.05 vs v2.0.1）+ Claude Code 5-10 sample smoke

### Out of scope (reserved for future)

- OpenCode adapter（等 `opencode run --format json` 修了 subagent 事件过滤 bug + `opencode serve` 修了 hang bug 再加）
- acpx CLI 集成（不修复 OpenCode 本身 bug，本次无收益）
- 跨 backend cross-validation（一个 pipeline 顺序跑多 backend 评分）
- Token budget circuit-breaker / Reflexion 学习闭环（独立 spec）

---

## 2. Current State (Why Refactor)

`backend/app/orchestrator.py` (~304 lines) 硬编码了 5 处 codex-specific 细节：

| 位置 | 硬编码内容 |
|---|---|
| `_setup_codex_workspace` (137-156) | `AGENTS.md` + `skills/` symlink 在 workdir 根（codex discovery 规则） |
| `_spawn_and_stream` cmd 构造 (173-184) | `codex exec --json --yolo --skip-git-repo-check --ephemeral --disable plugins -C workdir -i img -` |
| env 构造 (186-190) | `HTTP_PROXY` / `HTTPS_PROXY` |
| `CodexEvent` 类 (16-23) | JSONL schema：`type` / `item` / `usage` 字段 |
| 终止判断 (82) | `event.type == "turn.completed"` |

`config.py` 也硬编码：`codex_proxy` / `codex_timeout` 字段。`state_store.py` 的 `PipelineRecord` 没有 backend 字段（v2.0.1 之前默认即 codex）。

### 实际 backend 栈事实（基于 `~/.codex/config.toml` + `~/.claude/settings.json` 调研）

| 维度 | codex backend | claude-code backend |
|---|---|---|
| Agent runtime | codex CLI 0.144.1 | Claude Code CLI 2.1.196 |
| **主模型** | **OpenAI `gpt-5.6-sol`** | **DeepSeek `deepseek-v4-pro`**（via `api.deepseek.com/anthropic`） |
| 多模态能力 | **GPT-5.6 原生** ✅ | **DeepSeek 无原生** ❌ |
| 多模态来源 | CLI `-i` flag → 直接进 context | **必须调 MCP tool** `zai-mcp-server_analyze_image`（智谱 GLM 提供） |
| Subagent 机制 | `spawn_agent(fork_turns="none")` | Task tool（默认 fresh context） |
| Subagent 模型 | gpt-5.6-sol（同主模型） | DeepSeek-v4-pro（同主模型） |

> 注：AGENTS.md 里 `CODEX_MODEL=gemini-2.5-flash` 是 v1.0 时代残留（v1.0 LangGraph 三 Agent 直调 Gemini），与 v2.0 codex CLI 无关。

---

## 3. Architecture

### File structure (additions + changes)

```
backend/app/
├── orchestrator.py              [改] 从硬编码 codex → 调 backend interface
├── backends/                    [新]
│   ├── __init__.py              [新] BACKEND_REGISTRY + get_backend() factory
│   ├── base.py                  [新] BaseBackend ABC + AgentEvent TypedDict
│   ├── codex.py                 [新] CodexBackend（refactor 自现有 orchestrator）
│   └── claude_code.py           [新] ClaudeCodeBackend
├── state_store.py               [改] PipelineRecord 加 backend 字段（向后兼容默认 "codex"）
├── routers/
│   ├── pipeline.py              [改] POST /run 接受 backend 字段
│   └── config.py                [改] RuntimeConfig 加 backend 配置 + 删 v1.0 残留
└── config.py                    [改] per-backend proxy/timeout 字段

backend/tests/unit/
├── test_backends_base.py        [新] ABC 契约 + AgentEvent schema
├── test_codex_backend.py        [新] CodexBackend.parse_event 单测
├── test_claude_code_backend.py  [新] ClaudeCodeBackend.parse_event 单测
├── test_backend_registry.py     [新] get_backend() factory
└── test_state_store.py          [扩展] 向后兼容（无 backend 字段的老 JSON）

backend/tests/e2e/
└── run_v2_samples_via_ui.py     [改] 加 --backend 参数

frontend/src/components/
└── SettingsPanel.tsx            [改] 扩展为完整配置面板（4 组）
```

### Data flow

```
POST /run { samples, backend: "claude-code" }
    │
    ▼
PipelineOrchestrator.run(pipeline_id, workdir, keyframes, notes, backend_name)
    │
    ├── backend = BackendRegistry.get(backend_name)            # 工厂
    ├── backend.setup_workspace(workdir, skills_src)           # 多态
    ├── cmd = backend.build_command(workdir, prompt, ...)      # 多态
    ├── env = backend.build_env(base_env, proxy)               # 多态
    ├── subprocess.spawn(cmd, env, cwd=workdir)                # 基类统一
    ├── async for raw_line in proc.stdout:
    │       event = backend.parse_event(json.loads(raw_line))  # 多态
    │       yield event
    └── event.type == "completed" → break
    │
    ▼
PipelineRecord(backend="claude-code", ...) → StateStore.save()
```

**关键 invariant**：orchestrator 完全 backend-agnostic，所有 codex/claude-code 差异封装在 backend class 里。新增 backend = 加一个文件 + registry 加一行，orchestrator 主流程不动。

---

## 4. AgentBackend Interface

**Design pattern**: Template Method. Backend 差异封装在 3 个 abstract method；subprocess 生命周期由 `BaseBackend` 基类统一管理。orchestrator 只 `async for event in backend.stream(...)`。

### `backend/app/backends/base.py`

```python
from abc import ABC, abstractmethod
from pathlib import Path
from typing import AsyncIterator, Literal, Optional, TypedDict


class AgentEvent(TypedDict):
    """统一 backend 事件 schema，覆盖所有 backend 事件类型。"""
    type: Literal["text", "tool_call", "tool_result", "error", "completed"]
    content: str           # human-readable summary
    usage: Optional[dict]  # token usage（若 backend 提供）
    raw: dict              # 原始 JSONL 事件，debugging / events[] 持久化用


class BaseBackend(ABC):
    """Agent backend adapter 抽象基类（Template Method 模式）。

    子类只 override 3 个差异方法；subprocess lifecycle 由基类统一管理。
    """

    name: str = ""                 # "codex" | "claude-code"
    proxy: Optional[str] = None
    timeout_seconds: int = 600

    # ----------------------------------------------------------------
    # Abstract: 子类必须实现
    # ----------------------------------------------------------------

    @abstractmethod
    def setup_workspace(self, workdir: Path, skills_src: Path) -> None:
        """准备 backend-specific workspace（symlinks / config files）。"""

    @abstractmethod
    def build_command(
        self, workdir: Path, prompt: str, keyframes: list[str],
    ) -> list[str]:
        """构造 backend CLI 命令 list（不含 cwd，cwd 由 stream() 通过 subprocess 参数设）。"""

    @abstractmethod
    def parse_event(self, raw: dict) -> AgentEvent:
        """把 backend-specific JSONL event 转为统一 AgentEvent schema。"""

    # ----------------------------------------------------------------
    # Concrete: 基类统一实现
    # ----------------------------------------------------------------

    def build_env(self, base_env: dict) -> dict:
        env = {**base_env}
        if self.proxy:
            env["HTTP_PROXY"] = self.proxy
            env["HTTPS_PROXY"] = self.proxy
        return env

    async def stream(
        self, workdir: Path, prompt: str, keyframes: list[str],
        base_env: dict,
    ) -> AsyncIterator[AgentEvent]:
        """Template Method：subprocess + JSONL streaming + 硬超时。"""
        cmd = self.build_command(workdir, prompt, keyframes)
        env = self.build_env(base_env)
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(workdir),                                    # 关键：CLI 从 workdir 启动
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        # stdin write prompt / close
        # async with asyncio.timeout(self.timeout_seconds):
        #     async for line in proc.stdout:
        #         raw = json.loads(line)
        #         yield self.parse_event(raw)
        #     await proc.wait()
        #     check returncode → raise RuntimeError on !=0
        # except asyncio.TimeoutError: proc.terminate() → kill → raise
```

### AgentEvent type mapping

| 统一 type | codex 原事件 | claude-code 原事件 | 含义 |
|---|---|---|---|
| `text` | `{type: "message", item: {content}}` | `{type: "assistant", message: {content: [{type:"text", text}]}}` | agent 输出文本 |
| `tool_call` | `{type: "function_call", item: {name, arguments}}` | `{type: "assistant", message: {content: [{type:"tool_use", ...}]}}` | agent 调工具 |
| `tool_result` | `{type: "function_call_output", ...}` | `{type: "user", message: {content: [{type:"tool_result", ...}]}}` | 工具结果 |
| `error` | `{type: "error", ...}` | `{type: "system", subtype: "error"}` | 错误 |
| `completed` | `{type: "turn.completed", usage}` | `{type: "result", usage}` | 终止信号（带 usage） |

未知事件 → `{type: "text", content: "", raw: ...}`（保留 raw 不丢，但 type 标记为 fallback）。

### Design trade-offs

| 决策 | 选择 | 理由 |
|---|---|---|
| ABC vs Protocol | ABC | 强制子类实现契约，新增 backend 编译期可见遗漏 |
| subprocess 在 backend vs orchestrator | 在 backend（基类 Template Method） | 差异内聚、orchestrator 完全 agnostic |
| AgentEvent type 数量 | 5 种 | 覆盖核心场景又不爆炸；未知事件 fallback 到 text |
| `cwd` 传递方式 | subprocess `cwd=` 参数 | Claude Code 顶级 CLI 没有 `--cwd` flag（lib-5 verified），必须用 subprocess 参数 |
| 多模态差异处理 | Capability Discovery Protocol（agent 自发现） | 避免在 SKILL.md 写 backend 硬分支，新 backend 零文档改动 |

---

## 5. CodexBackend (Refactor)

**Refactor 策略：行为 100% 保持**，把现有 `orchestrator.py` 的 codex-specific 私有方法机械搬到 `backends/codex.py`：

| 现有 orchestrator 私有方法 | → CodexBackend 方法 |
|---|---|
| `_setup_codex_workspace(workdir)` (137-156) | `setup_workspace(workdir, skills_src)` |
| `_spawn_and_stream` cmd 构造 (173-184) | `build_command(workdir, prompt, keyframes)` |
| env 构造 (186-190) | `build_env(base_env)`（基类已实现，无需 override） |
| `CodexEvent` 类 (16-23) | `parse_event(raw) -> AgentEvent` |

### `backend/app/backends/codex.py` 骨架

```python
class CodexBackend(BaseBackend):
    name = "codex"

    def setup_workspace(self, workdir: Path, skills_src: Path) -> None:
        # 同现有 _setup_codex_workspace，symlink skills/ + AGENTS.md 到 workdir 根
        ...

    def build_command(self, workdir, prompt, keyframes) -> list[str]:
        cmd = [
            "codex", "exec",
            "--json", "--yolo", "--skip-git-repo-check",
            "--ephemeral", "--disable", "plugins",
            "-C", str(workdir),
        ]
        for img in keyframes:
            cmd.extend(["-i", img])
        cmd.append("-")  # read prompt from stdin
        return cmd

    def parse_event(self, raw: dict) -> AgentEvent:
        t = raw.get("type", "")
        if t == "turn.completed":
            return {"type": "completed", "content": "", "usage": raw.get("usage"), "raw": raw}
        elif t == "message":
            return {"type": "text", "content": raw.get("item", {}).get("content", ""), "usage": None, "raw": raw}
        elif t == "function_call":
            return {"type": "tool_call", "content": raw.get("item", {}).get("name", ""), "usage": None, "raw": raw}
        elif t == "function_call_output":
            return {"type": "tool_result", "content": "", "usage": None, "raw": raw}
        elif t == "error":
            return {"type": "error", "content": str(raw), "usage": None, "raw": raw}
        else:
            return {"type": "text", "content": "", "usage": None, "raw": raw}
```

**回归保证**：50-sample benchmark 抽样 5-10 个跑回归，与 v2.0.1 baseline delta <0.05 视为无损。

---

## 6. ClaudeCodeBackend (New)

### Key facts (from lib-5 verified)

- Claude Code CLI 顶级**没有 `--cwd` flag**，必须 subprocess `cwd=workdir` 参数
- `--permission-mode acceptEdits` 只批编辑操作，Bash 仍需 confirm → VFX-Agent pipeline 大量用 Bash（FFmpeg/Playwright），必须用 `bypassPermissions`
- `--output-format stream-json` + `--verbose` 是 streaming 必需组合
- Subagent 默认 fresh context，等价 codex `fork_turns="none"`
- 不原生读 `AGENTS.md`，必须 `CLAUDE.md`（或 `@AGENTS.md` import）

### `backend/app/backends/claude_code.py` 骨架

```python
class ClaudeCodeBackend(BaseBackend):
    name = "claude-code"

    def setup_workspace(self, workdir: Path, skills_src: Path) -> None:
        # 1. skills/ symlink（两 backend 共用）
        (workdir / "skills").symlink_to(skills_src.absolute(), target_is_directory=True)
        # 2. AGENTS.md（codex/OpenCode 发现，按 backend 区分但不影响 claude-code）
        (workdir / "AGENTS.md").symlink_to((skills_src / "AGENTS.md").resolve())
        # 3. CLAUDE.md（Claude Code 发现，内容同 AGENTS.md）
        (workdir / "CLAUDE.md").symlink_to((skills_src / "AGENTS.md").resolve())

    def build_command(self, workdir, prompt, keyframes) -> list[str]:
        # 注意：workdir 通过 subprocess cwd= 参数传，不放在 cmd 里
        # 图片不传 flag，由 agent 自身通过 Capability Discovery 协议处理
        cmd = [
            "claude", "-p", prompt,
            "--output-format", "stream-json",
            "--verbose",
            "--permission-mode", "bypassPermissions",
            "--allowedTools", "Bash,Read,Write,Edit,Glob,Grep,Task",
        ]
        return cmd

    def parse_event(self, raw: dict) -> AgentEvent:
        t = raw.get("type", "")
        if t == "result":
            return {"type": "completed", "content": "", "usage": raw.get("usage"), "raw": raw}
        elif t == "assistant":
            blocks = raw.get("message", {}).get("content", [])
            tools = [b for b in blocks if b.get("type") == "tool_use"]
            if tools:
                return {"type": "tool_call",
                        "content": ", ".join(b["name"] for b in tools),
                        "usage": None, "raw": raw}
            texts = [b["text"] for b in blocks if b.get("type") == "text"]
            return {"type": "text", "content": "\n".join(texts), "usage": None, "raw": raw}
        elif t == "user":
            return {"type": "tool_result", "content": "", "usage": None, "raw": raw}
        elif t == "system" and raw.get("subtype") == "error":
            return {"type": "error", "content": str(raw), "usage": None, "raw": raw}
        else:
            return {"type": "text", "content": "", "usage": None, "raw": raw}
```

### Subagent 评分

Claude Code Task tool 默认 fresh context（lib-4 verified），等价 codex `fork_turns="none"`。`--allowedTools` 列表含 `Task` 让 Phase 5 evaluator 能 spawn。SKILL.md 里 Phase 5 指令改成"Use Task tool to spawn an evaluator subagent with both image paths"，agent 自己适配。

---

## 7. Capability Discovery Protocol

**核心思想**：让 agent 自发现多模态能力，**不在 SKILL.md 写 backend 硬分支**。

### Why not hardcoded if/else

写 `if you are codex do X, if you are claude-code do Y` 等于把硬编码路由从 orchestrator 搬到 SKILL.md。每加一个 backend 就要改 SKILL.md 加分支，违背 agnostic 哲学。

### SKILL.md Phase 1 改写

```markdown
## Phase 1: Analyse keyframes

### Step 1: Establish Vision Capability

You need to "see" the keyframes. Try these in order until one works:

1. **Native multimodal**: Are keyframe images already visible in your context
   (passed as image content blocks)?
   → If YES: proceed to Step 2 with direct visual access.

2. **Discover image tools**: If NO native vision, probe your available tools:
   - List tools you can call
   - Find any tool that accepts an image path/source parameter
     (common patterns: `*analyze_image*`, `*view_image*`,
      `*describe_image*`, `*understand*image*`)
   - Call the discovered tool for each keyframe at:
     /abs/path/to/keyframe_001.png
     /abs/path/to/keyframe_002.png
     ...
   - Use returned descriptions as your "vision"

3. **Fail loudly**: If neither works, write
   `{"status": "failed", "reason": "no_multimodal_capability"}`
   to visual_description.json and stop. Do NOT fabricate descriptions.

### Step 2: Analysis (regardless of how you got vision)
... [existing visual analysis instructions unchanged]
```

### Phase 5 evaluator 同样走能力发现链

Evaluator subagent 收到 reference + render 两张图路径，同样按 Step 1 协议建立 vision，再比对。

### Expected behavior per backend

| Backend | Step 1 outcome |
|---|---|
| codex (GPT-5.6 原生多模态) | Step 1.1 成功（images 通过 `-i` flag 已在 context） |
| claude-code (DeepSeek 无多模态) | Step 1.1 失败 → Step 1.2 probe → 调 `zai-mcp-server_analyze_image` |
| 未来 OpenCode | 自动适配（agent 自己 probe） |

### Fail loudly invariant

`visual_description.json` 含 `{"status": "failed", "reason": "no_multimodal_capability"}` 时，orchestrator 读到 → 标 `PipelineStatus.FAILED` + record.error。**绝不**让 agent 编造描述蒙混过关。

---

## 8. Orchestrator + API + State Changes

### 8.1 Backend Registry

```python
# backend/app/backends/__init__.py
from .base import BaseBackend, AgentEvent
from .codex import CodexBackend
from .claude_code import ClaudeCodeBackend

BACKEND_REGISTRY: dict[str, type[BaseBackend]] = {
    "codex": CodexBackend,
    "claude-code": ClaudeCodeBackend,
}

def get_backend(name: str, *, proxy: str | None, timeout_seconds: int) -> BaseBackend:
    cls = BACKEND_REGISTRY.get(name)
    if not cls:
        raise ValueError(f"unknown backend '{name}', available: {list(BACKEND_REGISTRY)}")
    return cls(proxy=proxy, timeout_seconds=timeout_seconds)
```

### 8.2 orchestrator.run() signature

```python
async def run(
    self,
    pipeline_id: str,
    workdir: Path | str,
    keyframes: list[str],
    notes: str,
    max_iterations: int = 3,
    backend_name: str = "codex",  # NEW，default 保证向后兼容
) -> PipelineRecord:
    backend = get_backend(
        backend_name,
        proxy=settings.backend_proxy(backend_name),
        timeout_seconds=settings.backend_timeout(backend_name),
    )
    # 后续全是 backend.setup_workspace(...) / backend.stream(...) 多态调用
    # orchestrator 主流程零 backend-aware
```

### 8.3 POST /run API

```python
class RunRequest(BaseModel):
    sample_name: str
    backend: str = "codex"  # default，旧 client 不传字段时仍走 codex
    notes: str | None = None
    max_iterations: int = 3
```

### 8.4 PipelineRecord schema (backward compatible)

```python
class PipelineRecord(BaseModel):
    pipeline_id: str
    backend: str = "codex"     # NEW，default 保证老 JSON 无歧义
    status: PipelineStatus
    workdir: str
    keyframe_paths: list[str]
    final_shader: str = ""
    final_score: float = 0.0
    evaluation: dict | None = None
    codex_usage: dict | None = None  # 字段名保留（向后兼容），实际含义是 backend_usage
    events: list[dict] = []
    error: str | None = None
    duration_ms: int = 0
```

老 JSON（v2.0.1 baseline）无 `backend` 字段，Pydantic 自动用 default "codex"。

### 8.5 config.py

```python
class Settings(BaseSettings):
    # 全局
    proxy: str = ""
    host: str = "0.0.0.0"
    port: int = 8000
    frontend_url: str = "http://localhost:5173"

    # 通用 pipeline
    max_iterations: int = 5
    passing_score: float = 0.85
    workdir_root: str = "/tmp/vfx_workdirs"

    # 截图
    screenshot_width: int = 1280
    screenshot_height: int = 720
    render_timeout_ms: int = 2000

    # Per-backend（命名约定：{backend}_proxy / {backend}_timeout）
    codex_proxy: str = "http://127.0.0.1:7890"
    codex_timeout: int = 600
    claude_code_proxy: str = ""        # Claude Code 已用 anthropic-compatible proxy
    claude_code_timeout: int = 600

    def backend_proxy(self, name: str) -> str:
        return getattr(self, f"{name}_proxy", "")

    def backend_timeout(self, name: str) -> int:
        return getattr(self, f"{name}_timeout", 600)

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}
```

未来加 OpenCodeBackend 只需加 `opencode_proxy` / `opencode_timeout`。

### 8.6 RuntimeConfig 扩展（routers/config.py）

```python
class RuntimeConfig(BaseModel):
    # ── Backend ──
    backend: Literal["codex", "claude-code"] = "codex"
    codex_proxy: str = "http://127.0.0.1:7890"
    codex_timeout: int = Field(default=600, ge=60, le=3600)
    claude_code_proxy: str = ""
    claude_code_timeout: int = Field(default=600, ge=60, le=3600)

    # ── Pipeline ──
    max_iterations: int = Field(default=5, ge=1, le=100)
    passing_threshold: float = Field(default=0.85, ge=0.5, le=1.0)

    # ── Render ──
    render_timeout_ms: int = Field(default=2000, ge=500, le=10000)
    screenshot_width: int = Field(default=1280, ge=256, le=2048)
    screenshot_height: int = Field(default=720, ge=256, le=2048)

    # ── System ──
    workdir_root: str = "/tmp/vfx_workdirs"

    # ❌ 删除 v1.0 残留：re_decompose_threshold / gradient_window_size /
    #    stagnation_variance / stagnation_window / decompose_agent /
    #    generate_agent / inspect_agent（AgentModelConfig）
```

**配置源优先级**（低 → 高）：

| Source | Purpose |
|---|---|
| `backend/.env` | 初始默认（部署时配） |
| `app/config/runtime_config.json` | SettingsPanel 持久化的运行时配置 |
| `GET /config` 返回 | 当前生效值（给 SettingsPanel 显示） |
| `POST /run` body 字段 | per-pipeline override |

启动流程：先读 `.env` → override 自 `runtime_config.json`（如果存在）。

---

## 9. SettingsPanel Extension

### Configuration groups

```
┌─ Backend ─────────────────────────────────────┐
│ Default backend      [codex ▼]                │  下拉 codex / claude-code
│ Codex proxy          [http://127.0.0.1:7890]  │  文本
│ Codex timeout        [600] seconds            │  数字
│ Claude Code proxy    []                       │  文本（空 = 直连）
│ Claude Code timeout  [600] seconds            │  数字
└───────────────────────────────────────────────┘

┌─ Pipeline ────────────────────────────────────┐
│ Max iterations       [3]   (slider 1-100)     │
│ Passing score        [0.85] (slider 0.5-1.0)  │
└───────────────────────────────────────────────┘

┌─ Render & Screenshot ─────────────────────────┐
│ Screenshot width     [1280] (256-2048)        │
│ Screenshot height    [720]  (256-2048)        │
│ Render timeout       [2000] ms (500-10000)    │
└───────────────────────────────────────────────┘

┌─ System ──────────────────────────────────────┐
│ Workdir root         [/tmp/vfx_workdirs]      │  文本
└───────────────────────────────────────────────┘
```

**作用域**：SettingsPanel 配置**全局默认值**；POST /run 仍可传 backend 字段 override（e.g. 临时切 backend 跑一个 sample 不改全局）。

### Implementation note

复用现有 SettingsPanel.tsx (312 lines) 的滑块 / input / 分组 UI 风格，扩展为 4 个配置组 + 12 个字段。保留 "Apply / Defaults / Cancel" 底部按钮，字段编辑后实时验证（数字范围、URL 格式）。预估 ~150-200 行 TSX 改动（在现有 312 行基础上扩展）。

---

## 10. Error Handling Matrix

| 失败模式 | 检测点 | 处理 | PipelineRecord.status |
|---|---|---|---|
| backend 名不存在 | `get_backend()` lookup | 抛 `ValueError`，pipeline 启动前 fail | (未启动) |
| CLI 二进制不存在 | subprocess spawn raise `FileNotFoundError` | catch → record.error | `FAILED` |
| subprocess crash（exit ≠ 0） | `proc.returncode != 0` | 捕获 stderr 末尾 2000 字符 → record.error | `FAILED` |
| 硬超时 | `asyncio.timeout(seconds)` | terminate → wait 10s → kill | `TIMEOUT` |
| 输出文件缺失 | `_read_file()` / `_read_json()` 返回空 | 仍读已生成的 partial 输出 | `FAILED` 或 `MAX_ITERATIONS` |
| 未知事件类型 | `parse_event()` fallback 分支 | `AgentEvent.type="text"`，`raw` 保留 | (不影响 status) |
| **多模态能力缺失** | `visual_description.json` 含 `{"status":"failed","reason":"no_multimodal_capability"}` | orchestrator 读到 → record.error | `FAILED` |
| Subagent spawn 失败 | evaluation.json 不存在 | 沿用现有"has shader but no evaluation → FAILED"分支 | `FAILED` |

**核心原则**（沿用现有 orchestrator）：timeout / error 后**不立即 return**，仍尝试读已生成的 partial 输出。如果 partial 输出里 final_shader + evaluation 都齐全且 score 通过，**仍标为 PASSED**（timeout irrelevant if passed）。

---

## 11. Testing Matrix

### Unit tests (no external deps)

| File | Coverage |
|---|---|
| `test_backends_base.py` | BaseBackend ABC 契约（子类必须实现 3 method）+ AgentEvent TypedDict schema 验证 |
| `test_codex_backend.py` | Fixture JSONL 验证 `CodexBackend.parse_event` 5 type 映射 + 未知事件 fallback |
| `test_claude_code_backend.py` | Fixture stream-json 验证 `ClaudeCodeBackend.parse_event` 5 type 映射 + 未知事件 fallback |
| `test_backend_registry.py` | `get_backend("codex")` / `("claude-code")` / `("unknown")` → ValueError |
| `test_state_store.py` (扩展) | 老 JSON（无 backend 字段）→ 默认 "codex"；写新 JSON 含 backend |
| `test_orchestrator.py` (扩展) | orchestrator.run() 接受 backend_name 参数；mock backend 验证多态调用 |

**Fixture 来源**：从现有 50-sample benchmark 抽真实 codex JSONL；claude-code stream-json 用 lib-5 调研样例（手写 minimal fixture）。

### E2E smoke (需后端 + CLI + API key)

| Test | Scope | Acceptance |
|---|---|---|
| **Codex 回归** | 抽 5-10 个代表性 sample（覆盖 simple/medium/complex + 多 effect_type）跑 `--backend codex` | 与 v2.0.1 baseline 对比，同 sample score delta <0.05 |
| **Claude Code smoke** | 同 5-10 sample 跑 `--backend claude-code` | 不要求 baseline 对齐，只要求：(a) pipeline 跑通不 crash；(b) ≥50% sample 产出可用 shader（编译通过 + 渲染非全黑）；(c) ≥30% sample 产出有效 evaluation.json |
| **Capability Discovery 验证**（claude-code only） | 抽 1-2 sample 单独验证 | `visual_description.json` 必须含有效视效描述（证明 agent 成功 probe 到 `zai-mcp-server_analyze_image`） |

### Acceptance gate

| 维度 | 通过线 |
|---|---|
| 单元测试 | 全部 pass（含 fixture 驱动的 event parsing） |
| Codex 回归 | 抽样 delta <0.05 vs v2.0.1 baseline |
| Claude Code smoke | 5-10 sample 中 ≥50% 产出可用 shader + ≥30% 产出有效 evaluation |
| Capability Discovery | claude-code 至少 1 sample 的 visual_description.json 证明 agent 调用了 MCP analyze_image tool |
| PipelineRecord 向后兼容 | 老 JSON（无 backend 字段）能正常被 collect_v2_results.py 读取 |

---

## 12. Security Notes

### API key exposure incident (during brainstorming)

调研过程中 `~/.codex/config.toml` 和 `~/.claude.json` 输出泄露了两个真实 API key：

| Key | Source | Status |
|---|---|---|
| 智谱 `Z_AI_API_KEY` (`f21aeac78bd747828fbd3bcbb1e932cc.yfkKoZOIqWWmbPzW`) | `~/.claude.json` mcpServers.zai-mcp-server.env | **需要 rotate** |
| 智谱 `ANTHROPIC_AUTH_TOKEN` (`d76ce2149ed1454d83bc9fe1413b54fb.a4kQF3PlsFCkNFrI`) | `~/.codex/config.toml` shell_environment_policy.set | **需要 rotate** |

后续所有配置查询必须强制脱敏（regex 覆盖 `sk-*` / `*.key` / `Bearer *` / `<hex>.<base64>` 智谱格式）。

---

## 13. References

- **lib-4 调研报告**（多 agent backend 集成方式）：覆盖 codex/Claude Code/OpenCode headless 模式 + acpx 协议事实
- **lib-5 调研报告**（Claude Code CLAUDE.md 加载机制）：覆盖 `--cwd` flag 不存在 / `--permission-mode bypassPermissions` / SKILL.md 路径严格要求 / AGENTS.md 不兼容
- **现有 v2.0 设计文档**：`docs/superpowers/specs/2026-07-13-vfx-agent-v2-codex-od-design.md`
- **Loop Engineering skill 对照分析**（ora-3 / ses_0a5a21bd8ffeErf6b5A2OX6Ybs）
- **acpx 协议**：https://github.com/openclaw/acpx （本次不集成）
- **Claude Code headless 文档**：https://code.claude.com/docs/en/headless
- **Claude Code memory 文档**：https://code.claude.com/docs/en/memory
- **Claude Code subagent 文档**：https://code.claude.com/docs/en/sub-agents

---

## 14. Open Questions (Deferred to Implementation)

这些不阻塞 spec 批准，留到 implementation 阶段 verify：

1. **Claude Code CLI 多模态图片传递**：lib-5 说"将图像作为提示中的文件路径传递"，但没说具体格式（绝对路径 vs `file://` URL vs base64）。Implementation 时用 1 个 sample smoke test 验证 agent 能正确读图。
2. **codex subagent 模型**：`~/.codex/config.toml` 的 `[shell_environment_policy.set]` 设了 ANTHROPIC_BASE_URL 桥接到智谱 GLM-5.1。codex 原生 `spawn_agent` 是否仍用主模型 gpt-5.6-sol？需 verify。
3. **codex config.toml 历史 trust 污染**：~100 个 `/private/tmp/vfx_workdirs/p*` 之前 benchmark 留下的 trust 记录，可能影响新 pipeline。Implementation 前 cleanup。
4. **Claude Code `--allowedTools` 完整列表**：当前列了 `Bash,Read,Write,Edit,Glob,Grep,Task`，可能还需要 `WebFetch` 或 MCP tools 显式 allow。Implementation 时按 codex 调用工具对比补全。
5. **Skill 文件 backend-neutral 化**：现有 AGENTS.md 含 `spawn_agent(fork_turns="none")` 等 codex-specific 语法，需泛化为"用你的 runtime 支持的 subagent 机制（codex: spawn_agent / claude-code: Task tool）"。

---

*Last updated: 2026-07-17*
