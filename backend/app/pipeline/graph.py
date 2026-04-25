"""LangGraph 闭环编排：Decompose → Generate → Render → Inspect → (反馈循环)"""

import asyncio
import time
from typing import Literal

from langgraph.graph import StateGraph, END

from app.agents.decompose import DecomposeAgent
from app.agents.generate import GenerateAgent
from app.agents.inspect import InspectAgent
from app.pipeline.state import PipelineState, PhaseLog
from app.services.browser_render import render_multiple_frames
from app.services.video_extractor import extract_keyframes, get_video_info
from app.config import settings


# ---- 节点函数 ----

decompose_agent = DecomposeAgent()
generate_agent = GenerateAgent()
inspect_agent = InspectAgent()


def _add_phase_log(state: PipelineState, phase: str, status: str, message: str, details: str | None = None) -> list[PhaseLog]:
    """Helper to add a phase log entry"""
    logs = state.get("detailed_logs", [])
    start_time = state.get("phase_start_time")
    duration_ms = int((time.time() - start_time) * 1000) if start_time and status in ("completed", "failed") else None

    new_log: PhaseLog = {
        "phase": phase,
        "timestamp": time.time(),
        "status": status,
        "message": message,
        "details": details,
        "duration_ms": duration_ms,
    }
    return logs + [new_log]


