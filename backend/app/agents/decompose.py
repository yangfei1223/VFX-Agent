"""Decompose Agent：将视频/图片解构为视效语义描述 JSON"""

import json
from pathlib import Path

from app.agents.base import BaseAgent
from app.config import settings
from app.services.video_extractor import extract_keyframes


class DecomposeAgent(BaseAgent):
    def __init__(self):
        super().__init__(model_config=settings.decompose)
        self.system_prompt = Path("app/prompts/decompose_system.md").read_text()

    def run(
        self,
        image_paths: list[str],
        video_info: dict | None = None,
        user_notes: str = "",
    ) -> dict:
        """
        分析输入的视觉参考，输出结构化视效语义描述。

        Args:
            image_paths: 关键帧图片路径列表
            video_info: 视频元信息（时长、帧率等），可选
            user_notes: 用户附加的结构化参数标注，可选

        Returns:
            解构出的视效语义描述 dict
        """
        parts = ["请分析以下视觉参考，解构出视效语义描述。"]

        if video_info:
            parts.append(
                f"视频信息：时长 {video_info['duration']:.1f}s，"
                f"帧率 {video_info['fps']:.0f}fps，"
                f"分辨率 {video_info['width']}x{video_info['height']}。"
            )
            parts.append(
                f"以下 {len(image_paths)} 张图片是从视频中均匀提取的关键帧。"
            )
        else:
            parts.append(f"以下是 {len(image_paths)} 张设计稿图片。")

        if user_notes:
            parts.append(f"用户附加参数标注：{user_notes}")

        user_prompt = "\n".join(parts)

        response = self.chat(
            system_prompt=self.system_prompt,
            user_prompt=user_prompt,
            image_paths=image_paths,
            temperature=0.3,
            max_tokens=4096,  # 增加 token 限制，确保 JSON 完整
        )

        # 从响应中提取 JSON
        return self._parse_json(response)

    @staticmethod
    def _parse_json(text: str) -> dict:
        """从 LLM 响应中提取 JSON，处理多种格式"""
        text = text.strip()
        
        # 1. 处理 markdown code block
        if text.startswith("```"):
            lines = text.split("\n")
            # 去掉首尾的 ``` 行和可能的 language 标识
            lines = [l for l in lines if not l.strip().startswith("```") and not l.strip().lower() in ("json", "")]
            text = "\n".join(lines).strip()
        
        # 2. 提取 JSON 对象（查找第一个 { 到最后一个 }）
        start_idx = text.find("{")
        end_idx = text.rfind("}")
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            text = text[start_idx:end_idx + 1]
        
        # 3. 尝试解析
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            # 4. 尝试修复常见问题
            import re
            # 移除末尾的逗号
            text = re.sub(r',\s*}', '}', text)
            text = re.sub(r',\s*]', ']', text)
            # 移除控制字符
            text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
            
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                # 5. 最后尝试：返回一个包含原始文本的 fallback
                return {
                    "effect_name": "parse_failed",
                    "overall_description": text,
                    "shape": {"type": "full_screen", "description": "JSON 解析失败"},
                    "color": {"palette": ["#333333"], "gradient_type": "none"},
                    "animation": {"loop_duration_s": 2.0, "easing": "linear"},
                    "interaction": {"responds_to_pointer": False, "interaction_type": "none"},
                    "post_processing": {},
                    "parse_error": str(e),
                }