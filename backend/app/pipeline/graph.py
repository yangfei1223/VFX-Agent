"""LangGraph 闭环编排：Decompose → Generate → Validate → Render → Inspect → (反馈循环)"""

import asyncio
import time
from typing import Literal

from langgraph.graph import StateGraph, END

from app.agents.decompose import DecomposeAgent
from app.agents.generate import GenerateAgent
from app.agents.inspect import InspectAgent
from app.pipeline.state import PipelineState, PhaseLog
from app.services.browser_render import render_multiple_frames
from app.services.shader_validator import validate_shader
from app.services.video_extractor import extract_keyframes, get_video_info
from app.config import settings
from app.routers.config import get_runtime_config


# ---- 节点函数 ----

decompose_agent = DecomposeAgent()
generate_agent = GenerateAgent()
inspect_agent = InspectAgent()


def _add_phase_log(state: PipelineState, phase: str, status: str, message: str, details: str | None = None, start_time: float | None = None, agent_response: str | None = None) -> list[PhaseLog]:
    """Helper to add a phase log entry"""
    logs = state.get("detailed_logs", [])
    
    # Calculate duration: use provided start_time or state's phase_start_time
    phase_start = start_time or state.get("phase_start_time")
    duration_ms = None
    if phase_start and status in ("completed", "failed"):
        duration_ms = int((time.time() - phase_start) * 1000)

    new_log: PhaseLog = {
        "phase": phase,
        "timestamp": time.time(),
        "status": status,
        "message": message,
        "details": details,
        "duration_ms": duration_ms,
        "agent_response": agent_response,  # Agent's raw response for displaying reasoning
    }
    return logs + [new_log]


async def node_extract_keyframes(state: PipelineState) -> dict:
    """视频输入时，提取关键帧；纯文本输入时返回空列表"""
    # Record phase start time
    phase_start = time.time()
    
    # Emit phase start
    logs = _add_phase_log(state, "extract_keyframes", "started", "Starting keyframe extraction...")

    if state.get("input_type") == "video" and state.get("video_path"):
        video_info = get_video_info(state["video_path"])
        keyframe_paths = extract_keyframes(state["video_path"], max_frames=6)

        # Emit completion with duration
        logs = _add_phase_log(
            {**state, "detailed_logs": logs},
            "extract_keyframes", "completed",
            f"Extracted {len(keyframe_paths)} keyframes from video",
            f"Duration: {video_info.get('duration', 0):.1f}s, FPS: {video_info.get('fps', 0):.0f}",
            start_time=phase_start
        )

        return {
            "video_info": video_info,
            "keyframe_paths": keyframe_paths,
            "design_screenshots": keyframe_paths,
            "current_phase": "decompose",
            "phase_status": "running",
            "phase_message": "Analyzing visual content...",
            "phase_start_time": time.time(),  # Set for NEXT phase
            "detailed_logs": logs,
        }
    elif state.get("image_paths"):
        # Emit completion for image input with duration
        logs = _add_phase_log(
            {**state, "detailed_logs": logs},
            "extract_keyframes", "completed",
            f"Using {len(state['image_paths'])} uploaded images as references",
            start_time=phase_start
        )

        return {
            "keyframe_paths": state["image_paths"],
            "design_screenshots": state["image_paths"],
            "current_phase": "decompose",
            "phase_status": "running",
            "phase_message": "Analyzing visual content...",
            "phase_start_time": time.time(),  # Set for NEXT phase
            "detailed_logs": logs,
        }

    # 纯文本输入：返回空列表以避免 LangGraph "Must write to at least one of..." 错误
    logs = _add_phase_log(
        {**state, "detailed_logs": logs},
        "extract_keyframes", "completed",
        "Text-only mode: no media extraction needed",
        start_time=phase_start
    )

    return {
        "keyframe_paths": [],
        "design_screenshots": [],
        "current_phase": "decompose",
        "phase_status": "running",
        "phase_message": "Processing text description...",
        "phase_start_time": time.time(),  # Set for NEXT phase
        "detailed_logs": logs,
    }


