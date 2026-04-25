from pydantic_settings import BaseSettings


class ModelConfig:
    """单个 Agent 角色的模型配置"""
    def __init__(self, api_key: str, base_url: str, model: str, proxy: str | None = None):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.proxy = proxy


class Settings(BaseSettings):
    # Decompose Agent（视觉解构，需要多模态能力）
    decompose_api_key: str = ""
    decompose_base_url: str = "https://api.moonshot.cn/v1"
    decompose_model: str = "kimi-2.6"

    # Generate Agent（代码生成，需要强 coding 能力）
    generate_api_key: str = ""
    generate_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    generate_model: str = "glm-5.1"

    # Inspect Agent（视觉检视，需要多模态能力）
    inspect_api_key: str = ""
    inspect_base_url: str = "https://api.moonshot.cn/v1"
    inspect_model: str = "kimi-2.6"

    # 代理配置（全局）
    proxy: str = ""  # e.g. "http://127.0.0.1:7890" or "socks5://127.0.0.1:7890"

    # 服务配置
    host: str = "0.0.0.0"
    port: int = 8000
    frontend_url: str = "http://localhost:5173"

    # Pipeline 配置
    max_iterations: int = 5
    render_timeout_ms: int = 2000
    screenshot_width: int = 512
    screenshot_height: int = 512

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def decompose(self) -> ModelConfig:
        return ModelConfig(self.decompose_api_key, self.decompose_base_url, self.decompose_model, self.proxy)

    @property
    def generate(self) -> ModelConfig:
        return ModelConfig(self.generate_api_key, self.generate_base_url, self.generate_model, self.proxy)

    @property
    def inspect(self) -> ModelConfig:
        return ModelConfig(self.inspect_api_key, self.inspect_base_url, self.inspect_model, self.proxy)


settings = Settings()