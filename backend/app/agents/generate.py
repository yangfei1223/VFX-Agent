"""Generate Agent：根据自然语言视效描述生成 GLSL shader

使用 ContextAssembler 组装专属上下文：
- System Prompt + Skill Context + Visual Description + Current Shader + Feedback + Gradient Window

禁止注入：原始图片、渲染截图
"""

import json
import re
import time
from pathlib import Path

from app.agents.base import BaseAgent
from app.config import settings
from app.services.context_assembler import ContextAssembler, build_generate_prompt
from app.services.session_logger import SessionLogger
from app.pipeline.state import PipelineState


class GenerateAgent(BaseAgent):
    def __init__(self):
        super().__init__(model_config=settings.generate)
        self.system_prompt = Path("app/prompts/generate_system.md").read_text()

    def run(
        self,
        state: PipelineState,
        return_raw: bool = False,
    ) -> str | dict:
        """
        根据视效语义描述生成或修正 GLSL 着色器代码。

        Args:
            state: PipelineState（包含 snapshot + gradient_window + checkpoint）
            return_raw: 如果 True，返回包含原始响应的 dict

        Returns:
            shader str（完整 GLSL 代码）
        """
        start_time = time.time()
        pipeline_id = state.get("pipeline_id", "")
        snapshot = state.get("snapshot", {})
        iteration = snapshot.get("iteration", 0)

        # 判断是否为修正模式
        previous_shader = snapshot.get("shader", "")
        is_fix_mode = previous_shader and iteration > 0

        # 使用 ContextAssembler 组装上下文
        system_prompt, user_prompt = build_generate_prompt(state)

        temperature = 0.2 if is_fix_mode else 0.5
        response = self.chat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=16384,
            return_raw=True,
        )

        duration_ms = int((time.time() - start_time) * 1000)

        if response is None:
            print("WARNING: LLM returned None response")
            # 保存失败的 session
            if pipeline_id:
                SessionLogger.save_session(
                    pipeline_id=pipeline_id,
                    agent_name="generate",
                    iteration=iteration,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    raw_response="",
                    parsed_result={"error": "LLM returned None"},
                    usage=None,
                    temperature=temperature,
                    max_tokens=16384,
                    model=self.model_config.model,
                    duration_ms=duration_ms,
                )
            if return_raw:
                return {"shader": "", "raw_response": "", "usage": None}
            return ""

        content = response.get("content", "") if isinstance(response, dict) else response
        if content is None:
            content = ""

        shader = self._extract_glsl(content)

        if shader is None or shader.strip() == "":
            print(f"WARNING: Empty shader extracted (len={len(content)})")
            shader = ""

        # 保存 session
        if pipeline_id:
            usage = response.get("usage") if isinstance(response, dict) else None
            SessionLogger.save_session(
                pipeline_id=pipeline_id,
                agent_name="generate",
                iteration=iteration,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                raw_response=content,
                parsed_result={"shader": shader[:500] + "..." if len(shader) > 500 else shader},
                usage=usage,
                temperature=temperature,
                max_tokens=16384,
                model=self.model_config.model,
                duration_ms=duration_ms,
            )

        if return_raw and isinstance(response, dict):
            return {
                "shader": shader,
                "raw_response": content,
                "usage": response.get("usage"),
            }

        return shader

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


# === 向后兼容接口 ===

def run_legacy(
    visual_description: dict,
    previous_shader: str | None = None,
    feedback: str | None = None,
    context_history: list[dict] | None = None,
    human_feedback: str | None = None,
    pipeline_id: str | None = None,
    iteration: int = 0,
    return_raw: bool = False,
) -> str | dict:
    """向后兼容接口"""
    from app.pipeline.state import create_initial_state

    # 创建临时 state
    temp_state = create_initial_state(
        pipeline_id=pipeline_id or "temp",
        input_type="text",
        image_paths=[],
    )

    temp_state["snapshot"]["visual_description"] = visual_description
    temp_state["snapshot"]["shader"] = previous_shader or ""
    temp_state["snapshot"]["iteration"] = iteration

    # 构造 inspect_feedback（从 feedback）
    if feedback:
        temp_state["snapshot"]["inspect_feedback"] = {
            "visual_issues": [feedback],
            "visual_goals": [],
            "overall_score": 0,
        }

    # 构造 gradient_window（从 context_history）
    if context_history:
        temp_state["gradient_window"] = [
            {
                "iteration": e.get("iteration", 0),
                "score": 0,
                "feedback_summary": e.get("feedback_received", "")[:100] if e.get("feedback_received") else "",
            }
            for e in context_history[-3:]
        ]

    if human_feedback:
        temp_state["human_feedback"] = human_feedback

    agent = GenerateAgent()
    return agent.run(temp_state, return_raw=return_raw)