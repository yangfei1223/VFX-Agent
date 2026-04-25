"""Inspect Agent：对比渲染截图与设计参考，输出修正指令"""

import json
from pathlib import Path

from app.agents.base import BaseAgent
from app.config import settings


class InspectAgent(BaseAgent):
    def __init__(self):
        super().__init__(model_config=settings.inspect)
        self.system_prompt = Path("app/prompts/inspect_system.md").read_text()

    def run(
        self,
        design_images: list[str],
        render_screenshots: list[str],
        visual_description: dict | None = None,
        iteration: int = 0,
    ) -> dict:
        """
        对比渲染截图与设计参考，输出评估结果和修正指令。

        Args:
            design_images: 原始设计参考图片路径列表
            render_screenshots: 渲染截图路径列表（多时间点）
            visual_description: 原始视效语义描述（供参考）
            iteration: 当前迭代轮次

        Returns:
            评估结果 dict，包含 passed/score/feedback 等
        """
        all_images = list(design_images) + list(render_screenshots)

        parts = [
            f"请对比以下图片，评估生成着色器的视觉效果是否满足设计要求。",
            f"\n前 {len(design_images)} 张是原始设计参考，",
            f"后 {len(render_screenshots)} 张是着色器渲染截图（按时间顺序）。",
        ]

        if visual_description:
            parts.append(
                f"\n原始视效描述：{json.dumps(visual_description, indent=2, ensure_ascii=False)}"
            )

        if iteration > 0:
            parts.append(f"\n这是第 {iteration + 1} 轮迭代修正后的结果。")

        user_prompt = "\n".join(parts)

        response = self.chat(
            system_prompt=self.system_prompt,
            user_prompt=user_prompt,
            image_paths=all_images,
            temperature=0.2,
            max_tokens=2048,
        )

        return self._parse_json(response)

    @staticmethod
    def _parse_json(text: str) -> dict:
        """从 LLM 响应中提取 JSON"""
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)
        return json.loads(text)