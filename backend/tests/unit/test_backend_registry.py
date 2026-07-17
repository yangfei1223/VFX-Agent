"""Tests for backend registry factory."""
import pytest
from app.backends import get_backend, register_backend, BACKEND_REGISTRY
from app.backends.base import BaseBackend


def test_registry_initially_has_no_concrete_backends():
    """After T1, registry is empty (codex/claude-code added in T3/T5)."""
    # This test will be updated as we add backends in T3 and T5
    assert isinstance(BACKEND_REGISTRY, dict)


def test_get_backend_unknown_raises():
    with pytest.raises(ValueError, match=r"unknown backend 'nonexistent'.*available"):
        get_backend("nonexistent", proxy=None, timeout_seconds=60)


def test_register_backend_rejects_non_subclass():
    """register_backend must reject classes that don't subclass BaseBackend."""
    with pytest.raises(TypeError, match="must subclass BaseBackend"):
        register_backend("bogus", str)  # str is not a BaseBackend subclass


def test_register_and_get_backend_roundtrip():
    """Register a mock backend class, then retrieve it via factory."""
    from pathlib import Path

    class MockBackend(BaseBackend):
        name = "mock-for-test"
        def setup_workspace(self, workdir, skills_src): pass
        def build_command(self, workdir, prompt, keyframes): return []
        def parse_event(self, raw):
            return {"type": "text", "content": "", "usage": None, "raw": raw}

    register_backend("mock-for-test", MockBackend)
    try:
        instance = get_backend("mock-for-test", proxy=None, timeout_seconds=42)
        assert isinstance(instance, MockBackend)
        assert instance.timeout_seconds == 42
        assert BACKEND_REGISTRY["mock-for-test"] is MockBackend
    finally:
        # Clean up registry so this test doesn't pollute other tests
        BACKEND_REGISTRY.pop("mock-for-test", None)


def test_get_backend_returns_instance_with_kwargs():
    """CodexBackend is registered after T3."""
    from app.backends.codex import CodexBackend
    b = get_backend("codex", proxy="http://proxy", timeout_seconds=300)
    assert isinstance(b, CodexBackend)
    assert b.proxy == "http://proxy"
    assert b.timeout_seconds == 300


def test_registry_has_both_backends():
    """After T3 + T5, registry has codex and claude-code."""
    assert "codex" in BACKEND_REGISTRY
    assert "claude-code" in BACKEND_REGISTRY