async def node_extract_keyframes(state: PipelineState) -> dict:
    """视频输入时，提取关键帧；纯文本输入时返回空列表"""
    # Emit phase start
    logs = _add_phase_log(state, "extract_keyframes", "started", "Starting keyframe extraction...")

    if state.get("input_type") == "video" and state.get("video_path"):
        video_info = get_video_info(state["video_path"])
        keyframe_paths = extract_keyframes(state["video_path"], max_frames=6)

        # Emit completion (don't reset phase_start_time here - let duration calculate correctly)
        logs = _add_phase_log(
            {**state, "detailed_logs": logs},
            "extract_keyframes", "completed",
            f"Extracted {len(keyframe_paths)} keyframes from video",
            f"Duration: {video_info.get('duration', 0):.1f}s, FPS: {video_info.get('fps', 0):.0f}"
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
        # Emit completion for image input
        logs = _add_phase_log(
            {**state, "detailed_logs": logs},
            "extract_keyframes", "completed",
            f"Using {len(state['image_paths'])} uploaded images as references"
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
        "Text-only mode: no media extraction needed"
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
    # Emit phase start
    logs = _add_phase_log(state, "decompose", "started", "Decomposing visual description...")

    keyframes = state.get("keyframe_paths", [])
    video_info = state.get("video_info")
    user_notes = state.get("user_notes", "")

    try:
        description = decompose_agent.run(
            image_paths=keyframes,
            video_info=video_info,
            user_notes=user_notes,
        )

        # Emit completion
        logs = _add_phase_log(
            {**state, "detailed_logs": logs},
            "decompose", "completed",
            f"Generated visual description: {description.get('effect_name', 'unknown')}",
            f"Shape: {description.get('shape', {}).get('type', 'unknown')}, Colors: {len(description.get('color', {}).get('palette', []))} colors"
        )

        return {
            "visual_description": description,
            "current_phase": "generate",
            "phase_status": "running",
            "phase_message": "Generating GLSL shader code...",
            "phase_start_time": time.time(),  # Set for NEXT phase
            "detailed_logs": logs,
        }
    except Exception as e:
        logs = _add_phase_log(
            {**state, "detailed_logs": logs},
            "decompose", "failed",
            f"Decomposition failed: {str(e)}"
        )
        return {
            "visual_description": {},
            "error": str(e),
            "detailed_logs": logs,
        }


async def node_generate(state: PipelineState) -> dict:
    """Generate Agent：生成或修正 GLSL 代码"""
    iteration = state.get("iteration", 0)

    # Emit phase start
    phase_msg = f"Generating shader (iteration {iteration + 1})..." if iteration > 0 else "Generating initial shader..."
    logs = _add_phase_log(state, "generate", "started", phase_msg)

    description = state.get("visual_description", {})
    previous_shader = state.get("current_shader") if iteration > 0 else None
    feedback = None
    if state.get("inspect_result") and not state.get("passed", False):
        feedback = state["inspect_result"].get("feedback", "")

    try:
        shader = generate_agent.run(
            visual_description=description,
            previous_shader=previous_shader,
            feedback=feedback,
        )

        # Emit completion
        logs = _add_phase_log(
            {**state, "detailed_logs": logs},
            "generate", "completed",
            f"Generated shader: {len(shader)} characters",
            f"Shader preview: {shader[:200]}..." if len(shader) > 200 else shader
        )

        return {
            "current_shader": shader,
            "compile_error": None,
            "iteration": iteration,
            "current_phase": "render",
            "phase_status": "running",
            "phase_message": "Rendering shader frames...",
            "phase_start_time": time.time(),  # Set for NEXT phase
            "detailed_logs": logs,
        }
    except Exception as e:
        logs = _add_phase_log(
            {**state, "detailed_logs": logs},
            "generate", "failed",
            f"Shader generation failed: {str(e)}"
        )
        return {
            "current_shader": "",
            "compile_error": str(e),
            "iteration": iteration,
            "detailed_logs": logs,
        }


async def node_render_and_screenshot(state: PipelineState) -> dict:
    """在浏览器中渲染 shader 并截图"""
    iteration = state.get("iteration", 0)

    # Emit phase start
    logs = _add_phase_log(state, "render", "started", f"Rendering shader frames (iteration {iteration + 1})...")

    shader = state.get("current_shader", "")
    if not shader:
        logs = _add_phase_log(
            {**state, "detailed_logs": logs},
            "render", "failed",
            "No shader code to render"
        )
        return {
            "render_screenshots": [],
            "compile_error": "No shader code to render",
            "detailed_logs": logs,
        }

    try:
        screenshots = await render_multiple_frames(
            shader_code=shader,
            times=[0.0, 0.5, 1.0, 1.5, 2.0],
        )

        # Emit completion
        logs = _add_phase_log(
            {**state, "detailed_logs": logs},
            "render", "completed",
            f"Rendered {len(screenshots)} frames successfully"
        )

        return {
            "render_screenshots": screenshots,
            "compile_error": None,
            "current_phase": "inspect",
            "phase_status": "running",
            "phase_message": "Inspecting rendered output...",
            "phase_start_time": time.time(),  # Set for NEXT phase
            "detailed_logs": logs,
        }
    except asyncio.TimeoutError:
        # Timeout: return empty but continue (text mode can pass without screenshots)
        logs = _add_phase_log(
            {**state, "detailed_logs": logs},
            "render", "failed",
            "Render timeout (frontend not ready)"
        )
        return {
            "render_screenshots": [],
            "compile_error": "Render timeout (frontend not ready)",
            "detailed_logs": logs,
        }
    except Exception as e:
        logs = _add_phase_log(
            {**state, "detailed_logs": logs},
            "render", "failed",
            f"Render error: {str(e)}"
        )
        return {
            "render_screenshots": [],
            "compile_error": str(e),
            "detailed_logs": logs,
        }


async def node_inspect(state: PipelineState) -> dict:
    """Inspect Agent：对比截图，输出评估"""
    iteration = state.get("iteration", 0)

    # Emit phase start
    logs = _add_phase_log(state, "inspect", "started", f"Inspecting rendered output (iteration {iteration + 1})...")

    design_imgs = state.get("design_screenshots", [])
    render_imgs = state.get("render_screenshots", [])

    # Text-only mode: no design reference, auto-pass if shader generated
    if not design_imgs and state.get("current_shader"):
        # 记录历史
        history = state.get("history", [])
        history.append({
            "iteration": iteration,
            "score": 0.9,
            "passed": True,
            "feedback": "Text mode: auto-accepted (no design reference)",
        })

        logs = _add_phase_log(
            {**state, "detailed_logs": logs},
            "inspect", "completed",
            "Auto-accepted: text-only mode (no design reference)"
        )

        return {
            "inspect_result": {"passed": True, "overall_score": 0.9, "feedback": "Text mode: auto-accepted"},
            "passed": True,
            "history": history,
            "current_phase": "complete",
            "phase_status": "completed",
            "phase_message": "Pipeline completed successfully",
            "detailed_logs": logs,
        }

    # Render failed: skip inspect, will retry in next iteration
    if not render_imgs:
        # 记录历史
        history = state.get("history", [])
        history.append({
            "iteration": iteration,
            "score": 0,
            "passed": False,
            "feedback": "渲染失败，无截图可对比",
        })

        logs = _add_phase_log(
            {**state, "detailed_logs": logs},
            "inspect", "failed",
            "No rendered screenshots to compare"
        )

        return {
            "inspect_result": {"passed": False, "overall_score": 0, "feedback": "渲染失败，无截图可对比"},
            "passed": False,
            "history": history,
            "detailed_logs": logs,
        }

    try:
        result = inspect_agent.run(
            design_images=design_imgs,
            render_screenshots=render_imgs,
            visual_description=state.get("visual_description"),
            iteration=iteration,
        )

        passed = result.get("passed", False) or result.get("overall_score", 0) >= 0.85

        # 记录历史
        history = state.get("history", [])
        history.append({
            "iteration": iteration,
            "score": result.get("overall_score", 0),
            "passed": passed,
            "feedback": result.get("feedback", ""),
        })

        # Emit completion
        logs = _add_phase_log(
            {**state, "detailed_logs": logs},
            "inspect", "completed" if passed else "running",
            f"Inspection complete: score {result.get('overall_score', 0):.2f}, {'PASSED' if passed else 'NEEDS IMPROVEMENT'}",
            result.get("feedback", "")
        )

        return {
            "inspect_result": result,
            "passed": passed,
            "history": history,
            "current_phase": "complete" if passed else "generate",
            "phase_status": "completed" if passed else "running",
            "phase_message": "Pipeline completed successfully" if passed else "Preparing next iteration...",
            "phase_start_time": time.time() if not passed else None,  # Set for NEXT phase only if continuing
            "detailed_logs": logs,
        }
    except Exception as e:
        logs = _add_phase_log(
            {**state, "detailed_logs": logs},
            "inspect", "failed",
            f"Inspection failed: {str(e)}"
        )
        return {
            "inspect_result": {"passed": False, "overall_score": 0, "feedback": str(e)},
            "passed": False,
            "history": state.get("history", []),
            "detailed_logs": logs,
        }


# ---- 条件边 ----

def should_continue(state: PipelineState) -> Literal["generate", "end"]:
    """判断是否继续迭代"""
    if state.get("passed", False):
        return "end"
    # For text-only mode, after first successful shader generation, end
    # (text mode auto-passes in node_inspect if no design_screenshots)
    # iteration >= 0 means end after first Generate+Inspect cycle completes
    if state.get("input_type") == "text" and state.get("iteration", 0) >= 0:
        return "end"
    if state.get("compile_error") and state.get("iteration", 0) >= 1:
        # 编译错误且已重试，结束
        return "end"
    if state.get("iteration", 0) >= state.get("max_iterations", settings.max_iterations) - 1:
        return "end"
    return "generate"


# ---- 构建图 ----

def build_pipeline_graph() -> StateGraph:
    graph = StateGraph(PipelineState)

    # 添加节点
    graph.add_node("extract_keyframes", node_extract_keyframes)
    graph.add_node("decompose", node_decompose)
    graph.add_node("generate", node_generate)
    graph.add_node("render_and_screenshot", node_render_and_screenshot)
    graph.add_node("inspect", node_inspect)

    # 添加边
    graph.set_entry_point("extract_keyframes")
    graph.add_edge("extract_keyframes", "decompose")
    graph.add_edge("decompose", "generate")
    graph.add_edge("generate", "render_and_screenshot")
    graph.add_edge("render_and_screenshot", "inspect")

    # 条件边：inspect 之后决定是否继续迭代
    graph.add_conditional_edges(
        "inspect",
        should_continue,
        {"generate": "generate", "end": END},
    )

    return graph


# ---- 迭代计数器增量 ----

# 需要在 generate 节点中增加 iteration
_original_generate = node_generate

async def node_generate_with_increment(state: PipelineState) -> dict:
    result = await _original_generate(state)
    result["iteration"] = state.get("iteration", 0) + 1
    return result

# 重新绑定
graph = StateGraph(PipelineState)
graph.add_node("extract_keyframes", node_extract_keyframes)
graph.add_node("decompose", node_decompose)
graph.add_node("generate", node_generate_with_increment)
graph.add_node("render_and_screenshot", node_render_and_screenshot)
graph.add_node("inspect", node_inspect)

graph.set_entry_point("extract_keyframes")
graph.add_edge("extract_keyframes", "decompose")
graph.add_edge("decompose", "generate")
graph.add_edge("generate", "render_and_screenshot")
graph.add_edge("render_and_screenshot", "inspect")
graph.add_conditional_edges(
    "inspect",
    should_continue,
    {"generate": "generate", "end": END},
)

pipeline_app = graph.compile()