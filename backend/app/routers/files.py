"""Static file serving endpoint.

Allows the frontend to access local files (e.g. rendered screenshots
from the pipeline) via a controlled HTTP endpoint.

Endpoints
---------
GET /file?path=<absolute_path>
    Serve a local file with inferred Content-Type.  Path must be
    inside an allowed root directory.
"""

import mimetypes
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.config import settings

router = APIRouter(tags=["files"])


# ── Path-allowance helpers ────────────────────────────────────────────────


def _build_allowed_roots() -> list[Path]:
    """Return the list of directory roots files may be served from.

    Currently includes:
    * ``settings.workdir_root`` (e.g. ``/tmp/vfx_workdirs``)
    * ``tempfile.gettempdir()`` (on macOS: ``/var/folders/.../T/``)
    * ``/tmp`` as a common Unix temp root (resolves to ``/private/tmp`` on macOS)
    """
    roots: list[Path] = []
    if settings.workdir_root:
        roots.append(Path(settings.workdir_root).resolve())
    roots.append(Path(tempfile.gettempdir()).resolve())
    roots.append(Path("/tmp").resolve())
    return roots


def _is_path_allowed(path: Path, allowed_roots: list[Path]) -> bool:
    """Check that *path* resides under one of the *allowed_roots*.

    Uses ``Path.resolve()`` to resolve symlinks and ``..`` segments
    before checking, preventing directory-traversal attacks.
    """
    resolved = path.resolve()
    for root in allowed_roots:
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            continue
    return False


ALLOWED_ROOTS = _build_allowed_roots()


# ── Endpoint ──────────────────────────────────────────────────────────────


@router.get("/file")
async def get_file(
    path: str = Query(..., description="Absolute path to the file to serve"),
):
    """Serve a local file by absolute path.

    The caller must provide a ``path`` query parameter that is:
    * An absolute filesystem path.
    * Inside one of the allowed root directories (see ``_build_allowed_roots``).
    * A regular file (not a directory).

    Returns a ``FileResponse`` with the inferred ``Content-Type`` header.
    """
    # ── Validate: must be absolute ──
    file_path = Path(path)
    if not file_path.is_absolute():
        raise HTTPException(
            status_code=400,
            detail={"error": "Path must be absolute", "path": path},
        )

    # ── Validate: must be inside an allowed root ──
    if not _is_path_allowed(file_path, ALLOWED_ROOTS):
        raise HTTPException(
            status_code=403,
            detail={"error": "Path not allowed", "path": path},
        )

    # ── Validate: must exist and be a file ──
    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail={"error": "File not found", "path": str(file_path.resolve())},
        )

    if file_path.is_dir():
        raise HTTPException(
            status_code=400,
            detail={"error": "Path is a directory", "path": str(file_path.resolve())},
        )

    # ── Serve ──
    media_type, _ = mimetypes.guess_type(str(file_path))
    return FileResponse(
        path=str(file_path.resolve()),
        media_type=media_type or "application/octet-stream",
    )
