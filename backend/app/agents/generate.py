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
from app.services.context_assembler import build_generate_prompt
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
        
        # 从配置读取参数
        config = state.get("config", {})
        agent_config = config.get("generate_agent", {})
        max_tokens = agent_config.get("max_tokens", 8192)
        
        response = self.chat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            return_raw=True,
            enable_thinking=True,  # V2.0: 启用思考模式
            thinking_budget=2048,  # 思考预算 2048 tokens
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
            reasoning_content = response.get("reasoning_content") if isinstance(response, dict) else None
            
            SessionLogger.save_session(
                pipeline_id=pipeline_id,
                agent_name="generate",
                iteration=iteration,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                raw_response=content,
                reasoning_content=reasoning_content,  # V2.0: 保存思维链
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
        """从 LLM 响应中提取 GLSL 代码
        
        V2.0: Agent 输出 GLSL + Self-check，需要提取 Self-check 之前的 GLSL 部分
        V3.0: 新增 Self-check 评分验证，低分警告
        V4.0: 处理 qwen3 thinking 模式的混合输出（思考过程 + GLSL）
        V5.0: 修复 [Self-check] 在 ```glsl 块内部导致提取不完整的 bug
        """
        text = text.strip()

        # V3.0: 提取 Self-check 评分（从完整文本中，不截断）
        self_check_idx = text.find('[Self-check]')
        if self_check_idx > 0:
            self_check_text = text[self_check_idx:]
            overall_match = re.search(r'Overall:\s*(\d+)/(\d+)', self_check_text)
            if overall_match:
                score = int(overall_match.group(1))
                max_score = int(overall_match.group(2))
                if score < 3:
                    print(f"⚠️  WARNING: Self-check score {score}/{max_score} below threshold (3)")
                    print(f"   Agent may have produced low-quality output")
                    lines = self_check_text.split('\n')[:10]
                    for line in lines[:5]:
                        if line.strip():
                            print(f"   {line.strip()}")

        # V5.0: 先尝试提取 ```glsl 块（在完整文本上操作）
        # V6.0: 处理 DeepSeek 输出无闭合 ``` 的情况
        if "```glsl" in text:
            match = re.search(r"```glsl\s*\n(.*?)```", text, re.DOTALL)
            if match:
                shader = match.group(1).strip()
                # 在提取的 shader 中去掉 [Self-check] 部分
                sc_idx = shader.find('[Self-check]')
                if sc_idx > 0:
                    shader = shader[:sc_idx].strip()
                return shader
            
            # V6.0 fallback: 如果 ```glsl 存在但没有闭合 ```，提取到末尾
            glsl_start = text.find("```glsl")
            if glsl_start >= 0:
                shader = text[glsl_start + 7:]  # 跳过 ```glsl
                # 去掉 [Self-check] 部分
                sc_idx = shader.find('[Self-check]')
                if sc_idx > 0:
                    shader = shader[:sc_idx].strip()
                # 去掉末尾可能的 ```（如果有）
                if shader.endswith('```'):
                    shader = shader[:-3].strip()
                return shader.strip()

        # V2.0 fallback: 如果没有 ```glsl 块，先去掉 [Self-check]
        if self_check_idx > 0:
            text = text[:self_check_idx].strip()

        # V4.0: 处理混合输出（思考过程 + GLSL）
        # 找第一个函数定义（忽略思考过程的伪代码块）
        func_match = re.search(r'^(float (sd|hash|noise|[a-z_]+)\(.*?\)|void mainImage)', text, re.MULTILINE)
        
        if func_match:
            # 从第一个函数定义开始截取
            start = func_match.start()
            glsl_part = text[start:]
            
            # 如果有 ``` 块结束标记，截取到那里
            if "```" in glsl_part:
                block_end = glsl_part.find("```")
                glsl_part = glsl_part[:block_end].strip()
            
            return glsl_part.strip()

        # 兜底：尝试提取 ``` 块
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