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
    """Unknown event (not in DROP_EVENT_TYPES) → AgentEvent type=text with raw preserved."""
    b = ClaudeCodeBackend(proxy=None, timeout_seconds=60)
    # Use a type genuinely unknown to claude-code (not in DROP_EVENT_TYPES)
    raw = {"type": "totally_new_type", "subtype": "whatever"}
    event = b.parse_event(raw)
    assert event is not None
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


def test_parse_event_drops_thinking_tokens():
    """B1 regression: system/thinking_tokens must return None (drop).

    claude-code emits 80+ of these per sample; without filtering they
    flood orchestrator's events[-100:] buffer and crowd out useful events.
    """
    b = ClaudeCodeBackend(proxy=None, timeout_seconds=60)
    raw = {"type": "system", "subtype": "thinking_tokens", "tokens": "..."}
    assert b.parse_event(raw) is None


def test_parse_event_drops_subagent_task_progress():
    """system/task_started/progress/notification must return None.

    These are subagent internal progress notifications; the frontend
    useEventStream.ts has no TYPE_CONFIG entry for them, so they would
    render as generic 'lifecycle' JSON cards (visual noise).
    """
    b = ClaudeCodeBackend(proxy=None, timeout_seconds=60)
    for subtype in ("task_started", "task_progress", "task_notification"):
        raw = {"type": "system", "subtype": subtype, "data": {}}
        assert b.parse_event(raw) is None, f"Failed to drop system/{subtype}"


def test_parse_event_drops_stream_event_deltas():
    """stream_event/* partial deltas must return None.

    The final `assistant` event contains the complete content blocks;
    per-token deltas are pure noise.
    """
    b = ClaudeCodeBackend(proxy=None, timeout_seconds=60)
    for subtype in ("content_block_delta", "content_block_start", "content_block_stop",
                    "message_start", "message_stop", "message_delta", "ping"):
        raw = {"type": "stream_event", "subtype": subtype, "delta": {"text": "..."}}
        assert b.parse_event(raw) is None, f"Failed to drop stream_event/{subtype}"


def test_parse_event_keeps_useful_events_after_drop_filter():
    """Sanity: ensure drop filter doesn't accidentally filter useful events.

    After B1 fix, these must STILL be returned as proper AgentEvents:
    - assistant (tool_use + text)
    - user (tool_result)
    - result (terminal + usage)
    - system/error
    """
    b = ClaudeCodeBackend(proxy=None, timeout_seconds=60)

    # assistant with tool_use → tool_call
    e1 = b.parse_event({
        "type": "assistant",
        "message": {"content": [{"type": "tool_use", "name": "Bash", "input": {}}]}
    })
    assert e1 is not None and e1["type"] == "tool_call"

    # user with tool_result → tool_result
    e2 = b.parse_event({
        "type": "user",
        "message": {"content": [{"type": "tool_result", "content": "ok"}]}
    })
    assert e2 is not None and e2["type"] == "tool_result"

    # result/success → completed
    e3 = b.parse_event({"type": "result", "subtype": "success", "usage": {"x": 1}})
    assert e3 is not None and e3["type"] == "completed"

    # system/error → error
    e4 = b.parse_event({"type": "system", "subtype": "error", "message": "boom"})
    assert e4 is not None and e4["type"] == "error"
