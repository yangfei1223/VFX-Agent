#!/usr/bin/env python3
"""VFX-Agent E2E Batch Test Runner

Runs pipeline for each selected sample, collects results with checkpoint/resume support.

Usage:
    python test_e2e_batch.py                    # Run all 20 selected samples
    python test_e2e_batch.py --all              # Run all 50 samples
    python test_e2e_batch.py --samples heart-2d  # Run specific samples
    python test_e2e_batch.py --report-only      # Just generate report from existing results
"""

import json
import os
import re
import subprocess
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime

import httpx

# === Config ===
BACKEND_URL = "http://localhost:8000"
SAMPLES_DIR = Path(__file__).parent.parent / "test-samples"
RESULTS_DIR = Path(__file__).parent / "test_e2e_results"
CLASSIFICATIONS_FILE = RESULTS_DIR / "sample_classifications.json"
RESULTS_FILE = RESULTS_DIR / "test_results.json"

MAX_ITERATIONS = 3
PASSING_THRESHOLD = 0.7
POLL_INTERVAL = 3  # seconds
POLL_TIMEOUT = 360  # seconds per sample (6 min)
FRAMES_DIR = Path("/tmp/vfx-frames")

# 20 representative samples (from multimodal classification)
SELECTED_SAMPLES = [
    # C1: Glow (3) - largest category
    "buffer-bloom", "shiny-circle", "plasma-waves",
    # C2: Liquid (3)
    "vortex-street", "liquid-galss-test", "water-color-blending",
    # C3: Particle (3)
    "sparks-drifting", "happy-diwali-2019", "electron",
    # C4: Shape (2)
    "heart-2d", "twitter-blue-check",
    # C5: Space (2)
    "auroras", "warp-speed2",
    # C6: Gradient (2)
    "4-col-grad", "supah-frosted-glass",
    # C7: Warp (2)
    "cool-s-distance", "moon-distance-2d",
    # C8: Ripple (1)
    "hypnotic-ripples",
    # C9: Special (1)
    "liquid-glass-ui",
]


def load_results() -> dict:
    if RESULTS_FILE.exists():
        return json.loads(RESULTS_FILE.read_text())
    return {}


def save_results(data: dict):
    RESULTS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def extract_reference_frame(video_path: Path, output_dir: Path) -> str | None:
    """Extract first frame as reference screenshot"""
    out_path = output_dir / "reference_frame.png"
    if out_path.exists():
        return str(out_path)
    
    # Get duration
    try:
        dur_out = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(video_path)],
            capture_output=True, text=True, timeout=10
        )
        duration = float(dur_out.stdout.strip())
    except:
        duration = 3.0
    
    # Extract frame at 1/3 of duration
    t = duration / 3
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-ss", f"{t:.2f}", "-i", str(video_path), "-frames:v", "1", "-q:v", "3", str(out_path)],
            capture_output=True, timeout=15
        )
        if out_path.exists():
            return str(out_path)
    except:
        pass
    return None


def trigger_pipeline(sample_name: str) -> dict | None:
    """POST /pipeline/run with video file"""
    video_path = SAMPLES_DIR / f"{sample_name}.webm"
    if not video_path.exists():
        print(f"  ERROR: video not found: {video_path}")
        return None
    
    with open(video_path, "rb") as f:
        files = {"video": (f"{sample_name}.webm", f, "video/webm")}
        data = {"max_iterations": str(MAX_ITERATIONS), "passing_threshold": str(PASSING_THRESHOLD)}
        
        try:
            resp = httpx.post(f"{BACKEND_URL}/pipeline/run", files=files, data=data, timeout=30)
            if resp.status_code == 200:
                return resp.json()
            else:
                print(f"  ERROR: {resp.status_code} {resp.text[:200]}")
                return None
        except Exception as e:
            print(f"  ERROR: {e}")
            return None


