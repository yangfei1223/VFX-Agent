"""Run multiple v2.0 samples sequentially via orchestrator.

Usage:
    python tests/e2e/run_v2_samples.py <sample1> [sample2] ...
"""
import argparse
import asyncio
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_ROOT))

from app.orchestrator import PipelineOrchestrator
from app.state_store import StateStore

REPO_ROOT = BACKEND_ROOT.parent
TEST_SAMPLES = REPO_ROOT / "test-samples" / "data"
WORKDIR_ROOT = Path("/tmp/vfx_v2_runs")


def extract_keyframe(sample: str, workdir: Path) -> Path | None:
    """Extract first keyframe from sample webm."""
    webm = TEST_SAMPLES / f"{sample}.webm"
    if not webm.exists():
        print(f"[runner] WARN: {webm} not found")
        return None
    keyframes_dir = workdir / "keyframes"
    keyframes_dir.mkdir(parents=True, exist_ok=True)
    kf = keyframes_dir / "001.png"
    result = subprocess.run(
        ["ffmpeg", "-i", str(webm), "-vframes", "1", "-q:v", "2", "-update", "1",
         str(kf), "-y"],
        capture_output=True
    )
    if result.returncode != 0 or not kf.exists():
        print(f"[runner] ffmpeg failed: {result.stderr.decode()[-300:]}")
        return None
    return kf


def load_sample_notes(sample: str) -> str:
    """Get visual_description from sample json as user notes."""
    j = TEST_SAMPLES / f"{sample}.json"
    if not j.exists():
        return ""
    data = json.loads(j.read_text())
    parts = [data.get("visual_description", "")]
    if data.get("effect_name"):
        parts.append(f"Effect type: {data['effect_name']}")
    if data.get("dominant_colors"):
        parts.append(f"Dominant colors: {', '.join(data['dominant_colors'])}")
    return "\n".join(p for p in parts if p)


async def run_sample(sample: str) -> dict:
    """Run one sample through v2.0 orchestrator."""
    workdir = WORKDIR_ROOT / sample
    # Clean previous run
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True)

    print(f"\n[runner] === {sample} ===")
    kf = extract_keyframe(sample, workdir)
    if kf is None:
        return {"sample": sample, "status": "failed", "error": "keyframe extraction failed"}

    notes = load_sample_notes(sample)
    print(f"[runner] notes: {notes[:100]}...")

    orch = PipelineOrchestrator()
    start = time.time()
    record = await orch.run(
        pipeline_id=f"v2-{sample}-{int(start)}",
        workdir=str(workdir),
        keyframes=[str(kf)],
        notes=notes,
        max_iterations=3,
    )
    elapsed = time.time() - start

    result = {
        "sample": sample,
        "status": record.status,
        "final_score": record.final_score,
        "duration_s": round(elapsed, 1),
        "error": record.error,
        "v1_baseline_score": _v1_baseline(sample),
    }
    print(f"[runner] {sample}: status={record.status} score={record.final_score} elapsed={elapsed:.1f}s")
    return result


def _v1_baseline(sample: str) -> float:
    """Lookup v1.0 baseline score for comparison."""
    baselines = {
        "heart-2d": 0.78, "4-col-grad": 0.95, "shiny-circle": 0.88,
        "twitter-blue-check": 0.87, "water-color-blending": 0.86,
        "hypnotic-ripples": 0.86, "plasma-waves": 0.83,
        "supah-frosted-glass": 0.82, "vortex-street": 0.81,
        "warp-speed2": 0.81, "buffer-bloom": 0.74,
        "happy-diwali-2019": 0.78, "moon-distance-2d": 0.72,
        "liquid-glass-ui": 0.73, "electron": 0.68,
        "liquid-galss-test": 0.52, "cool-s-distance": 0.52,
        "auroras": 0.42, "sparks-drifting": 0.00,
    }
    return baselines.get(sample, -1)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("samples", nargs="+", help="Sample names (e.g. heart-2d 4-col-grad)")
    args = parser.parse_args()

    WORKDIR_ROOT.mkdir(parents=True, exist_ok=True)

    results = []
    for sample in args.samples:
        try:
            r = await run_sample(sample)
        except Exception as e:
            r = {"sample": sample, "status": "exception", "error": f"{type(e).__name__}: {e}"}
        results.append(r)

    # Summary
    print(f"\n[runner] ===== SUMMARY =====")
    print(f"{'Sample':<25} {'v2 Status':<15} {'v2 Score':<10} {'v1 Baseline':<12} {'Delta':<8}")
    print("-" * 75)
    for r in results:
        v2 = r.get("final_score", 0)
        v1 = r.get("v1_baseline_score", -1)
        delta = f"{v2 - v1:+.2f}" if v1 >= 0 else "?"
        print(f"{r['sample']:<25} {r['status']:<15} {v2:<10.3f} {v1:<12} {delta:<8}")
    print(f"\n[runner] Total samples: {len(results)}")
    passed = sum(1 for r in results if r["status"] == "passed")
    print(f"[runner] Passed: {passed}/{len(results)}")

    # Save summary
    out_path = WORKDIR_ROOT / "summary.json"
    out_path.write_text(json.dumps(results, indent=2, default=str))
    print(f"[runner] Summary saved: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
