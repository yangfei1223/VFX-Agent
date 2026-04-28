"""Inspect Agent：对比渲染截图与设计参考，输出修正指令"""

import json
from pathlib import Path

from app.agents.base import BaseAgent
from app.config import settings
from app.services.skill_loader import SkillLoader


class InspectAgent(BaseAgent):
    def __init__(self):
        super().__init__(model_config=settings.inspect)
        # 加载基础 system prompt
        base_prompt = Path("app/prompts/inspect_system.md").read_text()
        # 注入 Skill 知识库 context
        skill_context = SkillLoader.build_inspect_context()
        self.system_prompt = base_prompt + "\n\n" + skill_context

    def run(
        self,
        design_images: list[str],
        render_screenshots: list[str],
        visual_description: dict | None = None,
        iteration: int = 0,
        context_history: list[dict] | None = None,
        human_feedback: str | None = None,  # 用户人工反馈
    ) -> dict:
        """
        对比渲染截图与设计参考，输出评估结果和修正指令。

        Args:
            design_images: 原始设计参考图片路径列表
            render_screenshots: 渲染截图路径列表（多时间点）
            visual_description: 原始视效语义描述（供参考）
            iteration: 当前迭代轮次
            context_history: Inspect Agent 自身的历史调用记录（之前的评分和 feedback）

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

        # 注入 Inspect Agent 自身的历史上下文
        if context_history and len(context_history) > 0:
            history_summary = self._format_context_history(context_history)
            parts.extend([
                f"\n---\n你之前的历史评估记录：\n{history_summary}",
                "\n请参考之前的问题和评分趋势，判断当前是否在改进或仍有相同问题。",
            ])

        # 注入用户人工反馈（评估时参考）
        if human_feedback:
            parts.append(f"\n---\n[用户期望]\n用户希望的效果：{human_feedback}\n请评估渲染结果是否符合用户期望。")

        user_prompt = "\n".join(parts)

        response = self.chat(
            system_prompt=self.system_prompt,
            user_prompt=user_prompt,
            image_paths=all_images,
            temperature=0.2,
            max_tokens=4096,  # 增加以避免截断
        )

        # Safe handling of None response
        if response is None:
            print("WARNING: Inspect LLM returned None response")
            return {"passed": False, "overall_score": 0.0, "feedback": "LLM returned None", "parse_error": "LLM returned None"}

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
            # 尝试修复未终止的字符串（简单处理）
            # 找到最后一个未终止的字符串并尝试截断
            
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                # 5. 最后尝试：返回一个包含原始文本的 fallback
                return {
                    "passed": False,
                    "overall_score": 0.0,
                    "feedback": f"JSON 解析失败: {str(e)}。原始响应已保存。",
                    "raw_response": text[:500],  # 保存部分原始响应
                    "parse_error": str(e),
                }

    @staticmethod
    def _format_context_history(history: list[dict]) -> str:
        """格式化 Inspect Agent 的历史上下文"""
        lines = []
        for entry in history:
            iteration = entry.get("iteration", 0)
            score = entry.get("score", 0)
            passed = entry.get("passed", False)
            feedback = entry.get("feedback", "")
            issues = entry.get("issues_summary", "")
            
            lines.append(f"\n### 第 {iteration} 轮评估")
            lines.append(f"评分：{score:.2f} ({'通过' if passed else '未通过'})")
            if issues:
                lines.append(f"主要问题：{issues}")
            if feedback:
                # 截取 feedback 关键信息
                fb_preview = feedback[:150] + "..." if len(feedback) > 150 else feedback
                lines.append(f"反馈摘要：{fb_preview}")
        
        return "\n".join(lines)