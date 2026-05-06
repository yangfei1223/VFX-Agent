"""Runtime configuration API"""

from fastapi import APIRouter
from pydantic import BaseModel, Field
from pathlib import Path
import json

router = APIRouter(prefix="/config", tags=["config"])


class AgentModelConfig(BaseModel):
    """单个 Agent 的模型配置"""
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="LLM temperature")
    max_tokens: int = Field(default=4096, ge=1024, le=16384, description="Max output tokens")
    # model 名称和 API 从 .env 读取，不在此配置（安全考虑）


class RuntimeConfig(BaseModel):
    """Runtime configuration settings"""
    max_iterations: int = Field(default=5, ge=1, le=100, description="Maximum number of iteration cycles")
    passing_threshold: float = Field(default=0.85, ge=0.5, le=1.0, description="Minimum score to pass inspection")
    
    # V3.0 Pipeline 参数
    re_decompose_threshold: float = Field(default=0.5, ge=0.0, le=1.0, description="Score below this triggers re-decompose")
    gradient_window_size: int = Field(default=3, ge=1, le=10, description="Max entries in gradient window")
    stagnation_variance: float = Field(default=0.05, ge=0.0, le=0.5, description="Variance threshold for stagnation detection")
    stagnation_window: int = Field(default=3, ge=1, le=10, description="Window size for stagnation detection")
    render_timeout_ms: int = Field(default=2000, ge=500, le=10000, description="Shader render timeout in milliseconds")
    screenshot_width: int = Field(default=1024, ge=256, le=2048, description="Screenshot width")
    screenshot_height: int = Field(default=1024, ge=256, le=2048, description="Screenshot height")
    
    # Agent 模型参数（动态可调）
    decompose_agent: AgentModelConfig = Field(default_factory=lambda: AgentModelConfig(temperature=0.3, max_tokens=4096))
    generate_agent: AgentModelConfig = Field(default_factory=lambda: AgentModelConfig(temperature=0.5, max_tokens=8192))
    inspect_agent: AgentModelConfig = Field(default_factory=lambda: AgentModelConfig(temperature=0.3, max_tokens=4096))


# Global runtime config storage
runtime_config: RuntimeConfig = RuntimeConfig()

# Config file path
CONFIG_FILE_PATH = Path("app/config/runtime_config.json")


@router.get("")
async def get_config() -> dict:
    """Get current runtime configuration"""
    return runtime_config.model_dump()


@router.put("")
async def update_config(config: RuntimeConfig) -> dict:
    """Update runtime configuration"""
    global runtime_config
    runtime_config = config
    save_config_to_file()
    return runtime_config.model_dump()


@router.post("/reset")
async def reset_config() -> dict:
    """Reset configuration to defaults"""
    global runtime_config
    runtime_config = RuntimeConfig()
    save_config_to_file()
    return runtime_config.model_dump()


@router.get("/file")
async def get_config_file() -> dict:
    """Get config file content"""
    if CONFIG_FILE_PATH.exists():
        content = CONFIG_FILE_PATH.read_text()
        return {"path": str(CONFIG_FILE_PATH), "content": content}
    else:
        return {"path": str(CONFIG_FILE_PATH), "content": "File not found, using defaults"}


@router.put("/file")
async def update_config_file(content: str) -> dict:
    """Update config file directly"""
    try:
        # Parse and validate
        data = json.loads(content)
        config = RuntimeConfig(**data)
        
        # Save to file
        CONFIG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE_PATH.write_text(json.dumps(config.model_dump(), indent=2))
        
        # Update runtime config
        global runtime_config
        runtime_config = config
        
        return {"success": True, "config": runtime_config.model_dump()}
    except Exception as e:
        return {"success": False, "error": str(e)}


def save_config_to_file():
    """Save current config to file"""
    CONFIG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE_PATH.write_text(json.dumps(runtime_config.model_dump(), indent=2))


def load_config_from_file():
    """Load config from file (called on startup)"""
    if CONFIG_FILE_PATH.exists():
        try:
            data = json.loads(CONFIG_FILE_PATH.read_text())
            global runtime_config
            runtime_config = RuntimeConfig(**data)
        except Exception as e:
            print(f"Failed to load config from file: {e}")


def get_runtime_config() -> RuntimeConfig:
    """Get the runtime config instance for use in other modules"""
    return runtime_config