"""Test analyze_pixels.py CLI script."""
import json
import subprocess
import sys
from pathlib import Path
from PIL import Image
import pytest

SCRIPT = Path("app/skills/vfx-shader/reference/scripts/analyze_pixels.py")


def make_solid_image(path: Path, rgb: tuple):
    img = Image.new("RGB", (100, 100), rgb)
    img.save(path)


def run_script(ref: Path, render: Path) -> dict:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(ref), str(render)],
        capture_output=True, text=True, cwd=".", timeout=10,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    return json.loads(result.stdout)


def test_identical_images_zero_diff(tmp_path):
    ref = tmp_path / "ref.png"
    render = tmp_path / "render.png"
    make_solid_image(ref, (128, 128, 128))
    make_solid_image(render, (128, 128, 128))
    
    result = run_script(ref, render)
    
    assert result["avg_color_distance"] == 0.0
    for pos in ["tl", "tr", "bl", "br", "center"]:
        assert pos in result
        assert result[pos]["diff"] == 0.0


def test_different_images_nonzero_diff(tmp_path):
    ref = tmp_path / "ref.png"
    render = tmp_path / "render.png"
    make_solid_image(ref, (0, 0, 0))
    make_solid_image(render, (255, 255, 255))
    
    result = run_script(ref, render)
    
    assert result["avg_color_distance"] == 255.0
    assert result["tl"]["reference"] == [0, 0, 0]
    assert result["tl"]["render"] == [255, 255, 255]


def test_different_sizes_resizes_render(tmp_path):
    ref = tmp_path / "ref.png"
    render = tmp_path / "render.png"
    Image.new("RGB", (200, 200), (100, 100, 100)).save(ref)
    Image.new("RGB", (100, 100), (100, 100, 100)).save(render)
    
    result = run_script(ref, render)
    assert result["avg_color_distance"] == 0.0
