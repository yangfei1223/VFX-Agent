#!/usr/bin/env python3
"""Benchmark runner for VFX-Agent pipeline.

Runs each benchmark sample through the VFX-Agent pipeline and collects results.

Usage:
    python benchmark/runner.py                    # Run all samples
    python benchmark/runner.py --tier 1           # Run only Tier 1
    python benchmark/runner.py --ids buffer-bloom,glow-tutorial
    python benchmark/runner.py --in-scope-only    # Run only in_scope samples
    python benchmark/runner.py --api http://localhost:8000
    python benchmark/runner.py --sample-dir ~/Downloads/shadertoy-samples
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TERMINAL_STATUSES = {"passed", "max_iterations", "completed", "failed", "error"}
POLL_INTERVAL_SEC = 5
POLL_TIMEOUT_SEC = 600  # 10 min per-sample hard timeout

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = SCRIPT_DIR / "config.json"
REPORTS_DIR = SCRIPT_DIR / "reports"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_config(config_path: Path) -> list[dict]:
    """Load benchmark config.json."""
    if not config_path.exists():
        print(f"ERROR: Config file not found: {config_path}")
        sys.exit(1)
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_existing_results(results_path: Path) -> dict[str, dict]:
    """Load previously saved results (for resume support)."""
    if not results_path.exists():
        return {}
    try:
        with open(results_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {r["id"]: r for r in data.get("results", [])}
    except (json.JSONDecodeError, KeyError):
        return {}


def save_results(results_path: Path, results: list[dict], metadata: dict):
    """Save results to JSON file."""
    results_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "metadata": metadata,
        "results": results,
    }
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def filter_samples(
    samples: list[dict],
    tier: int | None = None,
    ids: list[str] | None = None,
    in_scope_only: bool = False,
    expected_type: str | None = None,
) -> list[dict]:
    """Filter samples based on CLI criteria."""
    filtered = samples
    if tier is not None:
        filtered = [s for s in filtered if s.get("tier") == tier]
    if ids is not None:
        id_set = set(ids)
        filtered = [s for s in filtered if s["id"] in id_set]
    if in_scope_only:
        filtered = [s for s in filtered if s.get("in_scope", False)]
    if expected_type is not None:
        filtered = [s for s in filtered if s.get("expected_type") == expected_type]
    return filtered


def submit_sample(
    api_base: str, video_path: Path, description: str
) -> str | None:
    """POST a video sample to the pipeline and return the pipeline_id."""
    url = f"{api_base}/pipeline/run"
    if not video_path.exists():
        print(f"  SKIP: file not found: {video_path}")
        return None
    with open(video_path, "rb") as f:
        files = {"video": (video_path.name, f, "video/webm")}
        data = {"description": description}
        try:
            resp = requests.post(url, files=files, data=data, timeout=30)
            resp.raise_for_status()
            body = resp.json()
            return body.get("pipeline_id")
        except requests.RequestException as e:
            print(f"  ERROR submitting: {e}")
            return None


def poll_until_done(
    api_base: str, pipeline_id: str, interval: int = 5, timeout: int = 600
) -> dict:
    """Poll pipeline status until a terminal state or timeout."""
    url = f"{api_base}/pipeline/status/{pipeline_id}"
    start = time.time()
    while True:
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            status_data = resp.json()
        except requests.RequestException as e:
            print(f"  WARN: poll error: {e}")
            time.sleep(interval)
            continue

        status = status_data.get("status", "unknown")
        if status in TERMINAL_STATUSES:
            return status_data

        elapsed = time.time() - start
        if elapsed > timeout:
            print(f"  TIMEOUT after {timeout}s")
            return {**status_data, "status": "timeout"}

        time.sleep(interval)


def extract_result(
    sample: dict, pipeline_id: str, status_data: dict, duration_sec: float
) -> dict:
    """Extract a structured result dict from pipeline status."""
    final_status = status_data.get("status", "unknown")
    passed = final_status == "passed" or status_data.get("passed", False)
    score = status_data.get("final_score") or status_data.get("inspect_score")
    iteration = status_data.get("iteration", 0)
    compile_errors = 0
    # Count compile errors from generate_history if available
    gen_history = status_data.get("generate_history") or []
    for entry in gen_history:
        if isinstance(entry, dict) and entry.get("compile_error"):
            compile_errors += 1

    return {
        "id": sample["id"],
        "pipeline_id": pipeline_id,
        "status": final_status,
        "final_status": final_status,
        "effect_type": sample.get("expected_type", "unknown"),
        "final_score": score,
        "iterations": iteration,
        "compile_errors": compile_errors,
        "passed": passed,
        "duration_sec": round(duration_sec, 1),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tier": sample.get("tier"),
        "in_scope": sample.get("in_scope", True),
        "description": sample.get("description", ""),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="VFX-Agent Benchmark Runner")
    parser.add_argument(
        "--tier", type=int, default=None, help="Filter by tier (1, 2, or 3)"
    )
    parser.add_argument(
        "--ids",
        type=str,
        default=None,
        help="Comma-separated sample IDs to run",
    )
    parser.add_argument(
        "--in-scope-only",
        action="store_true",
        help="Only run samples marked as in_scope",
    )
    parser.add_argument(
        "--expected-type",
        type=str,
        default=None,
        help="Filter by expected_type (e.g. glow, ripple, gradient, frosted, flow)",
    )
    parser.add_argument(
        "--api",
        type=str,
        default="http://localhost:8000",
        help="VFX-Agent API base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--sample-dir",
        type=str,
        default=os.path.expanduser("~/Downloads/shadertoy-samples"),
        help="Directory containing sample video files",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=POLL_INTERVAL_SEC,
        help=f"Polling interval in seconds (default: {POLL_INTERVAL_SEC})",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=POLL_TIMEOUT_SEC,
        help=f"Per-sample timeout in seconds (default: {POLL_TIMEOUT_SEC})",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Do not skip samples with existing results",
    )
    parser.add_argument(
        "--results-file",
        type=str,
        default=None,
        help="Custom path for results JSON file",
    )
    args = parser.parse_args()

    # Poll settings (used as local references)
    poll_interval = args.poll_interval
    poll_timeout = args.timeout

    # Load config
    samples = load_config(CONFIG_PATH)
    print(f"Loaded {len(samples)} samples from config")

    # Filter
    id_list = args.ids.split(",") if args.ids else None
    samples = filter_samples(
        samples,
        tier=args.tier,
        ids=id_list,
        in_scope_only=args.in_scope_only,
        expected_type=args.expected_type,
    )
    print(f"After filtering: {len(samples)} samples to run")

    if not samples:
        print("No samples match the filter criteria. Exiting.")
        sys.exit(0)

    # Results file
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    if args.results_file:
        results_path = Path(args.results_file)
    else:
        results_path = REPORTS_DIR / f"{timestamp}_results.json"

    # Resume support
    existing = {} if args.no_resume else load_existing_results(results_path)
    if existing:
        print(f"Found {len(existing)} existing results (will skip completed samples)")

    sample_dir = Path(args.sample_dir)
    api_base = args.api.rstrip("/")

    all_results: list[dict] = list(existing.values())
    skipped = 0
    completed = 0
    failed = 0

    metadata = {
        "timestamp": timestamp,
        "api_base": api_base,
        "sample_dir": str(sample_dir),
        "filter": {
            "tier": args.tier,
            "ids": id_list,
            "in_scope_only": args.in_scope_only,
            "expected_type": args.expected_type,
        },
        "total_samples": len(samples),
        "started_at": datetime.now(timezone.utc).isoformat(),
    }

    # Save initial empty results file
    save_results(results_path, all_results, metadata)
    print(f"Results will be saved to: {results_path}\n")

    for idx, sample in enumerate(samples, 1):
        sample_id = sample["id"]

        # Resume: skip if already processed
        if sample_id in existing:
            print(f"[{idx}/{len(samples)}] {sample_id} ... SKIP (already in results)")
            skipped += 1
            continue

        video_path = sample_dir / sample["file"]
        description = sample.get("description", "")

        print(
            f"[{idx}/{len(samples)}] {sample_id} ... ", end="", flush=True
        )

        t_start = time.time()

        # Submit
        pipeline_id = submit_sample(api_base, video_path, description)
        if pipeline_id is None:
            duration = time.time() - t_start
            result = {
                "id": sample_id,
                "pipeline_id": None,
                "status": "submission_failed",
                "final_status": "submission_failed",
                "effect_type": sample.get("expected_type", "unknown"),
                "final_score": None,
                "iterations": 0,
                "compile_errors": 0,
                "passed": False,
                "duration_sec": round(duration, 1),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tier": sample.get("tier"),
                "in_scope": sample.get("in_scope", True),
                "description": description,
            }
            all_results.append(result)
            save_results(results_path, all_results, metadata)
            failed += 1
            print(f"FAILED (submission, {result['duration_sec']}s)")
            continue

        # Poll
        print(f"polling ... ", end="", flush=True)
        status_data = poll_until_done(
            api_base, pipeline_id, interval=poll_interval, timeout=poll_timeout
        )
        duration = time.time() - t_start

        result = extract_result(sample, pipeline_id, status_data, duration)
        all_results.append(result)

        # Save incrementally
        save_results(results_path, all_results, metadata)

        status_str = result["final_status"]
        score_str = (
            f"score: {result['final_score']}"
            if result["final_score"] is not None
            else "no score"
        )
        passed_str = "PASSED" if result["passed"] else status_str
        print(
            f"{passed_str} ({score_str}, iter: {result['iterations']}, "
            f"{result['duration_sec']}s)"
        )

        if result["passed"]:
            completed += 1
        else:
            failed += 1

    # Final summary
    metadata["completed_at"] = datetime.now(timezone.utc).isoformat()
    metadata["summary"] = {
        "total": len(samples),
        "completed_passed": completed,
        "failed": failed,
        "skipped": skipped,
    }
    save_results(results_path, all_results, metadata)

    print(f"\n{'='*60}")
    print(f"Benchmark complete!")
    print(f"  Total:   {len(samples)}")
    print(f"  Passed:  {completed}")
    print(f"  Failed:  {failed}")
    print(f"  Skipped: {skipped}")
    print(f"  Results: {results_path}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
