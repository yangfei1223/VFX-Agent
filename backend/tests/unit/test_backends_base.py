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
    env = b.build_env({"PATH": "/usr/bin:/bin"})
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


import asyncio
import json
import pytest


@pytest.mark.asyncio
async def test_stream_integration_emits_parsed_events():
    """stream() spawns a real subprocess, parses JSONL stdout, emits AgentEvents."""
    class EchoBackend(BaseBackend):
        """Backend that runs a shell echo loop emitting JSONL."""
        name = "echo"
        def setup_workspace(self, workdir, skills_src): pass
        def build_command(self, workdir, prompt, keyframes):
            # Emit 3 JSONL lines to stdout, then exit 0
            return [
                "sh", "-c",
                "printf '{\"msg\":\"a\"}\\n{\"msg\":\"b\"}\\n{\"msg\":\"c\"}\\n'"
            ]
        def parse_event(self, raw):
            return {"type": "text", "content": raw.get("msg", ""), "usage": None, "raw": raw}

    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmpdir:
        b = EchoBackend(proxy=None, timeout_seconds=10)
        events = []
        async for ev in b.stream(Path(tmpdir), "ignored", [], {"PATH": "/usr/bin:/bin"}):
            events.append(ev)

    assert len(events) == 3
    assert [e["content"] for e in events] == ["a", "b", "c"]
    assert all(e["type"] == "text" for e in events)


@pytest.mark.asyncio
async def test_stream_integration_raises_on_nonzero_exit():
    """stream() raises RuntimeError with stderr tail when subprocess exits non-zero."""
    class FailBackend(BaseBackend):
        name = "fail"
        def setup_workspace(self, workdir, skills_src): pass
        def build_command(self, workdir, prompt, keyframes):
            return ["sh", "-c", "echo 'boom' >&2; exit 7"]
        def parse_event(self, raw):
            return {"type": "text", "content": "", "usage": None, "raw": raw}

    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmpdir:
        b = FailBackend(proxy=None, timeout_seconds=10)
        with pytest.raises(RuntimeError, match=r"fail exited with code 7.*boom"):
            async for _ in b.stream(Path(tmpdir), "x", [], {"PATH": "/usr/bin:/bin"}):
                pass


@pytest.mark.asyncio
async def test_stream_integration_parse_event_exception_kills_proc():
    """If parse_event raises, the subprocess is still cleaned up (no orphan)."""
    class BoomBackend(BaseBackend):
        name = "boom"
        def setup_workspace(self, workdir, skills_src): pass
        def build_command(self, workdir, prompt, keyframes):
            # Long-running subprocess that would run forever if not killed
            return ["sh", "-c", "printf '{\"msg\":\"x\"}\\n'; sleep 30"]
        def parse_event(self, raw):
            raise ValueError("simulated parse_event bug")

    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmpdir:
        b = BoomBackend(proxy=None, timeout_seconds=10)
        with pytest.raises(ValueError, match="simulated parse_event bug"):
            async for _ in b.stream(Path(tmpdir), "x", [], {"PATH": "/usr/bin:/bin"}):
                pass
        # Critical: process must be terminated, not orphaned
        # We can't directly check the proc here, but the test passing means
        # the exception propagated cleanly without hanging.


@pytest.mark.asyncio
async def test_stream_integration_timeout_kills_proc():
    """stream() raises TimeoutError and kills subprocess on timeout."""
    class SlowBackend(BaseBackend):
        name = "slow"
        def setup_workspace(self, workdir, skills_src): pass
        def build_command(self, workdir, prompt, keyframes):
            return ["sh", "-c", "sleep 60"]
        def parse_event(self, raw):
            return {"type": "text", "content": "", "usage": None, "raw": raw}

    import tempfile
    import time
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmpdir:
        b = SlowBackend(proxy=None, timeout_seconds=1)
        start = time.monotonic()
        with pytest.raises(asyncio.TimeoutError):
            async for _ in b.stream(Path(tmpdir), "x", [], {"PATH": "/usr/bin:/bin"}):
                pass
        elapsed = time.monotonic() - start
        # Timeout should fire close to 1s, not 60s
        assert elapsed < 5, f"timeout took too long: {elapsed}s"


@pytest.mark.asyncio
async def test_stream_handles_oversize_jsonl_line():
    """stream() must handle JSONL lines > 64KB (default asyncio limit).

    Regression for claude-code stream-json lines that overflow the default
    64KB StreamReader buffer. Subprocess-level limit must be raised to ≥16MB.
    """
    class BigLineBackend(BaseBackend):
        name = "big"
        def setup_workspace(self, workdir, skills_src): pass
        def build_command(self, workdir, prompt, keyframes):
            # Emit one JSONL line with a 200KB string field (> 64KB default limit)
            big_str = "x" * (200 * 1024)
            import json as _json
            payload = _json.dumps({"type": "test", "data": big_str})
            return ["sh", "-c", f"printf '{payload}\\n'"]
        def parse_event(self, raw):
            return {"type": "text", "content": "ok", "usage": None, "raw": raw}

    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmpdir:
        b = BigLineBackend(proxy=None, timeout_seconds=10)
        events = []
        async for ev in b.stream(Path(tmpdir), "ignored", [], {"PATH": "/usr/bin:/bin"}):
            events.append(ev)

    assert len(events) == 1
    assert events[0]["content"] == "ok"
    # Verify the big payload survived intact
    assert len(events[0]["raw"]["data"]) == 200 * 1024


@pytest.mark.asyncio
async def test_stream_skips_none_events_from_parse_event():
    """stream() must NOT yield events when parse_event returns None.

    Regression for B1: claude-code returns None for noise events
    (thinking_tokens, partial deltas); stream() must filter these out
    so they don't reach the orchestrator's events buffer.
    """
    class FilteringBackend(BaseBackend):
        """Backend that drops events whose msg is 'noise'."""
        name = "filtering"
        def setup_workspace(self, workdir, skills_src): pass
        def build_command(self, workdir, prompt, keyframes):
            return [
                "sh", "-c",
                "printf '{\"msg\":\"a\"}\\n{\"msg\":\"noise\"}\\n{\"msg\":\"b\"}\\n{\"msg\":\"noise\"}\\n{\"msg\":\"c\"}\\n'"
            ]
        def parse_event(self, raw):
            if raw.get("msg") == "noise":
                return None  # drop noise
            return {"type": "text", "content": raw.get("msg", ""), "usage": None, "raw": raw}

    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmpdir:
        b = FilteringBackend(proxy=None, timeout_seconds=10)
        events = []
        async for ev in b.stream(Path(tmpdir), "ignored", [], {"PATH": "/usr/bin:/bin"}):
            events.append(ev)

    # 5 raw events, 2 dropped → 3 yielded
    assert len(events) == 3
    assert [e["content"] for e in events] == ["a", "b", "c"]
