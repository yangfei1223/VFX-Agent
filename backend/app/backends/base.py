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

    def __init__(self, proxy: Optional[str] = None, timeout_seconds: int = 600):
        self.proxy = proxy
        self.timeout_seconds = timeout_seconds
        super().__init__()

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

        NOTE: stream() always passes `cwd=str(workdir)` to the subprocess.
        Subclasses MAY ALSO include a backend-specific project-root flag
        (e.g. codex's `-C <workdir>`) when the backend requires it; this
        is redundant with `cwd=` but harmless.
        """

    @abstractmethod
    def parse_event(self, raw: dict) -> Optional[AgentEvent]:
        """Convert backend-specific JSONL event to unified AgentEvent.

        Return None to drop noise events (e.g. partial stream deltas, debug
        tokens, internal progress notifications the frontend doesn't render).

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

        Subclasses MUST NOT override this — override the 3 abstract methods instead.

        Resource safety:
            - On TimeoutError: terminate gracefully (10s) then SIGKILL.
            - On any other exception (e.g. parse_event bug): finally clause kills proc.
            - stderr is drained concurrently to avoid pipe-buffer deadlock.
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
            limit=1024 * 1024 * 16,  # 16MB line limit (default 64KB overflows on large claude-code stream-json lines)
        )

        async def _drain_stderr() -> str:
            if proc.stderr is None:
                return ""
            return (await proc.stderr.read()).decode(errors="replace")

        stderr_task = asyncio.create_task(_drain_stderr())

        # Write prompt to stdin (backend reads prompt from stdin via "-" or "-p")
        # NOTE: claude-code uses `-p "<prompt>"` in argv, so stdin write is a no-op
        # for claude-code; codex uses "-" to read prompt from stdin.
        if "-" in cmd:  # codex convention (exact-match list membership)
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
                        parsed = self.parse_event(raw)
                        if parsed is None:
                            continue
                        yield parsed

                    await proc.wait()

                    stderr_text = await stderr_task
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
                    await proc.wait()
                raise
        finally:
            # Defensive: if we exit via any other exception (parse_event bug, etc.),
            # ensure proc is dead and stderr_task is not leaked.
            if not stderr_task.done():
                stderr_task.cancel()
            if proc.returncode is None:
                try:
                    proc.kill()
                    await proc.wait()
                except Exception:
                    pass
