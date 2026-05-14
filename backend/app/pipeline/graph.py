"""LangGraph Pipeline Orchestrator - V3.0 Four-Region Architecture

重构要点：
1. 所有节点使用四区字段 (baseline/snapshot/gradient_window/checkpoint)
2. Agent 调用使用新接口 run(state)
3. 物理回滚机制集成到 node_inspect
4. Re-decompose 路由新增
5. 梯度裁剪集成到 node_generate

向后兼容层：
- 保留旧字段双写（迁移期）
- Agent 使用 legacy 接口过渡
"""

import time
from typing import Literal

from langgraph.graph import StateGraph, END

from app.agents.decompose import DecomposeAgent
from app.agents.generate import run_legacy as generate_run
from app.agents.inspect import run_legacy as inspect_run
from app.pipeline.state import (
    PipelineState,
    PhaseLog,
    create_initial_state,
    update_gradient_window,
    should_trigger_re_decompose,
    detect_score_regression,
    rollback_to_checkpoint,
    update_checkpoint,
    GradientEntry,
)
from app.services.browser_render import render_multiple_frames
from app.services.shader_validator import validate_shader
from app.services.video_extractor import extract_keyframes, get_video_info
from app.config import settings
from app.routers.config import get_runtime_config


# === Agent 实例（暂用 legacy 接口，后续迁移到新 Agent.run(state)） ===


def _add_phase_log(
    state: PipelineState,
    phase: str,
    status: str,
    message: str,
    details: str | None = None,
    start_time: float | None = None,
    agent_response: str | None = None,
    visual_issues: list[str] | None = None,
    visual_goals: list[str] | None = None,
    correct_aspects: list[str] | None = None,
    re_decompose_triggered: bool | None = None,
    rollback_triggered: bool | None = None,
) -> list[PhaseLog]:
    """Helper to add a phase log entry"""
    logs = state.get("detailed_logs", [])

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
        "agent_response": agent_response,
        "visual_issues": visual_issues,
        "visual_goals": visual_goals,
        "correct_aspects": correct_aspects,
        "re_decompose_triggered": re_decompose_triggered,
        "rollback_triggered": rollback_triggered,
    }
    return logs + [new_log]


# === 节点函数 ===


async def node_extract_keyframes(state: PipelineState) -> dict:
    """Extract keyframes from video or use uploaded images
    
    Writes to: baseline.keyframe_paths, baseline.video_info
    """
    baseline = state.get("baseline", {})
    snapshot = state.get("snapshot", {})
    
    # Human iteration mode: skip extraction
    if state.get("human_iteration_mode"):
        phase_start = time.time()
        logs = _add_phase_log(
            state, "extract_keyframes", "completed",
            "Human iteration: skipping keyframe extraction",
            start_time=phase_start
        )
        return {
            "current_phase": "decompose",
            "phase_status": "running",
            "phase_message": "Human iteration mode active...",
            "phase_start_time": time.time(),
            "detailed_logs": logs,
            # 向后兼容
            "keyframe_paths": baseline.get("keyframe_paths", []),
            "design_screenshots": state.get("design_screenshots", []),
        }
    
    phase_start = time.time()
    logs = _add_phase_log(state, "extract_keyframes", "started", "Starting keyframe extraction...")
    
    input_type = baseline.get("input_type", "text")
    video_path = baseline.get("video_path")
    image_paths = baseline.get("image_paths", [])
    
    if input_type == "video" and video_path:
        video_info = get_video_info(video_path)
        keyframe_paths = extract_keyframes(video_path, max_frames=6)
        
        logs = _add_phase_log(
            {**state, "detailed_logs": logs},
            "extract_keyframes", "completed",
            f"Extracted {len(keyframe_paths)} keyframes from video",
            f"Duration: {video_info.get('duration', 0):.1f}s, FPS: {video_info.get('fps', 0):.0f}",
            start_time=phase_start
        )
        
        # 更新 baseline
        updated_baseline = {
            **baseline,
            "video_info": video_info,
            "keyframe_paths": keyframe_paths,
        }
        
        return {
            "baseline": updated_baseline,
            "current_phase": "decompose",
            "phase_status": "running",
            "phase_message": "Analyzing visual content...",
            "phase_start_time": time.time(),
            "detailed_logs": logs,
            # 向后兼容
            "video_info": video_info,
            "keyframe_paths": keyframe_paths,
            "design_screenshots": keyframe_paths,
        }
    
    elif image_paths:
        logs = _add_phase_log(
            {**state, "detailed_logs": logs},
            "extract_keyframes", "completed",
            f"Using {len(image_paths)} uploaded images as references",
            start_time=phase_start
        )
        
        updated_baseline = {
            **baseline,
            "keyframe_paths": image_paths,
        }
        
        return {
            "baseline": updated_baseline,
            "current_phase": "decompose",
            "phase_status": "running",
            "phase_message": "Analyzing visual content...",
            "phase_start_time": time.time(),
            "detailed_logs": logs,
            # 向后兼容
            "keyframe_paths": image_paths,
            "design_screenshots": image_paths,
        }
    
    # Text-only mode
    logs = _add_phase_log(
        {**state, "detailed_logs": logs},
        "extract_keyframes", "completed",
        "Text-only mode: no media extraction needed",
        start_time=phase_start
    )
    
    return {
        "current_phase": "decompose",
        "phase_status": "running",
        "phase_message": "Processing text description...",
        "phase_start_time": time.time(),
        "detailed_logs": logs,
        # 向后兼容
        "keyframe_paths": [],
        "design_screenshots": [],
    }


