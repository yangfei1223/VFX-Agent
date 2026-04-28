"""Generate Agent：根据视效语义描述生成 Shadertoy 格式 GLSL 代码

Skill 知识库（effect-dev）在 run() 方法中动态注入到 user prompt，
而非硬编码到 system prompt。
"""

import json
import re
from pathlib import Path

from app.agents.base import BaseAgent
from app.config import settings
from app.services.skill_loader import SkillLoader


class GenerateAgent(BaseAgent):
    def __init__(self):
        super().__init__(model_config=settings.generate)
        # System prompt 只包含角色定义和输出格式
        self.system_prompt = Path("app/prompts/generate_system.md").read_text()
        # Skill context 在 run() 中动态注入

    def run(
        self,
        visual_description: dict,
        previous_shader: str | None = None,
        feedback: str | None = None,
        context_history: list[dict] | None = None,
        human_feedback: str | None = None,
        return_raw: bool = False,
    ) -> str | dict:
        """
        生成或修正 GLSL 着色器代码。

        effect-dev Skill 知识库动态注入到 user prompt，包含：
        - SDF Operators（算子定义）
        - Shader Templates（效果模板）
        - Aesthetics Rules（美学原则 + 性能预算）
        - GLSL Constraints（安全约束）

        Args:
            visual_description: Decompose Agent 输出的视效语义描述
            previous_shader: 前一轮生成的 shader 代码（修正时传入）
            feedback: Inspect Agent 的修正指令（修正时传入）
            context_history: Generate Agent 自身的历史调用记录
            human_feedback: 用户人工反馈
            return_raw: 如果 True，返回包含原始响应的 dict

        Returns:
            完整的 Shadertoy 格式 GLSL 代码
        """
        # 构建 user prompt
        user_parts = []

        # 1. 动态注入 Skill 知识库 context（effect-dev）
        skill_context = SkillLoader.build_generate_context()
        user_parts.append("--- Skill 知识库参考 ---\n")
        user_parts.append(skill_context)
        user_parts.append("\n---\n\n")

        # 2. 任务描述
        user_parts.append("请根据以下视效语义描述生成 GLSL 着色器代码：\n")
        user_parts.append(f"```json\n{json.dumps(visual_description, indent=2, ensure_ascii=False)}\n```")

        # 3. 修正模式：注入上一轮代码和反馈
        if previous_shader and feedback:
            user_parts.extend([
                "\n---\n以下是上一轮生成的着色器代码：",
                f"```glsl\n{previous_shader}\n```",
                f"\n---\n检视 Agent 的反馈：\n{feedback}",
            ])

        # 4. 注入历史上下文
        if context_history and len(context_history) > 0:
            history_summary = self._format_context_history(context_history)
            user_parts.extend([
                f"\n---\n你之前的历史工作记录：\n{history_summary}",
                "\n请参考之前的工作，避免重复已尝试但无效的修改方向。",
            ])

        # 5. 注入用户人工反馈（优先级最高）
        if human_feedback:
            user_parts.append(f"\n---\n[用户检视指令]\n{human_feedback}\n请根据用户指令调整着色器效果。")

        # 6. 修正指令
        if previous_shader and feedback:
            user_parts.append("\n请根据反馈修正着色器代码，保持整体结构不变，仅修改有问题的部分。")

        user_prompt = "\n".join(user_parts)

        response = self.chat(
            system_prompt=self.system_prompt,
            user_prompt=user_prompt,
            temperature=0.2 if previous_shader else 0.5,
            max_tokens=16384,
            return_raw=True,
        )

        if response is None:
            print("WARNING: LLM returned None response")
            if return_raw:
                return {"shader": "", "raw_response": "", "usage": None}
            return ""

        content = response.get("content", "") if isinstance(response, dict) else response
        if content is None:
            content = ""

        shader = self._extract_glsl(content)

        if shader is None or shader.strip() == "":
            print(f"WARNING: Empty shader extracted from content (len={len(content)})")
            shader = ""

        if return_raw and isinstance(response, dict):
            return {
                "shader": shader,
                "raw_response": content,
                "usage": response.get("usage"),
            }

        return shader

    @staticmethod
    def _format_context_history(history: list[dict]) -> str:
        """格式化 Generate Agent 的历史上下文"""
        lines = []
        for entry in history:
            iteration = entry.get("iteration", 0)
            feedback_received = entry.get("feedback_received", "")
            shader_preview = entry.get("shader_preview", "")
            duration_ms = entry.get("duration_ms", 0)

            lines.append(f"\n### 第 {iteration} 轮")
            if feedback_received:
                fb_preview = feedback_received[:200] + "..." if len(feedback_received) > 200 else feedback_received
                lines.append(f"收到反馈：{fb_preview}")
            if shader_preview:
                lines.append(f"生成代码（前100字符）：{shader_preview[:100]}...")
            lines.append(f"耗时：{duration_ms}ms")

        return "\n".join(lines)

    @staticmethod
    def _extract_glsl(text: str) -> str:
        """从 LLM 响应中提取 GLSL 代码"""
        text = text.strip()

        if "```glsl" in text:
            match = re.search(r"```glsl\s*\n(.*?)```", text, re.DOTALL)
            if match:
                return match.group(1).strip()

        if "```" in text:
            first_block = text.find("```")
            last_block = text.rfind("```")
            if first_block != -1 and last_block != -1 and last_block > first_block:
                content = text[first_block:last_block]
                start_marker_end = content.find("\n")
                if start_marker_end != -1:
                    content = content[start_marker_end + 1:]
                return content.strip()

        if text.endswith("```"):
            text = text[:-3].strip()

        return text