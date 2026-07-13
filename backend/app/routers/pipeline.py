"""Pipeline 触发与状态查询 API (v2.0 codex OD).

Endpoints
---------
POST /pipeline/run
    Accept uploaded keyframe images + notes, spawn PipelineOrchestrator in
    background, return ``{"pipeline_id": "..."}``.
GET  /pipeline/status/{pipeline_id}
    Return current ``PipelineRecord`` (or ``{"status": "not_found"}``).
POST /pipeline/{pipeline_id}/human-iterate
    Placeholder — returns 501 Not Implemented until Phase D.
"""

import asyncio
import shutil
import time
import uuid
from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from app.config import settings
from app.orchestrator import PipelineOrchestrator
from app.routers.config import get_runtime_config
from app.state_store import StateStore

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.post("/run")
async def run_pipeline(
    notes: str = Form(""),
    images: list[UploadFile] = File(default=[]),
):
    """Spawn a new pipeline run in background.

    Accepts form data with optional ``notes`` (text) and ``images``
    (one or more image files). Returns immediately with a ``pipeline_id``;
    poll ``GET /pipeline/status/{id}`` for progress.
    """
    pipeline_id = f"p{int(time.time())}-{uuid.uuid4().hex[:8]}"

    # Setup workdir
    workdir = Path(settings.workdir_root) / pipeline_id
    workdir.mkdir(parents=True, exist_ok=True)
    keyframes_dir = workdir / "keyframes"
    keyframes_dir.mkdir(exist_ok=True)

    # Save uploaded images as keyframes (with error handling)
    keyframe_paths: list[str] = []
    try:
        for i, img in enumerate(images, start=1):
            suffix = Path(img.filename or "x.png").suffix or ".png"
            kf_path = keyframes_dir / f"{i:03d}{suffix}"
            with kf_path.open("wb") as f:
                shutil.copyfileobj(img.file, f)
            keyframe_paths.append(str(kf_path.resolve()))
    except Exception as e:
        shutil.rmtree(workdir, ignore_errors=True)
        raise HTTPException(
            status_code=400,
            detail=f"image save failed: {type(e).__name__}: {e}",
        )

    runtime_cfg = get_runtime_config()
    max_iterations = runtime_cfg.max_iterations

    # Spawn orchestrator in background (asyncio task, not BackgroundTasks,
    # because the orchestrator is async).
    async def _run():
        orch = PipelineOrchestrator()
        await orch.run(
            pipeline_id=pipeline_id,
            workdir=workdir,
            keyframes=keyframe_paths,
            notes=notes,
            max_iterations=max_iterations,
        )

    asyncio.create_task(_run())

    return {"pipeline_id": pipeline_id}


@router.get("/status/{pipeline_id}")
async def get_status(pipeline_id: str):
    """Return current PipelineRecord (or not_found)."""
    record = StateStore.load(pipeline_id)
    if record is None:
        return {"status": "not_found", "pipeline_id": pipeline_id}
    return asdict(record)


@router.post("/{pipeline_id}/human-iterate")
async def human_iterate(pipeline_id: str):
    """Placeholder — v2.0 human-in-the-loop not implemented yet."""
    raise HTTPException(
        status_code=501,
        detail="human-iterate not implemented in v2.0 yet",
    )
