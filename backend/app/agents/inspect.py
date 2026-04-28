"""Inspect Agent：对比渲染截图与设计参考，输出修正指令

此 Agent 不加载 effect-dev Skill（那是 Generate Agent 用的）。
它只负责质量评估和反馈生成。
"""

import json
from pathlib import Path

from app.agents.base import BaseAgent
from app.config import settings


class InspectAgent(BaseAgent):
    def __init__(self):
        super().__init__(model_config=settings.inspect)
        # System prompt 只包含角色定义和评估标准
        self.system_prompt = Path("app/prompts/inspect_system.md").read_text()

    def run(
        self,
        design_images: list[str],
        render_screenshots: list[str],
        visual_description: dict | None = None,
        iteration: int = 0,
        inspect_history: list[dict] | None = None,
        human_feedback: str | None = None,
        human_iteration_mode: bool = False,
        return_raw: bool = False,
    ) -> dict:
        """
        对比渲染结果与设计参考，输出评估和修正指令。

        Args:
            design_images: 设计参考图片路径列表
            render_screenshots: 渲染截图路径列表
            visual_description: 视效语义描述（用于参考）
            iteration: 当前迭代次数
            inspect_history: Inspect Agent 自身的历史评估记录
            human_feedback: 用户人工反馈（人工迭代模式）
            human_iteration_mode: 是否为人工迭代模式
            return_raw: 如果 True，返回包含原始响应的 dict

        Returns:
            评估结果 dict（包含 passed, score, feedback_commands 等）
        """
        parts = [f"请对比以下渲染结果与设计参考，进行第 {iteration + 1} 次评估。"]

        # 注入人工迭代模式提示
        if human_iteration_mode and human_feedback:
            parts.append(f"\n---\n[人工迭代模式]\n用户反馈：{human_feedback}\n请根据用户反馈评估当前效果是否满足要求。")

        # 注入历史评估记录
        if inspect_history and len(inspect_history) > 0:
            history_summary = self._format_inspect_history(inspect_history)
            parts.append(f"\n---\n你之前的历史评估记录：\n{history_summary}")

        if visual_description:
            parts.append(f"\n---\n视效语义描述：\n```json\n{json.dumps(visual_description, indent=2, ensure_ascii=False)}\n```")

        user_prompt = "\n".join(parts)

        # 收集图片路径（让 BaseAgent.chat() 处理编码）
        all_image_paths = []
        for img_path in design_images[:3]:
            all_image_paths.append(img_path)
        for img_path in render_screenshots[:3]:
            all_image_paths.append(img_path)

        response = self.chat(
            system_prompt=self.system_prompt,
            user_prompt=user_prompt,
            image_paths=all_image_paths,  # 传递路径列表
            temperature=0.2,
            return_raw=True,
        )

        if response is None:
            print("WARNING: LLM returned None response")
            default_result = self._default_result(iteration)
            if return_raw:
                return {**default_result, "raw_response": "", "usage": None}
            return default_result

        content = response.get("content", "") if isinstance(response, dict) else response
        if content is None:
            content = ""

        result = self._parse_json(content)
        result["iteration"] = iteration
        result["human_iteration"] = human_iteration_mode
        if human_feedback:
            result["human_feedback"] = human_feedback

        if return_raw and isinstance(response, dict):
            return {**result, "raw_response": content, "usage": response.get("usage")}

        return result

    def _parse_json(self, text: str) -> dict:
        """从 LLM 响应中解析 JSON"""
        text = text.strip()

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
            return self._default_result(0)

    def _default_result(self, iteration: int) -> dict:
        """返回默认评估结果"""
        return {
            "passed": False,
            "overall_score": 0.0,
            "dimensions": {
                "shape": {"score": 0.0, "notes": "评估失败"},
                "color": {"score": 0.0, "notes": "评估失败"},
                "animation": {"score": 0.0, "notes": "评估失败"},
                "performance": {"score": 0.0, "notes": "评估失败"},
            },
            "feedback_commands": [],
            "feedback_summary": "评估失败，请重试",
            "critical_issues": [],
            "iteration": iteration,
        }

    def _format_inspect_history(self, history: list[dict]) -> str:
        """格式化 Inspect Agent 的历史评估记录"""
        lines = []
        for entry in history:
            iteration = entry.get("iteration", 0)
            score = entry.get("overall_score", 0)
            passed = entry.get("passed", False)
            feedback_preview = entry.get("feedback_summary", "")[:100]

            lines.append(f"\n### 第 {iteration} 次评估")
            lines.append(f"评分：{score:.2f}，通过：{passed}")
            if feedback_preview:
                lines.append(f"反馈摘要：{feedback_preview}...")

        return "\n".join(lines)