"""Test orchestrator (mock codex subprocess)."""
import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.orchestrator import PipelineOrchestrator
from app.state_store import PipelineRecord, StateStore


@pytest.fixture
def fake_workdir(tmp_path, monkeypatch):
    """Fake workdir layout for one pipeline."""
    workdir = tmp_path / "pipeline_test"
    (workdir / "keyframes").mkdir(parents=True)
    (workdir / "output").mkdir(parents=True)
    # Fake keyframes
    (workdir / "keyframes" / "001.png").write_bytes(b"fake_png")
    (workdir / "keyframes" / "002.png").write_bytes(b"fake_png")
    return workdir


@pytest.fixture
def fake_codex_output():
    """Fake JSONL events from codex."""
    return [
        {"type": "thread.started", "thread_id": "abc"},
        {"type": "turn.started"},
        {"type": "item.completed", "item": {
            "id": "i1", "type": "agent_message", "text": "starting"
        }},
        {"type": "item.completed", "item": {
            "id": "i2", "type": "command_execution",
            "command": "python reference/scripts/validate_shader.py shader.glsl",
            "exit_code": 0
        }},
        {"type": "turn.completed", "usage": {
            "input_tokens": 1000, "output_tokens": 100
        }},
    ]


@pytest.mark.asyncio
async def test_orchestrator_run_success(fake_workdir, fake_codex_output, tmp_path, monkeypatch):
    """Test happy path: codex writes final_shader.glsl + evaluation.json."""
    # Prepare fake codex outputs
    (fake_workdir / "final_shader.glsl").write_text("void mainImage(out vec4 fragColor, vec2 fragCoord) { fragColor = vec4(1.0); }")
    (fake_workdir / "evaluation.json").write_text(json.dumps({
        "overall_score": 0.92,
        "dimension_scores": {"color": {"score": 0.9}},
    }))

    # Mock subprocess - use a regular MagicMock so `await proc` returns proc itself
    mock_proc = MagicMock()
    mock_proc.stdin = AsyncMock()
    mock_proc.stdin.write = MagicMock()
    mock_proc.stdin.drain = AsyncMock()
    mock_proc.stdin.close = MagicMock()
    mock_proc.stdin.wait_closed = AsyncMock()
    mock_proc.wait = AsyncMock(return_value=0)
    mock_proc.returncode = 0

    async def mock_stdout():
        for event in fake_codex_output:
            yield (json.dumps(event) + "\n").encode()
    mock_proc.stdout = mock_stdout()
    mock_proc.stderr = AsyncMock()
    mock_proc.stderr.read = AsyncMock(return_value=b"")

    # create_subprocess_exec is a coroutine; side_effect coroutine ensures await returns mock_proc
    async def _fake_cse(*args, **kwargs):
        return mock_proc

    monkeypatch.setattr(StateStore, "STORE_DIR", tmp_path / "states")
    with patch("asyncio.create_subprocess_exec", _fake_cse):
        orch = PipelineOrchestrator()
        record = await orch.run(
            pipeline_id="test-123",
            workdir=str(fake_workdir),
            keyframes=[str(fake_workdir / "keyframes" / "001.png")],
            notes="test shader",
            max_iterations=3,
        )

    assert record.status == "passed"
    assert record.final_score == 0.92
    assert "mainImage" in record.final_shader


@pytest.mark.asyncio
async def test_orchestrator_handles_missing_final_shader(fake_workdir, fake_codex_output, tmp_path, monkeypatch):
    """If codex didn't write final_shader.glsl, fallback to shader.glsl."""
    (fake_workdir / "shader.glsl").write_text("// fallback shader")
    # No final_shader.glsl

    mock_proc = MagicMock()
    mock_proc.stdin = AsyncMock()
    mock_proc.stdin.write = MagicMock()
    mock_proc.stdin.drain = AsyncMock()
    mock_proc.stdin.close = MagicMock()
    mock_proc.stdin.wait_closed = AsyncMock()
    mock_proc.wait = AsyncMock(return_value=0)
    mock_proc.returncode = 0

    async def mock_stdout():
        for event in fake_codex_output:
            yield (json.dumps(event) + "\n").encode()
    mock_proc.stdout = mock_stdout()
    mock_proc.stderr = AsyncMock()
    mock_proc.stderr.read = AsyncMock(return_value=b"")

    async def _fake_cse(*args, **kwargs):
        return mock_proc

    monkeypatch.setattr(StateStore, "STORE_DIR", tmp_path / "states")
    with patch("asyncio.create_subprocess_exec", _fake_cse):
        orch = PipelineOrchestrator()
        record = await orch.run(
            pipeline_id="test-456",
            workdir=str(fake_workdir),
            keyframes=[],
            notes="",
            max_iterations=3,
        )

    assert record.final_shader == "// fallback shader"
    assert record.status == "failed"


