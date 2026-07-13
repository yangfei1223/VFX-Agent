"""Collect v2.0 run results + v1.0 baselines into a single JSON for report generator.

Usage:
    python tests/e2e/collect_v2_results.py [--runs-dir /tmp/vfx_v2_runs] [--output /tmp/v2_report_data.json]
"""
import argparse
import base64
import json
import sys
from pathlib import Path

# v1.0 V2 baseline (from AGENTS.md, 2026-05-18)
V1_BASELINES = {
    "4-col-grad": {"score": 0.95, "status": "passed", "shader_lines": 19, "effect_type": "{effect.gradient}"},
    "shiny-circle": {"score": 0.88, "status": "passed", "shader_lines": 72, "effect_type": "{effect.glow}"},
    "twitter-blue-check": {"score": 0.87, "status": "passed", "shader_lines": 83, "effect_type": "{effect.shape}"},
    "water-color-blending": {"score": 0.86, "status": "passed", "shader_lines": 80, "effect_type": "{effect.flow}"},
    "hypnotic-ripples": {"score": 0.86, "status": "passed", "shader_lines": 56, "effect_type": "{effect.ripple}"},
    "plasma-waves": {"score": 0.83, "status": "acceptable", "shader_lines": 66, "effect_type": "{effect.flow}"},
    "supah-frosted-glass": {"score": 0.82, "status": "acceptable", "shader_lines": 66, "effect_type": "{effect.frosted}"},
    "vortex-street": {"score": 0.81, "status": "acceptable", "shader_lines": 109, "effect_type": "{effect.warp}"},
    "warp-speed2": {"score": 0.81, "status": "acceptable", "shader_lines": 112, "effect_type": "{effect.particle}"},
    "buffer-bloom": {"score": 0.74, "status": "failed", "shader_lines": 96, "effect_type": "{effect.glow}"},
    "happy-diwali-2019": {"score": 0.78, "status": "failed", "shader_lines": 112, "effect_type": "{effect.particle}"},
    "heart-2d": {"score": 0.78, "status": "failed", "shader_lines": 68, "effect_type": "{effect.shape}"},
    "moon-distance-2d": {"score": 0.72, "status": "failed", "shader_lines": 106, "effect_type": "{effect.warp}"},
    "liquid-glass-ui": {"score": 0.73, "status": "failed", "shader_lines": 155, "effect_type": "{effect.liquid}"},
    "electron": {"score": 0.68, "status": "failed", "shader_lines": 145, "effect_type": "{effect.particle}"},
    "liquid-galss-test": {"score": 0.52, "status": "failed", "shader_lines": 106, "effect_type": "{effect.liquid}"},
    "cool-s-distance": {"score": 0.52, "status": "failed", "shader_lines": 109, "effect_type": "{effect.warp}"},
    "auroras": {"score": 0.42, "status": "failed", "shader_lines": 121, "effect_type": "{effect.flow}"},
    "sparks-drifting": {"score": 0.00, "status": "timeout", "shader_lines": 0, "effect_type": "{effect.particle}"},
}

# Effect category metadata
EFFECT_META = {
    "{effect.gradient}": {"name": "Gradient", "difficulty": "simple"},
    "{effect.glow}": {"name": "Glow", "difficulty": "simple"},
    "{effect.shape}": {"name": "Solid Shape", "difficulty": "simple"},
    "{effect.ripple}": {"name": "Ripple", "difficulty": "simple"},
    "{effect.frosted}": {"name": "Frosted Glass", "difficulty": "simple"},
    "{effect.flow}": {"name": "Flow", "difficulty": "medium"},
    "{effect.particle}": {"name": "Particle", "difficulty": "complex"},
    "{effect.liquid}": {"name": "Liquid Glass", "difficulty": "medium"},
    "{effect.warp}": {"name": "Domain Warp", "difficulty": "medium"},
}


def encode_image_b64(path: Path) -> str | None:
    if not path.exists():
        return None
    return f"data:image/png;base64,{base64.b64encode(path.read_bytes()).decode()}"


