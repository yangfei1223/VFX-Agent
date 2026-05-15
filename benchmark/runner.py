#!/usr/bin/env python3
"""Benchmark runner for VFX-Agent pipeline.

Architecture:
  - BackendAdapter: abstract interface for submitting work and collecting results
  - HttpApiAdapter: current implementation via REST API
  - runner.py only depends on the adapter interface

Usage:
    python benchmark/runner.py                    # Run all samples
    python benchmark/runner.py --tier 1           # Run only Tier 1
    python benchmark/runner.py --ids buffer-bloom,glow-tutorial
    python benchmark/runner.py --in-scope-only    # Run only in_scope samples
    python benchmark/runner.py --api http://localhost:8000
    python benchmark/runner.py --sample-dir ~/Downloads/shadertoy-samples
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from abc import ABC, abstractmethod
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


# ===========================================================================
# Backend Adapter Interface
# ===========================================================================


class BenchmarkResult:
    """Standardized result from a single benchmark run.

    This is the **only** data contract between the runner and the backend.
    Adapters must produce this; the runner consumes this.
    """

    __slots__ = (
        "effect_type",
        "first_score",
        "final_score",
        "iterations",
        "passed",
        "status",
        "score_history",
    )

    def __init__(
        self,
        *,
        status: str,
        passed: bool = False,
        effect_type: str | None = None,
        first_score: float | None = None,
        final_score: float | None = None,
        iterations: int = 0,
        score_history: list[dict] | None = None,
    ):
        self.status = status
        self.passed = passed
        self.effect_type = effect_type
        self.first_score = first_score
        self.final_score = final_score
        self.iterations = iterations
        self.score_history = score_history or []

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "passed": self.passed,
            "effect_type": self.effect_type,
            "first_score": self.first_score,
            "final_score": self.final_score,
            "iterations": self.iterations,
            "score_history": self.score_history,
        }


class BackendAdapter(ABC):
    """Abstract interface for submitting a VFX sample and collecting results.

    Implementations:
    - HttpApiAdapter: calls the current FastAPI REST endpoints
    - (future) CliAdapter, SdkAdapter, etc.
    """

    @abstractmethod
    def submit(self, video_path: Path, description: str) -> str | None:
        """Submit a sample and return a job handle (or None on failure)."""

    @abstractmethod
    def wait_for_result(self, handle: str, timeout: int) -> BenchmarkResult | None:
        """Block until the job finishes and return a BenchmarkResult."""


# ===========================================================================
# HTTP API Adapter (current VFX-Agent backend)
# ===========================================================================


class HttpApiAdapter(BackendAdapter):
    """Adapter for the VFX-Agent FastAPI REST API."""

    def __init__(self, base_url: str, poll_interval: int = POLL_INTERVAL_SEC):
        self.base_url = base_url.rstrip("/")
        self.poll_interval = poll_interval

    def submit(self, video_path: Path, description: str) -> str | None:
        url = f"{self.base_url}/pipeline/run"
        if not video_path.exists():
            print(f"  SKIP: file not found: {video_path}")
            return None
        with open(video_path, "rb") as f:
            files = {"video": (video_path.name, f, "video/webm")}
            data = {"description": description}
            try:
                resp = requests.post(url, files=files, data=data, timeout=30)
                resp.raise_for_status()
                return resp.json().get("pipeline_id")
            except requests.RequestException as e:
                print(f"  ERROR submitting: {e}")
                return None

    def wait_for_result(self, handle: str, timeout: int) -> BenchmarkResult | None:
        url = f"{self.base_url}/pipeline/status/{handle}"
        start = time.time()
        seen_iterations: set[int] = set()
        score_history: list[dict] = []

        while True:
            try:
                resp = requests.get(url, timeout=10)
                resp.raise_for_status()
                data = resp.json()
            except requests.RequestException as e:
                print(f"  WARN: poll error: {e}")
                time.sleep(self.poll_interval)
                continue

            # Track score per iteration
            iteration = self._extract_iteration(data)
            score = self._extract_score(data)
            if iteration > 0 and iteration not in seen_iterations and score is not None:
                seen_iterations.add(iteration)
                score_history.append({"iteration": iteration, "score": score})

            status = data.get("status", "unknown")
            if status in TERMINAL_STATUSES:
                return self._parse_status(data, score_history)

            elapsed = time.time() - start
            if elapsed > timeout:
                print(f"  TIMEOUT after {timeout}s")
                return BenchmarkResult(status="timeout", score_history=score_history)

            time.sleep(self.poll_interval)

    # ---- internal ----

    @staticmethod
    def _extract_iteration(data: dict) -> int:
        return data.get("snapshot", {}).get("iteration", 0) or data.get("iteration", 0)

    @staticmethod
    def _extract_score(data: dict) -> float | None:
        inspect_feedback = data.get("snapshot", {}).get("inspect_feedback", {})
        if isinstance(inspect_feedback, dict):
            return inspect_feedback.get("overall_score")
        return None

    @staticmethod
    def _parse_status(data: dict, score_history: list[dict]) -> BenchmarkResult:
        """Parse pipeline status JSON into a BenchmarkResult."""
        status = data.get("status", "unknown")
        passed = status == "passed" or data.get("passed", False)

        # Extract effect_type from actual pipeline output
        effect_type = None
        visual_description = data.get("snapshot", {}).get("visual_description", {})
        if isinstance(visual_description, dict):
            effect_type = visual_description.get("effect_type")

        # Extract scores
        final_score = HttpApiAdapter._extract_score(data)
        iteration = HttpApiAdapter._extract_iteration(data)

        # First score = earliest score in history
        first_score = score_history[0]["score"] if score_history else None

        return BenchmarkResult(
            status=status,
            passed=passed,
            effect_type=effect_type,
            first_score=first_score,
            final_score=final_score,
            iterations=iteration,
            score_history=score_history,
        )


# ===========================================================================
# Helpers
# ===========================================================================


def load_config(config_path: Path) -> list[dict]:
    """Load benchmark config.json."""
    if not config_path.exists():
        print(f"ERROR: Config file not found: {config_path}")
        sys.exit(1)
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_existing_results(results_path: Path) -> dict[str, dict]:
    """Load existing results for resume support. Returns {sample_id: result}."""
    if not results_path.exists():
        return {}
    try:
        with open(results_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            results = data.get("results", [])
        elif isinstance(data, list):
            results = data
        else:
            return {}
        return {r["id"]: r for r in results if "id" in r}
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
        filtered = [s for s in filtered if s.get("id") in id_set]
    if in_scope_only:
        filtered = [s for s in filtered if s.get("in_scope", False)]
    if expected_type is not None:
        filtered = [s for s in filtered if s.get("expected_type") == expected_type]
    return filtered


# ===========================================================================
# Main
# ===========================================================================


def run_benchmark(
    adapter: BackendAdapter,
    samples: list[dict],
    sample_dir: Path,
    results_path: Path,
    *,
    poll_timeout: int = POLL_TIMEOUT_SEC,
    no_resume: bool = False,
    metadata: dict | None = None,
) -> None:
    """Core benchmark loop — adapter-agnostic."""

    # Resume support
    existing = {} if no_resume else load_existing_results(results_path)
    if existing:
        print(f"Found {len(existing)} existing results (will skip completed samples)")

    all_results: list[dict] = list(existing.values())
    skipped = 0
    completed = 0
    failed = 0
    total = len(samples)

    meta = metadata or {}
    meta.setdefault("started_at", datetime.now(timezone.utc).isoformat())

    # Save initial empty results file
    save_results(results_path, all_results, meta)
    print(f"Results will be saved to: {results_path}\n")

    for idx, sample in enumerate(samples, 1):
        sample_id = sample["id"]

        # Resume: skip if already processed
        if sample_id in existing:
            print(f"[{idx}/{total}] {sample_id} ... SKIP (already in results)")
            skipped += 1
            continue

        video_path = sample_dir / sample["file"]
        description = sample.get("description", "")

        print(f"[{idx}/{total}] {sample_id} ... ", end="", flush=True)
        t_start = time.time()

        # Submit via adapter
        handle = adapter.submit(video_path, description)
        if handle is None:
            duration = time.time() - t_start
            result = _build_result_dict(
                sample, handle=None, br=None, duration=duration
            )
            all_results.append(result)
            save_results(results_path, all_results, meta)
            failed += 1
            print(f"FAILED (submission, {duration:.1f}s)")
            continue

        # Wait via adapter
        print("polling ... ", end="", flush=True)
        br = adapter.wait_for_result(handle, timeout=poll_timeout)
        duration = time.time() - t_start

        result = _build_result_dict(
            sample, handle=handle, br=br, duration=duration
        )
        all_results.append(result)
        save_results(results_path, all_results, meta)

        # Print outcome
        if br is None:
            print(f"FAILED (no result, {duration:.1f}s)")
            failed += 1
            continue

        score_str = (
            f"1st: {br.first_score:.2f} → final: {br.final_score:.2f}"
            if br.first_score is not None and br.final_score is not None
            else f"final: {br.final_score:.2f}" if br.final_score is not None else "no score"
        )
        passed_str = "PASSED" if br.passed else br.status
        print(f"{passed_str} ({score_str}, iter: {br.iterations}, {duration:.1f}s)")

        if br.passed:
            completed += 1
        else:
            failed += 1

    # Final summary
    meta["completed_at"] = datetime.now(timezone.utc).isoformat()
    meta["summary"] = {
        "total": total,
        "completed_passed": completed,
        "failed": failed,
        "skipped": skipped,
    }
    save_results(results_path, all_results, meta)

    print(f"\n{'='*60}")
    print(f"Benchmark complete!")
    print(f"  Total:   {total}")
    print(f"  Passed:  {completed}")
    print(f"  Failed:  {failed}")
    print(f"  Skipped: {skipped}")
    print(f"  Results: {results_path}")
    print(f"{'='*60}")


def _build_result_dict(
    sample: dict,
    *,
    handle: str | None,
    br: BenchmarkResult | None,
    duration: float,
) -> dict:
    """Merge sample config + BenchmarkResult into a flat result dict."""
    br_dict = br.to_dict() if br else BenchmarkResult(status="no_result").to_dict()
    return {
        "id": sample["id"],
        "pipeline_id": handle,
        # From BenchmarkResult - 3 core metrics
        "status": br_dict["status"],
        "passed": br_dict["passed"],
        "effect_type": br_dict["effect_type"],
        "first_score": br_dict["first_score"],
        "final_score": br_dict["final_score"],
        "iterations": br_dict["iterations"],
        "score_history": br_dict["score_history"],
        "duration_sec": round(duration, 1),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        # From config (ground truth)
        "expected_type": sample.get("expected_type"),
        "tier": sample.get("tier"),
        "in_scope": sample.get("in_scope", True),
    }


def main():
    parser = argparse.ArgumentParser(description="VFX-Agent Benchmark Runner")
    parser.add_argument("--tier", type=int, default=None, help="Filter by tier (1, 2, or 3)")
    parser.add_argument("--ids", type=str, default=None, help="Comma-separated sample IDs to run")
    parser.add_argument("--in-scope-only", action="store_true", help="Only run in_scope samples")
    parser.add_argument("--expected-type", type=str, default=None, help="Filter by expected_type")
    parser.add_argument("--api", type=str, default="http://localhost:8000", help="API base URL")
    parser.add_argument("--sample-dir", type=str, default=os.path.expanduser("~/Downloads/shadertoy-samples"), help="Sample directory")
    parser.add_argument("--poll-interval", type=int, default=POLL_INTERVAL_SEC, help="Poll interval (seconds)")
    parser.add_argument("--timeout", type=int, default=POLL_TIMEOUT_SEC, help="Per-sample timeout (seconds)")
    parser.add_argument("--no-resume", action="store_true", help="Don't skip existing results")
    parser.add_argument("--results-file", type=str, default=None, help="Custom results file path")
    args = parser.parse_args()

    # Load config
    samples = load_config(CONFIG_PATH)
    print(f"Loaded {len(samples)} samples from config")

    # Filter
    id_list = args.ids.split(",") if args.ids else None
    samples = filter_samples(
        samples, tier=args.tier, ids=id_list,
        in_scope_only=args.in_scope_only, expected_type=args.expected_type,
    )
    print(f"After filtering: {len(samples)} samples to run")

    if not samples:
        print("No samples match the filter criteria. Exiting.")
        sys.exit(0)

    # Results file
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    results_path = Path(args.results_file) if args.results_file else REPORTS_DIR / f"{timestamp}_results.json"

    # Create adapter (currently only HTTP)
    adapter = HttpApiAdapter(base_url=args.api, poll_interval=args.poll_interval)

    # Metadata
    metadata = {
        "timestamp": timestamp,
        "adapter": "HttpApiAdapter",
        "api_base": args.api.rstrip("/"),
        "sample_dir": str(Path(args.sample_dir)),
        "filter": {
            "tier": args.tier,
            "ids": id_list,
            "in_scope_only": args.in_scope_only,
            "expected_type": args.expected_type,
        },
        "total_samples": len(samples),
    }

    # Run
    run_benchmark(
        adapter=adapter,
        samples=samples,
        sample_dir=Path(args.sample_dir),
        results_path=results_path,
        poll_timeout=args.timeout,
        no_resume=args.no_resume,
        metadata=metadata,
    )


if __name__ == "__main__":
    main()