def poll_pipeline(pipeline_id: str) -> dict:
    """Poll GET /pipeline/status/{id} until complete"""
    start = time.time()
    last_phase = ""
    
    while time.time() - start < POLL_TIMEOUT:
        try:
            resp = httpx.get(f"{BACKEND_URL}/pipeline/status/{pipeline_id}", timeout=10)
            state = resp.json()
        except Exception as e:
            print(f"  Poll error: {e}")
            time.sleep(POLL_INTERVAL)
            continue
        
        status = state.get("status", "unknown")
        phase = state.get("current_phase", "")
        
        if phase != last_phase:
            elapsed = int(time.time() - start)
            print(f"  [{elapsed}s] phase: {phase} | status: {status}")
            last_phase = phase
        
        if status in ("passed", "max_iterations", "completed", "failed"):
            elapsed = time.time() - start
            state["_elapsed_seconds"] = round(elapsed, 1)
            return state
        
        time.sleep(POLL_INTERVAL)
    
    return {"status": "timeout", "_elapsed_seconds": POLL_TIMEOUT}


def detect_issues(sample_name: str, state: dict) -> list[dict]:
    """Auto-detect problems from pipeline state"""
    issues = []
    
    # P-Pipeline failures
    if state.get("status") == "failed":
        issues.append({"id": "P-pipeline-failed", "severity": "P0", "desc": f"Pipeline failed: {state.get('error', 'unknown')[:100]}"})
    
    if state.get("status") == "timeout":
        issues.append({"id": "P-timeout", "severity": "P0", "desc": f"Pipeline timed out after {POLL_TIMEOUT}s"})
    
    # Get shader
    shader = state.get("current_shader", "") or state.get("snapshot", {}).get("shader", "")
    visual_desc = state.get("snapshot", {}).get("visual_description", {}) or {}
    inspect_fb = state.get("snapshot", {}).get("inspect_feedback", {}) or {}
    
    if not shader:
        issues.append({"id": "G-no-shader", "severity": "P0", "desc": "No shader generated"})
    else:
        # G-Format checks
        if "void mainImage" not in shader:
            issues.append({"id": "G-no-mainImage", "severity": "P1", "desc": "Missing mainImage function"})
        if "fragColor" not in shader:
            issues.append({"id": "G-no-fragColor", "severity": "P1", "desc": "Missing fragColor assignment"})
        
        # Banned items
        if "raymarching" in shader.lower() or "castRay" in shader:
            issues.append({"id": "G-raymarching-banned", "severity": "P1", "desc": "Contains raymarching code"})
        if "texture2D" in shader or "texture(" in shader:
            issues.append({"id": "G-texture-fetch", "severity": "P2", "desc": "Contains texture fetch"})
        
        # Code length
        lines = shader.count("\n") + 1
        if lines > 400:
            issues.append({"id": "G-code-too-long", "severity": "P2", "desc": f"Shader has {lines} lines (>400)"})
    
    # D-Decompose checks
    if not visual_desc:
        issues.append({"id": "D-no-description", "severity": "P1", "desc": "No visual description generated"})
    else:
        if not visual_desc.get("effect_type"):
            issues.append({"id": "D-no-effect-type", "severity": "P1", "desc": "Missing effect_type"})
        shape_def = visual_desc.get("shape_definition", {}) or {}
        if not shape_def.get("edge_width"):
            issues.append({"id": "D-no-edge-width", "severity": "P2", "desc": "Missing edge_width in shape_definition"})
        color_def = visual_desc.get("color_definition", {}) or {}
        if not color_def.get("primary_rgb"):
            issues.append({"id": "D-no-primary-rgb", "severity": "P2", "desc": "Missing primary_rgb in color_definition"})
    
    # Compile retry
    retry_count = state.get("compile_retry_count", 0) or 0
    if retry_count >= 2:
        issues.append({"id": "G-compile-retry-high", "severity": "P2", "desc": f"Compile retry count: {retry_count}"})
    
    # I-Inspect score
    score = inspect_fb.get("overall_score", 0) if inspect_fb else 0
    if score > 0 and score < 0.3:
        issues.append({"id": "I-low-quality", "severity": "P1", "desc": f"Very low inspect score: {score:.2f}"})
    
    # Iteration count
    iteration = state.get("iteration", 0) or state.get("snapshot", {}).get("iteration", 0) or 0
    if state.get("status") == "max_iterations" and iteration >= MAX_ITERATIONS:
        issues.append({"id": "P-max-iterations", "severity": "P2", "desc": f"Reached max iterations ({MAX_ITERATIONS}) without passing"})
    
    return issues


