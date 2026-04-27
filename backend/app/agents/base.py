"""Agent 基类：统一 LLM 调用封装，自动适配 Gemini 和 OpenAI API，支持代理"""

import base64
from pathlib import Path
from typing import Any

import httpx
from openai import OpenAI
from google import genai
from google.genai import types

from app.config import ModelConfig


class BaseAgent:
    """所有 Agent 的基类，封装 LLM 调用逻辑，自动检测 API 类型，支持代理"""

    def __init__(self, model_config: ModelConfig):
        """
        根据传入的 ModelConfig 初始化 LLM 客户端。
        自动检测 base_url 判断使用 Gemini SDK 还是 OpenAI SDK。
        支持代理配置（http/https/socks5）。
        """
        self.model = model_config.model
        self.model_config = model_config
        self._is_gemini = self._detect_gemini_api(model_config.base_url)

        # 创建 httpx client（带代理和超时）
        self._http_client = self._create_http_client(model_config.proxy)

        if self._is_gemini:
            # Gemini 原生 API（暂不使用，因为 SDK 代理配置复杂）
            # 改用 OpenAI-compatible URL
            self._is_gemini = False
            self._openai_client = OpenAI(
                api_key=model_config.api_key,
                base_url=model_config.base_url.replace("/v1beta", "/v1beta/openai"),
                http_client=self._http_client,
            )
        else:
            # OpenAI-compatible API (OpenAI, Moonshot, GLM, DeepSeek, Gemini OpenAI-compatible 等)
            self._openai_client = OpenAI(
                api_key=model_config.api_key,
                base_url=model_config.base_url,
                http_client=self._http_client,
            )

    def _create_http_client(self, proxy: str | None) -> httpx.Client:
        """创建 httpx client，支持代理和超时配置"""
        timeout = httpx.Timeout(60.0, connect=10.0)
        
        # 获取代理配置
        proxy_url = proxy
        if not proxy_url:
            # 检查环境变量中的代理
            import os
            proxy_url = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or os.environ.get("ALL_PROXY")
        
        if proxy_url:
            return httpx.Client(timeout=timeout, proxy=proxy_url)
        else:
            return httpx.Client(timeout=timeout)

    def _detect_gemini_api(self, base_url: str) -> bool:
        """检测是否为 Gemini 原生 API（非 OpenAI-compatible）"""
        if not base_url:
            return False
        
        # OpenAI-compatible URL 特征（优先检测）
        openai_compatible_patterns = [
            "/openai",
            "api.openai.com",
            "api.moonshot.cn",
            "open.bigmodel.cn",
            "api.deepseek.com",
        ]
        for pattern in openai_compatible_patterns:
            if pattern in base_url:
                return False
        
        # Gemini 原生 API URL 特征
        gemini_native_patterns = [
            "generativelanguage.googleapis.com/v1beta",
            "generativelanguage.googleapis.com/v1",
        ]
        for pattern in gemini_native_patterns:
            if pattern in base_url:
                return True
        
        return False

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        image_paths: list[str] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        return_raw: bool = False,
    ) -> str | dict:
        """
        调用 LLM，支持可选的图片输入（多模态）
        
        Args:
            return_raw: 如果 True，返回包含原始响应的 dict，用于显示 reasoning
        """
        return self._chat_openai(system_prompt, user_prompt, image_paths, temperature, max_tokens, return_raw)

    def _chat_openai(
        self,
        system_prompt: str,
        user_prompt: str,
        image_paths: list[str] | None,
        temperature: float,
        max_tokens: int,
        return_raw: bool = False,
    ) -> str | dict:
        """OpenAI-compatible API 调用"""
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

        response = self._openai_client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        response_content = response.choices[0].message.content or ""
        
        # 检查是否被截断（finish_reason 不是 "stop"）
        if response.choices[0].finish_reason != "stop":
            print(f"WARNING: Response truncated (finish_reason={response.choices[0].finish_reason})")
        
        if return_raw:
            return {
                "content": response_content,
                "model": self.model,
                "finish_reason": response.choices[0].finish_reason,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else None,
                    "completion_tokens": response.usage.completion_tokens if response.usage else None,
                    "total_tokens": response.usage.total_tokens if response.usage else None,
                },
            }
        
        return response_content