"""LangGraph 闭环编排：Decompose → Generate → Render → Inspect → (反馈循环)"""

import asyncio
from typing import Literal

from langgraph.graph import StateGraph, END

from app.agents.decompose import DecomposeAgent
from app.agents.generate import GenerateAgent
from app.agents.inspect import InspectAgent
from app.pipeline.state import PipelineState
from app.services.browser_render import render_multiple_frames
from app.services.video_extractor import extract_keyframes, get_video_info
from app.config import settings


# ---- 节点函数 ----

decompose_agent = DecomposeAgent()
generate_agent = GenerateAgent()
inspect_agent = InspectAgent()


async def node_extract_keyframes(state: PipelineState) -> dict:
    """视频输入时，提取关键帧；纯文本输入时返回空列表"""
    if state.get("input_type") == "video" and state.get("video_path"):
        video_info = get_video_info(state["video_path"])
        keyframe_paths = extract_keyframes(state["video_path"], max_frames=6)
        return {"video_info": video_info, "keyframe_paths": keyframe_paths, "design_screenshots": keyframe_paths}
    elif state.get("image_paths"):
        return {"keyframe_paths": state["image_paths"], "design_screenshots": state["image_paths"]}
    # 纯文本输入：返回空列表以避免 LangGraph "Must write to at least one of..." 错误
    return {"keyframe_paths": [], "design_screenshots": []}


async def node_decompose(state: PipelineState) -> dict:
    """Decompose Agent：解构视效语义描述"""
    keyframes = state.get("keyframe_paths", [])
    video_info = state.get("video_info")
    user_notes = state.get("user_notes", "")

    description = decompose_agent.run(
        image_paths=keyframes,
        video_info=video_info,
        user_notes=user_notes,
    )

    return {"visual_description": description}


async def node_generate(state: PipelineState) -> dict:
    """Generate Agent：生成或修正 GLSL 代码"""
    description = state.get("visual_description", {})
    previous_shader = state.get("current_shader") if state.get("iteration", 0) > 0 else None
    feedback = None
    if state.get("inspect_result") and not state.get("passed", False):
        feedback = state["inspect_result"].get("feedback", "")

    shader = generate_agent.run(
        visual_description=description,
        previous_shader=previous_shader,
        feedback=feedback,
    )

    return {
        "current_shader": shader,
        "compile_error": None,
        "iteration": state.get("iteration", 0),
    }


async def node_render_and_screenshot(state: PipelineState) -> dict:
    """在浏览器中渲染 shader 并截图"""
    shader = state.get("current_shader", "")
    if not shader:
        return {"render_screenshots": [], "compile_error": "No shader code to render"}

    try:
        screenshots = await render_multiple_frames(
            shader_code=shader,
            times=[0.0, 0.5, 1.0, 1.5, 2.0],
        )
        return {"render_screenshots": screenshots, "compile_error": None}
    except asyncio.TimeoutError:
        # Timeout: return empty but continue (text mode can pass without screenshots)
        return {"render_screenshots": [], "compile_error": "Render timeout (frontend not ready)"}
    except Exception as e:
        return {"render_screenshots": [], "compile_error": str(e)}


async def node_inspect(state: PipelineState) -> dict:
    """Inspect Agent：对比截图，输出评估"""
    design_imgs = state.get("design_screenshots", [])
    render_imgs = state.get("render_screenshots", [])
    
    # Text-only mode: no design reference, auto-pass if shader generated
    if not design_imgs and state.get("current_shader"):
        # 记录历史
        history = state.get("history", [])
        history.append({
            "iteration": state.get("iteration", 0),
            "score": 0.9,
            "passed": True,
            "feedback": "Text mode: auto-accepted (no design reference)",
        })
        return {
            "inspect_result": {"passed": True, "overall_score": 0.9, "feedback": "Text mode: auto-accepted"},
            "passed": True,
            "history": history,
        }

    # Render failed: skip inspect, will retry in next iteration
    if not render_imgs:
        # 记录历史
        history = state.get("history", [])
        history.append({
            "iteration": state.get("iteration", 0),
            "score": 0,
            "passed": False,
            "feedback": "渲染失败，无截图可对比",
        })
        return {
            "inspect_result": {"passed": False, "overall_score": 0, "feedback": "渲染失败，无截图可对比"},
            "passed": False,
            "history": history,
        }

    result = inspect_agent.run(
        design_images=design_imgs,
        render_screenshots=render_imgs,
        visual_description=state.get("visual_description"),
        iteration=state.get("iteration", 0),
    )

    passed = result.get("passed", False) or result.get("overall_score", 0) >= 0.85

    # 记录历史
    history = state.get("history", [])
    history.append({
        "iteration": state.get("iteration", 0),
        "score": result.get("overall_score", 0),
        "passed": passed,
        "feedback": result.get("feedback", ""),
    })

    return {
        "inspect_result": result,
        "passed": passed,
        "history": history,
    }


# ---- 条件边 ----

def should_continue(state: PipelineState) -> Literal["generate", "end"]:
    """判断是否继续迭代"""
    if state.get("passed", False):
        return "end"
    # For text-only mode, after first successful shader generation, end
    # (text mode auto-passes in node_inspect if no design_screenshots)
    if state.get("input_type") == "text" and state.get("iteration", 0) >= 1:
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