def node_decompose(state: PipelineState) -> dict:
    """Decompose Agent: Analyze visual references and generate visual_description
    
    Reads from: baseline.keyframe_paths, baseline.video_info, baseline.user_notes
    Writes to: snapshot.visual_description, checkpoint.best_visual_description (首次)
    
    Modes:
    - cold_start: First decomposition
    - re_decompose: Triggered by Inspect Agent (注入 Failure Log)
    """
    baseline = state.get("baseline", {})
    snapshot = state.get("snapshot", {})
    checkpoint = state.get("checkpoint", {})
    
    # Human iteration mode: skip decompose
    if state.get("human_iteration_mode"):
        phase_start = time.time()
        logs = _add_phase_log(
            state, "decompose", "completed",
            "Human iteration: skipping decompose, using existing visual description",
            start_time=phase_start
        )
        return {
            "current_phase": "generate",
            "phase_status": "running",
            "phase_message": "Generating shader with human feedback...",
            "phase_start_time": time.time(),
            "detailed_logs": logs,
            # 向后兼容
            "visual_description": snapshot.get("visual_description", {}),
        }
    
    phase_start = time.time()
    logs = _add_phase_log(state, "decompose", "started", "Decomposing visual description...")
    
    keyframes = baseline.get("keyframe_paths", [])
    video_info = baseline.get("video_info")
    user_notes = baseline.get("user_notes", "")
    iteration = snapshot.get("iteration", 0)
    pipeline_id = state.get("pipeline_id", "")
    
    # 判断是否为 re_decompose 模式
    mode = "cold_start"
    if should_trigger_re_decompose(state) and iteration > 0:
        mode = "re_decompose"
        print(f"[Decompose Node] Re-decompose triggered at iteration {iteration}")
    
    try:
        # 直接调用 Agent.run(state, mode)（传递完整 state 以构建 Failure Log）
        agent = DecomposeAgent()
        result = agent.run(state, mode=mode, return_raw=True)
        
        visual_description = result.get("visual_description", {})
        raw_response = result.get("raw_response", "")
        usage = result.get("usage")
        
        effect_name = visual_description.get("effect_name", "unknown")
        
        logs = _add_phase_log(
            {**state, "detailed_logs": logs},
            "decompose", "completed",
            f"Generated visual description: {effect_name}",
            f"Shape: {visual_description.get('shape_definition', {}).get('description', '')[:50]}",
            start_time=phase_start,
            agent_response=raw_response[:2000] if raw_response else None,
        )
        
        # 更新 snapshot
        updated_snapshot = {
            **snapshot,
            "visual_description": visual_description,
        }
        
        # 首次 Decompose：更新 checkpoint
        updated_checkpoint = checkpoint
        if iteration == 0:
            updated_checkpoint = {
                **checkpoint,
                "best_visual_description": visual_description,
            }
        
        return {
            "snapshot": updated_snapshot,
            "checkpoint": updated_checkpoint,
            "current_phase": "generate",
            "phase_status": "running",
            "phase_message": "Generating GLSL shader code...",
            "phase_start_time": time.time(),
            "detailed_logs": logs,
            # 向后兼容
            "visual_description": visual_description,
        }
    
    except Exception as e:
        logs = _add_phase_log(
            {**state, "detailed_logs": logs},
            "decompose", "failed",
            f"Decomposition failed: {str(e)}",
            start_time=phase_start
        )
        return {
            "error": str(e),
            "detailed_logs": logs,
            # 向后兼容
            "visual_description": {},
        }


