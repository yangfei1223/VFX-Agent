"""Inspect Agent：对比渲染截图与设计参考，输出语义反馈

Phase C A/B Cross-validation Agent（独立可运行，不依赖 v1.0 被删除模块）
- 不再继承 BaseAgent（v1.0 已移除），内联 LLM 调用逻辑
- 不再依赖 context_assembler，内联 prompt 构建逻辑
- 不再依赖 PipelineState TypedDict，使用通用 dict

V2.0: 保留作为离线评分 Agent，用于 A/B 对比 v2.0 codex-od 输出
"""

import base64
import json
import time
from pathlib import Path
from typing import Any

import httpx
from openai import OpenAI

from app.config import settings
from app.services.session_logger import SessionLogger


# Dimension weights (per system prompt)
DIMENSION_WEIGHTS = {
    "composition": 1.0,
    "geometry": 1.5,
    "color": 1.5,
    "animation": 1.5,
    "background": 1.0,
    "lighting": 1.5,
    "texture": 0.5,
    "vfx_details": 1.5,
}


class InspectAgent:
    def __init__(self):
        self.model_config = settings.inspect
        self.model = self.model_config.model
        self.system_prompt = Path("app/prompts/inspect_system.md").read_text()

        # 独立创建 OpenAI client（原来自 BaseAgent）
        proxy_url = self.model_config.proxy
        if not proxy_url:
            import os
            proxy_url = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or os.environ.get("ALL_PROXY")

        timeout = httpx.Timeout(120.0, connect=10.0, read=120.0, write=120.0)
        self._http_client = httpx.Client(timeout=timeout, proxy=proxy_url) if proxy_url else httpx.Client(timeout=timeout)
        self._openai_client = OpenAI(
            api_key=self.model_config.api_key,
            base_url=self.model_config.base_url,
            http_client=self._http_client,
        )

    def _chat(
        self,
        system_prompt: str,
        user_prompt: str,
        image_paths: list[str] | None = None,
        temperature: float = 0.2,
        return_raw: bool = True,
    ) -> str | dict:
        """Inline from BaseAgent._chat_openai — standalone LLM call with image support"""
        content: list[Any] = [{"type": "text", "text": user_prompt}]

        if image_paths:
            for path in image_paths:
                image_data = base64.b64encode(Path(path).read_bytes()).decode()
                ext = Path(path).suffix.lower()
                mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
                mime = mime_map.get(ext, "image/png")
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{image_data}"},
                })

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content if image_paths else user_prompt},
        ]

        response = self._openai_client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=4096,
        )

        response_content = response.choices[0].message.content or ""

        if response.choices[0].finish_reason != "stop":
            print(f"WARNING: Response truncated (finish_reason={response.choices[0].finish_reason})")

        if return_raw:
            return {
                "content": response_content,
                "model": self.model,
                "finish_reason": response.choices[0].finish_reason,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else None,
                    "completion_tokens": response.usage.completion_tokens if response.usage else None,
                    "total_tokens": response.usage.total_tokens if response.usage else None,
                },
            }

        return response_content

    @staticmethod
    def _load_prompt(prompt_name: str) -> str:
        """Inline from context_assembler.load_prompt"""
        prompt_path = Path(f"app/prompts/{prompt_name}.md")
        if prompt_path.exists():
            return prompt_path.read_text()
        print(f"WARNING: Prompt file not found: {prompt_path}")
        return ""

    def _build_inspect_prompt(self, state: dict) -> tuple[str, str, list[str]]:
        """Inline from context_assembler.build_inspect_prompt

        Prompt Stack:
        - Layer 1: Shared VFX Constraints
        - Layer 2: VFX Effect Catalog
        - Layer 3: Inspect System Prompt
        """
        baseline = state.get("baseline", {})
        snapshot = state.get("snapshot", {})

        # Prompt Stack 层叠注入
        constraints = self._load_prompt("shared_vfx_constraints")
        catalog = self._load_prompt("vfx_effect_catalog")
        terminology = self._load_prompt("shared_vfx_terminology")
        base_system = self._load_prompt("inspect_system")

        system_prompt = f"{base_system}\n\n---\n\n{constraints}\n\n---\n\n{catalog}\n\n---\n\n{terminology}"

        # User prompt
        user_parts = []

        # 1. UX Reference
        design_screenshots = baseline.get("keyframe_paths", [])
        if design_screenshots:
            user_parts.append(f"### 设计参考\n{chr(10).join(design_screenshots)}")

        # 2. Render Screenshots
        render_screenshots = snapshot.get("render_screenshots", [])
        if render_screenshots:
            user_parts.append(f"### 渲染截图\n{chr(10).join(render_screenshots)}")

        # 3. Visual Description
        visual_description = snapshot.get("visual_description", {})
        if visual_description:
            user_parts.append(f"### Visual Description\n```json\n{json.dumps(visual_description, indent=2, ensure_ascii=False)}\n```")

        # 4. Current Shader
        shader = snapshot.get("shader", "")
        if shader:
            user_parts.append(f"### 当前 Shader\n```glsl\n{shader}\n```")

        # 5. Human Feedback (如有)
        human_feedback = state.get("human_feedback")
        if human_feedback:
            user_parts.append(f"### 用户反馈\n{human_feedback}")

        user_prompt = "\n\n".join(user_parts)

        # 合并图片路径（设计参考 + 渲染截图）
        image_paths = design_screenshots + render_screenshots

        return system_prompt, user_prompt, image_paths

    def run(
        self,
        state: dict,
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

        # 使用内联 prompt 构建
        system_prompt, user_prompt, image_paths = self._build_inspect_prompt(state)

        response = self._chat(
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

        # Validate score calculation
        self._validate_score_calculation(result)

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
        """从 LLM 响应中解析 JSON
        
        V2.0: Agent 输出 JSON + Self-check，需要提取 Self-check 之前的 JSON 部分
        """
        text = text.strip()

        # V2.0: 提取 Self-check 之前的 JSON 部分
        self_check_idx = text.find('[Self-check]')
        if self_check_idx > 0:
            text = text[:self_check_idx].strip()

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
            "visual_issues": ["评估失败"],
            "visual_goals": [],
            "correct_aspects": [],
            "dimension_scores": {},
            "previous_score_reference": None,
            "re_decompose_trigger": False,
            "iteration": iteration,
        }

    def _validate_score_calculation(self, feedback: dict) -> float:
        """Validate overall_score matches weighted dimension scores.

        Returns the computed score (or LLM score if validation fails).
        Prints warning if discrepancy > 0.1.
        """
        overall_score = feedback.get("overall_score", 0)
        dimension_scores = feedback.get("dimension_scores", {})

        if not dimension_scores:
            return overall_score

        # Compute weighted sum
        total_weight = 0
        weighted_sum = 0

        for dim, weight in DIMENSION_WEIGHTS.items():
            dim_data = dimension_scores.get(dim, {})
            dim_score = dim_data.get("score", 0)
            if dim_score > 0:
                weighted_sum += dim_score * weight
                total_weight += weight

        if total_weight == 0:
            return overall_score

        computed_score = weighted_sum / total_weight

        # Warn if discrepancy
        discrepancy = abs(computed_score - overall_score)
        if discrepancy > 0.1:
            print(f"WARNING: Score calculation discrepancy")
            print(f"  LLM overall_score: {overall_score:.2f}")
            print(f"  Computed from dimensions: {computed_score:.2f}")
            print(f"  Discrepancy: {discrepancy:.2f}")

        return overall_score  # Return LLM score (don't override)


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
    """向后兼容接口（独立可运行，不依赖被删除的 state.py）"""
    # 内联最小 state，替代 create_initial_state（已删除）
    temp_state: dict = {
        "pipeline_id": pipeline_id or "temp",
        "baseline": {
            "input_type": "image",
            "image_paths": design_images,
            "keyframe_paths": design_images,
            "user_notes": "",
        },
        "snapshot": {
            "visual_description": {},
            "shader": "",
            "render_screenshots": [],
            "inspect_feedback": None,
            "iteration": 0,
        },
        "gradient_window": [],
        "checkpoint": {},
        "config": {},
        "human_feedback": None,
        "human_iteration_mode": False,
        "human_iteration_count": 0,
    }

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