"""Runtime configuration API"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/config", tags=["config"])


class RuntimeConfig(BaseModel):
    """Runtime configuration settings"""
    max_iterations: int = Field(default=5, ge=1, le=100, description="Maximum number of iteration cycles")
    passing_threshold: float = Field(default=0.85, ge=0.5, le=1.0, description="Minimum score to pass inspection")
    
    # V3.0 新增参数
    re_decompose_threshold: float = Field(default=0.5, ge=0.0, le=1.0, description="Score below this triggers re-decompose")
    gradient_window_size: int = Field(default=3, ge=1, le=10, description="Max entries in gradient window")
    stagnation_variance: float = Field(default=0.05, ge=0.0, le=0.5, description="Variance threshold for stagnation detection")
    stagnation_window: int = Field(default=3, ge=1, le=10, description="Window size for stagnation detection")
    render_timeout_ms: int = Field(default=2000, ge=500, le=10000, description="Shader render timeout in milliseconds")
    screenshot_width: int = Field(default=1024, ge=256, le=2048, description="Screenshot width")
    screenshot_height: int = Field(default=1024, ge=256, le=2048, description="Screenshot height")


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