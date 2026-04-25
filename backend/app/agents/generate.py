"""Generate Agent：根据视效语义描述 + Skill 资产生成 Shadertoy 格式 GLSL 代码"""

import json
import re
from pathlib import Path

from app.agents.base import BaseAgent
from app.config import settings


class GenerateAgent(BaseAgent):
    def __init__(self):
        super().__init__(model_config=settings.generate)
        self.system_prompt = Path("app/prompts/generate_system.md").read_text()
        # Skill 知识库通过 .claude/skills/effect-dev/ 的标准 Agent Skill 机制提供
        # 运行此 Agent 的 AI 编码工具（如 OpenCode/Claude Code）会自动发现并按需加载 Skill
        # 这里不需要自定义的 SkillLoader —— Skill 在 Agent 的 system prompt 层面生效

    def run(
        self,
        visual_description: dict,
        previous_shader: str | None = None,
        feedback: str | None = None,
    ) -> str:
        """
        生成或修正 GLSL 着色器代码。

        Skill 知识库（算子/模板/美学原则/纹理采样/约束）通过 Agent Skill 机制
        在 system prompt 层面自动注入，无需手动检索和拼装。

        Args:
            visual_description: Decompose Agent 输出的视效语义描述
            previous_shader: 前一轮生成的 shader 代码（修正时传入）
            feedback: Inspect Agent 的修正指令（修正时传入）

        Returns:
            完整的 Shadertoy 格式 GLSL 代码
        """
        # 构建 user prompt
        user_parts = [
            "请根据以下视效语义描述生成 GLSL 着色器代码：\n",
            f"```json\n{json.dumps(visual_description, indent=2, ensure_ascii=False)}\n```",
        ]

        # 修正模式下注入历史代码和反馈
        if previous_shader and feedback:
            user_parts.extend([
                "\n---\n以下是上一轮生成的着色器代码：",
                f"```glsl\n{previous_shader}\n```",
                f"\n---\n检视 Agent 的反馈：\n{feedback}",
                "\n请根据反馈修正着色器代码，保持整体结构不变，仅修改有问题的部分。",
            ])

        user_prompt = "\n".join(user_parts)

        response = self.chat(
            system_prompt=self.system_prompt,
            user_prompt=user_prompt,
            temperature=0.2 if previous_shader else 0.5,
            max_tokens=8192,  # GLSL shader 可能较长，增加 token 限制
        )

        return self._extract_glsl(response)

    @staticmethod
    def _extract_glsl(text: str) -> str:
        """从 LLM 响应中提取 GLSL 代码"""
        text = text.strip()

        # 如果被 markdown code block 包裹
        if "```glsl" in text:
            match = re.search(r"```glsl\s*\n(.*?)```", text, re.DOTALL)
            if match:
                return match.group(1).strip()
        if "```" in text:
            match = re.search(r"```\s*\n(.*?)```", text, re.DOTALL)
            if match:
                return match.group(1).strip()

        # 否则假定整个响应就是 GLSL 代码
        return text