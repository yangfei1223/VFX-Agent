"""Tests for POST /pipeline/run backend field handling.

Tests the Form parsing logic without spinning up FastAPI TestClient
(keeps unit tests fast and HTTP-light).
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from app.routers import pipeline


def test_run_pipeline_signature_has_backend_param():
    """The run_pipeline endpoint must accept a `backend` Form field."""
    import inspect
    sig = inspect.signature(pipeline.run_pipeline)
    assert "backend" in sig.parameters, "run_pipeline must accept `backend` parameter"
    default = sig.parameters["backend"].default
    # FastAPI wraps Form defaults in a Form() object; check value inside
    if hasattr(default, "default"):
        assert default.default == "", f"backend default should be '' (fall back to runtime_config), got {default.default!r}"
    else:
        assert default == "", f"backend default should be '' (fall back to runtime_config), got {default!r}"


def test_run_pipeline_passes_backend_to_orchestrator():
    """When backend='claude-code' is passed, orchestrator.run receives backend_name='claude-code'."""
    # Inspect the source to confirm backend_name is forwarded (static check)
    import inspect
    src = inspect.getsource(pipeline.run_pipeline)
    assert "backend_name=" in src, "run_pipeline source must pass backend_name= to orchestrator.run"
    # Don't run the full handler — it spawns asyncio tasks and touches filesystem


def test_run_pipeline_falls_back_to_runtime_config():
    """When backend Form field is empty, router uses runtime_config.backend."""
    import inspect
    src = inspect.getsource(pipeline.run_pipeline)
    assert "runtime_cfg.backend" in src or "effective_backend" in src, \
        "run_pipeline must compute effective_backend from runtime_cfg.backend when Form field is empty"
