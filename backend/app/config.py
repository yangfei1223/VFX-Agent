from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 服务配置
    proxy: str = ""
    host: str = "0.0.0.0"
    port: int = 8000
    frontend_url: str = "http://localhost:5173"

    # Codex backend (default)
    codex_proxy: str = "http://127.0.0.1:7890"
    codex_timeout: int = 600

    # Claude Code backend
    claude_code_proxy: str = ""  # empty = direct connection (DeepSeek doesn't need proxy)
    claude_code_timeout: int = 600

    # Kimi Code backend (Moonshot K3; China-domestic, no proxy needed)
    kimi_proxy: str = ""
    kimi_timeout: int = 600

    # Pipeline 配置
    max_iterations: int = 5
    passing_score: float = 0.85
    render_timeout_ms: int = 2000
    screenshot_width: int = 1280
    screenshot_height: int = 720

    # Workdir root for pipeline runs
    workdir_root: str = "/tmp/vfx_workdirs"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    def backend_proxy(self, name: str) -> str:
        """Get proxy URL for a backend by name.

        Naming convention: "<name>_proxy" with hyphens replaced by underscores.
        Empty string for unknown backends (safe fallback).
        """
        attr = f"{name.replace('-', '_')}_proxy"
        return getattr(self, attr, "")

    def backend_timeout(self, name: str) -> int:
        """Get timeout for a backend by name. 600s default if unknown."""
        attr = f"{name.replace('-', '_')}_timeout"
        return getattr(self, attr, 600)


settings = Settings()
