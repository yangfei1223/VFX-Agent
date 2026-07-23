#!/usr/bin/env python3
"""Re-render final shader for each sample, save to workdir/render_final.png.

Usage: python benchmark/skills/vfx-benchmark/reference/rerender_samples.py
"""
import asyncio
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]  # benchmark/skills/vfx-benchmark/reference/X.py → repo root
BACKEND_ROOT = REPO_ROOT / 'backend'
sys.path.insert(0, str(BACKEND_ROOT))

SCRIPT = BACKEND_ROOT / "app" / "skills" / "vfx-shader" / "reference" / "scripts" / "render_shader.py"
RUNS_ROOT = Path("/tmp/vfx_v2_runs")


async def rerender_one(sample_dir: Path) -> tuple[str, str | None]:
    """Returns (sample_name, screenshot_path_or_None)."""
    name = sample_dir.name
    shader_path = sample_dir / "final_shader.glsl"
    if not shader_path.exists():
        shader_path = sample_dir / "shader.glsl"
    if not shader_path.exists():
        return name, None

    # Read visual_description to determine if animated
    vd_path = sample_dir / "visual_description.json"
    time_seconds = 1.0
    if vd_path.exists():
        try:
            vd = json.loads(vd_path.read_text())
            anim = (vd.get("animation_definition") or {})
            if anim.get("anim_token", "").endswith(".static") or "static" in (anim.get("description") or "").lower():
                time_seconds = 1.0
            else:
                time_seconds = 2.0
        except Exception:
            pass

    # Run render_shader.py
    result = subprocess.run(
        ["python", str(SCRIPT), str(shader_path), str(time_seconds)],
        capture_output=True, text=True, cwd=str(BACKEND_ROOT), timeout=60,
    )
    if result.returncode != 0:
        print(f"  [{name}] render failed: {result.stderr[:200]}", file=sys.stderr)
        return name, None

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"  [{name}] bad JSON: {result.stdout[:200]}", file=sys.stderr)
        return name, None

    if not data.get("success"):
        print(f"  [{name}] render unsuccessful: {data.get('error', '?')[:200]}", file=sys.stderr)
        return name, None

    src = Path(data["screenshot_path"])
    if not src.exists():
        return name, None

    # Copy to workdir as render_final.png
    dest = sample_dir / "render_final.png"
    dest.write_bytes(src.read_bytes())
    return name, str(dest)


async def main():
    if not RUNS_ROOT.exists():
        print(f"Runs root not found: {RUNS_ROOT}", file=sys.stderr)
        sys.exit(1)

    samples = sorted([d for d in RUNS_ROOT.iterdir() if d.is_dir()])
    print(f"[rerender] Found {len(samples)} sample dirs")

    success = 0
    failed = 0
    for s in samples:
        name, path = await rerender_one(s)
        if path:
            print(f"  ✅ {name} → {path}")
            success += 1
        else:
            print(f"  ❌ {name}")
            failed += 1

    print(f"\n[rerender] Done: {success} success, {failed} failed")


if __name__ == "__main__":
    asyncio.run(main())
