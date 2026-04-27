"""Runtime configuration API"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/config", tags=["config"])


class RuntimeConfig(BaseModel):
    """Runtime configuration settings"""
    max_iterations: int = Field(default=3, ge=1, le=100, description="Maximum number of iteration cycles (includes both visual refinement and compile fixes)")
    passing_threshold: float = Field(default=0.85, ge=0.5, le=1.0, description="Minimum similarity score to pass inspection")


# Global runtime config storage
runtime_config: RuntimeConfig = RuntimeConfig()


@router.get("")
async def get_config() -> dict:
    """Get current runtime configuration"""
    return runtime_config.model_dump()


@router.put("")
async def update_config(config: RuntimeConfig) -> dict:
    """Update runtime configuration"""
    global runtime_config
    runtime_config = config
    return runtime_config.model_dump()


@router.post("/reset")
async def reset_config() -> dict:
    """Reset configuration to defaults"""
    global runtime_config
    runtime_config = RuntimeConfig()
    return runtime_config.model_dump()


def get_runtime_config() -> RuntimeConfig:
    """Get the runtime config instance for use in other modules"""
    return runtime_config