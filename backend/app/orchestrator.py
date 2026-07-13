"""Pipeline orchestrator (v2.0).

Minimal Python wrapper: prepares workdir, spawns codex, parses JSONL, extracts outputs.
Does NOT do phase switching / iteration control / scoring (all delegated to codex via SKILL.md).
"""
import asyncio
import json
import os
import time
from pathlib import Path
from typing import AsyncIterator, Optional

from app.state_store import PipelineStatus, PipelineRecord, StateStore


class CodexEvent:
    """Parsed codex JSONL event."""

    def __init__(self, raw: dict) -> None:
        self.type: str = raw.get("type", "")
        self.item: dict = raw.get("item", {})
        self.usage: Optional[dict] = raw.get("usage")
        self.raw = raw


class PipelineOrchestrator:
    """Main v2.0 pipeline runner.

    Lifecycle per sample:
        1. setup workspace (symlink skill assets into .codex/)
        2. spawn codex exec with user prompt on stdin
        3. stream JSONL events from stdout
        4. extract final_shader.glsl + evaluation.json
        5. determine final status
    """

    CODEX_PROXY = os.environ.get("CODEX_PROXY", "http://127.0.0.1:7890")
    CODEX_TIMEOUT = int(os.environ.get("CODEX_TIMEOUT", "600"))
    PASSING_SCORE = 0.85

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(
        self,
        pipeline_id: str,
        workdir: Path | str,
        keyframes: list[str],
        notes: str,
        max_iterations: int = 3,
    ) -> PipelineRecord:
        """Run full v2.0 pipeline for one sample.

        Returns a ``PipelineRecord`` reflecting the final state.
        """
        start_time = time.monotonic()
        workdir = Path(workdir)

        record = PipelineRecord(
            pipeline_id=pipeline_id,
            status=PipelineStatus.RUNNING,
            workdir=str(workdir),
            keyframe_paths=keyframes,
        )
        StateStore.save(record)

        try:
            # 1. Setup codex workspace (symlink skill assets)
            self._setup_codex_workspace(workdir)

            # 2. Spawn codex + stream JSONL
            events: list[dict] = []
            usage: Optional[dict] = None
            try:
                async for event in self._spawn_and_stream(
                    pipeline_id, workdir, keyframes, notes, max_iterations,
                ):
                    events.append(event.raw)
                    if event.type == "turn.completed" and event.usage:
                        usage = event.usage
                    record.events = events[-100:]  # keep last 100
                    StateStore.save(record)
            except asyncio.TimeoutError:
                record.status = PipelineStatus.TIMEOUT
                record.error = "codex subprocess timed out"
                return record
            except RuntimeError as e:
                record.status = PipelineStatus.FAILED
                record.error = f"codex subprocess error: {e}"
                return record

            # 3. Extract outputs
            record.final_shader = self._read_file(workdir / "final_shader.glsl") or \
                self._read_file(workdir / "shader.glsl", default="")
            evaluation = self._read_json(workdir / "evaluation.json")
            record.evaluation = evaluation
            record.codex_usage = usage

            # 4. Determine status
            #   - no shader at all          → failed
            #   - has shader, no evaluation → failed (codex didn't finish workflow)
            #   - has both                 → passed / max_iterations by score
            if not record.final_shader:
                record.status = PipelineStatus.FAILED
                record.error = "no shader output written"
            elif evaluation is None:
                record.status = PipelineStatus.FAILED
                record.error = "no evaluation.json written — codex did not complete workflow"
                record.final_score = 0.0
            else:
                record.final_score = evaluation.get("overall_score", 0.0)
                record.status = PipelineStatus.PASSED if record.final_score >= self.PASSING_SCORE else PipelineStatus.MAX_ITERATIONS

            return record
        finally:
            record.duration_ms = int((time.monotonic() - start_time) * 1000)
            StateStore.save(record)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _setup_codex_workspace(self, workdir: Path) -> None:
        """Symlink skill assets into workdir root.

        Codex discovers AGENTS.md and skills/ from CWD root (workdir),
        NOT from workdir/.codex/. So we put symlinks at workdir root.
        """
        backend_root = Path(__file__).resolve().parent.parent
        skills_src = backend_root / "app" / "skills"
        if not skills_src.exists():
            raise RuntimeError(f"skills source not found: {skills_src}")

        # Symlink skills/ at workdir root (codex discovers via CWD)
        skills_link = workdir / "skills"
        if not skills_link.exists():
            skills_link.symlink_to(skills_src.absolute(), target_is_directory=True)

        # Symlink top-level AGENTS.md at workdir root (codex primary discovery)
        agents_link = workdir / "AGENTS.md"
        if not agents_link.exists():
            agents_link.symlink_to((skills_src / "AGENTS.md").resolve())

    async def _spawn_and_stream(
        self,
        pipeline_id: str,
        workdir: Path,
        keyframes: list[str],
        notes: str,
        max_iterations: int,
    ) -> AsyncIterator[CodexEvent]:
        """Spawn ``codex exec`` and yield parsed JSONL events.

        Enforces a hard wall-clock timeout via ``asyncio.timeout()``
        (Python 3.11+).
        """
        user_prompt = self._build_user_prompt(keyframes, notes, max_iterations)

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

        env = {
            **os.environ,
            "HTTP_PROXY": self.CODEX_PROXY,
            "HTTPS_PROXY": self.CODEX_PROXY,
        }

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        # Write prompt to stdin
        proc.stdin.write(user_prompt.encode())
        await proc.stdin.drain()
        proc.stdin.close()
        if hasattr(proc.stdin, "wait_closed"):
            await proc.stdin.wait_closed()

        # Stream stdout JSONL with hard timeout via asyncio.timeout (3.11+)
        try:
            async with asyncio.timeout(self.CODEX_TIMEOUT):
                async for line in proc.stdout:
                    line = line.decode().strip()
                    if not line:
                        continue
                    try:
                        yield CodexEvent(json.loads(line))
                    except json.JSONDecodeError:
                        continue

                await proc.wait()

                # Capture stderr + check exit code
                stderr_bytes = await proc.stderr.read() if proc.stderr else b""
                stderr_text = stderr_bytes.decode(errors="replace") if stderr_bytes else ""
                if proc.returncode != 0:
                    raise RuntimeError(
                        f"codex exited with code {proc.returncode}. "
                        f"stderr (last 2000 chars): ...{stderr_text[-2000:]}"
                    )
        except asyncio.TimeoutError:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=10)
            except asyncio.TimeoutError:
                proc.kill()
            raise

    def _build_user_prompt(
        self,
        keyframes: list[str],
        notes: str,
        max_iterations: int,
    ) -> str:
        """Build the user prompt passed to codex via stdin."""
        keyframe_list = "\n".join(f"- {p}" for p in keyframes)
        return f"""You are running inside a VFX shader generation pipeline.

## Setup

Your working directory contains:
- `AGENTS.md` (auto-loaded) — project context and VFX terminology
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
   - Phase 5: Spawn subagent evaluator with `fork_turns="none"` (MANDATORY — no self-eval)
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

- NO self-evaluation in Phase 5. MUST spawn subagent.
- NO skipping Phase 3 (validation) before Phase 4 (render).
- Maximum {max_iterations} iterations total.
- Stop as soon as subagent score >= 0.85.
"""

    # ------------------------------------------------------------------
    # File I/O helpers
    # ------------------------------------------------------------------

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