@pytest.mark.asyncio
async def test_orchestrator_handles_codex_crash(fake_workdir, fake_codex_output, tmp_path, monkeypatch):
    """If codex subprocess crashes (returncode != 0), record.error contains stderr snippet."""
    # No outputs written - codex crashed before producing anything

    mock_proc = MagicMock()
    mock_proc.stdin = AsyncMock()
    mock_proc.stdin.write = MagicMock()
    mock_proc.stdin.drain = AsyncMock()
    mock_proc.stdin.close = MagicMock()
    mock_proc.stdin.wait_closed = AsyncMock()
    mock_proc.wait = AsyncMock(return_value=2)  # non-zero exit
    mock_proc.returncode = 2

    async def mock_stdout():
        for event in fake_codex_output[:2]:
            yield (json.dumps(event) + "\n").encode()
    mock_proc.stdout = mock_stdout()

    mock_proc.stderr = AsyncMock()
    mock_proc.stderr.read = AsyncMock(return_value=b"Error: API key invalid\n")

    async def _fake_cse(*args, **kwargs):
        return mock_proc

    monkeypatch.setattr(StateStore, "STORE_DIR", tmp_path / "states")
    with patch("asyncio.create_subprocess_exec", _fake_cse):
        orch = PipelineOrchestrator()
        record = await orch.run(
            pipeline_id="test-crash",
            workdir=str(fake_workdir),
            keyframes=[],
            notes="",
            max_iterations=3,
        )

    assert record.status == "failed"
    assert "codex subprocess error" in (record.error or "")
    assert "API key invalid" in (record.error or "")


@pytest.mark.asyncio
async def test_orchestrator_timeout_with_valid_outputs_marks_passed(
    fake_workdir, fake_codex_output, tmp_path, monkeypatch
):
    """If codex times out but wrote final_shader.glsl + evaluation.json with score >= 0.85,
    status should be 'passed' (not 'timeout'). Mirrors heart-2d MVP observed behavior.
    """
    # Pre-write the outputs codex would have produced
    (fake_workdir / "final_shader.glsl").write_text("void mainImage(...) {}")
    (fake_workdir / "evaluation.json").write_text(json.dumps({
        "overall_score": 0.901,
        "passed": True,
        "dimension_scores": {"color": {"score": 0.9}},
    }))

    mock_proc = MagicMock()
    mock_proc.stdin = AsyncMock()
    mock_proc.stdin.write = MagicMock()
    mock_proc.stdin.drain = AsyncMock()
    mock_proc.stdin.close = MagicMock()
    mock_proc.stdin.wait_closed = AsyncMock()
    mock_proc.wait = AsyncMock(return_value=0)
    mock_proc.returncode = 0

    async def mock_stdout():
        # Yield some events then EOF (codex timed out mid-stream)
        for event in fake_codex_output[:3]:
            yield (json.dumps(event) + "\n").encode()
    mock_proc.stdout = mock_stdout()
    mock_proc.stderr = AsyncMock()
    mock_proc.stderr.read = AsyncMock(return_value=b"")

    async def _fake_cse(*args, **kwargs):
        return mock_proc

    # Force timeout=0.001 to trigger TimeoutError immediately after first event
    monkeypatch.setattr(StateStore, "STORE_DIR", tmp_path / "states")
    with patch("asyncio.create_subprocess_exec", _fake_cse):
        # Patch timeout to near-zero to force the timeout path
        orch = PipelineOrchestrator()
        orch.CODEX_TIMEOUT = 0.001
        record = await orch.run(
            pipeline_id="test-timeout-pass",
            workdir=str(fake_workdir),
            keyframes=[],
            notes="",
            max_iterations=3,
        )

    assert record.final_score == 0.901
    assert record.status == "passed"  # NOT timeout, because outputs are valid and score >= 0.85
    assert record.error is None  # error cleared on pass


@pytest.mark.asyncio
async def test_orchestrator_timeout_with_missing_outputs_marks_timeout(
    fake_workdir, fake_codex_output, tmp_path, monkeypatch
):
    """If codex times out and produced NO outputs, status should be 'timeout'."""
    # No outputs written

    async def _fake_spawn_and_stream(*args, **kwargs):
        # Simulate codex hanging forever — raise TimeoutError directly
        raise asyncio.TimeoutError("fake timeout")
        yield  # noqa: never reached, makes this an async generator

    monkeypatch.setattr(StateStore, "STORE_DIR", tmp_path / "states")
    monkeypatch.setattr(PipelineOrchestrator, "_spawn_and_stream", _fake_spawn_and_stream)
    orch = PipelineOrchestrator()
    record = await orch.run(
        pipeline_id="test-timeout-real",
        workdir=str(fake_workdir),
        keyframes=[],
        notes="",
        max_iterations=3,
    )

    assert record.status == "timeout"
    assert "timed out" in (record.error or "")
