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

        # Symlink CLAUDE.md -> AGENTS.md so the orchestrator's backend-neutral prompt
        # (which mentions CLAUDE.md) doesn't cause a wasted file-not-found turn.
        # Same source content; harmless for codex (it never auto-loads CLAUDE.md).
        claude_link = workdir / "CLAUDE.md"
        if not claude_link.exists():
            claude_link.symlink_to((skills_src / "AGENTS.md").resolve())

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