def save_sample_artifacts(sample_name: str, state: dict, reference_frame: str | None):
    """Save per-sample artifacts"""
    sample_dir = RESULTS_DIR / sample_name
    sample_dir.mkdir(exist_ok=True)
    
    # Copy reference frame
    if reference_frame and Path(reference_frame).exists():
        ref_dest = sample_dir / "reference_frame.png"
        if not ref_dest.exists():
            import shutil
            shutil.copy2(reference_frame, ref_dest)
    
    # Copy rendered screenshots
    render_screenshots = state.get("snapshot", {}).get("render_screenshots", []) or state.get("design_screenshots", [])
    if render_screenshots:
        import shutil
        for i, src in enumerate(render_screenshots):
            if Path(src).exists():
                dest = sample_dir / f"render_{i}.png"
                if not dest.exists():
                    shutil.copy2(src, dest)
    
    # Save visual description
    visual_desc = state.get("snapshot", {}).get("visual_description", {})
    if visual_desc:
        (sample_dir / "visual_description.json").write_text(
            json.dumps(visual_desc, indent=2, ensure_ascii=False)
        )
    
    # Save shader code
    shader = state.get("current_shader", "") or state.get("snapshot", {}).get("shader", "")
    if shader:
        (sample_dir / "shader.glsl").write_text(shader)
    
    # Save full state (exclude large binary data)
    state_copy = {k: v for k, v in state.items() if k not in ("_elapsed_seconds",)}
    (sample_dir / "pipeline_state.json").write_text(
        json.dumps(state_copy, indent=2, ensure_ascii=False, default=str)
    )


def run_single(sample_name: str, results: dict) -> dict:
    """Run pipeline for one sample"""
    sample_dir = RESULTS_DIR / sample_name
    sample_dir.mkdir(exist_ok=True)
    
    print(f"\n{'='*60}")
    print(f"  {sample_name}")
    print(f"{'='*60}")
    
    # 1. Extract reference frame
    video_path = SAMPLES_DIR / f"{sample_name}.webm"
    ref_frame = extract_reference_frame(video_path, sample_dir)
    print(f"  Reference frame: {'OK' if ref_frame else 'FAILED'}")
    
    # 2. Trigger pipeline
    print(f"  Triggering pipeline (max_iter={MAX_ITERATIONS}, threshold={PASSING_THRESHOLD})...")
    trigger_result = trigger_pipeline(sample_name)
    if not trigger_result:
        result = {
            "sample_name": sample_name,
            "status": "trigger_failed",
            "issues": [{"id": "P-trigger-failed", "severity": "P0", "desc": "Failed to trigger pipeline"}],
            "timestamp": datetime.now().isoformat(),
        }
        results[sample_name] = result
        save_results(results)
        return result
    
    pipeline_id = trigger_result["pipeline_id"]
    print(f"  Pipeline ID: {pipeline_id}")
    
    # 3. Poll until complete
    print(f"  Polling (timeout={POLL_TIMEOUT}s)...")
    final_state = poll_pipeline(pipeline_id)
    
    status = final_state.get("status", "unknown")
    elapsed = final_state.get("_elapsed_seconds", 0)
    
    # 4. Detect issues
    issues = detect_issues(sample_name, final_state)
    
    # 5. Extract key metrics
    inspect_fb = final_state.get("snapshot", {}).get("inspect_feedback", {}) or {}
    score = inspect_fb.get("overall_score", 0)
    iteration = final_state.get("iteration", 0) or final_state.get("snapshot", {}).get("iteration", 0) or 0
    visual_desc = final_state.get("snapshot", {}).get("visual_description", {}) or {}
    shader = final_state.get("current_shader", "") or final_state.get("snapshot", {}).get("shader", "")
    
    # 6. Save artifacts
    save_sample_artifacts(sample_name, final_state, ref_frame)
    
    # 7. Build result
    result = {
        "sample_name": sample_name,
        "pipeline_id": pipeline_id,
        "status": status,
        "elapsed_seconds": elapsed,
        "score": score,
        "iteration": iteration,
        "effect_type": visual_desc.get("effect_type", ""),
        "shader_lines": shader.count("\n") + 1 if shader else 0,
        "issues": issues,
        "issue_count": len(issues),
        "timestamp": datetime.now().isoformat(),
    }
    
    # Print summary
    issue_str = f", {len(issues)} issues" if issues else ""
    print(f"\n  >>> {sample_name}: status={status}, score={score:.2f}, iter={iteration}, {elapsed}s{issue_str}")
    
    results[sample_name] = result
    save_results(results)
    return result


