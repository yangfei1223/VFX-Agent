# Multi-Agent Backend Abstraction Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 把 v2.0 orchestrator 硬编码的 codex CLI 调用抽象为统一 `AgentBackend` interface，新增 `ClaudeCodeBackend` 适配器，兑现 README "后端可插拔" 承诺。

**Architecture:** Template Method 模式 —— `BaseBackend` 基类统一管 subprocess lifecycle，子类只 override 3 个差异方法（`setup_workspace` / `build_command` / `parse_event`）。orchestrator 完全 backend-agnostic。

**Tech Stack:** Python 3.11+ / FastAPI / Pydantic / asyncio / pytest / TypeScript / React 18

**Spec reference:** `docs/superpowers/specs/2026-07-17-multi-agent-backend-abstraction-design.md` (681 行，14 sections)

**Branch:** `feat/backend-ext` (current worktree)

---

## Plan Overview

14 tasks across 8 phases. Each task is TDD-driven with frequent commits.

| Phase | Tasks | Focus |
|---|---|---|
| 1. Foundation | T1-T2 | `BaseBackend` ABC + Registry |
| 2. Codex refactor | T3-T4 | `CodexBackend` + orchestrator 改造 |
| 3. Claude Code | T5 | `ClaudeCodeBackend` 新增 |
| 4. Skill rewrite | T6 | Capability Discovery Protocol |
| 5. Data + API | T7-T10 | state_store + config + POST /run |
| 6. Frontend | T11 | SettingsPanel 4 组扩展 |
| 7. E2E | T12 | run_v2_samples_via_ui.py `--backend` |
| 8. Acceptance | T13-T14 | Codex 回归 + Claude Code smoke |

---

## Task 1: Create `backends/base.py` (BaseBackend ABC + AgentEvent)

**Files:**
- Create: `backend/app/backends/__init__.py` (empty placeholder)
- Create: `backend/app/backends/base.py`
- Test: `backend/tests/unit/test_backends_base.py`

**Step 1: Write the failing test**

Create `backend/tests/unit/test_backends_base.py`:

```python
"""Tests for BaseBackend ABC and AgentEvent schema."""
import pytest
from app.backends.base import BaseBackend, AgentEvent
from pathlib import Path


def test_basebackend_is_abstract():
    """BaseBackend cannot be instantiated directly."""
    with pytest.raises(TypeError):
        BaseBackend()


def test_subclass_must_implement_three_methods():
    """Subclass missing any of 3 abstract methods fails to instantiate."""
    class Incomplete(BaseBackend):
        name = "incomplete"
        # missing setup_workspace / build_command / parse_event

    with pytest.raises(TypeError):
        Incomplete()


def test_subclass_with_all_methods_instantiates():
    """Complete subclass can instantiate."""
    class Complete(BaseBackend):
        name = "complete"

        def setup_workspace(self, workdir, skills_src):
            pass

        def build_command(self, workdir, prompt, keyframes):
            return ["echo", "hello"]

        def parse_event(self, raw):
            return {"type": "text", "content": "", "usage": None, "raw": raw}

    b = Complete(proxy="http://proxy:8080", timeout_seconds=300)
    assert b.name == "complete"
    assert b.proxy == "http://proxy:8080"
    assert b.timeout_seconds == 300


def test_build_env_adds_proxy():
    """build_env injects HTTP_PROXY / HTTPS_PROXY when proxy set."""
    class B(BaseBackend):
        name = "b"
        def setup_workspace(self, workdir, skills_src): pass
        def build_command(self, workdir, prompt, keyframes): return []
        def parse_event(self, raw): return {"type": "text", "content": "", "usage": None, "raw": raw}

    b = B(proxy="http://proxy:8080", timeout_seconds=60)
    env = b.build_env({"PATH": "/usr/bin"})
    assert env["HTTP_PROXY"] == "http://proxy:8080"
    assert env["HTTPS_PROXY"] == "http://proxy:8080"
    assert env["PATH"] == "/usr/bin"  # base env preserved


def test_build_env_no_proxy_when_empty():
    """build_env does not inject proxy vars when proxy is None."""
    class B(BaseBackend):
        name = "b"
        def setup_workspace(self, workdir, skills_src): pass
        def build_command(self, workdir, prompt, keyframes): return []
        def parse_event(self, raw): return {"type": "text", "content": "", "usage": None, "raw": raw}

    b = B(proxy=None, timeout_seconds=60)
    env = b.build_env({"PATH": "/usr/bin"})
    assert "HTTP_PROXY" not in env
    assert "HTTPS_PROXY" not in env


def test_agent_event_schema():
    """AgentEvent TypedDict accepts the 4 required fields with correct types."""
    event: AgentEvent = {
        "type": "text",
        "content": "hello",
        "usage": {"input_tokens": 100},
        "raw": {"original": "event"},
    }
    assert event["type"] == "text"
    assert event["content"] == "hello"
    assert event["usage"]["input_tokens"] == 100
    assert event["raw"]["original"] == "event"
```

**Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/unit/test_backends_base.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.backends'`

**Step 3: Create package + base.py**

Create `backend/app/backends/__init__.py` (empty for now):

```python
"""Agent backend adapters (codex / claude-code / future)."""
```

Create `backend/app/backends/base.py`:

```python
"""Base classes for agent backend abstraction.

Template Method pattern: BaseBackend provides concrete stream() / build_env();
subclasses override the 3 abstract methods (setup_workspace / build_command /
parse_event) to encapsulate per-backend differences.
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import AsyncIterator, Literal, Optional, TypedDict


class AgentEvent(TypedDict):
    """Unified backend event schema covering all backend event types.

    Fields:
        type: One of "text" | "tool_call" | "tool_result" | "error" | "completed".
              Unknown events fall back to "text" with raw preserved.
        content: Human-readable summary (may be empty).
        usage: Token usage dict if backend provides; None otherwise.
        raw: Original JSONL event dict, preserved for debugging / events[].
    """
    type: Literal["text", "tool_call", "tool_result", "error", "completed"]
    content: str
    usage: Optional[dict]
    raw: dict


class BaseBackend(ABC):
    """Agent backend adapter abstract base class.

    Subclasses MUST override 3 abstract methods. Subprocess lifecycle
    (spawn / stdin / stdout streaming / timeout / stderr capture) is provided
    by the concrete stream() method below; subclasses generally do not
    override stream() or build_env().
    """

    name: str = ""
    proxy: Optional[str] = None
    timeout_seconds: int = 600

    # ----------------------------------------------------------------
    # Abstract: subclasses MUST implement
    # ----------------------------------------------------------------

    @abstractmethod
    def setup_workspace(self, workdir: Path, skills_src: Path) -> None:
        """Prepare backend-specific workspace (symlinks / config files).

        Called by orchestrator before stream(). Idempotent (safe to call
        repeatedly; use `if not path.exists()` guards).
        """

    @abstractmethod
    def build_command(
        self, workdir: Path, prompt: str, keyframes: list[str],
    ) -> list[str]:
        """Construct backend CLI argv list.

        NOTE: workdir is passed via subprocess cwd= parameter in stream(),
        NOT included in the command. Subclasses should not add a --cwd flag.
        """

    @abstractmethod
    def parse_event(self, raw: dict) -> AgentEvent:
        """Convert backend-specific JSONL event to unified AgentEvent.

        Unknown events should fall back to {"type": "text", "content": "",
        "usage": None, "raw": raw} — never raise.
        """

    # ----------------------------------------------------------------
    # Concrete: base class provides default implementations
    # ----------------------------------------------------------------

    def build_env(self, base_env: dict) -> dict:
        """Construct env vars for subprocess. Override to add backend-specific vars."""
        env = {**base_env}
        if self.proxy:
            env["HTTP_PROXY"] = self.proxy
            env["HTTPS_PROXY"] = self.proxy
        return env

    async def stream(
        self, workdir: Path, prompt: str, keyframes: list[str],
        base_env: dict,
    ) -> AsyncIterator[AgentEvent]:
        """Template Method: subprocess + JSONL streaming + hard timeout.

        Uses asyncio.timeout (Python 3.11+). On timeout, terminates process
        gracefully (10s wait) then SIGKILLs. On non-zero exit code, raises
        RuntimeError with stderr tail.
        """
        import asyncio
        import json

        cmd = self.build_command(workdir, prompt, keyframes)
        env = self.build_env(base_env)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(workdir),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        # Write prompt to stdin (backend reads prompt from stdin via "-" or "-p")
        # NOTE: claude-code uses `-p "<prompt>"` in argv, so stdin write is a no-op
        # for claude-code; codex uses "-" to read prompt from stdin.
        if "-" in cmd:  # codex convention
            proc.stdin.write(prompt.encode())
            await proc.stdin.drain()
        if proc.stdin:
            proc.stdin.close()
            if hasattr(proc.stdin, "wait_closed"):
                try:
                    await proc.stdin.wait_closed()
                except Exception:
                    pass

        try:
            async with asyncio.timeout(self.timeout_seconds):
                async for line in proc.stdout:
                    line = line.decode().strip()
                    if not line:
                        continue
                    try:
                        raw = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    yield self.parse_event(raw)

                await proc.wait()

                stderr_bytes = await proc.stderr.read() if proc.stderr else b""
                stderr_text = stderr_bytes.decode(errors="replace") if stderr_bytes else ""
                if proc.returncode != 0:
                    raise RuntimeError(
                        f"{self.name} exited with code {proc.returncode}. "
                        f"stderr (last 2000 chars): ...{stderr_text[-2000:]}"
                    )
        except asyncio.TimeoutError:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=10)
            except asyncio.TimeoutError:
                proc.kill()
            raise
```

