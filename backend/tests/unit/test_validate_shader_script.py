"""Test validate_shader.py CLI script."""
import json
import subprocess
import sys
from pathlib import Path
import pytest

SCRIPT = Path("app/skills/vfx-shader/reference/scripts/validate_shader.py")
VALID_SHADER = """void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    fragColor = vec4(1.0);
}
"""
INVALID_SHADER = "this is not valid glsl"


def run_script(shader_code: str, tmp_path: Path) -> dict:
    shader_file = tmp_path / "test.glsl"
    shader_file.write_text(shader_code)
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(shader_file)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    return json.loads(result.stdout)


def test_validate_valid_shader(tmp_path):
    result = run_script(VALID_SHADER, tmp_path)
    assert result["valid"] is True
    assert isinstance(result["errors"], list)
    assert result["can_attempt_render"] is True


def test_validate_invalid_shader(tmp_path):
    result = run_script(INVALID_SHADER, tmp_path)
    assert result["valid"] is False
    assert len(result["errors"]) > 0


def test_validate_output_has_warnings_field(tmp_path):
    result = run_script(VALID_SHADER, tmp_path)
    assert "warnings" in result
    assert isinstance(result["warnings"], list)
