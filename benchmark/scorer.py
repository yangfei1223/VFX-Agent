#!/usr/bin/env python3
"""Benchmark Scorer - Core Metrics Evaluation.

Focus on 3 key metrics:
1. First Generation Quality (first_score) - how good is the initial output?
2. Convergence Speed (iterations) - how fast does it converge?
3. Final Score (final_score) - what's the best achievable quality?
"""

import json
import argparse
import sys
from pathlib import Path
from statistics import mean, median
from collections import defaultdict


EFFECT_TYPES = ["glow", "ripple", "frosted", "gradient", "flow", "out_of_scope"]


def check_decompose_correct(predicted: str | None, expected: str) -> bool:
    if not predicted:
        return False
    p = predicted.lower().strip().strip("{}").replace("effect.", "")
    return p == expected.lower()


def percentile(data: list[float], p: float) -> float:
    if not data:
        return 0.0
    s = sorted(data)
    idx = int(len(s) * p / 100)
    return s[min(idx, len(s) - 1)]


def score_results(results: list[dict], config: list[dict]) -> dict:
    """Score all results against ground truth."""
    config_map = {s["id"]: s for s in config}
    scored = []

    for r in results:
        sid = r.get("id", "")
        cfg = config_map.get(sid, {})
        expected_type = cfg.get("expected_type", "unknown")
        in_scope = cfg.get("in_scope", True)
        tier = cfg.get("tier", 3)

        first_score = r.get("first_score")
        final_score = r.get("final_score")
        iterations = r.get("iterations", 0)
        passed = r.get("passed", False)
        effect_type = r.get("effect_type")

        scored.append({
            **r,
            "expected_type": expected_type,
            "in_scope": in_scope,
            "tier": tier,
            "decompose_correct": check_decompose_correct(effect_type, expected_type),
            "converged": passed,
        })

    aggregates = calc_aggregates(scored)
    return {"samples": scored, "aggregates": aggregates}


def calc_aggregates(samples: list[dict]) -> dict:
    if not samples:
        return {}

    n = len(samples)

    # --- Overall ---
    in_scope = [s for s in samples if s.get("in_scope")]
    out_scope = [s for s in samples if not s.get("in_scope")]

    first_scores = [s["first_score"] for s in in_scope if s.get("first_score") is not None]
    final_scores = [s["final_score"] for s in in_scope if s.get("final_score") is not None]
    converged = [s for s in in_scope if s.get("converged")]
    decompose_correct = [s for s in in_scope if s.get("decompose_correct")]

    overall = {
        "total": n,
        "in_scope": len(in_scope),
        "out_scope": len(out_scope),
        # Core metric 1: First generation quality
        "first_score_avg": mean(first_scores) if first_scores else 0,
        "first_score_median": median(first_scores) if first_scores else 0,
        # Core metric 2: Convergence speed
        "convergence_rate": len(converged) / len(in_scope) if in_scope else 0,
        "avg_iterations": mean([s.get("iterations", 0) or 0 for s in in_scope]) if in_scope else 0,
        # Core metric 3: Final quality
        "final_score_avg": mean(final_scores) if final_scores else 0,
        "final_score_median": median(final_scores) if final_scores else 0,
        "final_score_p75": percentile(final_scores, 75),
        # Auxiliary
        "decompose_accuracy": len(decompose_correct) / len(in_scope) if in_scope else 0,
    }

    # --- By Tier ---
    by_tier = {}
    for t in [1, 2, 3]:
        tier_s = [s for s in in_scope if s.get("tier") == t]
        if not tier_s:
            continue
        ts_first = [s["first_score"] for s in tier_s if s.get("first_score") is not None]
        ts_final = [s["final_score"] for s in tier_s if s.get("final_score") is not None]
        ts_conv = [s for s in tier_s if s.get("converged")]
        by_tier[f"tier_{t}"] = {
            "total": len(tier_s),
            "first_score_avg": mean(ts_first) if ts_first else 0,
            "final_score_avg": mean(ts_final) if ts_final else 0,
            "convergence_rate": len(ts_conv) / len(tier_s),
            "avg_iterations": mean([s.get("iterations", 0) or 0 for s in tier_s]),
        }

    # --- By Effect Type ---
    by_type = {}
    for et in ["glow", "ripple", "frosted", "gradient", "flow"]:
        type_s = [s for s in in_scope if s.get("expected_type") == et]
        if not type_s:
            continue
        ts_first = [s["first_score"] for s in type_s if s.get("first_score") is not None]
        ts_final = [s["final_score"] for s in type_s if s.get("final_score") is not None]
        ts_conv = [s for s in type_s if s.get("converged")]
        ts_correct = [s for s in type_s if s.get("decompose_correct")]
        by_type[et] = {
            "total": len(type_s),
            "first_score_avg": mean(ts_first) if ts_first else 0,
            "final_score_avg": mean(ts_final) if ts_final else 0,
            "convergence_rate": len(ts_conv) / len(type_s),
            "avg_iterations": mean([s.get("iterations", 0) or 0 for s in type_s]),
            "decompose_accuracy": len(ts_correct) / len(type_s),
        }

    return {"overall": overall, "by_tier": by_tier, "by_type": by_type}