def node_generate(state: PipelineState) -> dict:
    """Generate Agent: Generate or fix GLSL shader
    
    Reads from: 
      snapshot.visual_description, snapshot.shader, snapshot.inspect_feedback
      gradient_window (裁剪后注入)
      checkpoint.best_shader (回滚时使用)
    
    Writes to: snapshot.shader, gradient_window (新增 entry)
    
    Gradient truncation: 禁止注入完整 shader 到 history
    """
    baseline = state.get("baseline", {})
    snapshot = state.get("snapshot", {})
    gradient_window = state.get("gradient_window", [])
    checkpoint = state.get("checkpoint", {})
    config = state.get("config", {})
    
    iteration = snapshot.get("iteration", 0)
    compile_error_count = state.get("compile_retry_count", 0)
    
    phase_start = time.time()
    
    # 统一计数：任何返回 generate 都增加 iteration
    has_compile_error = state.get("compile_error") or state.get("validation_errors")
    has_inspect_feedback = snapshot.get("inspect_feedback") and not state.get("passed", False)
    
    if has_compile_error or has_inspect_feedback:
        iteration += 1
    
    # 检查 max_iterations
    max_iterations = config.get("max_iterations", get_runtime_config().max_iterations)
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
            "snapshot": {**snapshot, "iteration": iteration},
            "detailed_logs": logs,
            # 向后兼容
            "iteration": iteration,
        }
    
    # Emit phase start
    phase_msg = f"Fixing shader errors (iteration {iteration + 1})..." if has_compile_error else f"Generating shader (iteration {iteration + 1})..."
    logs = _add_phase_log(state, "generate", "started", phase_msg)
    
    # 构造 feedback
    feedback_parts = []
    
    # 视觉反馈：从 inspect_feedback 提取 visual_issues 和 visual_goals
    inspect_feedback = snapshot.get("inspect_feedback")
    if inspect_feedback and not state.get("passed", False):
        visual_issues = inspect_feedback.get("visual_issues", [])
        visual_goals = inspect_feedback.get("visual_goals", [])
        
        if visual_issues:
            issues_text = "\n".join([f"- {issue}" for issue in visual_issues])
            feedback_parts.append(f"[视觉问题]\n{issues_text}")
        
        if visual_goals:
            goals_text = "\n".join([f"- {goal}" for goal in visual_goals])
            feedback_parts.append(f"[期望效果]\n{goals_text}")
        
        feedback_summary = inspect_feedback.get("feedback_summary", "")
        if feedback_summary:
            feedback_parts.append(f"[整体方向]\n{feedback_summary}")
    
    if state.get("compile_error"):
        feedback_parts.append(f"[编译错误 - 请自行修正]\nShader 编译/渲染失败：{state['compile_error']}")
    
    if state.get("validation_errors"):
        val_errors = state["validation_errors"]
        if "BANNED" in val_errors:
            feedback_parts.append(f"""[验证错误 - 必须修正]
Shader 验证失败：{val_errors}

⚠️ 你声明了 Shadertoy 内置变量，禁止手动声明。

修正方法：
1. 删除代码中的所有 uniform 声明行
2. 直接在 mainImage 中使用变量名（如 iTime, iResolution.xy）""")
        else:
            feedback_parts.append(f"[验证错误]\nShader 验证失败：{val_errors}")
    
    feedback = "\n\n".join(feedback_parts) if feedback_parts else None
    
    # 物理回滚检测已移到 node_inspect（正确位置）
    # node_generate 不再检测回滚（避免时序错位）
    
    # 获取 previous_shader
    previous_shader = snapshot.get("shader", "")
    
    # 构造 generate_history（向后兼容）
    generate_history = state.get("generate_history", [])
    
    try:
        # 调用 legacy 接口
        result = generate_run(
            visual_description=snapshot.get("visual_description", {}),
            previous_shader=previous_shader if iteration > 0 else None,
            feedback=feedback,
            context_history=generate_history,
            human_feedback=state.get("human_feedback"),
            pipeline_id=state.get("pipeline_id"),
            iteration=iteration + 1,
            return_raw=True,
        )
        
        if result is None:
            logs = _add_phase_log(
                {**state, "detailed_logs": logs},
                "generate", "failed",
                "Generate Agent returned None",
                start_time=phase_start
            )
            return {
                "snapshot": {**snapshot, "shader": "", "compile_error": "Generate Agent returned None"},
                "detailed_logs": logs,
                # 向后兼容
                "current_shader": "",
                "iteration": iteration,
            }
        
        shader = result.get("shader", "")
        raw_response = result.get("raw_response", "")
        
        if not shader.strip():
            print(f"[Pipeline] WARNING: Empty shader generated (iteration {iteration})")
        
        duration_ms = int((time.time() - phase_start) * 1000)
        
        logs = _add_phase_log(
            {**state, "detailed_logs": logs},
            "generate", "completed",
            f"Generated shader: {len(shader)} characters",
            f"Shader preview: {shader[:200]}...",
            start_time=phase_start,
            agent_response=raw_response[:3000] if raw_response else None,
        )
        
        # 更新 snapshot
        updated_snapshot = {
            **snapshot,
            "shader": shader,
            "iteration": iteration,
            "compile_error": None,
            "validation_errors": None,
        }
        
        # 更新 gradient_window（梯度裁剪：不存 shader）
        new_gradient_entry: GradientEntry = {
            "iteration": iteration,
            "score": inspect_feedback.get("overall_score", 0) if inspect_feedback else 0,
            "feedback_summary": feedback[:100] if feedback else "",
            "shader_diff_summary": None,  # 可选：本轮修改摘要
            "issues_fixed": None,
            "issues_remaining": inspect_feedback.get("visual_issues") if inspect_feedback else None,
            "duration_ms": duration_ms,
            "human_iteration": state.get("human_iteration_mode", False),
        }
        
        window_size = config.get("gradient_window_size", 3)
        updated_gradient_window = update_gradient_window(
            gradient_window, new_gradient_entry, window_size
        )
        
        # 更新 generate_history（向后兼容）
        new_history_entry = {
            "iteration": iteration + 1,
            "feedback_received": feedback[:500] if feedback else None,
            "shader": shader,
            "duration_ms": duration_ms,
        }
        updated_generate_history = generate_history + [new_history_entry]
        
        return {
            "snapshot": updated_snapshot,
            "gradient_window": updated_gradient_window,
            "current_phase": "validate_shader",
            "phase_status": "running",
            "phase_message": "Validating shader...",
            "phase_start_time": time.time(),
            "detailed_logs": logs,
            "compile_retry_count": 0,
            # 向后兼容
            "current_shader": shader,
            "iteration": iteration,
            "generate_history": updated_generate_history,
        }
    
    except Exception as e:
        logs = _add_phase_log(
            {**state, "detailed_logs": logs},
            "generate", "failed",
            f"Shader generation failed: {str(e)}",
            start_time=phase_start
        )
        return {
            "snapshot": {**snapshot, "shader": "", "compile_error": str(e)},
            "detailed_logs": logs,
            # 向后兼容
            "current_shader": "",
            "compile_error": str(e),
            "iteration": iteration,
        }


