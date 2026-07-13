"""Unit tests for state_store (v2.0)"""
import json
import tempfile
from pathlib import Path
import pytest
from app.state_store import PipelineRecord, StateStore


@pytest.fixture
def temp_store(tmp_path, monkeypatch):
    monkeypatch.setattr(StateStore, "STORE_DIR", tmp_path / "states")
    return StateStore


def test_save_and_load_record(temp_store):
    record = PipelineRecord(
        pipeline_id="test-123",
        status="running",
        workdir="/tmp/test",
        keyframe_paths=["/tmp/a.png", "/tmp/b.png"],
    )
    temp_store.save(record)
    
    loaded = temp_store.load("test-123")
    assert loaded is not None
    assert loaded.pipeline_id == "test-123"
    assert loaded.status == "running"
    assert loaded.keyframe_paths == ["/tmp/a.png", "/tmp/b.png"]


def test_load_nonexistent_returns_none(temp_store):
    assert temp_store.load("nonexistent") is None


def test_save_overwrites_existing(temp_store):
    record = PipelineRecord(
        pipeline_id="test-456",
        status="running",
        workdir="/tmp/test",
        keyframe_paths=[],
    )
    temp_store.save(record)
    
    record.status = "passed"
    record.final_score = 0.92
    temp_store.save(record)
    
    loaded = temp_store.load("test-456")
    assert loaded.status == "passed"
    assert loaded.final_score == 0.92


def test_save_creates_store_dir(temp_store, tmp_path):
    store_dir = tmp_path / "states"
    assert not store_dir.exists()
    
    record = PipelineRecord(
        pipeline_id="test-789",
        status="running",
        workdir="/tmp/test",
        keyframe_paths=[],
    )
    temp_store.save(record)
    
    assert store_dir.exists()
    assert (store_dir / "test-789.json").exists()
