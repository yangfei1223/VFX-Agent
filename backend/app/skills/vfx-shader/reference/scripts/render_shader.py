#!/usr/bin/env python3
"""Render GLSL shader at given time. Returns absolute screenshot path.

Usage: render_shader.py <shader_file> [time_seconds]
Output: JSON to stdout

Used by codex as skill reference script (Bash invocation).
Wraps v1.0 backend/app/services/browser_render.py.
"""
import sys
import json
import asyncio
from pathlib import Path


def _find_backend_root() -> Path:
    """Walk up from this file to find backend/ directory.

    render_shader.py 位于 backend/app/skills/vfx-shader/reference/scripts/
    """
    p = Path(__file__).resolve()
    while p.name != "backend" and p != p.parent:
        p = p.parent
    if p.name != "backend":
        raise RuntimeError("Could not find backend/ root")
    return p


BACKEND_ROOT = _find_backend_root()
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.browser_render import render_and_screenshot


def main():
    if len(sys.argv) < 2:
        print(json.dumps({
            "screenshot_path": "",
            "success": False,
            "error": "Missing shader_file argument",
        }))
        sys.exit(1)

    shader_file = Path(sys.argv[1])
    if not shader_file.exists():
        print(json.dumps({
            "screenshot_path": "",
            "success": False,
            "error": f"File not found: {shader_file}",
        }))
        sys.exit(1)

    time_seconds = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0

    try:
        shader_code = shader_file.read_text()
        path = asyncio.run(render_and_screenshot(shader_code, time_seconds=time_seconds))
        print(json.dumps({
            "screenshot_path": str(Path(path).resolve()) if path else "",
            "success": True,
            "error": None,
        }))
    except Exception as e:
        print(json.dumps({
            "screenshot_path": "",
            "success": False,
            "error": f"{type(e).__name__}: {e}",
        }))


if __name__ == "__main__":
    main()
