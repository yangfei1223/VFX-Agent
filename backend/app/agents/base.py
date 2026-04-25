"""Agent 基类：统一 LLM 调用封装，支持文本和图片输入"""

import base64
from pathlib import Path
from typing import Any

from openai import OpenAI

from app.config import ModelConfig


class BaseAgent:
    """所有 Agent 的基类，封装 LLM 调用逻辑"""

    def __init__(self, model_config: ModelConfig):
        """
        根据传入的 ModelConfig 初始化 LLM 客户端。
        ModelConfig 来自 settings.decompose / settings.generate / settings.inspect。
        """
        self.client = OpenAI(
            api_key=model_config.api_key,
            base_url=model_config.base_url,
        )
        self.model = model_config.model
        self.model_config = model_config

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        image_paths: list[str] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """调用 LLM，支持可选的图片输入（多模态）"""
        content: list[Any] = [{"type": "text", "text": user_prompt}]

        if image_paths:
            for path in image_paths:
                image_data = base64.b64encode(Path(path).read_bytes()).decode()
                ext = Path(path).suffix.lower()
                mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
                mime = mime_map.get(ext, "image/png")
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{image_data}"},
                })

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content if image_paths else user_prompt},
        ]

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        return response.choices[0].message.content or ""