async def node_decompose(state: PipelineState) -> dict:
    """Decompose Agent：解构视效语义描述"""
    # Record phase start time
    phase_start = time.time()
    
    # Emit phase start
    logs = _add_phase_log(state, "decompose", "started", "Decomposing visual description...")

    keyframes = state.get("keyframe_paths", [])
    video_info = state.get("video_info")
    user_notes = state.get("user_notes", "")

    try:
        # 获取原始响应以显示 reasoning
        description = decompose_agent.run(
            image_paths=keyframes,
            video_info=video_info,
            user_notes=user_notes,
            return_raw=True,
        )

        # 提取 raw_response 用于显示
        raw_response = description.get("_raw_response", "")
        usage = description.get("_usage", {})
        effect_name = description.get("effect_name", "unknown")

        # Emit completion with duration and raw response
        logs = _add_phase_log(
            {**state, "detailed_logs": logs},
            "decompose", "completed",
            f"Generated visual description: {effect_name}",
            f"Shape: {description.get('shape', {}).get('type', 'unknown')}, Colors: {len(description.get('color', {}).get('palette', []))} colors",
            start_time=phase_start,
            agent_response=raw_response[:2000] if raw_response else None,  # 截取前 2000 字符
        )

        return {
            "visual_description": description,
            "current_phase": "generate",
            "phase_status": "running",
            "phase_message": "Generating GLSL shader code...",
            "phase_start_time": time.time(),
            "detailed_logs": logs,
        }
    except Exception as e:
        logs = _add_phase_log(
            {**state, "detailed_logs": logs},
            "decompose", "failed",
            f"Decomposition failed: {str(e)}",
            start_time=phase_start
        )
        return {
            "visual_description": {},
            "error": str(e),
            "detailed_logs": logs,
        }


async def node_validate_shader(state: PipelineState) -> dict:
    """Shader 验证：静态检查 + 语法验证。失败时返回 generate 由 Agent 闭环修正。"""
    iteration = state.get("iteration", 0)
    
    # Record phase start time
    phase_start = time.time()
    
    logs = _add_phase_log(state, "validate_shader", "started", f"Validating shader syntax (iteration {iteration + 1})...")
    
    shader = state.get("current_shader", "")
    if not shader:
        logs = _add_phase_log(
            {**state, "detailed_logs": logs},
            "validate_shader", "failed",
            "No shader code to validate",
            start_time=phase_start
        )
        # 返回 generate 让 Agent 修正（计入 iteration）
        return {
            "validation_errors": "No shader code generated",
            "compile_error": "No shader code",
            "compile_retry_count": state.get("compile_retry_count", 0) + 1,  # 仅日志记录
            "current_phase": "generate",
            "phase_status": "running",
            "phase_message": "Shader empty, requesting Agent to regenerate...",
            "phase_start_time": time.time(),
            "detailed_logs": logs,
        }
    
    # 执行验证
    validation_result = validate_shader(shader)
    
    duration_ms = int((time.time() - phase_start) * 1000)
    
    if not validation_result["valid"]:
        errors_str = "; ".join(validation_result["errors"])
        logs = _add_phase_log(
            {**state, "detailed_logs": logs},
            "validate_shader", "failed",
            f"Shader validation failed: {len(validation_result['errors'])} errors",
            errors_str,
            start_time=phase_start
        )
        
        # 返回 generate 让 Agent 闭环修正（不设置终止条件）
        return {
            "validation_errors": errors_str,
            "compile_error": None,
            "compile_retry_count": state.get("compile_retry_count", 0) + 1,  # 仅日志记录
            "current_phase": "generate",
            "phase_status": "running",
            "phase_message": "Shader validation failed, Agent will fix in next iteration...",
            "phase_start_time": time.time(),
            "detailed_logs": logs,
        }
    
    # 验证通过，进入 render
    warnings_str = "; ".join(validation_result["warnings"]) if validation_result["warnings"] else None
    logs = _add_phase_log(
        {**state, "detailed_logs": logs},
        "validate_shader", "completed",
        f"Shader validation passed ({duration_ms}ms)",
        warnings_str,
        start_time=phase_start
    )
    
    return {
        "validation_errors": None,
        "compile_error": None,
        "compile_retry_count": 0,  # 验证通过，重置计数（仅日志）
        "validation_warnings": warnings_str,
        "current_phase": "render",
        "phase_status": "running",
        "phase_message": "Rendering shader frames...",
        "phase_start_time": time.time(),
        "detailed_logs": logs,
    }


