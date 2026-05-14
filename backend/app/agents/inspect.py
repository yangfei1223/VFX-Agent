"""Inspect Agent：对比渲染截图与设计参考，输出语义反馈

使用 ContextAssembler 组装专属上下文：
- System Prompt + Skill Context + UX Reference + Render Screenshots + Shader + Gradient Window

输出格式：visual_issues/visual_goals（自然语言，非参数调整）
"""

import json
import time
from pathlib import Path

from app.agents.base import BaseAgent
from app.config import settings
from app.services.context_assembler import build_inspect_prompt
from app.services.session_logger import SessionLogger
from app.pipeline.state import PipelineState


class InspectAgent(BaseAgent):
    def __init__(self):
        super().__init__(model_config=settings.inspect)
        self.system_prompt = Path("app/prompts/inspect_system.md").read_text()

    def run(
        self,
        state: PipelineState,
        return_raw: bool = False,
    ) -> dict:
        """
        对比渲染结果与设计参考，输出语义反馈。

        Args:
            state: PipelineState（包含 baseline + snapshot + gradient_window）
            return_raw: 如果 True，返回包含原始响应的 dict

        Returns:
            inspect_feedback dict（包含 visual_issues/visual_goals/dimension_scores 等）
        """
        start_time = time.time()
        pipeline_id = state.get("pipeline_id", "")
        snapshot = state.get("snapshot", {})
        iteration = snapshot.get("iteration", 0)

        # 使用 ContextAssembler 组装上下文
        system_prompt, user_prompt, image_paths = build_inspect_prompt(state)

        response = self.chat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            image_paths=image_paths,
            temperature=0.2,
            return_raw=True,
        )

        duration_ms = int((time.time() - start_time) * 1000)

        if response is None:
            print("WARNING: LLM returned None response")
            # 保存失败的 session
            if pipeline_id:
                SessionLogger.save_session(
                    pipeline_id=pipeline_id,
                    agent_name="inspect",
                    iteration=iteration,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    image_paths=image_paths,
                    raw_response="",
                    parsed_result={"error": "LLM returned None"},
                    usage=None,
                    temperature=0.2,
                    model=self.model_config.model,
                    duration_ms=duration_ms,
                )
            default_result = self._default_result(iteration)
            if return_raw:
                return {**default_result, "raw_response": "", "usage": None}
            return default_result

        content = response.get("content", "") if isinstance(response, dict) else response
        if content is None:
            content = ""

        result = self._parse_json(content)
        result["iteration"] = iteration

        # 保存 session
        if pipeline_id:
            usage = response.get("usage") if isinstance(response, dict) else None
            SessionLogger.save_session(
                pipeline_id=pipeline_id,
                agent_name="inspect",
                iteration=iteration,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                image_paths=image_paths,
                raw_response=content,
                parsed_result=result,
                usage=usage,
                temperature=0.2,
                model=self.model_config.model,
                duration_ms=duration_ms,
            )

        if return_raw and isinstance(response, dict):
            return {**result, "raw_response": content, "usage": response.get("usage")}

        return result

    def _parse_json(self, text: str) -> dict:
        """从 LLM 响应中解析 JSON，并验证 Self-check"""
        text = text.strip()

        # 检查 Self-check 部分
        self_check_section = None
        if "[Self-check]" in text:
            import re
            match = re.search(r"\[Self-check\](.*?)(?=```|$)", text, re.DOTALL)
            if match:
                self_check_section = match.group(1).strip()
                print(f"INFO: Inspect Self-check found:\n{self_check_section[:200]}")

                # 检查是否有低分维度 (<3 分)
                low_score_match = re.search(r"Overall Score:\s*(\d+)/8", self_check_section)
                if low_score_match:
                    overall_score = int(low_score_match.group(1))
                    if overall_score < 3:
                        print(f"WARNING: Inspect Self-check overall score {overall_score}/8 is too low! Agent should retry.")
                else:
                    print("WARNING: Inspect Self-check missing Overall Score! Agent should output 'Overall Score: X/8'")
        else:
            print("WARNING: Inspect response missing [Self-check] section! Agent MUST follow Step 8 workflow.")

        # 尝试提取 JSON block
        json_text = text
        if "```json" in text:
            import re
            match = re.search(r"```json\s*\n(.*?)```", text, re.DOTALL)
            if match:
                json_text = match.group(1).strip()
        elif "```" in text:
            import re
            match = re.search(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL)
            if match:
                json_text = match.group(1).strip()

        try:
            parsed = json.loads(json_text)

            # 验证 V2.0 Schema 强制字段
            required_fields = ["passed", "overall_score", "visual_issues", "visual_goals", "dimension_scores"]
            missing_fields = [f for f in required_fields if f not in parsed]
            if missing_fields:
                print(f"WARNING: Inspect missing required fields: {missing_fields}")

            # 验证 dimension_scores 包含 8 个维度
            if "dimension_scores" in parsed:
                expected_dimensions = [
                    "composition", "geometry", "color", "animation",
                    "background", "lighting", "texture", "vfx_details"
                ]
                actual_dimensions = list(parsed["dimension_scores"].keys())
                missing_dimensions = [d for d in expected_dimensions if d not in actual_dimensions]
                if missing_dimensions:
                    print(f"WARNING: Inspect missing dimension scores: {missing_dimensions}")

            return parsed
        except json.JSONDecodeError:
            print(f"WARNING: Failed to parse JSON: {json_text[:100]}")
            return self._default_result(0)

    def _default_result(self, iteration: int) -> dict:
        """返回默认评估结果"""
        return {
            "passed": False,
            "overall_score": 0.0,
            "visual_issues": ["评估失败"],
            "visual_goals": [],
            "correct_aspects": [],
            "dimension_scores": {},
            "previous_score_reference": None,
            "re_decompose_trigger": False,
            "iteration": iteration,
        }


# === 向后兼容接口 ===

def run_legacy(
    design_images: list[str],
    render_screenshots: list[str],
    visual_description: dict | None = None,
    iteration: int = 0,
    inspect_history: list[dict] | None = None,
    human_feedback: str | None = None,
    human_iteration_mode: bool = False,
    pipeline_id: str | None = None,
    return_raw: bool = False,
) -> dict:
    """向后兼容接口"""
    from app.pipeline.state import create_initial_state

    # 创建临时 state
    temp_state = create_initial_state(
        pipeline_id=pipeline_id or "temp",
        input_type="image",
        image_paths=design_images,
    )

    temp_state["snapshot"]["visual_description"] = visual_description or {}
    temp_state["snapshot"]["render_screenshots"] = render_screenshots
    temp_state["snapshot"]["iteration"] = iteration

    # 构造 gradient_window（从 inspect_history）
    if inspect_history:
        temp_state["gradient_window"] = [
            {
                "iteration": e.get("iteration", 0),
                "score": e.get("overall_score", 0),
                "feedback_summary": e.get("feedback_summary", "")[:100] if e.get("feedback_summary") else "",
            }
            for e in inspect_history[-3:]
        ]

    if human_iteration_mode:
        temp_state["human_iteration_mode"] = True
        temp_state["human_feedback"] = human_feedback

    agent = InspectAgent()
    return agent.run(temp_state, return_raw=return_raw)