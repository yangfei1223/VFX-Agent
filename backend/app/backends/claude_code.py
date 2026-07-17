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