async def node_generate(state: PipelineState) -> dict:
    """Generate Agent：生成或修正 GLSL 代码。编译错误由 Agent 在 ReAct loop 中闭环解决。"""
    iteration = state.get("iteration", 0)
    compile_error_count = state.get("compile_retry_count", 0)  # 仅用于日志

    # Record phase start time
    phase_start = time.time()

    # 统一计数：任何返回 generate 都增加 iteration（编译错误或视觉反馈）
    has_compile_error = state.get("compile_error") or state.get("validation_errors")
    has_inspect_feedback = state.get("inspect_result") and not state.get("passed", False)
    
    # 每次进入 generate 都计入 iteration（编译修正和视觉修正都算）
    if has_compile_error or has_inspect_feedback:
        iteration += 1
    
    # 检查是否达到 max_iterations（唯一的终止条件）
    max_iterations = get_runtime_config().max_iterations
    if iteration >= max_iterations:
        reason = "compile errors" if has_compile_error else "visual inspection"
        logs = _add_phase_log(
            state, "generate", "failed",
            f"Max iterations ({max_iterations}) reached after {reason}",
            start_time=phase_start
        )
        return {
            "error": f"Max iterations ({max_iterations}) reached",
            "current_phase": "complete",
            "phase_status": "max_iterations",
            "iteration": iteration,
            "detailed_logs": logs,
        }

    # Emit phase start
    if has_compile_error:
        phase_msg = f"Fixing shader errors (iteration {iteration + 1})..."
    else:
        phase_msg = f"Generating shader (iteration {iteration + 1})..."
    logs = _add_phase_log(state, "generate", "started", phase_msg)

    description = state.get("visual_description", {})
    previous_shader = state.get("current_shader") if iteration > 0 else None
    feedback = None
    
    # 收集反馈来源：
    # 1. Inspect Agent 的视觉评估 feedback（视觉效果问题）
    # 2. 编译错误（shader 编译/渲染失败）—— Generate Agent 自己解决
    # 3. 验证错误（静态检查失败）—— Generate Agent 自己解决
    
    feedback_parts = []
    
    if state.get("inspect_result") and not state.get("passed", False):
        inspect_feedback = state["inspect_result"].get("feedback", "")
        if inspect_feedback:
            feedback_parts.append(f"[视觉评估反馈]\n{inspect_feedback}")
    
    if state.get("compile_error"):
        compile_error = state["compile_error"]
        feedback_parts.append(f"[编译错误 - 请自行修正]\nShader 编译/渲染失败：{compile_error}\n请检查 GLSL 语法并修正错误。")
    
    if state.get("validation_errors"):
        val_errors = state["validation_errors"]
        # 增强 banned declaration 的修复指导
        if "BANNED" in val_errors:
            feedback_parts.append(f"""[验证错误 - 必须修正]
Shader 验证失败：{val_errors}

⚠️ 你声明了 Shadertoy 内置变量，这些变量由运行时自动注入，**禁止手动声明**。

Shadertoy 标准内置变量：
- iTime (float) - 全局时间
- iResolution (vec3) - 视窗分辨率
- iMouse (vec4) - 鼠标状态
- iFrame (int) - 当前帧号

修正方法：
1. 删除代码中的所有 uniform 声明行
2. 直接在 mainImage 中使用变量名（如 iTime, iResolution.xy）

正确示例：
  vec2 uv = fragCoord / iResolution.xy;  // 直接使用
  float t = fract(iTime / 2.0);          // 直接使用""")
        else:
            feedback_parts.append(f"[验证错误]\nShader 验证失败：{val_errors}\n请检查 GLSL 语法并修正。")
    
    if feedback_parts:
        feedback = "\n\n".join(feedback_parts)
    
    # 传递 Generate Agent 自身的历史上下文
    generate_history = state.get("generate_history", [])

    try:
        result = generate_agent.run(
            visual_description=description,
            previous_shader=previous_shader,
            feedback=feedback,
            context_history=generate_history,
            return_raw=True,  # 获取原始响应
        )
        
        # Safe handling of None result
        if result is None:
            logs = _add_phase_log(
                {**state, "detailed_logs": logs},
                "generate", "failed",
                "Generate Agent returned None",
                start_time=phase_start
            )
            return {
                "current_shader": "",
                "compile_error": "Generate Agent returned None",
                "validation_errors": None,
                "iteration": iteration,
                "detailed_logs": logs,
            }
        
        # 提取 shader 和 raw_response with safe defaults
        shader = result.get("shader", "") if isinstance(result, dict) else (result if result else "")
        raw_response = result.get("raw_response", "") if isinstance(result, dict) else ""
        
        # Ensure shader is a string
        if not isinstance(shader, str):
            shader = str(shader) if shader else ""
        
        # Check if shader is empty
        if not shader.strip():
            print(f"[Pipeline] WARNING: Empty shader generated (iteration {iteration})")
        
        duration_ms = int((time.time() - phase_start) * 1000)

        # Emit completion with duration and raw response
        shader_preview = shader[:200] + "..." if len(shader) > 200 else shader
        logs = _add_phase_log(
            {**state, "detailed_logs": logs},
            "generate", "completed",
            f"Generated shader: {len(shader)} characters",
            f"Shader preview: {shader_preview}",
            start_time=phase_start,
            agent_response=raw_response[:3000] if raw_response else None,  # 截取前 3000 字符
        )

        # 更新 Generate Agent 的历史上下文
        new_history_entry = {
            "iteration": iteration + 1,
            "feedback_received": feedback[:500] if feedback else None,
            "shader_preview": shader[:200] if shader else None,
            "duration_ms": duration_ms,
        }
        updated_generate_history = generate_history + [new_history_entry]

        return {
            "current_shader": shader,
            "compile_error": None,
            "validation_errors": None,
            "compile_retry_count": compile_error_count,  # 仅日志记录
            "iteration": iteration,  # 更新迭代计数
            "current_phase": "validate_shader",
            "phase_status": "running",
            "phase_message": "Validating shader...",
            "phase_start_time": time.time(),
            "detailed_logs": logs,
            "generate_history": updated_generate_history,
        }
    except Exception as e:
        logs = _add_phase_log(
            {**state, "detailed_logs": logs},
            "generate", "failed",
            f"Shader generation failed: {str(e)}",
            start_time=phase_start
        )
        # 异常也返回 generate 重试（计入 iteration）
        return {
            "current_shader": "",
            "compile_error": str(e),
            "validation_errors": None,
            "iteration": iteration,
            "detailed_logs": logs,
        }