def print_summary(results: dict):
    """Print batch summary"""
    total = len(results)
    if total == 0:
        print("No results yet.")
        return
    
    statuses = {}
    scores = []
    all_issues = []
    
    for name, r in results.items():
        s = r.get("status", "unknown")
        statuses[s] = statuses.get(s, 0) + 1
        
        score = r.get("score", 0)
        if score > 0:
            scores.append((name, score))
        
        for issue in r.get("issues", []):
            all_issues.append((name, issue))
    
    print(f"\n{'='*60}")
    print(f"  BATCH SUMMARY ({total} samples)")
    print(f"{'='*60}")
    
    print(f"\n  Status distribution:")
    for s, cnt in sorted(statuses.items(), key=lambda x: -x[1]):
        print(f"    {s}: {cnt}")
    
    if scores:
        avg = sum(s for _, s in scores) / len(scores)
        sorted_scores = sorted(scores, key=lambda x: x[1], reverse=True)
        print(f"\n  Score stats: avg={avg:.2f}, min={sorted_scores[-1][1]:.2f}, max={sorted_scores[0][1]:.2f}")
        print(f"\n  Top 5:")
        for name, score in sorted_scores[:5]:
            print(f"    {name}: {score:.2f}")
        print(f"\n  Bottom 5:")
        for name, score in sorted_scores[-5:]:
            print(f"    {name}: {score:.2f}")
    
    if all_issues:
        # Count by issue id
        from collections import Counter
        issue_counts = Counter(iid for _, i in all_issues for iid in [i["id"]])
        print(f"\n  Issue frequency (total {len(all_issues)}):")
        for iid, cnt in issue_counts.most_common(10):
            print(f"    {iid}: {cnt}")
    
    print(f"\n  Results saved to: {RESULTS_DIR}")


def main():
    global POLL_TIMEOUT
    
    parser = argparse.ArgumentParser(description="VFX-Agent E2E Batch Test")
    parser.add_argument("--all", action="store_true", help="Test all 50 samples")
    parser.add_argument("--samples", nargs="+", help="Test specific samples")
    parser.add_argument("--report-only", action="store_true", help="Only generate report from existing results")
    parser.add_argument("--timeout", type=int, default=POLL_TIMEOUT, help="Per-sample timeout in seconds")
    args = parser.parse_args()
    
    POLL_TIMEOUT = args.timeout
    
    # Ensure results dir
    RESULTS_DIR.mkdir(exist_ok=True)
    
    # Check backend
    if not args.report_only:
        try:
            resp = httpx.get(f"{BACKEND_URL}/docs", timeout=5, follow_redirects=True)
            print(f"Backend: OK")
        except:
            print(f"ERROR: Backend not running at {BACKEND_URL}")
            print(f"Start with: ./start.sh start")
            sys.exit(1)
    
    # Determine samples to test
    if args.report_only:
        results = load_results()
        print_summary(results)
        return
    
    if args.all:
        samples = sorted([f.stem for f in SAMPLES_DIR.glob("*.webm")])
    elif args.samples:
        samples = args.samples
    else:
        samples = SELECTED_SAMPLES
    
    print(f"Samples to test: {len(samples)}")
    print(f"Max iterations: {MAX_ITERATIONS}")
    print(f"Passing threshold: {PASSING_THRESHOLD}")
    print(f"Timeout per sample: {POLL_TIMEOUT}s")
    
    # Load existing results (for resume)
    results = load_results()
    todo = [s for s in samples if s not in results or results[s].get("status") in ("timeout", "trigger_failed")]
    
    if todo:
        print(f"Already done: {len(results)}, Todo: {len(todo)}")
    else:
        print(f"All {len(samples)} samples already done. Use --report-only for summary.")
        print_summary(results)
        return
    
    start_time = time.time()
    
    for i, sample in enumerate(todo):
        print(f"\n[{len(results) + 1}/{len(samples)}] ", end="")
        run_single(sample, results)
        
        elapsed_total = time.time() - start_time
        remaining = len(todo) - (i + 1)
        if remaining > 0:
            avg_per_sample = elapsed_total / (i + 1)
            eta = avg_per_sample * remaining
            print(f"\n  ETA: ~{eta/60:.0f}min remaining ({remaining} samples left)")
    
    total_time = time.time() - start_time
    print(f"\n  Total time: {total_time/60:.1f}min")
    
    print_summary(load_results())


if __name__ == "__main__":
    main()
