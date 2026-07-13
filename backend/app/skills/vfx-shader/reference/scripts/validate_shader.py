#!/usr/bin/env python3
"""Validate GLSL shader code for Shadertoy compatibility.

Usage: validate_shader.py <shader_file>
Output: JSON to stdout

Used by codex as skill reference script (Bash invocation).
Wraps v1.0 backend/app/services/shader_validator.py.
"""
import sys
import json
from pathlib import Path


def _find_backend_root() -> Path:
    """Walk up from this file to find backend/ directory.

    validate_shader.py 位于 backend/app/skills/vfx-shader/reference/scripts/
    """
    p = Path(__file__).resolve()
    while p.name != "backend" and p != p.parent:
        p = p.parent
    if p.name != "backend":
        raise RuntimeError("Could not find backend/ root")
    return p


BACKEND_ROOT = _find_backend_root()
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.shader_validator import validate_shader


def main():
    if len(sys.argv) < 2:
        print(json.dumps({
            "valid": False,
            "errors": ["Missing shader_file argument"],
            "warnings": [],
            "can_attempt_render": False,
        }))
        sys.exit(1)

    shader_file = Path(sys.argv[1])
    if not shader_file.exists():
        print(json.dumps({
            "valid": False,
            "errors": [f"File not found: {shader_file}"],
            "warnings": [],
            "can_attempt_render": False,
        }))
        sys.exit(1)

    shader_code = shader_file.read_text()
    result = validate_shader(shader_code)

    output = {
        "valid": result["valid"],
        "errors": result.get("errors", []),
        "warnings": result.get("warnings", []),
        "can_attempt_render": result.get("can_attempt_render", result["valid"]),
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
