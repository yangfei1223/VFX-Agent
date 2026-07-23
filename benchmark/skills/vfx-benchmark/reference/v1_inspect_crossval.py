"""A/B cross-validation: run v1.0 InspectAgent on v2.0 outputs.

# NOTE: This script depends on v1.0 InspectAgent which was deleted in Phase E.
# Kept as historical reference for Phase C A/B cross-validation results.

Usage:
    python tests/e2e/v1_inspect_crossval.py <v2_workdir> [--render-name render_iteration3.png]

Reads <v2_workdir>/{keyframes/001.png, visual_description.json, final_shader.glsl, <render_name>},
builds a v1.0-compatible state, runs InspectAgent, prints comparison.
"""
import argparse
import json
import sys
import time
from pathlib import Path

# Setup path so imports from backend/app work
REPO_ROOT = Path(__file__).resolve().parents[4]  # benchmark/skills/vfx-benchmark/reference/X.py → repo root
BACKEND_ROOT = REPO_ROOT / 'backend'
sys.path.insert(0, str(BACKEND_ROOT))

from app.agents.inspect import InspectAgent


def build_state(workdir: Path, render_name: str) -> dict:
    keyframe = workdir / "keyframes" / "001.png"
    render = workdir / render_name
    vd_path = workdir / "visual_description.json"
    shader_path = workdir / "final_shader.glsl"
    eval_path = workdir / "evaluation.json"

    missing = [p for p in [keyframe, render, vd_path, shader_path] if not p.exists()]
    if missing:
        raise FileNotFoundError(
            f"Missing required files in {workdir}:\n  " + "\n  ".join(str(p) for p in missing)
        )

    visual_description = json.loads(vd_path.read_text())
    shader = shader_path.read_text()

    # v2.0 score for comparison
    v2_eval = json.loads(eval_path.read_text()) if eval_path.exists() else {}

    state = {
        "pipeline_id": f"crossval-{workdir.name}",
        "baseline": {"keyframe_paths": [str(keyframe)]},
        "snapshot": {
            "render_screenshots": [str(render)],
            "visual_description": visual_description,
            "shader": shader,
            "iteration": 1,
        },
    }
    return state, v2_eval


def main():
    parser = argparse.ArgumentParser(description="A/B cross-validation with v1.0 InspectAgent")
    parser.add_argument("workdir", help="v2.0 workdir path")
    parser.add_argument("--render-name", default="render_iteration3.png",
                        help="Render screenshot filename (default: render_iteration3.png)")
    args = parser.parse_args()

    workdir = Path(args.workdir)
    if not workdir.is_dir():
        print(f"ERROR: {workdir} is not a directory")
        sys.exit(1)

    state, v2_eval = build_state(workdir, args.render_name)
    v2_score = v2_eval.get("overall_score", 0.0)

    print("=" * 60)
    print("  A/B Cross-Validation: v1.0 InspectAgent vs v2.0 subagent")
    print("=" * 60)
    print(f"  workdir:  {workdir}")
    print(f"  render:   {args.render_name}")
    print(f"  keyframe: {state['baseline']['keyframe_paths'][0]}")
    print(f"  v2.0 score: {v2_score:.3f}")
    print()
    print("  Invoking v1.0 InspectAgent ...")
    sys.stdout.flush()

    t0 = time.time()
    agent = InspectAgent()
    result = agent.run(state, return_raw=True)
    elapsed = time.time() - t0

    v1_score = result.get("overall_score", 0.0)
    delta = abs(v1_score - v2_score)
    objective = delta <= 0.10

    print()
    print("=" * 60)
    print("  A/B RESULT")
    print("=" * 60)
    print(f"  v1.0 InspectAgent score:  {v1_score:.3f}")
    print(f"  v2.0 subagent score:      {v2_score:.3f}")
    print(f"  delta:                    {delta:.3f}  {'(within 0.10)' if objective else '(EXCEEDS 0.10)'}")
    print(f"  elapsed:                  {elapsed:.1f}s")
    print(f"  verdict:                  {'OBJECTIVE ✅' if objective else 'BIAS SUSPECTED ⚠️'}")
    print()
    print("  v1.0 dimension_scores:")
    for dim, data in result.get("dimension_scores", {}).items():
        print(f"    {dim:20s}: {data.get('score', 0):.2f}  {data.get('notes', '')[:60]}")
    print()
    print("  v1.0 visual_issues (first 5):")
    for issue in result.get("visual_issues", [])[:5]:
        print(f"    - {issue}")
    print()
    passed = result.get("passed", False)
    print(f"  passed: {passed}")

    # Save full result
    out_path = workdir / "v1_inspect_crossval.json"
    out_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, default=str)
    )
    print(f"\n  Full result saved: {out_path}")
    print()


if __name__ == "__main__":
    main()