def node_validate_shader(state: PipelineState) -> dict:
    """Shader validation: static check + syntax validation
    
    Reads from: snapshot.shader
    Writes to: snapshot.validation_errors (失败时)
    
    Routing: 
    - 失败 → generate (Agent fixes)
    - 通过 → render
    """
    snapshot = state.get("snapshot", {})
    
    phase_start = time.time()
    iteration = snapshot.get("iteration", 0)
    
    logs = _add_phase_log(state, "validate_shader", "started", f"Validating shader syntax (iteration {iteration + 1})...")
    
    shader = snapshot.get("shader", "")
    if not shader:
        logs = _add_phase_log(
            {**state, "detailed_logs": logs},
            "validate_shader", "failed",
            "No shader code to validate",
            start_time=phase_start
        )
        return {
            "snapshot": {**snapshot, "validation_errors": "No shader code generated"},
            "current_phase": "generate",
            "phase_status": "running",
            "phase_message": "Shader empty, requesting Agent to regenerate...",
            "phase_start_time": time.time(),
            "detailed_logs": logs,
            "compile_retry_count": state.get("compile_retry_count", 0) + 1,
            # 向后兼容
            "validation_errors": "No shader code generated",
            "compile_error": "No shader code",
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
        
        return {
            "snapshot": {**snapshot, "validation_errors": errors_str},
            "current_phase": "generate",
            "phase_status": "running",
            "phase_message": "Shader validation failed, Agent will fix...",
            "phase_start_time": time.time(),
            "detailed_logs": logs,
            "compile_retry_count": state.get("compile_retry_count", 0) + 1,
            # 向后兼容
            "validation_errors": errors_str,
        }
    
    # 验证通过
    warnings_str = "; ".join(validation_result["warnings"]) if validation_result["warnings"] else None
    logs = _add_phase_log(
        {**state, "detailed_logs": logs},
        "validate_shader", "completed",
        f"Shader validation passed ({duration_ms}ms)",
        warnings_str,
        start_time=phase_start
    )
    
    return {
        "snapshot": {**snapshot, "validation_errors": None, "compile_error": None},
        "current_phase": "render",
        "phase_status": "running",
        "phase_message": "Rendering shader frames...",
        "phase_start_time": time.time(),
        "detailed_logs": logs,
        "compile_retry_count": 0,
        # 向后兼容
        "validation_errors": None,
        "validation_warnings": warnings_str,
    }


def node_render_and_screenshot(state: PipelineState) -> dict:
    """Render shader in WebGL and capture screenshots
    
    Reads from: snapshot.shader
    Writes to: snapshot.render_screenshots
    
    Routing:
    - 失败 → generate (Agent fixes)
    - 成功 → inspect
    """
    snapshot = state.get("snapshot", {})
    
    phase_start = time.time()
    iteration = snapshot.get("iteration", 0)
    
    logs = _add_phase_log(state, "render", "started", f"Rendering shader frames (iteration {iteration + 1})...")
    
    shader = snapshot.get("shader", "")
    if not shader:
        logs = _add_phase_log(
            {**state, "detailed_logs": logs},
            "render", "failed",
            "No shader code to render",
            start_time=phase_start
        )
        return {
            "snapshot": {**snapshot, "compile_error": "No shader code to render"},
            "current_phase": "generate",
            "phase_status": "running",
            "phase_message": "No shader, Agent will regenerate...",
            "phase_start_time": time.time(),
            "detailed_logs": logs,
            "compile_retry_count": state.get("compile_retry_count", 0) + 1,
            # 向后兼容
            "render_screenshots": [],
            "compile_error": "No shader code to render",
        }
    
    try:
        # render_multiple_frames 是同步函数，直接调用
        screenshots = render_multiple_frames(
            shader_code=shader,
            times=[0.0, 0.5, 1.0, 1.5, 2.0],
        )
        
        logs = _add_phase_log(
            {**state, "detailed_logs": logs},
            "render", "completed",
            f"Rendered {len(screenshots)} frames successfully",
            start_time=phase_start
        )
        
        return {
            "snapshot": {**snapshot, "render_screenshots": screenshots, "compile_error": None},
            "current_phase": "inspect",
            "phase_status": "running",
            "phase_message": "Inspecting rendered output...",
            "phase_start_time": time.time(),
            "detailed_logs": logs,
            "compile_retry_count": 0,
            # 向后兼容
            "render_screenshots": screenshots,
        }
    
    except TimeoutError:
        logs = _add_phase_log(
            {**state, "detailed_logs": logs},
            "render", "failed",
            "Render timeout (frontend not ready)",
            start_time=phase_start
        )
        return {
            "snapshot": {**snapshot, "compile_error": "Render timeout"},
            "current_phase": "generate",
            "phase_status": "running",
            "phase_message": "Render timeout, Agent will fix...",
            "phase_start_time": time.time(),
            "detailed_logs": logs,
            "compile_retry_count": state.get("compile_retry_count", 0) + 1,
            # 向后兼容
            "render_screenshots": [],
            "compile_error": "Render timeout",
        }
    
    except Exception as e:
        logs = _add_phase_log(
            {**state, "detailed_logs": logs},
            "render", "failed",
            f"Render error: {str(e)}",
            start_time=phase_start
        )
        return {
            "snapshot": {**snapshot, "compile_error": str(e)},
            "current_phase": "generate",
            "phase_status": "running",
            "phase_message": f"Shader compile error: {str(e)[:50]}...",
            "phase_start_time": time.time(),
            "detailed_logs": logs,
            "compile_retry_count": state.get("compile_retry_count", 0) + 1,
            # 向后兼容
            "render_screenshots": [],
            "compile_error": str(e),
        }


def node_inspect(state: PipelineState) -> dict:
    """Inspect Agent: Compare render screenshots with design reference
    
    Reads from:
      baseline.image_paths, snapshot.render_screenshots, snapshot.shader
      snapshot.visual_description, gradient_window
    
    Writes to: snapshot.inspect_feedback, checkpoint (if improved), gradient_window
    
    Physical rollback: if score regression detected
    Re-decompose trigger: if score below threshold or stagnation
    """
    baseline = state.get("baseline", {})
    snapshot = state.get("snapshot", {})
    gradient_window = state.get("gradient_window", [])
    checkpoint = state.get("checkpoint", {})
    config = state.get("config", {})
    
    iteration = snapshot.get("iteration", 0)
    human_iteration_mode = state.get("human_iteration_mode", False)
    human_feedback = state.get("human_feedback")
    
    phase_start = time.time()
    
    # Human iteration mode: skip Agent inspection
    if human_iteration_mode and human_feedback:
        human_fb_preview = human_feedback[:30] + "..." if len(human_feedback) > 30 else human_feedback
        
        logs = _add_phase_log(
            state, "inspect", "completed",
            f"User inspection mode: skipping Agent evaluation",
            f"User directive: {human_fb_preview}",
            start_time=phase_start
        )
        
        result = {
            "passed": False,
            "overall_score": None,
            "visual_issues": [f"用户反馈：{human_feedback}"],
            "visual_goals": ["根据用户指令调整视觉效果"],
            "feedback_summary": f"用户指令：{human_feedback}",
            "human_iteration": True,
        }
        
        # 更新 snapshot
        updated_snapshot = {
            **snapshot,
            "inspect_feedback": result,
        }
        
        # 更新 gradient_window
        new_gradient_entry: GradientEntry = {
            "iteration": iteration,
            "score": None,
            "feedback_summary": human_fb_preview,
            "duration_ms": int((time.time() - phase_start) * 1000),
            "human_iteration": True,
        }
        updated_gradient_window = update_gradient_window(
            gradient_window, new_gradient_entry, config.get("gradient_window_size", 3)
        )
        
        # 更新 inspect_history（向后兼容）
        inspect_history = state.get("inspect_history", [])
        inspect_history.append({
            "iteration": iteration,
            "score": None,
            "passed": False,
            "feedback": human_feedback,
            "human_iteration": True,
        })
        
        return {
            "snapshot": updated_snapshot,
            "gradient_window": updated_gradient_window,
            "current_phase": "generate",
            "phase_status": "running",
            "phase_message": f"Processing user directive: {human_fb_preview}",
            "phase_start_time": time.time(),
            "detailed_logs": logs,
            "human_iteration_processed": True,
            "human_iteration_mode": False,
            "human_feedback": None,
            # 向后兼容
            "inspect_result": result,
            "passed": False,
            "inspect_history": inspect_history,
        }
    
    logs = _add_phase_log(state, "inspect", "started", f"Inspecting rendered output (iteration {iteration})...")
    
    design_imgs = state.get("design_screenshots", baseline.get("image_paths", []))
    render_imgs = snapshot.get("render_screenshots", [])
    visual_description = snapshot.get("visual_description")
    shader = snapshot.get("shader", "")
    
    # Text-only mode: auto-pass
    if not design_imgs and shader:
        result = {
            "passed": True,
            "overall_score": 0.9,
            "visual_issues": [],
            "visual_goals": [],
            "feedback_summary": "Text mode: auto-accepted",
        }
        
        logs = _add_phase_log(
            {**state, "detailed_logs": logs},
            "inspect", "completed",
            "Auto-accepted: text-only mode",
            start_time=phase_start
        )
        
        updated_snapshot = {
            **snapshot,
            "inspect_feedback": result,
        }
        
        # 更新 checkpoint
        checkpoint_update = update_checkpoint({**state, "snapshot": updated_snapshot})
        updated_checkpoint = checkpoint_update.get("checkpoint", checkpoint)
        
        return {
            "snapshot": updated_snapshot,
            "checkpoint": updated_checkpoint,
            "current_phase": "complete",
            "phase_status": "completed",
            "phase_message": "Pipeline completed successfully",
            "detailed_logs": logs,
            "passed": True,
            # 向后兼容
            "inspect_result": result,
        }
    
    # Render failed: skip inspect
    if not render_imgs:
        logs = _add_phase_log(
            {**state, "detailed_logs": logs},
            "inspect", "failed",
            "No rendered screenshots to compare",
            start_time=phase_start
        )
        
        return {
            "snapshot": {**snapshot, "inspect_feedback": {"passed": False, "overall_score": 0}},
            "detailed_logs": logs,
            # 向后兼容
            "inspect_result": {"passed": False, "overall_score": 0},
        }
    
    # 获取上一轮评分（用于回滚检测）
    last_score = checkpoint.get("best_score", 0)
    
    try:
        # 调用 legacy 接口
        result = inspect_run(
            design_images=design_imgs,
            render_screenshots=render_imgs,
            visual_description=visual_description,
            iteration=iteration,
            inspect_history=state.get("inspect_history", []),
            human_feedback=human_feedback,
            human_iteration_mode=human_iteration_mode,
            pipeline_id=state.get("pipeline_id"),
            return_raw=True,
        )
        
        current_score = result.get("overall_score", 0)
        passed = result.get("passed", False) or current_score >= config.get("passing_threshold", 0.85)
        
        # === Re-decompose 触发检测（优先级最高）===
        # 如果技术方向错误，跳过 rollback（Decompose 会覆盖）
        re_decompose_triggered = should_trigger_re_decompose({**state, "snapshot": {**snapshot, "inspect_feedback": result}})
        result["re_decompose_trigger"] = re_decompose_triggered
        
        # === 物理回滚检测（仅在 Re-decompose 不触发时执行）===
        rollback_triggered = False
        rollback_snapshot = snapshot  # 默认使用当前 snapshot
        
        if re_decompose_triggered:
            # Re-decompose 时跳过 rollback（避免冗余）
            print(f"[Inspect Node] Re-decompose triggered (score {current_score:.2f}), skip rollback")
        else:
            # 正常 rollback 检测
            if current_score < last_score and last_score > 0:
                rollback_triggered = True
                rollback_update = rollback_to_checkpoint({**state, "snapshot": {**snapshot, "inspect_feedback": result}})
                if rollback_update:
                    rollback_snapshot = rollback_update.get("snapshot", snapshot)
                    print(f"[Inspect Node] Score regression: {current_score:.2f} < {last_score:.2f}, rollback triggered")
                    print(f"[Inspect Node] Restored best shader from iteration {checkpoint.get('best_iteration', 0)}")
        
        # 更新 snapshot（使用 rollback 后的 snapshot）
        updated_snapshot = {
            **rollback_snapshot,
            "inspect_feedback": result,
        }
        
        # 更新 checkpoint（如果评分提高）
        checkpoint_update = update_checkpoint({**state, "snapshot": updated_snapshot})
        updated_checkpoint = checkpoint_update.get("checkpoint", checkpoint)
        
        # 更新 gradient_window
        new_gradient_entry: GradientEntry = {
            "iteration": iteration,
            "score": current_score,
            "feedback_summary": result.get("feedback_summary", "")[:100],
            "issues_fixed": None,
            "issues_remaining": result.get("visual_issues"),
            "duration_ms": int((time.time() - phase_start) * 1000),
            "human_iteration": human_iteration_mode,
        }
        updated_gradient_window = update_gradient_window(
            gradient_window, new_gradient_entry, config.get("gradient_window_size", 3)
        )
        
        # Emit completion
        score_info = f"score {current_score:.2f}"
        if last_score > 0:
            score_info += f" (best: {last_score:.2f}, {'↑' if current_score >= last_score else '↓'})"

        # 构建消息和详情
        feedback_parts = [f"Inspection complete: {score_info}, {'PASSED' if passed else 'NEEDS IMPROVEMENT'}"]
        if re_decompose_triggered:
            feedback_parts.append("⚠️ RE-DECOMPOSE TRIGGERED")
        if rollback_triggered:
            feedback_parts.append("↩️ SCORE REGRESSION ROLLBACK")

        details_parts = []
        visual_issues = result.get("visual_issues", [])
        visual_goals = result.get("visual_goals", [])
        correct_aspects = result.get("correct_aspects", [])
        feedback_summary = result.get("feedback_summary", "")

        if visual_issues:
            details_parts.append("[视觉问题]\n" + "\n".join(f"  • {i}" for i in visual_issues))
        if visual_goals:
            details_parts.append("[期望目标]\n" + "\n".join(f"  → {g}" for g in visual_goals))
        if correct_aspects:
            details_parts.append("[保留优点]\n" + "\n".join(f"  ✓ {a}" for a in correct_aspects))
        if feedback_summary:
            details_parts.append(f"[整体反馈]\n{feedback_summary}")

        details_text = "\n\n".join(details_parts) if details_parts else feedback_summary

        logs = _add_phase_log(
            {**state, "detailed_logs": logs},
            "inspect", "completed" if passed else "running",
            "\n".join(feedback_parts),
            details_text,
            start_time=phase_start,
            agent_response=result.get("raw_response"),
            visual_issues=visual_issues,
            visual_goals=visual_goals,
            correct_aspects=correct_aspects,
            re_decompose_triggered=re_decompose_triggered,
            rollback_triggered=rollback_triggered,
        )
        
        # 决定下一阶段
        if re_decompose_triggered:
            next_phase = "decompose"
            next_message = "Re-decompose triggered due to low score or stagnation..."
        elif passed:
            next_phase = "complete"
            next_message = "Pipeline completed successfully"
        else:
            next_phase = "generate"
            next_message = "Preparing next iteration..."
        
        # 更新 inspect_history（向后兼容）
        inspect_history = state.get("inspect_history", [])
        inspect_history.append({
            "iteration": iteration,
            "score": current_score,
            "passed": passed,
            "feedback": result.get("feedback_summary", ""),
            "human_iteration": human_iteration_mode,
        })
        
        return {
            "snapshot": updated_snapshot,
            "checkpoint": updated_checkpoint,
            "gradient_window": updated_gradient_window,
            "current_phase": next_phase,
            "phase_status": "completed" if passed else "running",
            "phase_message": next_message,
            "phase_start_time": time.time() if not passed else None,
            "detailed_logs": logs,
            "passed": passed,
            "inspect_history": inspect_history,
            # 向后兼容
            "current_shader": updated_snapshot.get("shader", ""),
            "iteration": updated_snapshot.get("iteration", iteration),
            "inspect_result": result,
        }
    
    except Exception as e:
        logs = _add_phase_log(
            {**state, "detailed_logs": logs},
            "inspect", "failed",
            f"Inspection failed: {str(e)}",
            start_time=phase_start
        )
        
        return {
            "snapshot": {**snapshot, "inspect_feedback": {"passed": False, "overall_score": 0}},
            "detailed_logs": logs,
            # 向后兼容
            "inspect_result": {"passed": False, "overall_score": 0, "error": str(e)},
        }


# === 路由函数 ===


def route_from_validate(state: PipelineState) -> Literal["generate", "render_and_screenshot", "end"]:
    """Validation node routing"""
    if state.get("error"):
        return "end"
    
    snapshot = state.get("snapshot", {})
    validation_errors = snapshot.get("validation_errors")
    
    # 调试日志
    print(f"[Router] route_from_validate: validation_errors={validation_errors}")
    
    if validation_errors is not None:
        print(f"[Router] Routing to generate (validation_errors={validation_errors})")
        return "generate"
    
    print(f"[Router] Routing to render_and_screenshot (validation_errors=None)")
    return "render_and_screenshot"


def route_from_generate(state: PipelineState) -> Literal["validate_shader", "end"]:
    """Generate node routing"""
    if state.get("error"):
        return "end"
    
    return "validate_shader"


def route_from_render(state: PipelineState) -> Literal["generate", "inspect", "end"]:
    """Render node routing"""
    if state.get("error"):
        return "end"
    
    snapshot = state.get("snapshot", {})
    if snapshot.get("compile_error"):
        return "generate"
    
    return "inspect"


def route_from_inspect(state: PipelineState) -> Literal["generate", "decompose", "end"]:
    """Inspect node routing (新增 decompose 分支)"""
    if state.get("error"):
        return "end"
    
    if state.get("passed", False):
        return "end"
    
    # 检查 re_decompose_trigger
    snapshot = state.get("snapshot", {})
    inspect_feedback = snapshot.get("inspect_feedback", {})
    
    if inspect_feedback.get("re_decompose_trigger"):
        print(f"[Router] Re-decompose branch triggered")
        return "decompose"
    
    # Inspect JSON 解析完全失败
    if inspect_feedback.get("parse_error") and not inspect_feedback.get("raw_response"):
        return "end"
    
    # Text-only mode: end after first iteration (unless human iteration)
    baseline = state.get("baseline", {})
    iteration = snapshot.get("iteration", 0)
    
    if baseline.get("input_type") == "text" and iteration >= 1:
        if state.get("human_iteration_processed") or state.get("human_iteration_mode"):
            return "generate"
        return "end"
    
    # Max iterations
    config = state.get("config", {})
    max_iterations = config.get("max_iterations", get_runtime_config().max_iterations)
    if iteration >= max_iterations:
        return "end"
    
    return "generate"


# === 构建图 ===


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
    
    # generate 条件边
    graph.add_conditional_edges(
        "generate",
        route_from_generate,
        {"validate_shader": "validate_shader", "end": END},
    )
    
    # validate_shader 条件边
    graph.add_conditional_edges(
        "validate_shader",
        route_from_validate,
        {"generate": "generate", "render_and_screenshot": "render_and_screenshot", "end": END},
    )
    
    # render 条件边
    graph.add_conditional_edges(
        "render_and_screenshot",
        route_from_render,
        {"generate": "generate", "inspect": "inspect", "end": END},
    )
    
    # inspect 条件边（新增 decompose 分支）
    graph.add_conditional_edges(
        "inspect",
        route_from_inspect,
        {"generate": "generate", "decompose": "decompose", "end": END},
    )
    
    return graph


# 实例化 pipeline graph
pipeline_app = build_pipeline_graph().compile()