**Step 4: Run test to verify pass**

```bash
cd backend && python -m pytest tests/unit/test_backends_base.py -v
```

Expected: PASS (6 tests)

**Step 5: Commit**

```bash
git add backend/app/backends/__init__.py backend/app/backends/base.py backend/tests/unit/test_backends_base.py
git commit -m "feat(backends): add BaseBackend ABC + AgentEvent schema (T1)

Template Method pattern: BaseBackend provides concrete stream() / build_env();
subclasses override setup_workspace / build_command / parse_event."
```

---

## Task 2: Create `backends/__init__.py` Registry

**Files:**
- Modify: `backend/app/backends/__init__.py`
- Test: `backend/tests/unit/test_backend_registry.py`

**Step 1: Write the failing test**

Create `backend/tests/unit/test_backend_registry.py`:

```python
"""Tests for backend registry factory."""
import pytest
from app.backends import get_backend, BACKEND_REGISTRY
from app.backends.base import BaseBackend


def test_registry_initially_has_no_concrete_backends():
    """After T1, registry is empty (codex/claude-code added in T3/T5)."""
    # This test will be updated as we add backends in T3 and T5
    assert isinstance(BACKEND_REGISTRY, dict)


def test_get_backend_unknown_raises():
    with pytest.raises(ValueError, match="unknown backend 'nonexistent'"):
        get_backend("nonexistent", proxy=None, timeout_seconds=60)


def test_get_backend_returns_instance_with_kwargs():
    """After T3 adds CodexBackend, this should work. For now, expect ValueError."""
    # Will be filled in once CodexBackend is registered
    pass
```

**Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/unit/test_backend_registry.py -v
```

Expected: FAIL with `ImportError: cannot import name 'get_backend' from 'app.backends'`

**Step 3: Write the registry**

Modify `backend/app/backends/__init__.py`:

```python
"""Agent backend adapters (codex / claude-code / future).

Backend registration happens here. Adding a new backend = add a class +
register one line in BACKEND_REGISTRY. Orchestrator code never changes.
"""
from pathlib import Path
from typing import Optional

from .base import BaseBackend, AgentEvent

# Lazy registry: concrete backends are added as they're implemented (T3, T5).
# Type annotation makes it clear this is a class registry, not instances.
BACKEND_REGISTRY: dict[str, type[BaseBackend]] = {}


def register_backend(name: str, cls: type[BaseBackend]) -> None:
    """Register a backend class under a name. Idempotent."""
    if not issubclass(cls, BaseBackend):
        raise TypeError(f"{cls} must subclass BaseBackend")
    BACKEND_REGISTRY[name] = cls


def get_backend(
    name: str, *, proxy: Optional[str], timeout_seconds: int,
) -> BaseBackend:
    """Factory: instantiate a backend by name.

    Args:
        name: Backend identifier ("codex" | "claude-code" | future).
        proxy: HTTP/HTTPS proxy URL, or None for direct connection.
        timeout_seconds: Hard subprocess timeout.

    Raises:
        ValueError: If name is not in BACKEND_REGISTRY.
    """
    cls = BACKEND_REGISTRY.get(name)
    if not cls:
        available = list(BACKEND_REGISTRY.keys())
        raise ValueError(f"unknown backend '{name}', available: {available}")
    return cls(proxy=proxy, timeout_seconds=timeout_seconds)


__all__ = ["BaseBackend", "AgentEvent", "BACKEND_REGISTRY", "register_backend", "get_backend"]
```

**Step 4: Run test to verify pass**

```bash
cd backend && python -m pytest tests/unit/test_backend_registry.py -v
```

Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add backend/app/backends/__init__.py backend/tests/unit/test_backend_registry.py
git commit -m "feat(backends): add BACKEND_REGISTRY + get_backend factory (T2)"
```

---

## Task 3: Create `backends/codex.py` (CodexBackend refactor)

**Files:**
- Create: `backend/app/backends/codex.py`
- Modify: `backend/app/backends/__init__.py` (register CodexBackend)
- Test: `backend/tests/unit/test_codex_backend.py`