def collect_sample(runs_root: Path, sample_name: str) -> dict:
    """Collect v2.0 run data for one sample."""
    # Try v2.0 workdirs (3 different locations used during dev)
    candidates = [
        runs_root / sample_name,                   # /tmp/vfx_v2_runs/<sample>
        Path("/tmp/vfx_" + sample_name),           # /tmp/vfx_heart-2d etc (early MVP)
    ]
    workdir = next((c for c in candidates if c.exists() and (c / "shader.glsl").exists()), None)

    entry = {
        "sample_name": sample_name,
        "v1_baseline": V1_BASELINES.get(sample_name, {"score": -1, "status": "unknown"}),
        "v2": {"present": False, "status": "missing", "score": 0.0, "duration_s": 0, "shader_lines": 0},
        "images": {"reference": None, "render": None},
        "visual_description": None,
        "evaluation": None,
        "shader_code": None,
    }

    if workdir is None:
        return entry

    entry["v2"]["present"] = True
    entry["v2"]["workdir"] = str(workdir)

    # Find reference image
    kf_dir = workdir / "keyframes"
    if kf_dir.exists():
        kfs = sorted(kf_dir.glob("*.png"))
        if kfs:
            entry["images"]["reference"] = encode_image_b64(kfs[0])

    # Find render image (prefer final render_iterN.png, fallback to screenshot_path)
    render_candidates = sorted(workdir.glob("render_iter*.png"), reverse=True)
    if not render_candidates:
        render_candidates = sorted(workdir.glob("render_iteration*.png"), reverse=True)
    if render_candidates:
        entry["images"]["render"] = encode_image_b64(render_candidates[0])

    # Read visual_description.json
    vd_path = workdir / "visual_description.json"
    if vd_path.exists():
        entry["visual_description"] = json.loads(vd_path.read_text())

    # Read evaluation.json (v2.0 subagent output)
    eval_path = workdir / "evaluation.json"
    if eval_path.exists():
        ev = json.loads(eval_path.read_text())
        entry["evaluation"] = ev
        entry["v2"]["score"] = ev.get("overall_score", 0.0)
        entry["v2"]["status"] = "passed" if ev.get("passed") else (
            "timeout" if ev.get("_timeout_flag") else "max_iterations"
        )

    # Read shader
    shader_path = workdir / "final_shader.glsl"
    if not shader_path.exists():
        shader_path = workdir / "shader.glsl"
    if shader_path.exists():
        code = shader_path.read_text()
        entry["shader_code"] = code
        entry["v2"]["shader_lines"] = len(code.splitlines())

    # Duration from state file if available
    return entry


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs-dir", default="/tmp/vfx_v2_runs",
                        help="Root dir of v2.0 sample workdirs")
    parser.add_argument("--output", default="/tmp/v2_report_data.json",
                        help="Output JSON path")
    args = parser.parse_args()

    runs_root = Path(args.runs_dir)
    samples = sorted(V1_BASELINES.keys())

    results = []
    for s in samples:
        print(f"[collect] {s}...", file=sys.stderr)
        results.append(collect_sample(runs_root, s))

    # Aggregate stats
    present = [r for r in results if r["v2"]["present"]]
    passed = [r for r in present if r["v2"]["status"] == "passed"]
    v2_scores = [r["v2"]["score"] for r in present]
    v1_scores = [r["v1_baseline"]["score"] for r in present if r["v1_baseline"]["score"] >= 0]

    summary = {
        "total_samples": len(samples),
        "present": len(present),
        "passed": len(passed),
        "v2_avg_score": sum(v2_scores) / len(v2_scores) if v2_scores else 0,
        "v1_avg_score": sum(v1_scores) / len(v1_scores) if v1_scores else 0,
        "delta_avg": (sum(v2_scores) / len(v2_scores) - sum(v1_scores) / len(v1_scores))
                     if v2_scores and v1_scores else 0,
    }
    print(f"[collect] summary: {summary}", file=sys.stderr)

    out = {
        "generated_at": str(Path().resolve()),
        "summary": summary,
        "samples": results,
    }
    Path(args.output).write_text(json.dumps(out, indent=2, default=str))
    print(f"[collect] Wrote {args.output} ({len(results)} samples, {len(present)} present)")


if __name__ == "__main__":
    main()
