"""KimiBackend: wraps Moonshot Kimi Code CLI (v0.28.1) for headless execution.

Closest sibling: ClaudeCodeBackend. Same shape (subprocess + stream-json),
same `cwd=` workdir mechanism, same AGENTS.md auto-load behavior, same
prompt-lists-image-paths approach for multimodal input.

Key differences from ClaudeCodeBackend (see spec
docs/superpowers/specs/2026-07-22-kimi-backend-design.md):
- Binary at ~/.kimi-code/bin/kimi (NOT in PATH by default)
- No --yolo / --auto flag needed (kimi -p auto-approves tool calls)
- No --allowedTools flag (no granular allow-listing)
- No -C flag for workdir (uses subprocess cwd=)
- Event schema is OpenAI chat completion style ({role, content/tool_calls})
- No token usage output → all events have usage=None
- No terminal result event → orchestrator detects completion via proc exit
- Multimodal via k3 native image_in + agent's built-in ReadMediaFile tool
  (no MCP server needed, unlike claude-code which needs zai-mcp-server)

Default model: kimi-code/k3 (K3, 1M context, capabilities: thinking +
image_in + video_in + tool_use). Configured in ~/.kimi-code/config.toml.
"""
import os
from pathlib import Path
from typing import Optional

from .base import BaseBackend, AgentEvent
from . import register_backend


class KimiBackend(BaseBackend):
    """Adapter for Kimi Code CLI (kimi-code v0.28.1+)."""

    name = "kimi"

    # Meta event types to drop at parse time.
    #
    # Background: kimi emits a final {"role":"meta","type":"session.resume_hint"}
    # event after the agent loop completes. This carries no debugging value
    # (just a `kimi -r <session_id>` hint to resume interactively). Dropping
    # it keeps the orchestrator's events buffer clean for actual agent turns.
    #
    # Other meta types (forward-compat for future kimi versions) are NOT
    # dropped — they fall through to text fallback so we can see them.
    DROP_META_TYPES = frozenset({"session.resume_hint"})

    def setup_workspace(self, workdir: Path, skills_src: Path) -> None:
        """Create symlinks for AGENTS.md + CLAUDE.md + skills/ at workdir root.

        Identical pattern to CodexBackend. kimi auto-loads workdir/AGENTS.md
        (verified via v0.28.1 manual test: AGENTS.md prefix rule applied).
        CLAUDE.md symlink is defensive (AGENTS.md content is already
        backend-neutral; harmless for kimi which does not auto-load CLAUDE.md).
        """
        # Symlink skills/ at workdir root (kimi auto-discovers from cwd)
        skills_link = workdir / "skills"
        if not skills_link.exists():
            skills_link.symlink_to(skills_src.absolute(), target_is_directory=True)

        # Symlink AGENTS.md (kimi primary discovery)
        agents_link = workdir / "AGENTS.md"
        if not agents_link.exists():
            agents_link.symlink_to((skills_src / "AGENTS.md").resolve())

        # Symlink CLAUDE.md -> same source (defensive; harmless for kimi)
        claude_link = workdir / "CLAUDE.md"
        if not claude_link.exists():
            claude_link.symlink_to((skills_src / "AGENTS.md").resolve())

    def build_command(
        self, workdir: Path, prompt: str, keyframes: list[str],
    ) -> list[str]:
        """Build `kimi -p` argv.

        NOTE: workdir is NOT in argv. It's passed via subprocess cwd=
        parameter (handled by BaseBackend.stream()).

        NOTE: keyframes are NOT passed via CLI flag. They are listed in the
        user prompt as absolute paths; the k3 agent uses its built-in
        ReadMediaFile tool to read them (k3 has native image_in capability).

        NOTE: no --yolo / --auto flag. kimi v0.28.1 in -p mode auto-approves
        tool calls (verified via Bash/Write test). Attempting to add --yolo
        with -p raises "Cannot combine --prompt with --yolo".

        NOTE: KIMI_BIN_PATH is read here (not in __init__) to avoid import
        cycle with config.py and to allow runtime env override.
        """
        bin_path = os.getenv(
            "KIMI_BIN_PATH",
            os.path.expanduser("~/.kimi-code/bin/kimi"),
        )
        return [
            bin_path,
            "-p", prompt,
            "--output-format", "stream-json",
        ]

    def parse_event(self, raw: dict) -> Optional[AgentEvent]:
        """Map Kimi stream-json event to unified AgentEvent.

        Returns None for the session-end meta marker so it is filtered at
        the BaseBackend.stream() layer before reaching orchestrator's events
        buffer.

        Kimi event schema (OpenAI chat completion style, JSONL):
            {"role":"assistant","tool_calls":[...]}     -> tool_call
            {"role":"assistant","content":"<text>"}     -> text
            {"role":"assistant","content":"...","tool_calls":[...]}
                                                         -> tool_call (mixed wins)
            {"role":"tool","tool_call_id":"...","content":"..."}
                                                         -> tool_result
            {"role":"meta","type":"session.resume_hint"} -> None (drop)
            other / unknown                              -> text fallback

        Token usage: kimi v0.28.1 does not emit token counts in -p mode.
        All returned events have usage=None. Frontend usage panel renders
        "—" for kimi backend.
        """
        role = raw.get("role", "")

        # Drop known session-end noise.
        if role == "meta":
            meta_type = raw.get("type", "")
            if meta_type in self.DROP_META_TYPES:
                return None
            # Unknown meta types: fall through to text fallback (do not
            # silently swallow future meta events we haven't seen yet).

        if role == "assistant":
            tool_calls = raw.get("tool_calls") or []
            if tool_calls:
                # tool_call wins even when content is present (matches
                # ClaudeCodeBackend behavior on mixed assistant messages).
                tool_names = ", ".join(
                    tc.get("function", {}).get("name", "")
                    for tc in tool_calls
                    if isinstance(tc, dict)
                )
                return {
                    "type": "tool_call",
                    "content": tool_names,
                    "usage": None,
                    "raw": raw,
                }
            # No tool_calls: pure text response
            return {
                "type": "text",
                "content": raw.get("content", ""),
                "usage": None,
                "raw": raw,
            }

        if role == "tool":
            return {
                "type": "tool_result",
                "content": "",  # raw preserved; frontend can deep-read
                "usage": None,
                "raw": raw,
            }

        # Unknown / malformed event: text fallback, never raise.
        # Covers: empty dict, missing role field, future event types.
        return {
            "type": "text",
            "content": "",
            "usage": None,
            "raw": raw,
        }


# Auto-register on import (triggers when backends/__init__.py imports this)
register_backend("kimi", KimiBackend)
