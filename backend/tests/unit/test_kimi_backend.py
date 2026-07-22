"""Tests for KimiBackend event parsing and command construction.

Covers Kimi Code CLI v0.28.1 stream-json event schema (OpenAI chat completion
style). All event samples mirror real kimi output captured during manual
verification (see spec 2026-07-22-kimi-backend-design.md §2.3).
"""
from pathlib import Path

import pytest

from app.backends import BACKEND_REGISTRY
from app.backends.base import BaseBackend
from app.backends.kimi import KimiBackend


# ----------------------------------------------------------------------
# Registration / class structure
# ----------------------------------------------------------------------

def test_kimi_registered_in_registry():
    """KimiBackend auto-registers on import."""
    assert "kimi" in BACKEND_REGISTRY
    assert BACKEND_REGISTRY["kimi"] is KimiBackend


def test_kimi_is_basebackend_subclass():
    assert issubclass(KimiBackend, BaseBackend)


def test_kimi_name_attr():
    b = KimiBackend(proxy=None, timeout_seconds=60)
    assert b.name == "kimi"


# ----------------------------------------------------------------------
# build_command
# ----------------------------------------------------------------------

def test_build_command_default_bin_endswith_kimi(monkeypatch, tmp_path):
    """Default KIMI_BIN_PATH resolves to a path ending in 'kimi'."""
    monkeypatch.delenv("KIMI_BIN_PATH", raising=False)
    b = KimiBackend(proxy=None, timeout_seconds=60)
    cmd = b.build_command(tmp_path, "p", [])
    assert cmd[0].endswith("kimi")


def test_build_command_has_required_flags(tmp_path):
    """Must include `-p <prompt>` + `--output-format stream-json`."""
    b = KimiBackend(proxy=None, timeout_seconds=60)
    cmd = b.build_command(tmp_path, "hello world", [])
    assert "-p" in cmd
    assert "hello world" in cmd
    assert "--output-format" in cmd
    assert "stream-json" in cmd


def test_build_command_no_yolo_no_auto(tmp_path):
    """kimi v0.28.1 -p mode auto-approves; --yolo/--auto cannot combine with -p."""
    b = KimiBackend(proxy=None, timeout_seconds=60)
    cmd = b.build_command(tmp_path, "p", [])
    assert "--yolo" not in cmd
    assert "--auto" not in cmd
    assert "-y" not in cmd


def test_build_command_no_cwd_flag(tmp_path):
    """KimiBackend uses subprocess cwd= (no -C / --cwd flag in argv)."""
    b = KimiBackend(proxy=None, timeout_seconds=60)
    cmd = b.build_command(tmp_path, "p", [])
    assert "-C" not in cmd
    assert "--cwd" not in cmd
    assert "--work-dir" not in cmd
    assert "-w" not in cmd
    # tmp_path itself must not appear in argv
    assert str(tmp_path) not in cmd


def test_build_command_no_i_flag_for_keyframes(tmp_path):
    """kimi has no -i flag; keyframes listed in prompt body, agent uses
    built-in ReadMediaFile tool to read them."""
    b = KimiBackend(proxy=None, timeout_seconds=60)
    cmd = b.build_command(tmp_path, "p", ["/tmp/001.png", "/tmp/002.png"])
    assert "-i" not in cmd
    assert "/tmp/001.png" not in cmd
    assert "/tmp/002.png" not in cmd


def test_build_command_env_override(monkeypatch, tmp_path):
    """KIMI_BIN_PATH env overrides default binary location."""
    monkeypatch.setenv("KIMI_BIN_PATH", "/custom/path/kimi")
    b = KimiBackend(proxy=None, timeout_seconds=60)
    cmd = b.build_command(tmp_path, "p", [])
    assert cmd[0] == "/custom/path/kimi"


# ----------------------------------------------------------------------
# parse_event
# ----------------------------------------------------------------------

def test_parse_assistant_with_tool_calls_becomes_tool_call():
    """{"role":"assistant","tool_calls":[...]} → tool_call event."""
    b = KimiBackend(proxy=None, timeout_seconds=60)
    raw = {
        "role": "assistant",
        "tool_calls": [
            {
                "type": "function",
                "id": "tool_abc",
                "function": {
                    "name": "Bash",
                    "arguments": '{"command":"ls"}',
                },
            }
        ],
    }
    ev = b.parse_event(raw)
    assert ev is not None
    assert ev["type"] == "tool_call"
    assert ev["content"] == "Bash"
    assert ev["usage"] is None
    assert ev["raw"] is raw


def test_parse_assistant_with_multiple_tool_calls_joins_names():
    """Multiple tool_calls in one message → content = names joined by ', '."""
    b = KimiBackend(proxy=None, timeout_seconds=60)
    raw = {
        "role": "assistant",
        "tool_calls": [
            {"type": "function", "id": "t1",
             "function": {"name": "Read", "arguments": "{}"}},
            {"type": "function", "id": "t2",
             "function": {"name": "Bash", "arguments": "{}"}},
        ],
    }
    ev = b.parse_event(raw)
    assert ev["type"] == "tool_call"
    assert ev["content"] == "Read, Bash"


def test_parse_assistant_with_content_only_becomes_text():
    """{"role":"assistant","content":"..."} (no tool_calls) → text event."""
    b = KimiBackend(proxy=None, timeout_seconds=60)
    raw = {"role": "assistant", "content": "Done. Wrote the file."}
    ev = b.parse_event(raw)
    assert ev["type"] == "text"
    assert ev["content"] == "Done. Wrote the file."


