from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 代理配置（全局）
    proxy: str = ""  # e.g. "http://127.0.0.1:7890" or "socks5://127.0.0.1:7890"

    # 服务配置
    host: str = "0.0.0.0"
    port: int = 8000
    frontend_url: str = "http://localhost:5173"

    # Codex 调用配置
    codex_proxy: str = "http://127.0.0.1:7890"
    codex_timeout: int = 600
    passing_score: float = 0.85

    # Pipeline 配置
    max_iterations: int = 5
    render_timeout_ms: int = 2000
    screenshot_width: int = 1280
    screenshot_height: int = 720

    # Workdir root for pipeline runs
    workdir_root: str = "/tmp/vfx_workdirs"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
