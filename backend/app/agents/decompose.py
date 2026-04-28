"""Decompose Agent：将视频/图片解构为视效语义描述 JSON

此 Agent 加载 visual-effect-decomposition skill：
- Operator Catalog（GLSL 算子库）
- DSL Schema（完整 DSL 规范）

这些知识库在 run() 方法中动态注入到 user prompt。
"""

import json
from pathlib import Path

from app.agents.base import BaseAgent
from app.config import settings
from app.services.skill_loader import SkillLoader
from app.services.video_extractor import extract_keyframes


class DecomposeAgent(BaseAgent):
    def __init__(self):
        super().__init__(model_config=settings.decompose)
        # System prompt 只包含角色定义
        self.system_prompt = Path("app/prompts/decompose_system.md").read_text()

    def run(
        self,
        image_paths: list[str],
        video_info: dict | None = None,
        user_notes: str = "",
        return_raw: bool = False,
    ) -> dict:
        """
        分析输入的视觉参考，输出结构化视效语义描述。

        visual-effect-decomposition skill 知识库动态注入到 user prompt，包含：
        - Operator Catalog（GLSL 算子库）
        - DSL Schema（完整 DSL 规范）

        Args:
            image_paths: 关键帧图片路径列表
            video_info: 视频元信息（时长、帧率等）
            user_notes: 用户附加的结构化参数标注
            return_raw: 如果 True，返回包含原始响应的 dict

        Returns:
            解构出的视效语义描述 dict
        """
        parts = []

        # 1. 动态注入 Skill 知识库 context (visual-effect-decomposition)
        skill_context = SkillLoader.build_decompose_context()
        parts.append("--- Skill 知识库参考 ---\n")
        parts.append(skill_context)
        parts.append("\n---\n\n")

        # 2. 任务描述
        parts.append("请分析以下视觉参考，解构出视效语义描述。")

        if video_info:
            parts.append(
                f"视频信息：时长 {video_info['duration']:.1f}s，"
                f"帧率 {video_info['fps']:.0f}fps，"
                f"分辨率 {video_info['width']}x{video_info['height']}。"
            )
            parts.append(
                f"以下 {len(image_paths)} 张图片是从视频中均匀提取的关键帧。"
            )
        elif image_paths:
            parts.append(f"以下是 {len(image_paths)} 张设计稿图片。")
        else:
            # 纯文本输入模式
            parts.append("用户仅提供文本描述，没有图片参考。请根据用户描述直接生成视效语义描述。")

        if user_notes:
            parts.append(f"\n用户附加标注：{user_notes}")

        user_prompt = "\n".join(parts)

        response = self.chat(
            system_prompt=self.system_prompt,
            user_prompt=user_prompt,
            image_paths=image_paths,  # 传递原始路径，BaseAgent 内部处理编码
            temperature=0.3,
            return_raw=True,
        )

        if response is None:
            print("WARNING: LLM returned None response")
            if return_raw:
                return {"visual_description": {}, "raw_response": "", "usage": None}
            return {}

        content = response.get("content", "") if isinstance(response, dict) else response
        if content is None:
            content = ""

        visual_description = self._parse_json(content)

        if return_raw and isinstance(response, dict):
            return {
                "visual_description": visual_description,
                "raw_response": content,
                "usage": response.get("usage"),
            }

        return visual_description

    def _encode_image(self, path: str) -> str:
        """将图片编码为 base64"""
        import base64
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def _parse_json(self, text: str) -> dict:
        """从 LLM 响应中解析 JSON"""
        text = text.strip()

        # 尝试提取 JSON block
        if "```json" in text:
            import re
            match = re.search(r"```json\s*\n(.*?)```", text, re.DOTALL)
            if match:
                text = match.group(1).strip()
        elif "```" in text:
            import re
            match = re.search(r"```(.*?)```", text, re.DOTALL)
            if match:
                text = match.group(1).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            print(f"WARNING: Failed to parse JSON: {text[:100]}")
            return {}