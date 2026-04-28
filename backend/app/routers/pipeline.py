"""Pipeline 触发与状态查询 API"""

import asyncio
import time
import uuid
from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks
from pathlib import Path
import shutil

from app.pipeline.graph import pipeline_app
from app.pipeline.state import PipelineState
from app.config import settings
from app.routers.config import get_runtime_config

router = APIRouter(prefix="/pipeline", tags=["pipeline"])

# 简单的内存存储（MVP 阶段足够）
pipeline_results: dict[str, dict] = {}


def _run_pipeline(pipeline_id: str, initial_state: PipelineState):
    """同步执行 pipeline（在后台线程中运行）"""
    try:
        # 从 pipeline_results 获取最新状态（human-iterate 可能已更新）
        current_state = pipeline_results.get(pipeline_id, initial_state)
        
        # Debug: 检查 human_iteration_mode 是否正确传入
        print(f"[Pipeline {pipeline_id}] Starting execution...")
        print(f"[Pipeline {pipeline_id}] human_iteration_mode: {current_state.get('human_iteration_mode')}")
        human_fb = current_state.get('human_feedback') or 'N/A'
        print(f"[Pipeline {pipeline_id}] human_feedback: {human_fb[:50]}")
        
        # 使用 asyncio.run 在后台线程中执行
        async def _async_run():
            nonlocal current_state  # 允许在闭包内修改外部变量
            # 设置 recursion_limit=200（每次迭代约4步，max_iterations=100可能需要400步）
            config = {"recursion_limit": 200}
            async for event in pipeline_app.astream(current_state, config=config, stream_mode="updates"):
                for node_name, node_output in event.items():
                    if node_output:
                        print(f"[Pipeline {pipeline_id}] Node {node_name} completed")
                        current_state = {**current_state, **node_output}
                        result_dict = {k: v for k, v in current_state.items()}
                        result_dict["status"] = "running"
                        pipeline_results[pipeline_id] = result_dict
            
            print(f"[Pipeline {pipeline_id}] All nodes completed")
            
            result_dict = {k: v for k, v in current_state.items()}
            if current_state.get("passed"):
                result_dict["status"] = "passed"
            elif current_state.get("iteration", 0) >= get_runtime_config().max_iterations:
                result_dict["status"] = "max_iterations"
            elif current_state.get("error"):
                result_dict["status"] = "failed"
            else:
                result_dict["status"] = "completed"
            
            print(f"[Pipeline {pipeline_id}] Final status: {result_dict['status']}")
            pipeline_results[pipeline_id] = result_dict
        
        asyncio.run(_async_run())
        
    except Exception as e:
        print(f"[Pipeline {pipeline_id}] FAILED: {e}")
        import traceback
        traceback.print_exc()
        pipeline_results[pipeline_id] = {"status": "failed", "error": str(e)}


