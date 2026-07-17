"""Agent backend adapters (codex / claude-code / future).

Backend registration happens here. Adding a new backend = add a class +
register one line in BACKEND_REGISTRY. Orchestrator code never changes.
"""
from pathlib import Path
from typing import Optional

from .base import BaseBackend, AgentEvent

# Lazy registry: concrete backends are added as they're implemented (T3, T5).
# Type annotation makes it clear this is a class registry, not instances.
BACKEND_REGISTRY: dict[str, type[BaseBackend]] = {}


def register_backend(name: str, cls: type[BaseBackend]) -> None:
    """Register a backend class under a name. Idempotent."""
    if not issubclass(cls, BaseBackend):
        raise TypeError(f"{cls} must subclass BaseBackend")
    BACKEND_REGISTRY[name] = cls


def get_backend(
    name: str, *, proxy: Optional[str], timeout_seconds: int,
) -> BaseBackend:
    """Factory: instantiate a backend by name.

    Args:
        name: Backend identifier ("codex" | "claude-code" | future).
        proxy: HTTP/HTTPS proxy URL, or None for direct connection.
        timeout_seconds: Hard subprocess timeout.

    Raises:
        ValueError: If name is not in BACKEND_REGISTRY.
    """
    cls = BACKEND_REGISTRY.get(name)
    if not cls:
        available = list(BACKEND_REGISTRY.keys())
        raise ValueError(f"unknown backend '{name}', available: {available}")
    return cls(proxy=proxy, timeout_seconds=timeout_seconds)


__all__ = ["BaseBackend", "AgentEvent", "BACKEND_REGISTRY", "register_backend", "get_backend"]