**Reference:** Existing `backend/app/orchestrator.py:16-23, 137-184` (the methods we're lifting).

**Step 1: Write the failing test**

Create `backend/tests/unit/test_codex_backend.py`:

```python
"""Tests for CodexBackend event parsing and command construction."""
from pathlib import Path
from app.backends.codex import CodexBackend


def test_codex_backend_name():
    b = CodexBackend(proxy=None, timeout_seconds=60)
    assert b.name == "codex"


def test_parse_event_completed():
    """turn.completed event → AgentEvent type=completed with usage."""
    b = CodexBackend(proxy=None, timeout_seconds=60)
    raw = {"type": "turn.completed", "usage": {"input_tokens": 100, "output_tokens": 50}}
    event = b.parse_event(raw)
    assert event["type"] == "completed"
    assert event["usage"] == {"input_tokens": 100, "output_tokens": 50}
    assert event["raw"] == raw


def test_parse_event_message():
    """message event → AgentEvent type=text with content extracted from item.content."""
    b = CodexBackend(proxy=None, timeout_seconds=60)
    raw = {"type": "message", "item": {"content": "Hello world"}}
    event = b.parse_event(raw)
    assert event["type"] == "text"
    assert event["content"] == "Hello world"
    assert event["usage"] is None


def test_parse_event_function_call():
    """function_call event → AgentEvent type=tool_call with content=item.name."""
    b = CodexBackend(proxy=None, timeout_seconds=60)
    raw = {"type": "function_call", "item": {"name": "shell", "arguments": "{}"}}
    event = b.parse_event(raw)
    assert event["type"] == "tool_call"
    assert event["content"] == "shell"


def test_parse_event_function_call_output():
    """function_call_output event → AgentEvent type=tool_result."""
    b = CodexBackend(proxy=None, timeout_seconds=60)
    raw = {"type": "function_call_output", "item": {"output": "result"}}
    event = b.parse_event(raw)
    assert event["type"] == "tool_result"


def test_parse_event_error():
    """error event → AgentEvent type=error."""
    b = CodexBackend(proxy=None, timeout_seconds=60)
    raw = {"type": "error", "message": "something broke"}
    event = b.parse_event(raw)
    assert event["type"] == "error"
    assert "something broke" in event["content"]


def test_parse_event_unknown_falls_back_to_text():
    """Unknown event type → AgentEvent type=text with empty content + raw preserved."""
    b = CodexBackend(proxy=None, timeout_seconds=60)
    raw = {"type": "some_unknown_type", "foo": "bar"}
    event = b.parse_event(raw)
    assert event["type"] == "text"
    assert event["content"] == ""
    assert event["raw"] == raw


def test_build_command_has_required_flags():
    """CodexBackend.build_command must include all required codex exec flags."""
    b = CodexBackend(proxy=None, timeout_seconds=60)
    cmd = b.build_command(Path("/tmp/wd"), "test prompt", ["/tmp/001.png"])
    assert cmd[0] == "codex"
    assert "exec" in cmd
    assert "--json" in cmd
    assert "--yolo" in cmd
    assert "--skip-git-repo-check" in cmd
    assert "--ephemeral" in cmd
    assert "--disable" in cmd
    assert "plugins" in cmd
    assert "-C" in cmd
    assert "/tmp/wd" in cmd
    assert "-i" in cmd
    assert "/tmp/001.png" in cmd
    assert cmd[-1] == "-"  # stdin marker


def test_build_command_multiple_keyframes():
    """Multiple keyframes → multiple -i flags."""
    b = CodexBackend(proxy=None, timeout_seconds=60)
    cmd = b.build_command(Path("/tmp/wd"), "p", ["/tmp/1.png", "/tmp/2.png", "/tmp/3.png"])
    assert cmd.count("-i") == 3


def test_setup_workspace_creates_symlinks(tmp_path):
    """setup_workspace symlinks AGENTS.md and skills/ at workdir root."""
    # Create fake skills_src
    skills_src = tmp_path / "fake_skills"
    skills_src.mkdir()
    (skills_src / "AGENTS.md").write_text("# Test AGENTS")
    (skills_src / "vfx-shader").mkdir()
    (skills_src / "vfx-shader" / "SKILL.md").write_text("# Skill")

    workdir = tmp_path / "workdir"
    workdir.mkdir()

    b = CodexBackend(proxy=None, timeout_seconds=60)
    b.setup_workspace(workdir, skills_src)

    assert (workdir / "AGENTS.md").is_symlink()
    assert (workdir / "skills").is_symlink()
    assert (workdir / "skills").resolve() == skills_src.resolve()


def test_setup_workspace_idempotent(tmp_path):
    """Calling setup_workspace twice doesn't error."""
    skills_src = tmp_path / "skills"
    skills_src.mkdir()
    (skills_src / "AGENTS.md").write_text("# Test")
    workdir = tmp_path / "wd"
    workdir.mkdir()

    b = CodexBackend(proxy=None, timeout_seconds=60)
    b.setup_workspace(workdir, skills_src)
    b.setup_workspace(workdir, skills_src)  # should not raise
```

**Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/unit/test_codex_backend.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.backends.codex'`

**Step 3: Implement CodexBackend**

Create `backend/app/backends/codex.py`:

```python
"""CodexBackend: wraps OpenAI codex CLI for headless agent execution.

Refactored from orchestrator.py private methods (_setup_codex_workspace,
_spawn_and_stream, CodexEvent). Behavior is 100% preserved — the only
change is structural (methods moved from orchestrator class to backend class).
"""
import os
from pathlib import Path

from .base import BaseBackend, AgentEvent
from . import register_backend


class CodexBackend(BaseBackend):
    """Adapter for OpenAI codex CLI (default backend, model=gpt-5.6-sol)."""

    name = "codex"

    def setup_workspace(self, workdir: Path, skills_src: Path) -> None:
        """Symlink skill assets into workdir root.

        Codex discovers AGENTS.md and skills/ from CWD root (workdir),
        NOT from workdir/.codex/. So we put symlinks at workdir root.
        """
        # Symlink skills/ at workdir root (codex discovers via CWD)
        skills_link = workdir / "skills"
        if not skills_link.exists():
            skills_link.symlink_to(skills_src.absolute(), target_is_directory=True)

        # Symlink top-level AGENTS.md at workdir root (codex primary discovery)
        agents_link = workdir / "AGENTS.md"
        if not agents_link.exists():
            agents_link.symlink_to((skills_src / "AGENTS.md").resolve())

    def build_command(
        self, workdir: Path, prompt: str, keyframes: list[str],
    ) -> list[str]:
        """Build `codex exec` argv. NOTE: workdir passed via subprocess cwd=, not in cmd."""
        cmd = [
            "codex", "exec",
            "--json",
            "--yolo",
            "--skip-git-repo-check",
            "--ephemeral",
            "--disable", "plugins",
            "-C", str(workdir),
        ]
        for img in keyframes:
            cmd.extend(["-i", img])
        cmd.append("-")  # read prompt from stdin
        return cmd

    def parse_event(self, raw: dict) -> AgentEvent:
        """Map codex JSONL event types to unified AgentEvent."""
        t = raw.get("type", "")
        if t == "turn.completed":
            return {
                "type": "completed",
                "content": "",
                "usage": raw.get("usage"),
                "raw": raw,
            }
        elif t == "message":
            return {
                "type": "text",
                "content": raw.get("item", {}).get("content", ""),
                "usage": None,
                "raw": raw,
            }
        elif t == "function_call":
            return {
                "type": "tool_call",
                "content": raw.get("item", {}).get("name", ""),
                "usage": None,
                "raw": raw,
            }
        elif t == "function_call_output":
            return {
                "type": "tool_result",
                "content": "",
                "usage": None,
                "raw": raw,
            }
        elif t == "error":
            return {
                "type": "error",
                "content": str(raw),
                "usage": None,
                "raw": raw,
            }
        # Unknown event fallback: preserve raw, mark as text
        return {
            "type": "text",
            "content": "",
            "usage": None,
            "raw": raw,
        }


# Auto-register on import
register_backend("codex", CodexBackend)
```

Modify `backend/app/backends/__init__.py` to import codex (triggers registration):

```python
# Add at end of file:
from . import codex as _codex  # noqa: F401 (triggers register_backend on import)
```

**Step 4: Run test to verify pass**

```bash
cd backend && python -m pytest tests/unit/test_codex_backend.py tests/unit/test_backend_registry.py -v
```

Expected: PASS (all codex tests + updated registry test)

Update `test_backend_registry.py` test_get_backend_returns_instance_with_kwargs:

```python
def test_get_backend_returns_instance_with_kwargs():
    """CodexBackend is registered after T3."""
    from app.backends.codex import CodexBackend
    b = get_backend("codex", proxy="http://proxy", timeout_seconds=300)
    assert isinstance(b, CodexBackend)
    assert b.proxy == "http://proxy"
    assert b.timeout_seconds == 300
```

**Step 5: Commit**

```bash
git add backend/app/backends/codex.py backend/app/backends/__init__.py backend/tests/unit/test_codex_backend.py backend/tests/unit/test_backend_registry.py
git commit -m "feat(backends): CodexBackend refactor from orchestrator (T3)

Behavior 100% preserved; methods moved from orchestrator.py private helpers
to CodexBackend class. Will be wired into orchestrator in T4."
```

---

## Task 4: Refactor orchestrator.py to use backend abstraction

**Files:**
- Modify: `backend/app/orchestrator.py` (replace codex-specific code with backend calls)
- Test: `backend/tests/unit/test_orchestrator.py` (existing; should still pass)
- Reference: `backend/app/orchestrator.py` current state (304 lines)

**Strategy:** Pure mechanical refactor. Replace `_setup_codex_workspace` / `_spawn_and_stream` / `CodexEvent` with `backend.setup_workspace` / `backend.stream`. Orchestrator no longer needs codex-specific code.

**Step 1: Read existing orchestrator.py to confirm test coverage**

```bash
cd backend && python -m pytest tests/unit/test_orchestrator.py -v
```

Expected: All existing tests PASS (baseline before refactor).

**Step 2: Refactor orchestrator.py**

Rewrite `backend/app/orchestrator.py`:

```python
"""Pipeline orchestrator (v2.0, multi-backend).

Minimal Python wrapper: prepares workdir, instantiates backend, streams events,
extracts outputs. Does NOT do phase switching / iteration control / scoring
(all delegated to backend agent via SKILL.md).
"""
import asyncio
import json
import time
from pathlib import Path
from typing import Optional

from app.state_store import PipelineStatus, PipelineRecord, StateStore
from app.backends import get_backend
from app.config import settings


class PipelineOrchestrator:
    """Main v2.0 pipeline runner (backend-agnostic).

    Lifecycle per sample:
        1. instantiate backend by name
        2. backend.setup_workspace (symlink skill assets)
        3. backend.stream (subprocess + JSONL events)
        4. extract final_shader.glsl + evaluation.json
        5. determine final status
    """

    PASSING_SCORE = 0.85

    async def run(
        self,
        pipeline_id: str,
        workdir: Path | str,
        keyframes: list[str],
        notes: str,
        max_iterations: int = 3,
        backend_name: str = "codex",  # NEW: per-pipeline backend selection
    ) -> PipelineRecord:
        """Run full v2.0 pipeline for one sample.

        Returns a PipelineRecord reflecting the final state.
        """
        start_time = time.monotonic()
        workdir = Path(workdir)

        # Resolve backend
        backend = get_backend(
            backend_name,
            proxy=settings.backend_proxy(backend_name),
            timeout_seconds=settings.backend_timeout(backend_name),
        )

        record = PipelineRecord(
            pipeline_id=pipeline_id,
            backend=backend_name,  # NEW: persist backend in record
            status=PipelineStatus.RUNNING,
            workdir=str(workdir),
            keyframe_paths=keyframes,
        )
        StateStore.save(record)

        try:
            # 1. Setup workspace (backend-specific symlinks)
            backend_root = Path(__file__).resolve().parent.parent
            skills_src = backend_root / "app" / "skills"
            if not skills_src.exists():
                raise RuntimeError(f"skills source not found: {skills_src}")
            backend.setup_workspace(workdir, skills_src)

            # 2. Build prompt + stream events
            user_prompt = self._build_user_prompt(keyframes, notes, max_iterations)
            events: list[dict] = []
            usage: Optional[dict] = None
            timeout_flag = False
            runtime_error: Optional[str] = None
            try:
                async for event in backend.stream(
                    workdir=workdir,
                    prompt=user_prompt,
                    keyframes=keyframes,
                    base_env=dict(__import__("os").environ),
                ):
                    events.append(event["raw"])
                    if event["type"] == "completed" and event.get("usage"):
                        usage = event["usage"]
                    record.events = events[-100:]
                    StateStore.save(record)
            except asyncio.TimeoutError:
                timeout_flag = True
                record.error = f"{backend_name} subprocess timed out (outputs may still be valid)"
            except RuntimeError as e:
                runtime_error = f"{backend_name} subprocess error: {e}"
                record.error = runtime_error

            # 3. Extract outputs (always, even on timeout/runtime error)
            record.final_shader = self._read_file(workdir / "final_shader.glsl") or \
                self._read_file(workdir / "shader.glsl", default="")
            evaluation = self._read_json(workdir / "evaluation.json")
            record.evaluation = evaluation
            record.codex_usage = usage  # field name kept for backward compat

            # 4. Determine status (logic unchanged from pre-refactor)
            if runtime_error and not record.final_shader:
                record.status = PipelineStatus.FAILED
            elif not record.final_shader:
                record.status = PipelineStatus.TIMEOUT if timeout_flag else PipelineStatus.FAILED
                if not record.error:
                    record.error = "no shader output written"
            elif evaluation is None:
                record.status = PipelineStatus.TIMEOUT if timeout_flag else PipelineStatus.FAILED
                if not record.error:
                    record.error = f"no evaluation.json written — {backend_name} did not complete workflow"
                record.final_score = 0.0
            else:
                record.final_score = evaluation.get("overall_score", 0.0)
                if record.final_score >= self.PASSING_SCORE:
                    record.status = PipelineStatus.PASSED
                    record.error = None
                else:
                    record.status = PipelineStatus.TIMEOUT if timeout_flag else PipelineStatus.MAX_ITERATIONS

            return record
        finally:
            record.duration_ms = int((time.monotonic() - start_time) * 1000)
            StateStore.save(record)

    def _build_user_prompt(
        self,
        keyframes: list[str],
        notes: str,
        max_iterations: int,
    ) -> str:
        """Build the user prompt passed to backend via stdin or argv."""
        keyframe_list = "\n".join(f"- {p}" for p in keyframes)
        return f"""You are running inside a VFX shader generation pipeline.

## Setup

Your working directory contains:
- `AGENTS.md` (auto-loaded) — project context and VFX terminology
- `CLAUDE.md` (auto-loaded for Claude Code) — same content as AGENTS.md
- `skills/vfx-shader/SKILL.md` — the 6-phase workflow you MUST follow
- `skills/vfx-shader/reference/` — shader templates + few-shot examples + scripts
- `keyframes/001.png`, `002.png`, ... — reference images ({len(keyframes)} provided)

## Your Task

1. FIRST: `Read skills/vfx-shader/SKILL.md` to understand the 6-phase workflow.
2. Then execute phases 1-6 in order:
   - Phase 1: Analyze keyframes → write `visual_description.json`
   - Phase 2: Generate → write `shader.glsl`
   - Phase 3: Validate via `python skills/vfx-shader/reference/scripts/validate_shader.py shader.glsl`
   - Phase 4: Render via `python skills/vfx-shader/reference/scripts/render_shader.py shader.glsl 2.0`
   - Phase 5: Spawn subagent evaluator with isolated context (MANDATORY — no self-eval)
   - Phase 6: If subagent score >= 0.85, finalize. Else iterate (max {max_iterations} times).

## Reference Images
{keyframe_list}

## User Notes
{notes or "(none)"}

## Output Requirements

When you finish (either passed or max_iterations reached), these files MUST exist:
- `visual_description.json`
- `shader.glsl` (latest version)
- `final_shader.glsl` (best version, copied from shader.glsl)
- `evaluation.json` (latest subagent evaluation)

## Critical Rules (from SKILL.md)

- NO self-evaluation in Phase 5. MUST spawn subagent (use your runtime's
  subagent mechanism: codex `spawn_agent(fork_turns="none")`, claude-code
  Task tool, or equivalent).
- NO skipping Phase 3 (validation) before Phase 4 (render).
- Maximum {max_iterations} iterations total.
- Stop as soon as subagent score >= 0.85.
"""

    @staticmethod
    def _read_file(path: Path, default: str = "") -> str:
        try:
            return path.read_text()
        except FileNotFoundError:
            return default

    @staticmethod
    def _read_json(path: Path) -> Optional[dict]:
        try:
            return json.loads(path.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return None
```

**Step 3: Run all existing orchestrator tests to verify behavior preserved**

```bash
cd backend && python -m pytest tests/unit/test_orchestrator.py tests/unit/test_state_store.py -v
```

Expected: PASS (all existing tests; if any fail, the refactor broke behavior — investigate before proceeding).

**Step 4: Verify smoke (manual codex run)**

```bash
cd backend && python -c "
import asyncio
from pathlib import Path
from app.orchestrator import PipelineOrchestrator

async def smoke():
    orch = PipelineOrchestrator()
    # Use a tiny test workdir; skip actual execution, just verify imports work
    print('orchestrator imports OK with backend abstraction')

asyncio.run(smoke())
"
```

Expected: prints "orchestrator imports OK with backend abstraction"

**Step 5: Commit**

```bash
git add backend/app/orchestrator.py
git commit -m "refactor(orchestrator): use AgentBackend abstraction (T4)

Replace _setup_codex_workspace / _spawn_and_stream / CodexEvent with
backend.setup_workspace / backend.stream. Adds backend_name parameter to
run() (default 'codex' for backward compat). Behavior preserved for codex."
```

---

## Task 5: Create `backends/claude_code.py` (ClaudeCodeBackend new)

**Files:**
- Create: `backend/app/backends/claude_code.py`
- Modify: `backend/app/backends/__init__.py` (register ClaudeCodeBackend)
- Test: `backend/tests/unit/test_claude_code_backend.py`

**Step 1: Write the failing test**

Create `backend/tests/unit/test_claude_code_backend.py`:

```python
"""Tests for ClaudeCodeBackend event parsing and command construction."""
from pathlib import Path
from app.backends.claude_code import ClaudeCodeBackend


def test_claude_code_backend_name():
    b = ClaudeCodeBackend(proxy=None, timeout_seconds=60)
    assert b.name == "claude-code"


def test_build_command_no_cwd_flag():
    """ClaudeCodeBackend must NOT include --cwd (uses subprocess cwd= instead)."""
    b = ClaudeCodeBackend(proxy=None, timeout_seconds=60)
    cmd = b.build_command(Path("/tmp/wd"), "prompt", [])
    assert "--cwd" not in cmd
    assert "/tmp/wd" not in cmd  # cwd passed via subprocess, not argv


def test_build_command_has_required_flags():
    """Must include claude -p + stream-json + verbose + bypassPermissions."""
    b = ClaudeCodeBackend(proxy=None, timeout_seconds=60)
    cmd = b.build_command(Path("/wd"), "test prompt", [])
    assert cmd[0] == "claude"
    assert "-p" in cmd
    assert "test prompt" in cmd
    assert "--output-format" in cmd
    assert "stream-json" in cmd
    assert "--verbose" in cmd
    assert "--permission-mode" in cmd
    assert "bypassPermissions" in cmd
    assert "--allowedTools" in cmd
    # Task tool must be allowed for Phase 5 subagent spawn
    tools_str = cmd[cmd.index("--allowedTools") + 1]
    assert "Task" in tools_str
    assert "Bash" in tools_str
    assert "Read" in tools_str


def test_build_command_no_i_flag_for_keyframes():
    """ClaudeCodeBackend does NOT use -i flag for images
    (agent uses Capability Discovery Protocol to read images via MCP tool)."""
    b = ClaudeCodeBackend(proxy=None, timeout_seconds=60)
    cmd = b.build_command(Path("/wd"), "p", ["/tmp/001.png", "/tmp/002.png"])
    assert "-i" not in cmd
    assert "/tmp/001.png" not in cmd


def test_parse_event_result_completed():
    """result event → AgentEvent type=completed with usage."""
    b = ClaudeCodeBackend(proxy=None, timeout_seconds=60)
    raw = {"type": "result", "usage": {"input_tokens": 100}, "subtype": "success"}
    event = b.parse_event(raw)
    assert event["type"] == "completed"
    assert event["usage"] == {"input_tokens": 100}


def test_parse_event_assistant_with_text():
    """assistant event with text content → AgentEvent type=text."""
    b = ClaudeCodeBackend(proxy=None, timeout_seconds=60)
    raw = {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "text", "text": "Hello world"}
            ]
        }
    }
    event = b.parse_event(raw)
    assert event["type"] == "text"
    assert event["content"] == "Hello world"


def test_parse_event_assistant_with_tool_use():
    """assistant event with tool_use → AgentEvent type=tool_call."""
    b = ClaudeCodeBackend(proxy=None, timeout_seconds=60)
    raw = {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "tool_use", "name": "Bash", "input": {"cmd": "ls"}}
            ]
        }
    }
    event = b.parse_event(raw)
    assert event["type"] == "tool_call"
    assert "Bash" in event["content"]


def test_parse_event_assistant_mixed_prefers_tool_call():
    """assistant event with both text + tool_use → tool_call (text in raw)."""
    b = ClaudeCodeBackend(proxy=None, timeout_seconds=60)
    raw = {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "text", "text": "Running ls"},
                {"type": "tool_use", "name": "Bash", "input": {}}
            ]
        }
    }
    event = b.parse_event(raw)
    assert event["type"] == "tool_call"
    assert "Bash" in event["content"]


def test_parse_event_user_tool_result():
    """user event → AgentEvent type=tool_result."""
    b = ClaudeCodeBackend(proxy=None, timeout_seconds=60)
    raw = {
        "type": "user",
        "message": {
            "content": [{"type": "tool_result", "content": "ok"}]
        }
    }
    event = b.parse_event(raw)
    assert event["type"] == "tool_result"


def test_parse_event_system_error():
    """system event with subtype=error → AgentEvent type=error."""
    b = ClaudeCodeBackend(proxy=None, timeout_seconds=60)
    raw = {"type": "system", "subtype": "error", "message": "boom"}
    event = b.parse_event(raw)
    assert event["type"] == "error"


def test_parse_event_unknown_falls_back_to_text():
    """Unknown event → AgentEvent type=text with raw preserved."""
    b = ClaudeCodeBackend(proxy=None, timeout_seconds=60)
    raw = {"type": "stream_event", "subtype": "something"}
    event = b.parse_event(raw)
    assert event["type"] == "text"
    assert event["content"] == ""
    assert event["raw"] == raw


def test_setup_workspace_creates_dual_symlinks(tmp_path):
    """setup_workspace symlinks AGENTS.md AND CLAUDE.md + skills/."""
    skills_src = tmp_path / "skills"
    skills_src.mkdir()
    (skills_src / "AGENTS.md").write_text("# Main agents file")
    (skills_src / "vfx-shader").mkdir()
    (skills_src / "vfx-shader" / "SKILL.md").write_text("# Skill")

    workdir = tmp_path / "wd"
    workdir.mkdir()

    b = ClaudeCodeBackend(proxy=None, timeout_seconds=60)
    b.setup_workspace(workdir, skills_src)

    assert (workdir / "AGENTS.md").is_symlink()
    assert (workdir / "CLAUDE.md").is_symlink()
    assert (workdir / "skills").is_symlink()
    # AGENTS.md and CLAUDE.md should resolve to same source file
    agents_target = (workdir / "AGENTS.md").resolve()
    claude_target = (workdir / "CLAUDE.md").resolve()
    assert agents_target == claude_target
```

**Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/unit/test_claude_code_backend.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.backends.claude_code'`

**Step 3: Implement ClaudeCodeBackend**

Create `backend/app/backends/claude_code.py`:

```python
"""ClaudeCodeBackend: wraps Anthropic Claude Code CLI for headless execution.

Key differences from CodexBackend:
- No --cwd flag (uses subprocess cwd= parameter)
- bypassPermissions mode (Bash auto-approved for FFmpeg/Playwright)
- No -i flag for images (agent uses Capability Discovery Protocol + MCP tools)
- Dual symlink: AGENTS.md + CLAUDE.md (Claude Code reads CLAUDE.md, not AGENTS.md)

Main model: deepseek-v4-pro via api.deepseek.com/anthropic
Multimodal: zai-mcp-server (GLM) — must be configured globally in ~/.claude.json
"""
from pathlib import Path

from .base import BaseBackend, AgentEvent
from . import register_backend


class ClaudeCodeBackend(BaseBackend):
    """Adapter for Claude Code CLI."""

    name = "claude-code"

    # Tools allowed by default. Task is required for Phase 5 subagent spawn.
    # MCP tools (zai-mcp-server_*) are auto-discovered by Claude Code from
    # ~/.claude.json global config; do not need to be in this list.
    ALLOWED_TOOLS = "Bash,Read,Write,Edit,Glob,Grep,Task"

    def setup_workspace(self, workdir: Path, skills_src: Path) -> None:
        """Create dual-naming symlinks: AGENTS.md + CLAUDE.md (same source).

        Claude Code reads CLAUDE.md (not AGENTS.md). codex/OpenCode read
        AGENTS.md. By symlinking both to the same source, the same content
        serves both runtimes.
        """
        # Symlink skills/ at workdir root (both backends use this)
        skills_link = workdir / "skills"
        if not skills_link.exists():
            skills_link.symlink_to(skills_src.absolute(), target_is_directory=True)

        # Symlink AGENTS.md (codex/OpenCode discovery)
        agents_link = workdir / "AGENTS.md"
        if not agents_link.exists():
            agents_link.symlink_to((skills_src / "AGENTS.md").resolve())

        # Symlink CLAUDE.md → same source (Claude Code discovery)
        claude_link = workdir / "CLAUDE.md"
        if not claude_link.exists():
            claude_link.symlink_to((skills_src / "AGENTS.md").resolve())

    def build_command(
        self, workdir: Path, prompt: str, keyframes: list[str],
    ) -> list[str]:
        """Build `claude -p` argv.

        NOTE: keyframes are NOT passed via -i flag. They are listed in the
        user prompt as absolute paths, and the agent uses Capability Discovery
        Protocol (see SKILL.md Phase 1) to read them via MCP tool
        (zai-mcp-server_analyze_image).

        NOTE: workdir is NOT in argv. It's passed via subprocess cwd= parameter.
        """
        return [
            "claude",
            "-p", prompt,
            "--output-format", "stream-json",
            "--verbose",
            "--permission-mode", "bypassPermissions",
            "--allowedTools", self.ALLOWED_TOOLS,
        ]

    def parse_event(self, raw: dict) -> AgentEvent:
        """Map Claude Code stream-json event types to unified AgentEvent.

        Claude Code event types (from lib-5 research):
            - system (subtype=init/error)
            - stream_event (subtype=content_block_delta/...)
            - assistant (message.content: text/tool_use blocks)
            - user (message.content: tool_result blocks)
            - result (terminal, contains usage)
        """
        t = raw.get("type", "")
        subtype = raw.get("subtype", "")

        if t == "result":
            return {
                "type": "completed",
                "content": "",
                "usage": raw.get("usage"),
                "raw": raw,
            }
        elif t == "assistant":
            blocks = raw.get("message", {}).get("content", [])
            tool_uses = [b for b in blocks if b.get("type") == "tool_use"]
            if tool_uses:
                # If any tool_use block, classify as tool_call
                # (text blocks preserved in raw)
                tool_names = ", ".join(b.get("name", "") for b in tool_uses)
                return {
                    "type": "tool_call",
                    "content": tool_names,
                    "usage": None,
                    "raw": raw,
                }
            # No tool_use: extract text
            texts = [b.get("text", "") for b in blocks if b.get("type") == "text"]
            return {
                "type": "text",
                "content": "\n".join(texts),
                "usage": None,
                "raw": raw,
            }
        elif t == "user":
            # Claude Code user channel carries tool_result blocks
            return {
                "type": "tool_result",
                "content": "",
                "usage": None,
                "raw": raw,
            }
        elif t == "system" and subtype == "error":
            return {
                "type": "error",
                "content": str(raw),
                "usage": None,
                "raw": raw,
            }
        # Unknown event (incl. stream_event partial deltas, system init, etc.)
        # Fall back to text with raw preserved.
        return {
            "type": "text",
            "content": "",
            "usage": None,
            "raw": raw,
        }


# Auto-register on import
register_backend("claude-code", ClaudeCodeBackend)
```

Modify `backend/app/backends/__init__.py` to import claude_code:

```python
# Add after codex import:
from . import claude_code as _claude_code  # noqa: F401 (triggers register_backend)
```

**Step 4: Run test to verify pass**

```bash
cd backend && python -m pytest tests/unit/test_claude_code_backend.py tests/unit/test_backend_registry.py -v
```

Expected: PASS

Update `test_backend_registry.py`:

```python
def test_registry_has_both_backends():
    """After T3 + T5, registry has codex and claude-code."""
    assert "codex" in BACKEND_REGISTRY
    assert "claude-code" in BACKEND_REGISTRY
```

**Step 5: Commit**

```bash
git add backend/app/backends/claude_code.py backend/app/backends/__init__.py backend/tests/unit/test_claude_code_backend.py backend/tests/unit/test_backend_registry.py
git commit -m "feat(backends): ClaudeCodeBackend new adapter (T5)

Wraps claude -p CLI. Dual symlink AGENTS.md+CLAUDE.md. No --cwd flag
(uses subprocess cwd=). bypassPermissions for Bash auto-approve. No -i flag
(agent uses Capability Discovery Protocol for images)."
```

---

## Task 6: Rewrite SKILL.md Phase 1 + Phase 5 for Capability Discovery Protocol

**Files:**
- Modify: `backend/app/skills/vfx-shader/SKILL.md` (Phase 1 + Phase 5 sections)
- Modify: `backend/app/skills/AGENTS.md` (generalize codex-specific syntax)

**Reference:** Spec Section 7 (Capability Discovery Protocol).

**Strategy:** This is a documentation change, not test-driven. Verify by manual diff + smoke test that agent can follow the new instructions.

**Step 1: Read current SKILL.md Phase 1 and Phase 5**

```bash
grep -n "^## Phase" backend/app/skills/vfx-shader/SKILL.md
```

**Step 2: Rewrite Phase 1 with Capability Discovery**

Edit `backend/app/skills/vfx-shader/SKILL.md` — replace the Phase 1 section:

```markdown
## Phase 1: Analyse keyframes → visual_description.json

### Step 1: Establish Vision Capability

You need to "see" the keyframes before analysing. Try these in order until one works:

1. **Native multimodal**: Are keyframe images already visible in your context
   (passed as image content blocks)?
   → If YES: proceed to Step 2 with direct visual access.

2. **Discover image tools**: If NO native vision, probe your available tools:
   - List the tools you can call
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

### Step 2: Visual Analysis (regardless of how you got vision)

Write `visual_description.json` with these fields:
... [existing analysis instructions unchanged]
```

**Step 3: Rewrite Phase 5 with Capability Discovery**

Edit Phase 5 section:

```markdown
## Phase 5: Spawn evaluator subagent → evaluation.json

### MANDATORY: NO self-evaluation

You MUST spawn an isolated-context subagent to evaluate the render.
Spawning mechanism depends on your runtime:
- codex: `spawn_agent(prompt="...", fork_turns="none")`
- claude-code: Use Task tool with description="..." subagent_type="..."
- Other runtimes: Use your native subagent mechanism with fresh context

### Evaluator prompt template

Spawn the subagent with this prompt (fill in the actual paths):

```
You are an impartial VFX shader evaluator.

Reference image: /abs/path/to/keyframe_001.png
Render image: /abs/path/to/render_output.png

Compare them on 4 dimensions:
1. Color accuracy (0.0-1.0)
2. Shape fidelity (0.0-1.0)
3. Animation/motion match (0.0-1.0)
4. Overall impression (0.0-1.0)

Establish your vision using the Capability Discovery Protocol from Phase 1
(native multimodal first, then probe image tools, then fail loudly).

Write your evaluation to evaluation.json with this schema:
{
  "overall_score": <average of 4 dimensions>,
  "dimension_scores": {...},
  "visual_issues": [...]
}
```

### Stop condition

If overall_score >= 0.85 → proceed to Phase 6 finalize.
Else → return to Phase 2 for another iteration (up to max_iterations total).
```

**Step 4: Generalize AGENTS.md codex-specific syntax**

```bash
grep -n "spawn_agent\|fork_turns" backend/app/skills/AGENTS.md
```

For each occurrence, add a runtime-agnostic note. For example:

Before:
```
Use `spawn_agent(prompt="...", fork_turns="none")` to isolate context.
```

After:
```
Use your runtime's isolated-context subagent mechanism:
- codex: `spawn_agent(prompt="...", fork_turns="none")`
- claude-code: Task tool with `subagent_type="..."` (default fresh context)
```

**Step 5: Verify SKILL.md is well-formed markdown**

```bash
# Quick sanity check
wc -l backend/app/skills/vfx-shader/SKILL.md backend/app/skills/AGENTS.md
grep -c "^## Phase" backend/app/skills/vfx-shader/SKILL.md  # should be 6
```

**Step 6: Commit**

```bash
git add backend/app/skills/vfx-shader/SKILL.md backend/app/skills/AGENTS.md
git commit -m "docs(skills): Capability Discovery Protocol + runtime-agnostic subagent (T6)

Phase 1 rewritten with vision establishment protocol (native multimodal
first, then probe image tools, then fail loudly). Phase 5 generalized
to support both codex spawn_agent and claude-code Task tool."
```

---

## Task 7: PipelineRecord backward-compatible `backend` field

**Files:**
- Modify: `backend/app/state_store.py`
- Test: `backend/tests/unit/test_state_store.py` (extend existing)

**Step 1: Read current state_store.py**

```bash
cat backend/app/state_store.py
```

**Step 2: Write the failing test (extend test_state_store.py)**

Append to `backend/tests/unit/test_state_store.py`:

```python
def test_pipeline_record_backend_defaults_to_codex():
    """New field 'backend' defaults to 'codex' for backward compat."""
    from app.state_store import PipelineRecord, PipelineStatus
    record = PipelineRecord(
        pipeline_id="test-1",
        status=PipelineStatus.RUNNING,
        workdir="/tmp/test",
        keyframe_paths=[],
    )
    assert record.backend == "codex"


def test_pipeline_record_backend_explicit_value():
    """backend field accepts any string."""
    from app.state_store import PipelineRecord, PipelineStatus
    record = PipelineRecord(
        pipeline_id="test-2",
        backend="claude-code",
        status=PipelineStatus.RUNNING,
        workdir="/tmp/test",
        keyframe_paths=[],
    )
    assert record.backend == "claude-code"


def test_pipeline_record_backward_compat_old_json_without_backend(tmp_path):
    """Loading an old JSON (no backend field) auto-fills default 'codex'."""
    import json
    from app.state_store import PipelineRecord
    # Simulate old JSON from v2.0.1 baseline
    old_json = {
        "pipeline_id": "v2-old-123",
        "status": "passed",
        "workdir": "/tmp/old",
        "keyframe_paths": ["/tmp/001.png"],
        "final_shader": "void main() {}",
        "final_score": 0.92,
        # NOTE: no "backend" field
    }
    record = PipelineRecord(**old_json)
    assert record.backend == "codex"  # default applied


def test_pipeline_record_save_load_preserves_backend(tmp_path):
    """Round-trip save+load preserves backend field."""
    from app.state_store import PipelineRecord, PipelineStatus, StateStore
    StateStore.STORE_DIR = tmp_path  # redirect to temp
    record = PipelineRecord(
        pipeline_id="round-trip",
        backend="claude-code",
        status=PipelineStatus.PASSED,
        workdir="/tmp/rt",
        keyframe_paths=[],
        final_score=0.88,
    )
    StateStore.save(record)
    loaded = StateStore.load("round-trip")
    assert loaded is not None
    assert loaded.backend == "claude-code"
```

**Step 3: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/unit/test_state_store.py -v
```

Expected: FAIL with AttributeError on `record.backend` (field doesn't exist yet).

**Step 4: Add backend field to PipelineRecord**

Edit `backend/app/state_store.py` — add `backend: str = "codex"` to PipelineRecord class (after pipeline_id):

```python
class PipelineRecord(BaseModel):
    pipeline_id: str
    backend: str = "codex"  # NEW: backward-compatible default
    status: PipelineStatus
    workdir: str
    keyframe_paths: list[str]
    # ... rest unchanged
```

If StateStore doesn't have a `load()` method, add it (test_step 4 uses it):

```python
@staticmethod
def load(pipeline_id: str) -> Optional[PipelineRecord]:
    """Load a record by pipeline_id, or None if not found."""
    path = StateStore.STORE_DIR / f"{pipeline_id}.json"
    if not path.exists():
        return None
    try:
        return PipelineRecord(**json.loads(path.read_text()))
    except Exception:
        return None
```

**Step 5: Run test to verify pass**

```bash
cd backend && python -m pytest tests/unit/test_state_store.py -v
```

Expected: PASS

**Step 6: Commit**

```bash
git add backend/app/state_store.py backend/tests/unit/test_state_store.py
git commit -m "feat(state): add backward-compatible backend field to PipelineRecord (T7)

Default 'codex' ensures v2.0.1 baseline JSON loads without breakage."
```

---

## Task 8: config.py per-backend proxy/timeout helpers

**Files:**
- Modify: `backend/app/config.py`
- Test: `backend/tests/unit/test_config.py` (new or extend)

**Step 1: Write the failing test**

Create `backend/tests/unit/test_config.py`:

```python
"""Tests for per-backend config helpers."""
from app.config import Settings


def test_settings_has_codex_proxy_timeout():
    s = Settings()
    assert hasattr(s, "codex_proxy")
    assert hasattr(s, "codex_timeout")


def test_settings_has_claude_code_proxy_timeout():
    s = Settings()
    assert hasattr(s, "claude_code_proxy")
    assert hasattr(s, "claude_code_timeout")


def test_backend_proxy_lookup():
    s = Settings()
    assert s.backend_proxy("codex") == s.codex_proxy
    assert s.backend_proxy("claude-code") == s.claude_code_proxy


def test_backend_proxy_unknown_backend_returns_empty():
    """Unknown backend name → empty proxy (safe fallback)."""
    s = Settings()
    assert s.backend_proxy("nonexistent") == ""


def test_backend_timeout_lookup():
    s = Settings()
    assert s.backend_timeout("codex") == s.codex_timeout
    assert s.backend_timeout("claude-code") == s.claude_code_timeout


def test_backend_timeout_unknown_backend_returns_default():
    """Unknown backend → 600s default (safe fallback)."""
    s = Settings()
    assert s.backend_timeout("nonexistent") == 600
```

**Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/unit/test_config.py -v
```

Expected: FAIL (claude_code_proxy doesn't exist; backend_proxy method doesn't exist).

**Step 3: Update Settings**

Edit `backend/app/config.py`:

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 服务配置
    proxy: str = ""
    host: str = "0.0.0.0"
    port: int = 8000
    frontend_url: str = "http://localhost:5173"

    # Codex backend
    codex_proxy: str = "http://127.0.0.1:7890"
    codex_timeout: int = 600

    # Claude Code backend
    claude_code_proxy: str = ""  # empty = direct connection
    claude_code_timeout: int = 600

    # Pipeline 配置
    max_iterations: int = 5
    passing_score: float = 0.85
    render_timeout_ms: int = 2000
    screenshot_width: int = 1280
    screenshot_height: int = 720

    # Workdir root for pipeline runs
    workdir_root: str = "/tmp/vfx_workdirs"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    def backend_proxy(self, name: str) -> str:
        """Get proxy URL for a backend by name. Empty string if unknown."""
        return getattr(self, f"{name}_proxy", "")

    def backend_timeout(self, name: str) -> int:
        """Get timeout for a backend by name. 600s default if unknown."""
        return getattr(self, f"{name}_timeout", 600)


settings = Settings()
```

**Step 4: Run test to verify pass**

```bash
cd backend && python -m pytest tests/unit/test_config.py -v
```

Expected: PASS (6 tests)

**Step 5: Commit**

```bash
git add backend/app/config.py backend/tests/unit/test_config.py
git commit -m "feat(config): per-backend proxy/timeout + helper methods (T8)"
```

---

## Task 9: RuntimeConfig (routers/config.py) — add backend, drop v1.0 remnants

**Files:**
- Modify: `backend/app/routers/config.py`

**Reference:** Spec Section 8.6 (RuntimeConfig new schema).

**Strategy:** Pure schema change; existing SettingsPanel.tsx already reads via GET /config + writes via PUT /config, so the runtime config is dict-shaped and tolerant of new fields.

**Step 1: Update RuntimeConfig**

Edit `backend/app/routers/config.py`:

```python
"""Runtime configuration API"""
from fastapi import APIRouter
from pydantic import BaseModel, Field
from pathlib import Path
from typing import Literal
import json

router = APIRouter(prefix="/config", tags=["config"])


class RuntimeConfig(BaseModel):
    """Runtime configuration settings (v2.0+ multi-backend)."""
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


# Global runtime config storage
runtime_config: RuntimeConfig = RuntimeConfig()
CONFIG_FILE_PATH = Path("app/config/runtime_config.json")


@router.get("")
async def get_config() -> dict:
    return runtime_config.model_dump()


@router.put("")
async def update_config(config: RuntimeConfig) -> dict:
    global runtime_config
    runtime_config = config
    save_config_to_file()
    return runtime_config.model_dump()


@router.post("/reset")
async def reset_config() -> dict:
    global runtime_config
    runtime_config = RuntimeConfig()
    save_config_to_file()
    return runtime_config.model_dump()


@router.get("/file")
async def get_config_file() -> dict:
    if CONFIG_FILE_PATH.exists():
        return {"path": str(CONFIG_FILE_PATH), "content": CONFIG_FILE_PATH.read_text()}
    return {"path": str(CONFIG_FILE_PATH), "content": "File not found, using defaults"}


@router.put("/file")
async def update_config_file(content: str) -> dict:
    try:
        data = json.loads(content)
        config = RuntimeConfig(**data)
        CONFIG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE_PATH.write_text(json.dumps(config.model_dump(), indent=2))
        global runtime_config
        runtime_config = config
        return {"success": True, "config": runtime_config.model_dump()}
    except Exception as e:
        return {"success": False, "error": str(e)}


def save_config_to_file():
    CONFIG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE_PATH.write_text(json.dumps(runtime_config.model_dump(), indent=2))


def load_config_from_file():
    if CONFIG_FILE_PATH.exists():
        try:
            data = json.loads(CONFIG_FILE_PATH.read_text())
            global runtime_config
            runtime_config = RuntimeConfig(**data)
        except Exception as e:
            print(f"Failed to load config from file: {e}")


def get_runtime_config() -> RuntimeConfig:
    return runtime_config
```

**Removed v1.0 fields**: `AgentModelConfig`, `re_decompose_threshold`, `gradient_window_size`, `stagnation_variance`, `stagnation_window`, `decompose_agent`, `generate_agent`, `inspect_agent`.

**Step 2: Verify backend starts without import errors**

```bash
cd backend && python -c "from app.routers.config import runtime_config; print(runtime_config.model_dump())"
```

Expected: prints config dict with all 11 fields.

**Step 3: Commit**

```bash
git add backend/app/routers/config.py
git commit -m "refactor(config): RuntimeConfig multi-backend schema + drop v1.0 remnants (T9)

Add: backend / codex_proxy / codex_timeout / claude_code_proxy / claude_code_timeout / workdir_root
Drop: AgentModelConfig / re_decompose_threshold / gradient_window_size / stagnation_*"
```

---

## Task 10: POST /run API accepts `backend` field

**Files:**
- Modify: `backend/app/routers/pipeline.py`
- Test: `backend/tests/unit/test_routers_pipeline.py` (new or extend)

**Step 1: Read current pipeline.py**

```bash
cat backend/app/routers/pipeline.py
```

**Step 2: Write the failing test**

Create or extend `backend/tests/unit/test_routers_pipeline.py`:

```python
"""Tests for POST /run API with backend field."""
import pytest
from app.routers.pipeline import RunRequest


def test_run_request_defaults_to_codex():
    """RunRequest without backend field defaults to 'codex'."""
    req = RunRequest(sample_name="heart-2d")
    assert req.backend == "codex"


def test_run_request_accepts_claude_code():
    req = RunRequest(sample_name="heart-2d", backend="claude-code")
    assert req.backend == "claude-code"


def test_run_request_rejects_unknown_backend():
    """Unknown backend name rejected by Literal validator."""
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        RunRequest(sample_name="x", backend="nonexistent")
```

**Step 3: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/unit/test_routers_pipeline.py -v
```

Expected: FAIL (RunRequest doesn't have backend field).

**Step 4: Add backend field to RunRequest + pass to orchestrator**

Edit `backend/app/routers/pipeline.py` — find RunRequest class and add backend:

```python
from typing import Literal
from pydantic import BaseModel


class RunRequest(BaseModel):
    sample_name: str
    backend: Literal["codex", "claude-code"] = "codex"  # NEW
    notes: str | None = None
    max_iterations: int = 3
```

Then in the route handler, pass `backend_name=req.backend` to `orchestrator.run(...)`:

```python
@router.post("/run")
async def run_pipeline(req: RunRequest):
    pipeline_id = f"v2-{req.sample_name}-{int(time.time())}"
    # ... workdir / keyframes setup unchanged ...
    record = await orchestrator.run(
        pipeline_id=pipeline_id,
        workdir=workdir,
        keyframes=keyframe_paths,
        notes=req.notes or "",
        max_iterations=req.max_iterations,
        backend_name=req.backend,  # NEW
    )
    return record.model_dump()
```

**Step 5: Run test to verify pass**

```bash
cd backend && python -m pytest tests/unit/test_routers_pipeline.py -v
```

Expected: PASS

**Step 6: Commit**

```bash
git add backend/app/routers/pipeline.py backend/tests/unit/test_routers_pipeline.py
git commit -m "feat(api): POST /run accepts backend field (T10)

Default 'codex' preserves backward compat. Passes backend_name to
orchestrator.run()."
```

---

## Task 11: Extend SettingsPanel.tsx to 4-group config panel

**Files:**
- Modify: `frontend/src/components/SettingsPanel.tsx`
- Reference: Spec Section 9 (4 configuration groups).

**Strategy:** This is a UI task. Reuse existing slider/input/group styles. Add 4 groups: Backend / Pipeline / Render / System. Keep "Apply / Defaults / Cancel" footer.

**Step 1: Read current SettingsPanel.tsx for reference**

```bash
wc -l frontend/src/components/SettingsPanel.tsx
```

Expected: 312 lines.

**Step 2: Extend Settings interface + state**

Edit `frontend/src/components/SettingsPanel.tsx` — replace Settings interface:

```typescript
interface Settings {
  // Backend
  backend: 'codex' | 'claude-code';
  codex_proxy: string;
  codex_timeout: number;
  claude_code_proxy: string;
  claude_code_timeout: number;
  // Pipeline
  max_iterations: number;
  passing_threshold: number;
  // Render
  screenshot_width: number;
  screenshot_height: number;
  render_timeout_ms: number;
  // System
  workdir_root: string;
}

const DEFAULT_SETTINGS: Settings = {
  backend: 'codex',
  codex_proxy: 'http://127.0.0.1:7890',
  codex_timeout: 600,
  claude_code_proxy: '',
  claude_code_timeout: 600,
  max_iterations: 3,
  passing_threshold: 0.85,
  screenshot_width: 1280,
  screenshot_height: 720,
  render_timeout_ms: 2000,
  workdir_root: '/tmp/vfx_workdirs',
};
```

**Step 3: Update fetch logic to read all fields**

Update the `fetchSettings` function to map all fields from API response:

```typescript
const data = await res.json();
const mapped: Settings = {
  backend: data.backend ?? 'codex',
  codex_proxy: data.codex_proxy ?? '',
  codex_timeout: data.codex_timeout ?? 600,
  claude_code_proxy: data.claude_code_proxy ?? '',
  claude_code_timeout: data.claude_code_timeout ?? 600,
  max_iterations: data.max_iterations,
  passing_threshold: data.passing_threshold,
  screenshot_width: data.screenshot_width,
  screenshot_height: data.screenshot_height,
  render_timeout_ms: data.render_timeout_ms,
  workdir_root: data.workdir_root ?? '/tmp/vfx_workdirs',
};
setSettings(mapped);
setSavedSettings(mapped);
```

**Step 4: Update save logic**

Update `handleSave` body:

```typescript
body: JSON.stringify({
  backend: settings.backend,
  codex_proxy: settings.codex_proxy,
  codex_timeout: settings.codex_timeout,
  claude_code_proxy: settings.claude_code_proxy,
  claude_code_timeout: settings.claude_code_timeout,
  max_iterations: settings.max_iterations,
  passing_threshold: settings.passing_threshold,
  screenshot_width: settings.screenshot_width,
  screenshot_height: settings.screenshot_height,
  render_timeout_ms: settings.render_timeout_ms,
  workdir_root: settings.workdir_root,
}),
```

**Step 5: Add 4 config groups in render**

Replace the existing content section with 4 grouped sections. Each group has a header label and inputs matching the existing visual style (sliders for ranges, text inputs for strings, number inputs for bounded ints).

Specifically:
- **Backend group**: dropdown (codex/claude-code) + 4 inputs (codex_proxy text, codex_timeout number, claude_code_proxy text, claude_code_timeout number)
- **Pipeline group**: 2 sliders (max_iterations 1-100, passing_threshold 0.5-1.0) — reuse existing slider component pattern
- **Render group**: 3 number inputs (screenshot_width 256-2048, screenshot_height 256-2048, render_timeout_ms 500-10000)
- **System group**: 1 text input (workdir_root)

For the backend dropdown, use a styled `<select>` matching the existing visual language.

**Step 6: Manual smoke test**

```bash
cd backend && uvicorn app.main:app --reload --port 8000 &
cd frontend && npm run dev
# Open http://localhost:5173, click settings gear, verify 4 groups render
# Edit a field, click Apply, reload page, verify value persisted
```

**Step 7: Commit**

```bash
git add frontend/src/components/SettingsPanel.tsx
git commit -m "feat(frontend): SettingsPanel 4-group config (Backend/Pipeline/Render/System) (T11)

Replaces 2-field panel with full 11-field config editor. Backend dropdown,
per-backend proxy/timeout inputs, screenshot/render controls, workdir_root."
```

---

## Task 12: `run_v2_samples_via_ui.py` accepts `--backend` flag

**Files:**
- Modify: `backend/tests/e2e/run_v2_samples_via_ui.py`

**Reference:** exp-3 / fix-24 sessions already explored this file.

**Step 1: Read current script**

```bash
grep -n "argparse\|backend\|post" backend/tests/e2e/run_v2_samples_via_ui.py | head -30
```

**Step 2: Add --backend argument**

Find the argparse setup and add:

```python
parser.add_argument(
    "--backend",
    choices=["codex", "claude-code"],
    default="codex",
    help="Agent backend to use (default: codex)",
)
```

**Step 3: Pass backend to POST /run request body**

Find where the script POSTs to `/run` and add `backend` to the JSON body:

```python
response = requests.post(
    f"{API_BASE}/run",
    json={
        "sample_name": sample_name,
        "backend": args.backend,  # NEW
        "notes": notes,
        "max_iterations": args.max_iterations,
    },
)
```

**Step 4: Update output directory naming**

Find where the script writes outputs (likely under `backend/test_results/<date>_<description>/`) and include backend in the directory name:

```python
# Before:
output_dir = f"backend/test_results/{date}_{description}/"
# After:
output_dir = f"backend/test_results/{date}_{backend}_{description}/"
```

(Verify this matches `collect_v2_results.py` expectations; if collect_v2_results.py scans `test_results/*/`, no further change needed.)

**Step 5: Verify with --help**

```bash
cd backend && python tests/e2e/run_v2_samples_via_ui.py --help | grep -A 2 backend
```

Expected: shows `--backend {codex,claude-code}` option.

**Step 6: Commit**

```bash
git add backend/tests/e2e/run_v2_samples_via_ui.py
git commit -m "feat(e2e): run_v2_samples_via_ui.py accepts --backend (T12)"
```

---

## Task 13: Acceptance — Codex regression smoke (5-10 samples)

**Files:**
- Test: live execution, no file changes

**Goal:** Verify CodexBackend refactor preserves behavior. Run 5-10 representative samples and compare scores vs v2.0.1 baseline.

**Step 1: Select representative samples**

Pick 5-10 samples covering:
- Easy: `4-col-grad`, `heart-2d`, `twitter-blue-check`
- Medium: `shiny-circle`, `water-color-blending`, `plasma-waves`
- Hard: `vortex-street`, `electron`, `auroras`

**Step 2: Start backend + frontend**

```bash
cd /Users/yangfei/Code/VFX-Agent/.worktrees/v2.0-codex-od
./start.sh start
./start.sh status
```

**Step 3: Run benchmark with --backend codex**

```bash
cd backend && python tests/e2e/run_v2_samples_via_ui.py \
    4-col-grad heart-2d twitter-blue-check shiny-circle water-color-blending \
    plasma-waves vortex-street electron auroras \
    --backend codex \
    --output-suffix regression-T13
```

**Step 4: Compare scores vs v2.0.1 baseline**

For each sample, look up its score in `backend/test_results/2026-07-16_v2-codex-od-50samples/test_results.json` and compute delta:

```bash
python tests/e2e/compare_with_baseline.py \
    --new backend/test_results/*regression-T13*/test_results.json \
    --baseline backend/test_results/2026-07-16_v2-codex-od-50samples/test_results.json
```

(If `compare_with_baseline.py` doesn't exist, manually diff via Python REPL.)

**Step 5: Verify acceptance**

| Sample | Baseline score | New score | Delta | Pass? (delta <0.05) |
|---|---|---|---|---|
| 4-col-grad | ... | ... | ... | ... |
| ... | ... | ... | ... | ... |

**Acceptance**: All sampled deltas <0.05. If any sample's delta ≥0.05, investigate (refactor may have broken behavior for that sample).

**Step 6: Commit acceptance record**

```bash
mkdir -p docs/acceptance/
cp backend/test_results/*regression-T13*/test_results.json docs/acceptance/T13-codex-regression.json
git add docs/acceptance/T13-codex-regression.json
git commit -m "test(acceptance): T13 codex regression delta <0.05 (verify refactor无损)"
```

---

## Task 14: Acceptance — Claude Code smoke (5-10 samples)

**Files:**
- Test: live execution, no file changes

**Goal:** Verify ClaudeCodeBackend works end-to-end. Don't require baseline alignment; just verify (a) pipeline runs without crash, (b) ≥50% samples produce usable shader, (c) ≥30% produce valid evaluation, (d) Capability Discovery Protocol works (visual_description.json contains real analysis, not "no_multimodal_capability").

**Step 1: Verify Claude Code CLI is installed + API keys configured**

```bash
which claude
# Should print: /usr/local/bin/claude or similar
# Verify ~/.claude.json has zai-mcp-server configured (multimodal provider)
python3 -c "import json; d=json.load(open('$HOME/.claude.json')); print('zai-mcp-server' in d.get('mcpServers', {}))"
# Expected: True
```

**Step 2: Run benchmark with --backend claude-code**

Pick 5-10 samples (same as T13, for direct comparison):

```bash
cd backend && python tests/e2e/run_v2_samples_via_ui.py \
    4-col-grad heart-2d twitter-blue-check shiny-circle water-color-blending \
    plasma-waves vortex-street electron auroras \
    --backend claude-code \
    --output-suffix smoke-T14
```

**Step 3: Verify acceptance criteria**

For each sample, check:

```python
# Check pipeline didn't crash
record.status != "FAILED-with-no-shader"

# Check usable shader (compiled + non-black)
shader_compiles = validate_shader(record.final_shader)
render_non_black = check_render_not_all_black(record.render_path)

# Check valid evaluation
has_evaluation = record.evaluation is not None
score_is_float = isinstance(record.evaluation.get("overall_score"), float)

# Check Capability Discovery worked
vd = json.load(open(workdir / "visual_description.json"))
capability_discovery_ok = vd.get("status") != "failed"  # i.e., agent did NOT fail loudly
```

**Acceptance table:**

| Sample | Pipeline OK? | Usable shader? | Valid evaluation? | Capability Discovery OK? |
|---|---|---|---|---|
| 4-col-grad | ... | ... | ... | ... |
| ... | ... | ... | ... | ... |

**Aggregate pass criteria**:
- ≥50% samples produce usable shader (compiled + non-black render)
- ≥30% samples produce valid evaluation.json with float overall_score
- ≥1 sample's visual_description.json proves Capability Discovery worked (e.g., contains real visual description text, not the fail-loudly stub)

**Step 4: If Capability Discovery fails for all samples**

This means Claude Code agent didn't find / call `zai-mcp-server_analyze_image`. Investigate:
- Check `--allowedTools` includes the MCP tool name
- Check Claude Code session log for tool listing
- May need to update ClaudeCodeBackend.ALLOWED_TOOLS to include `mcp__zai-mcp-server__analyze_image` or similar namespaced form

**Step 5: Commit acceptance record**

```bash
mkdir -p docs/acceptance/
cp backend/test_results/*smoke-T14*/test_results.json docs/acceptance/T14-claude-code-smoke.json
git add docs/acceptance/T14-claude-code-smoke.json
git commit -m "test(acceptance): T14 Claude Code smoke passes (≥50% shader + ≥30% eval)"
```

---

## Final Verification

After all 14 tasks:

**Step 1: Run full unit test suite**

```bash
cd backend && python -m pytest tests/unit/ -v
```

Expected: all tests PASS (existing + new backend tests).

**Step 2: Verify backend / frontend end-to-end**

```bash
./start.sh start
./start.sh status
# Open http://localhost:5173
# Manually run 1 sample with backend=codex (should work as before)
# Manually run 1 sample with backend=claude-code (should work)
```

**Step 3: Update README**

Add brief note to README about new multi-backend support, link to spec:

```bash
# Edit README.md, add to "Features" or "Architecture" section:
- Multi-agent backend support: codex (default) + Claude Code. See
  [spec](docs/superpowers/specs/2026-07-17-multi-agent-backend-abstraction-design.md).
```

**Step 4: Final commit**

```bash
git add README.md
git commit -m "docs: README notes multi-backend support"
```

---

## References

- **Spec**: `docs/superpowers/specs/2026-07-17-multi-agent-backend-abstraction-design.md` (681 lines, 14 sections)
- **lib-4 report**: Multi-agent backend integration research (codex + Claude Code + OpenCode headless modes, acpx protocol fact check)
- **lib-5 report**: Claude Code CLAUDE.md loading mechanism fact check (--cwd flag absent, --permission-mode bypassPermissions, SKILL.md path requirements, AGENTS.md non-compat)
- **Open Questions**: Spec Section 14 — 5 items deferred to implementation (Claude Code image format, codex subagent model, codex trust cleanup, allowedTools list, AGENTS.md neutralization)

---

*Plan written: 2026-07-17*
