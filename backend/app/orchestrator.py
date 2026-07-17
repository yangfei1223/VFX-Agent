"""Pipeline orchestrator (v2.0, multi-backend).

Minimal Python wrapper: prepares workdir, instantiates backend, streams events,
extracts outputs. Does NOT do phase switching / iteration control / scoring
(all delegated to backend agent via SKILL.md).
"""
import asyncio
import json
import os
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
        backend_name: str = "codex",
    ) -> PipelineRecord:
        """Run full v2.0 pipeline for one sample.

        Args:
            backend_name: Which agent backend to use ("codex" | "claude-code" | future).
                         Default "codex" for backward compat with existing callers.

        Returns a PipelineRecord reflecting the final state.
        """
        start_time = time.monotonic()
        workdir = Path(workdir)

        # Resolve backend via registry + per-backend settings
        backend = get_backend(
            backend_name,
            proxy=settings.backend_proxy(backend_name) or None,
            timeout_seconds=settings.backend_timeout(backend_name),
        )

        record = PipelineRecord(
            pipeline_id=pipeline_id,
            backend=backend_name,
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
                    base_env=dict(os.environ),
                ):
                    events.append(event["raw"])
                    if event["type"] == "completed" and event.get("usage"):
                        usage = event["usage"]
                    record.events = events[-100:]  # keep last 100
                    StateStore.save(record)
            except asyncio.TimeoutError:
                # Don't return early — backend may have written outputs before timeout.
                # Fall through to extraction; mark as failed only if outputs missing.
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
            #   - runtime error AND no usable outputs → failed
            #   - no shader at all          → failed (or timeout if timeout_flag)
            #   - has shader, no evaluation → failed (backend didn't finish workflow)
            #   - has both, score >= 0.85   → passed (timeout irrelevant if passed)
            #   - has both, score < 0.85    → max_iterations (or timeout if flag)
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
                    # Score passed — timeout is irrelevant, run succeeded
                    record.status = PipelineStatus.PASSED
                    record.error = None  # clear timeout warning since we got a pass
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
- `AGENTS.md` (auto-loaded by codex) — project context and VFX terminology
- `CLAUDE.md` (auto-loaded by Claude Code) — same content as AGENTS.md
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