def main():
    parser = argparse.ArgumentParser(description="VFX-Agent Benchmark Scorer")
    parser.add_argument("--results", required=True, help="Path to results JSON")
    parser.add_argument("--config", default=None, help="Path to config.json")
    parser.add_argument("--verbose", action="store_true", help="Print per-sample details")
    args = parser.parse_args()

    results_path = Path(args.results)
    with open(results_path) as f:
        raw = json.load(f)
    results = raw.get("results", []) if isinstance(raw, dict) else raw

    config_path = Path(args.config) if args.config else results_path.parent.parent / "config.json"
    with open(config_path) as f:
        config = json.load(f)

    scored = score_results(results, config)
    agg = scored["aggregates"]
    o = agg["overall"]

    print(f"\n{'='*60}")
    print(f"  VFX-Agent Benchmark Report")
    print(f"{'='*60}")
    print(f"  Samples: {o['total']} (in-scope: {o['in_scope']}, out-of-scope: {o['out_scope']})")
    print(f"")
    print(f"  --- Core Metrics (In-Scope) ---")
    print(f"  1st Gen Quality:  avg={o['first_score_avg']:.3f}  median={o['first_score_median']:.3f}")
    print(f"  Convergence Rate: {o['convergence_rate']:.1%}  avg_iterations={o['avg_iterations']:.1f}")
    print(f"  Final Quality:    avg={o['final_score_avg']:.3f}  median={o['final_score_median']:.3f}  p75={o['final_score_p75']:.3f}")
    print(f"  Decompose Acc:    {o['decompose_accuracy']:.1%}")

    print(f"\n  --- By Tier ---")
    for name, td in agg.get("by_tier", {}).items():
        print(f"  {name}: 1st={td['first_score_avg']:.3f}  final={td['final_score_avg']:.3f}  conv={td['convergence_rate']:.1%}  iter={td['avg_iterations']:.1f}")

    print(f"\n  --- By Effect Type ---")
    for name, td in agg.get("by_type", {}).items():
        print(f"  {name:<10}: 1st={td['first_score_avg']:.3f}  final={td['final_score_avg']:.3f}  conv={td['convergence_rate']:.1%}  iter={td['avg_iterations']:.1f}  acc={td['decompose_accuracy']:.1%}")

    if args.verbose:
        print(f"\n  --- Per-Sample ---")
        for s in scored["samples"]:
            status = "✓" if s.get("converged") else "✗"
            correct = "✓" if s.get("decompose_correct") else "✗"
            first = s.get("first_score")
            final = s.get("final_score")
            first_str = f"{first:.2f}" if first is not None else "N/A"
            final_str = f"{final:.2f}" if final is not None else "N/A"
            pred = s.get("effect_type", "?") or "?"
            print(f"  {status} {s['id']:<35} {pred:<15} → {s['expected_type']:<10} [{correct}] 1st={first_str} final={final_str} iter={s.get('iterations',0)}")

    output_path = results_path.parent / results_path.name.replace("_results.json", "_scored.json")
    with open(output_path, "w") as f:
        json.dump(scored, f, indent=2, ensure_ascii=False)
    print(f"\n  Saved: {output_path}")


if __name__ == "__main__":
    main()
