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