async def node_render_and_screenshot(state: PipelineState) -> dict:
    """在浏览器中渲染 shader 并截图。失败时返回 generate 由 Agent 闭环修正。"""
    iteration = state.get("iteration", 0)
    compile_error_count = state.get("compile_retry_count", 0)  # 仅用于日志

    # Record phase start time
    phase_start = time.time()

    logs = _add_phase_log(state, "render", "started", f"Rendering shader frames (iteration {iteration + 1})...")

    shader = state.get("current_shader", "")
    if not shader:
        logs = _add_phase_log(
            {**state, "detailed_logs": logs},
            "render", "failed",
            "No shader code to render",
            start_time=phase_start
        )
        # 返回 generate 让 Agent 修正（不终止）
        return {
            "render_screenshots": [],
            "compile_error": "No shader code to render",
            "compile_retry_count": compile_error_count + 1,  # 仅日志
            "current_phase": "generate",
            "phase_status": "running",
            "phase_message": "No shader, Agent will regenerate...",
            "phase_start_time": time.time(),
            "detailed_logs": logs,
        }

    try:
        screenshots = await render_multiple_frames(
            shader_code=shader,
            times=[0.0, 0.5, 1.0, 1.5, 2.0],
        )

        # Emit completion with duration
        logs = _add_phase_log(
            {**state, "detailed_logs": logs},
            "render", "completed",
            f"Rendered {len(screenshots)} frames successfully",
            start_time=phase_start
        )

        # 渲染成功 → 进入 inspect
        return {
            "render_screenshots": screenshots,
            "compile_error": None,
            "compile_retry_count": 0,  # 成功，重置（仅日志）
            "current_phase": "inspect",
            "phase_status": "running",
            "phase_message": "Inspecting rendered output...",
            "phase_start_time": time.time(),
            "detailed_logs": logs,
        }
    except asyncio.TimeoutError:
        logs = _add_phase_log(
            {**state, "detailed_logs": logs},
            "render", "failed",
            "Render timeout (frontend not ready)",
            start_time=phase_start
        )
        # 返回 generate 让 Agent 修正（不终止）
        return {
            "render_screenshots": [],
            "compile_error": "Render timeout - frontend not ready or shader too slow",
            "compile_retry_count": compile_error_count + 1,  # 仅日志
            "current_phase": "generate",
            "phase_status": "running",
            "phase_message": "Render timeout, Agent will fix shader performance...",
            "phase_start_time": time.time(),
            "detailed_logs": logs,
        }
    except Exception as e:
        logs = _add_phase_log(
            {**state, "detailed_logs": logs},
            "render", "failed",
            f"Render error: {str(e)}",
            start_time=phase_start
        )
        # 返回 generate 让 Agent 修正（不终止）
        return {
            "render_screenshots": [],
            "compile_error": str(e),
            "compile_retry_count": compile_error_count + 1,  # 仅日志
            "current_phase": "generate",
            "phase_status": "running",
            "phase_message": f"Shader compile error, Agent will fix: {str(e)[:50]}...",
            "phase_start_time": time.time(),
            "detailed_logs": logs,
        }


