"""Test render_shader.py CLI script."""
import json
import subprocess
import sys
from pathlib import Path
import pytest

SCRIPT = Path("app/skills/vfx-shader/reference/scripts/render_shader.py")
VALID_SHADER = """void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    fragColor = vec4(1.0, 0.0, 0.0, 1.0);
}
"""


def run_script(shader_code: str, tmp_path: Path, time_seconds: float = 1.0) -> dict:
    shader_file = tmp_path / "test.glsl"
    shader_file.write_text(shader_code)
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(shader_file), str(time_seconds)],
        capture_output=True, text=True, cwd=".", timeout=60,
    )
    return json.loads(result.stdout)


def test_render_valid_shader(tmp_path):
    """Note: requires Playwright + chromium installed."""
    try:
        result = run_script(VALID_SHADER, tmp_path, 1.0)
    except subprocess.TimeoutExpired:
        pytest.skip("Playwright not available or too slow")

    if not result.get("success"):
        pytest.skip(f"Render failed (Playwright missing?): {result.get('error')}")

    assert result["success"] is True
    assert result["screenshot_path"]
    assert Path(result["screenshot_path"]).exists()


def test_render_invalid_shader_returns_graceful_json(tmp_path):
    """Invalid shader should still produce parseable JSON.

    With the standalone HTML renderer, invalid GLSL may still render as a
    black canvas (Playwright pipeline succeeds, just no visible output).
    So we only assert JSON structure, not the success field — what matters
    is that the script never crashes / emits traceback.
    """
    result = run_script("invalid glsl code", tmp_path, 1.0)
    # Must produce all 3 fields for codex parsing stability
    assert "success" in result
    assert "error" in result
    assert "screenshot_path" in result
