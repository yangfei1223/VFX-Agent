"""Decompose Agent：将视频/图片解构为自然语言视效语义描述

此 Agent 使用 ContextAssembler 组装专属上下文：
- System Prompt + Skill Context + UX Reference + Failure Log (re_decompose模式)

输出格式：自然语言结构化描述（非 DSL AST）
"""

import json
import time
from pathlib import Path

from app.agents.base import BaseAgent
from app.config import settings
from app.services.context_assembler import build_decompose_prompt
from app.services.session_logger import SessionLogger
from app.pipeline.state import PipelineState


class DecomposeAgent(BaseAgent):
    def __init__(self):
        super().__init__(model_config=settings.decompose)
        self.system_prompt = Path("app/prompts/decompose_system.md").read_text()

    def run(
        self,
        state: PipelineState,
        mode: str = "cold_start",
        return_raw: bool = False,
    ) -> dict:
        """
        分析输入的视觉参考，输出自然语言视效语义描述。

        Args:
            state: PipelineState（包含 baseline + snapshot + gradient_window + checkpoint）
            mode: "cold_start" | "re_decompose"
            return_raw: 如果 True，返回包含原始响应的 dict

        Returns:
            visual_description dict（自然语言结构化描述）
        """
        start_time = time.time()
        pipeline_id = state.get("pipeline_id", "")
        iteration = state.get("snapshot", {}).get("iteration", 0)

        # 使用 ContextAssembler 组装上下文
        system_prompt, user_prompt, image_paths = build_decompose_prompt(state, mode)

        response = self.chat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            image_paths=image_paths,
            temperature=0.3,
            return_raw=True,
        )

        duration_ms = int((time.time() - start_time) * 1000)

        if response is None:
            print("WARNING: LLM returned None response")
            # 保存失败的 session
            if pipeline_id:
                SessionLogger.save_session(
                    pipeline_id=pipeline_id,
                    agent_name="decompose",
                    iteration=iteration,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    image_paths=image_paths,
                    raw_response="",
                    parsed_result={"error": "LLM returned None"},
                    usage=None,
                    temperature=0.3,
                    model=self.model_config.model,
                    duration_ms=duration_ms,
                )
            if return_raw:
                return {"visual_description": {}, "raw_response": "", "usage": None}
            return {}

        content = response.get("content", "") if isinstance(response, dict) else response
        if content is None:
            content = ""

        visual_description = self._parse_json(content)

        # 保存 session
        if pipeline_id:
            usage = response.get("usage") if isinstance(response, dict) else None
            SessionLogger.save_session(
                pipeline_id=pipeline_id,
                agent_name="decompose",
                iteration=iteration,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                image_paths=image_paths,
                raw_response=content,
                parsed_result=visual_description,
                usage=usage,
                temperature=0.3,
                model=self.model_config.model,
                duration_ms=duration_ms,
            )

        if return_raw and isinstance(response, dict):
            return {
                "visual_description": visual_description,
                "raw_response": content,
                "usage": response.get("usage"),
            }

        return visual_description

    def _parse_json(self, text: str) -> dict:
        """从 LLM 响应中解析 JSON
        
        V2.0: Agent 输出 JSON + Self-check，需要提取 Self-check 之前的 JSON 部分
        """
        text = text.strip()

        # V2.0: 提取 Self-check 之前的 JSON 部分
        self_check_idx = text.find('[Self-check]')
        if self_check_idx > 0:
            text = text[:self_check_idx].strip()

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


# === 向后兼容接口（迁移期保留） ===

def run_legacy(
    image_paths: list[str],
    video_info: dict | None = None,
    user_notes: str = "",
    pipeline_id: str | None = None,
    iteration: int = 0,
    return_raw: bool = False,
) -> dict:
    """
    向后兼容接口（供 graph.py 逐步迁移使用）

    内部创建临时 state，调用新的 run(state, mode)
    """
    from app.pipeline.state import create_initial_state

    # 创建临时 state
    temp_state = create_initial_state(
        pipeline_id=pipeline_id or "temp",
        input_type="video" if video_info else ("image" if image_paths else "text"),
        video_path=None,
        image_paths=image_paths,
        user_notes=user_notes,
    )

    # 注入 video_info
    if video_info:
        temp_state["baseline"]["video_info"] = video_info

    temp_state["snapshot"]["iteration"] = iteration

    # 调用新接口
    agent = DecomposeAgent()
    return agent.run(temp_state, mode="cold_start", return_raw=return_raw)