async def node_inspect(state: PipelineState) -> dict:
    """Inspect Agent：对比截图，输出评估"""
    iteration = state.get("iteration", 0)

    # Record phase start time
    phase_start = time.time()

    # Emit phase start
    logs = _add_phase_log(state, "inspect", "started", f"Inspecting rendered output (iteration {iteration})...")

    design_imgs = state.get("design_screenshots", [])
    render_imgs = state.get("render_screenshots", [])
    
    # 获取 Inspect Agent 自身的历史上下文
    inspect_history = state.get("inspect_history", [])

    # Text-only mode: no design reference, auto-pass if shader generated
    if not design_imgs and state.get("current_shader"):
        # 记录 pipeline 级别历史
        history = state.get("history", [])
        history.append({
            "iteration": iteration,
            "score": 0.9,
            "passed": True,
            "feedback": "Text mode: auto-accepted (no design reference)",
        })
        
        # 记录 Inspect Agent 历史
        new_inspect_entry = {
            "iteration": iteration,
            "score": 0.9,
            "passed": True,
            "feedback": "Text mode: auto-accepted",
            "issues_summary": None,
        }
        updated_inspect_history = inspect_history + [new_inspect_entry]

        logs = _add_phase_log(
            {**state, "detailed_logs": logs},
            "inspect", "completed",
            "Auto-accepted: text-only mode (no design reference)",
            start_time=phase_start
        )

        return {
            "inspect_result": {"passed": True, "overall_score": 0.9, "feedback": "Text mode: auto-accepted"},
            "passed": True,
            "history": history,
            "inspect_history": updated_inspect_history,
            "current_phase": "complete",
            "phase_status": "completed",
            "phase_message": "Pipeline completed successfully",
            "detailed_logs": logs,
        }

    # Render failed: skip inspect, will retry in next iteration
    if not render_imgs:
        # 记录 pipeline 级别历史
        history = state.get("history", [])
        history.append({
            "iteration": iteration,
            "score": 0,
            "passed": False,
            "feedback": "渲染失败，无截图可对比",
        })
        
        # 记录 Inspect Agent 历史
        new_inspect_entry = {
            "iteration": iteration,
            "score": 0,
            "passed": False,
            "feedback": "渲染失败，无截图可对比",
            "issues_summary": "Render failed",
        }
        updated_inspect_history = inspect_history + [new_inspect_entry]

        logs = _add_phase_log(
            {**state, "detailed_logs": logs},
            "inspect", "failed",
            "No rendered screenshots to compare",
            start_time=phase_start
        )

        return {
            "inspect_result": {"passed": False, "overall_score": 0, "feedback": "渲染失败，无截图可对比"},
            "passed": False,
            "history": history,
            "inspect_history": updated_inspect_history,
            "detailed_logs": logs,
        }

    try:
        result = inspect_agent.run(
            design_images=design_imgs,
            render_screenshots=render_imgs,
            visual_description=state.get("visual_description"),
            iteration=iteration,
            context_history=inspect_history,  # Agent 自己的历史
        )

        passed = result.get("passed", False) or result.get("overall_score", 0) >= get_runtime_config().passing_threshold
        
        # 提取 issues summary（如果有 dimensions）
        issues_summary = None
        if result.get("dimensions"):
            dims = result["dimensions"]
            issues_list = []
            for dim_name, dim_info in dims.items():
                if dim_info.get("score", 1.0) < 0.7:
                    issues_list.append(f"{dim_name}: {dim_info.get('notes', '')[:50]}")
            issues_summary = "; ".join(issues_list) if issues_list else None
        
        # 记录 pipeline 级别历史
        history = state.get("history", [])
        history.append({
            "iteration": iteration,
            "score": result.get("overall_score", 0),
            "passed": passed,
            "feedback": result.get("feedback", ""),
        })
        
        # 记录 Inspect Agent 历史
        new_inspect_entry = {
            "iteration": iteration,
            "score": result.get("overall_score", 0),
            "passed": passed,
            "feedback": result.get("feedback", ""),
            "issues_summary": issues_summary,
        }
        updated_inspect_history = inspect_history + [new_inspect_entry]

        # Emit completion with duration
        logs = _add_phase_log(
            {**state, "detailed_logs": logs},
            "inspect", "completed" if passed else "running",
            f"Inspection complete: score {result.get('overall_score', 0):.2f}, {'PASSED' if passed else 'NEEDS IMPROVEMENT'}",
            result.get("feedback", ""),
            start_time=phase_start
        )

        return {
            "inspect_result": result,
            "passed": passed,
            "history": history,
            "inspect_history": updated_inspect_history,
            "current_phase": "complete" if passed else "generate",
            "phase_status": "completed" if passed else "running",
            "phase_message": "Pipeline completed successfully" if passed else "Preparing next iteration...",
            "phase_start_time": time.time() if not passed else None,
            "detailed_logs": logs,
        }
    except Exception as e:
        logs = _add_phase_log(
            {**state, "detailed_logs": logs},
            "inspect", "failed",
            f"Inspection failed: {str(e)}",
            start_time=phase_start
        )
        
        # 记录 Inspect Agent 历史（失败）
        new_inspect_entry = {
            "iteration": iteration,
            "score": 0,
            "passed": False,
            "feedback": str(e),
            "issues_summary": f"Error: {str(e)[:50]}",
        }
        updated_inspect_history = inspect_history + [new_inspect_entry]
        
        return {
            "inspect_result": {"passed": False, "overall_score": 0, "feedback": str(e)},
            "passed": False,
            "history": state.get("history", []),
            "inspect_history": updated_inspect_history,
            "detailed_logs": logs,
        }


