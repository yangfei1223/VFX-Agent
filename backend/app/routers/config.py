"""Runtime configuration API (v2.0+ multi-backend)."""
from fastapi import APIRouter
from pydantic import BaseModel, Field
from pathlib import Path
from typing import Literal
import json

router = APIRouter(prefix="/config", tags=["config"])


class RuntimeConfig(BaseModel):
    """Runtime configuration settings (v2.0+ multi-backend)."""
    # ── Backend ──
    backend: Literal["codex", "claude-code", "kimi"] = "codex"
    codex_proxy: str = "http://127.0.0.1:7890"
    codex_timeout: int = Field(default=600, ge=60, le=3600)
    claude_code_proxy: str = ""  # empty = direct connection
    claude_code_timeout: int = Field(default=600, ge=60, le=3600)
    kimi_proxy: str = ""  # China-domestic, no proxy needed
    kimi_timeout: int = Field(default=600, ge=60, le=3600)

    # ── Pipeline ──
    max_iterations: int = Field(default=5, ge=1, le=100)
    passing_threshold: float = Field(default=0.85, ge=0.5, le=1.0)

    # ── Render ──
    render_timeout_ms: int = Field(default=2000, ge=500, le=10000)
    screenshot_width: int = Field(default=1280, ge=256, le=2048)
    screenshot_height: int = Field(default=720, ge=256, le=2048)

    # ── System ──
    workdir_root: str = "/tmp/vfx_workdirs"


# Global runtime config storage
runtime_config: RuntimeConfig = RuntimeConfig()
CONFIG_FILE_PATH = Path("app/config/runtime_config.json")


@router.get("")
async def get_config() -> dict:
    return runtime_config.model_dump()


@router.put("")
async def update_config(config: RuntimeConfig) -> dict:
    global runtime_config
    runtime_config = config
    save_config_to_file()
    return runtime_config.model_dump()


@router.post("/reset")
async def reset_config() -> dict:
    global runtime_config
    runtime_config = RuntimeConfig()
    save_config_to_file()
    return runtime_config.model_dump()


@router.get("/file")
async def get_config_file() -> dict:
    if CONFIG_FILE_PATH.exists():
        return {"path": str(CONFIG_FILE_PATH), "content": CONFIG_FILE_PATH.read_text()}
    return {"path": str(CONFIG_FILE_PATH), "content": "File not found, using defaults"}


@router.put("/file")
async def update_config_file(content: str) -> dict:
    try:
        data = json.loads(content)
        config = RuntimeConfig(**data)
        CONFIG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE_PATH.write_text(json.dumps(config.model_dump(), indent=2))
        global runtime_config
        runtime_config = config
        return {"success": True, "config": runtime_config.model_dump()}
    except Exception as e:
        return {"success": False, "error": str(e)}


def save_config_to_file():
    CONFIG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE_PATH.write_text(json.dumps(runtime_config.model_dump(), indent=2))


def load_config_from_file():
    if CONFIG_FILE_PATH.exists():
        try:
            data = json.loads(CONFIG_FILE_PATH.read_text())
            global runtime_config
            runtime_config = RuntimeConfig(**data)
        except Exception as e:
            print(f"Failed to load config from file: {e}")


def get_runtime_config() -> RuntimeConfig:
    return runtime_config