@router.post("/run")
async def run_pipeline(
    background_tasks: BackgroundTasks,
    video: UploadFile | None = File(None),
    images: list[UploadFile] = File([]),
    notes: str = Form(""),
):
    """触发 Pipeline 执行"""
    pipeline_id = str(uuid.uuid4())
    upload_dir = Path(f"/tmp/vfx_uploads/{pipeline_id}")
    upload_dir.mkdir(parents=True, exist_ok=True)

    # 保存上传文件
    video_path = None
    image_paths = []

    if video:
        video_path = str(upload_dir / video.filename)
        with open(video_path, "wb") as f:
            shutil.copyfileobj(video.file, f)

    for img in images:
        img_path = str(upload_dir / img.filename)
        with open(img_path, "wb") as f:
            shutil.copyfileobj(img.file, f)
        image_paths.append(img_path)

    # 构建初始状态
    initial_state: PipelineState = {
        "pipeline_id": pipeline_id,  # Track pipeline ID in state
        "input_type": "text" if not video_path and not image_paths else ("video" if video_path else "image"),
        "video_path": video_path,
        "image_paths": image_paths,
        "user_notes": notes,
        "video_info": None,
        "keyframe_paths": [],
        "visual_description": {},
        "iteration": 0,
        "max_iterations": get_runtime_config().max_iterations,
        "current_shader": "",
        "compile_error": None,
        "validation_errors": None,
        "validation_warnings": None,
        "compile_retry_count": 0,  # Deprecated: only for logging
        "human_feedback": None,
        "human_modified_shader": None,
        "human_iteration_mode": False,
        "human_iteration_count": 0,
        "inspect_result": None,
        "passed": False,
        "render_screenshots": [],
        "design_screenshots": [],
        "status": "running",
        "error": None,
        "history": [],
        "generate_history": [],
        "inspect_history": [],
        "current_phase": "extract_keyframes",
        "phase_status": "running",
        "phase_message": "Initializing pipeline...",
        "phase_start_time": time.time(),
        "detailed_logs": [],
    }

    # 立即写入初始状态，避免 "not_found"
    pipeline_results[pipeline_id] = {k: v for k, v in initial_state.items()}
    pipeline_results[pipeline_id]["status"] = "running"

    # 使用 BackgroundTasks 在后台执行 pipeline
    background_tasks.add_task(_run_pipeline, pipeline_id, initial_state)

    return {"pipeline_id": pipeline_id, "status": "running"}


@router.get("/status/{pipeline_id}")
async def get_pipeline_status(pipeline_id: str):
    """查询 Pipeline 执行状态"""
    result = pipeline_results.get(pipeline_id)
    if not result:
        return {"status": "not_found"}
    return result


@router.post("/{pipeline_id}/human-iterate")
async def human_iterate(
    pipeline_id: str,
    background_tasks: BackgroundTasks,
    feedback: str = Form(...),
    modified_shader: str | None = Form(None),
):
    """
    触发人工迭代。
    
    Args:
        feedback: 用户自然语言反馈
        modified_shader: 用户修改的代码（可选）
    
    Returns:
        Pipeline status
    """
    # 1. 检查 pipeline 是否存在且已结束
    if pipeline_id not in pipeline_results:
        return {"error": "Pipeline not found", "status": "not_found"}
    
    current_state = pipeline_results[pipeline_id]
    if current_state.get("status") == "running":
        return {"error": "Pipeline still running", "status": "error"}
    
    # 2. 更新状态
    current_state["human_feedback"] = feedback
    current_state["human_modified_shader"] = modified_shader
    current_state["human_iteration_mode"] = True
    current_state["human_iteration_count"] = current_state.get("human_iteration_count", 0) + 1
    current_state["status"] = "running"
    current_state["phase_status"] = "running"
    
    print(f"[Human Iterate {pipeline_id}] State updated:")
    print(f"  human_iteration_mode: {current_state.get('human_iteration_mode')}")
    print(f"  human_iteration_count: {current_state.get('human_iteration_count')}")
    print(f"  human_feedback: {(feedback or 'N/A')[:50]}...")
    print(f"  modified_shader: {modified_shader[:50] if modified_shader else 'None'}...")
    
    # 3. 决定起始节点
    if modified_shader and modified_shader.strip():
        current_state["current_shader"] = modified_shader
        current_state["current_phase"] = "render"
        current_state["phase_message"] = "Rendering user-modified shader..."
    else:
        current_state["current_phase"] = "generate"
        current_state["phase_message"] = "Generating with human feedback..."
    
    # 4. 清除之前的错误状态
    current_state["compile_error"] = None
    current_state["validation_errors"] = None
    current_state["passed"] = False
    current_state["error"] = None
    
    # 5. 启动 Pipeline（后台任务）
    background_tasks.add_task(_run_pipeline, pipeline_id, current_state)
    
    return {
        "status": "running",
        "pipeline_id": pipeline_id,
        "human_iteration_count": current_state["human_iteration_count"],
        "message": "Human iteration triggered",
    }