# ---- 条件边 ----

def route_from_validate(state: PipelineState) -> Literal["generate", "render", "end"]:
    """验证节点后的路由"""
    # 检查是否达到重试上限（通过 error 字段）
    if state.get("error"):
        return "end"
    
    # 验证失败 → 返回 generate（包括空字符串的情况）
    validation_errors = state.get("validation_errors")
    if validation_errors is not None:  # 存在 validation_errors 字段（包括空字符串）
        return "generate"
    
    # 验证通过 → 进入 render
    return "render"


def route_from_generate(state: PipelineState) -> Literal["validate_shader", "end"]:
    """Generate 节点后的路由"""
    # 检查是否出错
    if state.get("error"):
        return "end"
    
    # 正常进入 validate_shader
    return "validate_shader"


def route_from_render(state: PipelineState) -> Literal["generate", "inspect", "end"]:
    """渲染节点后的路由"""
    # 检查是否出错
    if state.get("error"):
        return "end"
    
    # 编译/渲染失败 → 返回 generate
    if state.get("compile_error"):
        return "generate"
    
    # 渲染成功 → 进入 inspect
    return "inspect"


def route_from_inspect(state: PipelineState) -> Literal["generate", "end"]:
    """检视节点后的路由"""
    # 检查是否出错
    if state.get("error"):
        return "end"
    
    if state.get("passed", False):
        return "end"
    
    # Inspect JSON 解析完全失败，终止
    inspect_result = state.get("inspect_result", {})
    if inspect_result.get("parse_error") and not inspect_result.get("raw_response"):
        return "end"
    
    # Text-only mode: end after first iteration
    if state.get("input_type") == "text" and state.get("iteration", 0) >= 1:
        return "end"
    
    # 达到最大迭代次数
    max_iterations = get_runtime_config().max_iterations
    if state.get("iteration", 0) >= max_iterations:
        return "end"
    
    # 视觉效果未通过 → 返回 generate 修正
    return "generate"


