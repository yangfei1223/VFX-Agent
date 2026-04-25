"""Pipeline 触发与状态查询 API"""

import asyncio
import uuid
from fastapi import APIRouter, UploadFile, File, Form
from pathlib import Path
import shutil

from app.pipeline.graph import pipeline_app
from app.pipeline.state import PipelineState
from app.config import settings

router = APIRouter(prefix="/pipeline", tags=["pipeline"])

# 简单的内存存储（MVP 阶段足够）
pipeline_results: dict[str, dict] = {}


@router.post("/run")
async def run_pipeline(
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
        "input_type": "text" if not video_path and not image_paths else ("video" if video_path else "image"),
        "video_path": video_path,
        "image_paths": image_paths,
        "user_notes": notes,
        "video_info": None,
        "keyframe_paths": [],
        "visual_description": {},
        "iteration": 0,
        "max_iterations": settings.max_iterations,
        "current_shader": "",
        "compile_error": None,
        "inspect_result": None,
        "passed": False,
        "render_screenshots": [],
        "design_screenshots": [],
        "status": "running",
        "error": None,
        "history": [],
    }

    # 异步执行 pipeline
    async def _run():
        try:
            result = await pipeline_app.ainvoke(initial_state)
            result_dict = {k: v for k, v in result.items()}
            # Set final status based on passed flag and iteration count
            if result.get("passed"):
                result_dict["status"] = "passed"
            elif result.get("iteration", 0) >= settings.max_iterations:
                result_dict["status"] = "max_iterations"
            else:
                result_dict["status"] = "failed"
            pipeline_results[pipeline_id] = result_dict
        except Exception as e:
            pipeline_results[pipeline_id] = {"status": "failed", "error": str(e)}

    asyncio.create_task(_run())

    return {"pipeline_id": pipeline_id, "status": "running"}


@router.get("/status/{pipeline_id}")
async def get_pipeline_status(pipeline_id: str):
    """查询 Pipeline 执行状态"""
    result = pipeline_results.get(pipeline_id)
    if not result:
        return {"status": "not_found"}
    return result