def test_parse_assistant_mixed_prefers_tool_call():
    """assistant with both content + tool_calls → tool_call wins
    (matches ClaudeCodeBackend behavior)."""
    b = KimiBackend(proxy=None, timeout_seconds=60)
    raw = {
        "role": "assistant",
        "content": "I'll write the file now.",
        "tool_calls": [
            {"type": "function", "id": "x",
             "function": {"name": "Write", "arguments": "{}"}},
        ],
    }
    ev = b.parse_event(raw)
    assert ev["type"] == "tool_call"
    assert ev["content"] == "Write"


def test_parse_tool_result_event():
    """{"role":"tool","tool_call_id":"...","content":"..."} → tool_result."""
    b = KimiBackend(proxy=None, timeout_seconds=60)
    raw = {
        "role": "tool",
        "tool_call_id": "tool_abc",
        "content": "Command executed successfully.",
    }
    ev = b.parse_event(raw)
    assert ev["type"] == "tool_result"
    # content left empty (raw preserved for frontend deep-read)
    assert ev["content"] == ""
    assert ev["usage"] is None
    assert ev["raw"] is raw


def test_parse_meta_session_resume_hint_dropped():
    """meta/session.resume_hint is session-end noise → parse_event returns None."""
    b = KimiBackend(proxy=None, timeout_seconds=60)
    raw = {
        "role": "meta",
        "type": "session.resume_hint",
        "session_id": "session_abc",
        "command": "kimi -r session_abc",
        "content": "To resume this session: ...",
    }
    ev = b.parse_event(raw)
    assert ev is None


def test_parse_meta_unknown_type_falls_back_to_text():
    """Unknown meta types are not silently dropped (forward-compat: future
    kimi versions may add new meta subtypes we want to see)."""
    b = KimiBackend(proxy=None, timeout_seconds=60)
    raw = {"role": "meta", "type": "unknown_future_type", "content": "foo"}
    ev = b.parse_event(raw)
    assert ev is not None
    assert ev["type"] == "text"


def test_parse_unknown_event_falls_back_to_text():
    """Unknown role → text fallback (matches CodexBackend / ClaudeCodeBackend)."""
    b = KimiBackend(proxy=None, timeout_seconds=60)
    raw = {"role": "system", "message": "something weird"}
    ev = b.parse_event(raw)
    assert ev is not None
    assert ev["type"] == "text"
    assert ev["content"] == ""
    assert ev["raw"] is raw


def test_parse_empty_dict_does_not_raise():
    """parse_event must never raise, even on empty input."""
    b = KimiBackend(proxy=None, timeout_seconds=60)
    ev = b.parse_event({})
    assert ev is not None
    assert ev["type"] == "text"


def test_parse_missing_role_does_not_raise():
    """Missing 'role' field → text fallback."""
    b = KimiBackend(proxy=None, timeout_seconds=60)
    raw = {"content": "no role here"}
    ev = b.parse_event(raw)
    assert ev is not None
    assert ev["type"] == "text"


def test_parse_tool_call_missing_function_name():
    """Defensive: tool_call without function.name → empty string in content,
    not raise."""
    b = KimiBackend(proxy=None, timeout_seconds=60)
    raw = {
        "role": "assistant",
        "tool_calls": [
            {"type": "function", "id": "x", "function": {}},  # missing name
        ],
    }
    ev = b.parse_event(raw)
    assert ev["type"] == "tool_call"
    assert ev["content"] == ""


# ----------------------------------------------------------------------
# setup_workspace
# ----------------------------------------------------------------------

def test_setup_workspace_creates_three_symlinks(tmp_path):
    """setup_workspace must create skills/ + AGENTS.md + CLAUDE.md symlinks."""
    skills_src = tmp_path / "skills_src"
    skills_src.mkdir()
    (skills_src / "AGENTS.md").write_text("# fake AGENTS")
    (skills_src / "vfx-shader").mkdir()
    (skills_src / "vfx-shader" / "SKILL.md").write_text("# fake SKILL")

    workdir = tmp_path / "workdir"
    workdir.mkdir()

    b = KimiBackend(proxy=None, timeout_seconds=60)
    b.setup_workspace(workdir, skills_src)

    assert (workdir / "skills").is_symlink()
    assert (workdir / "skills").resolve() == skills_src.resolve()
    assert (workdir / "AGENTS.md").is_symlink()
    assert (workdir / "CLAUDE.md").is_symlink()
    # AGENTS.md + CLAUDE.md point to same source
    agents_target = (workdir / "AGENTS.md").resolve()
    claude_target = (workdir / "CLAUDE.md").resolve()
    assert agents_target == (skills_src / "AGENTS.md").resolve()
    assert claude_target == (skills_src / "AGENTS.md").resolve()


def test_setup_workspace_is_idempotent(tmp_path):
    """Calling setup_workspace twice must not error."""
    skills_src = tmp_path / "skills_src"
    skills_src.mkdir()
    (skills_src / "AGENTS.md").write_text("# fake")

    workdir = tmp_path / "workdir"
    workdir.mkdir()

    b = KimiBackend(proxy=None, timeout_seconds=60)
    b.setup_workspace(workdir, skills_src)
    b.setup_workspace(workdir, skills_src)  # second call: no-op
    assert (workdir / "AGENTS.md").exists()
    assert (workdir / "CLAUDE.md").exists()
    assert (workdir / "skills").exists()
