"""Tests for per-backend config helpers."""
from app.config import Settings


def test_settings_has_codex_proxy_timeout():
    s = Settings()
    assert hasattr(s, "codex_proxy")
    assert hasattr(s, "codex_timeout")


def test_settings_has_claude_code_proxy_timeout():
    s = Settings()
    assert hasattr(s, "claude_code_proxy")
    assert hasattr(s, "claude_code_timeout")


def test_settings_has_kimi_proxy_timeout():
    s = Settings()
    assert hasattr(s, "kimi_proxy")
    assert hasattr(s, "kimi_timeout")


def test_backend_proxy_lookup():
    s = Settings()
    assert s.backend_proxy("codex") == s.codex_proxy
    assert s.backend_proxy("claude-code") == s.claude_code_proxy
    assert s.backend_proxy("kimi") == s.kimi_proxy


def test_backend_proxy_unknown_backend_returns_empty():
    """Unknown backend name → empty proxy (safe fallback)."""
    s = Settings()
    assert s.backend_proxy("nonexistent") == ""


def test_backend_timeout_lookup():
    s = Settings()
    assert s.backend_timeout("codex") == s.codex_timeout
    assert s.backend_timeout("claude-code") == s.claude_code_timeout
    assert s.backend_timeout("kimi") == s.kimi_timeout


def test_backend_timeout_unknown_backend_returns_default():
    """Unknown backend → 600s default (safe fallback)."""
    s = Settings()
    assert s.backend_timeout("nonexistent") == 600