# ---- 构建图 ----

def build_pipeline_graph() -> StateGraph:
    graph = StateGraph(PipelineState)

    # 添加节点
    graph.add_node("extract_keyframes", node_extract_keyframes)
    graph.add_node("decompose", node_decompose)
    graph.add_node("generate", node_generate)
    graph.add_node("validate_shader", node_validate_shader)
    graph.add_node("render_and_screenshot", node_render_and_screenshot)
    graph.add_node("inspect", node_inspect)

    # 添加边
    graph.set_entry_point("extract_keyframes")
    graph.add_edge("extract_keyframes", "decompose")
    graph.add_edge("decompose", "generate")
    
    # generate 的条件边（可以终止或进入 validate_shader）
    graph.add_conditional_edges(
        "generate",
        route_from_generate,
        {"validate_shader": "validate_shader", "end": END},
    )
    
    # validate_shader 的条件边（可以终止、返回 generate、或进入 render）
    graph.add_conditional_edges(
        "validate_shader",
        route_from_validate,
        {"generate": "generate", "render": "render_and_screenshot", "end": END},
    )
    
    # render 的条件边
    graph.add_conditional_edges(
        "render_and_screenshot",
        route_from_render,
        {"generate": "generate", "inspect": "inspect", "end": END},
    )
    
    # inspect 的条件边
    graph.add_conditional_edges(
        "inspect",
        route_from_inspect,
        {"generate": "generate", "end": END},
    )

    return graph


# 实例化最终的 pipeline graph
pipeline_app = build_pipeline_graph().compile()