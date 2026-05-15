"""Benchmark Scorer - Metrics Collection"""
import json
import argparse
import sys
from pathlib import Path
from statistics import mean, median
from collections import defaultdict


EFFECT_TYPES = ["glow", "ripple", "frosted", "gradient", "flow", "out_of_scope"]
VALID_EFFECT_TOKENS = {
    "glow": ["glow", "{effect.glow}"],
    "ripple": ["ripple", "{effect.ripple}"],
    "frosted": ["frosted", "{effect.frosted}"],
    "gradient": ["gradient", "{effect.gradient}"],
    "flow": ["flow", "{effect.flow}"],
    "out_of_scope": ["out_of_scope"],
}


def check_decompose_correct(predicted: str, expected: str) -> bool:
    """Check if predicted effect_type matches expected"""
    if not predicted:
        return False
    predicted_lower = predicted.lower().strip("{}").replace("effect.", "")
    return predicted_lower == expected.lower()


def percentile(data: list[float], p: float) -> float:
    """Calculate percentile"""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    idx = int(len(sorted_data) * p / 100)
    return sorted_data[min(idx, len(sorted_data) - 1)]


def score_results(results: list[dict], config: list[dict]) -> dict:
    """Score all results against ground truth"""
    # Build config lookup
    config_map = {s["id"]: s for s in config}

    # Score each sample
    scored = []
    for r in results:
        sample_id = r.get("id", "")
        cfg = config_map.get(sample_id, {})

        expected_type = cfg.get("expected_type", "unknown")
        in_scope = cfg.get("in_scope", True)
        tier = cfg.get("tier", 3)

        effect_type = r.get("effect_type", "")
        final_score = r.get("final_score", 0)
        passed = r.get("passed", False)
        iterations = r.get("iterations", 0)

        scored.append({
            **r,
            "expected_type": expected_type,
            "in_scope": in_scope,
            "tier": tier,
            "decompose_correct": check_decompose_correct(effect_type, expected_type),
            "converged": passed,
        })

    # Calculate aggregates
    aggregates = calc_aggregates(scored)

    return {
        "samples": scored,
        "aggregates": aggregates,
    }


def calc_aggregates(samples: list[dict]) -> dict:
    """Calculate aggregate metrics"""
    if not samples:
        return {}

    n = len(samples)

    # Overall
    scores = [s.get("final_score", 0) for s in samples if s.get("final_score") is not None]
    decompose_correct = sum(1 for s in samples if s.get("decompose_correct"))
    converged = sum(1 for s in samples if s.get("converged"))
    iterations = [s.get("iterations", 0) for s in samples]

    overall = {
        "total": n,
        "convergence_rate": converged / n if n > 0 else 0,
        "decompose_accuracy": decompose_correct / n if n > 0 else 0,
        "avg_score": mean(scores) if scores else 0,
        "median_score": median(scores) if scores else 0,
        "p50_score": percentile(scores, 50) if scores else 0,
        "p75_score": percentile(scores, 75) if scores else 0,
        "p90_score": percentile(scores, 90) if scores else 0,
        "avg_iterations": mean(iterations) if iterations else 0,
    }

    # By tier
    by_tier = {}
    for t in [1, 2, 3]:
        tier_samples = [s for s in samples if s.get("tier") == t]
        if tier_samples:
            ts = [s.get("final_score", 0) for s in tier_samples if s.get("final_score") is not None]
            by_tier[f"tier_{t}"] = {
                "total": len(tier_samples),
                "convergence_rate": sum(1 for s in tier_samples if s.get("converged")) / len(tier_samples),
                "decompose_accuracy": sum(1 for s in tier_samples if s.get("decompose_correct")) / len(tier_samples),
                "avg_score": mean(ts) if ts else 0,
                "avg_iterations": mean([s.get("iterations", 0) or 0 for s in tier_samples]) if tier_samples else 0,
            }

    # By type
    by_type = {}
    for et in EFFECT_TYPES:
        type_samples = [s for s in samples if s.get("expected_type") == et]
        if type_samples:
            ts = [s.get("final_score", 0) for s in type_samples if s.get("final_score") is not None]
            by_type[et] = {
                "total": len(type_samples),
                "convergence_rate": sum(1 for s in type_samples if s.get("converged")) / len(type_samples),
                "decompose_accuracy": sum(1 for s in type_samples if s.get("decompose_correct")) / len(type_samples),
                "avg_score": mean(ts) if ts else 0,
            }

    # In scope vs out of scope
    in_scope_samples = [s for s in samples if s.get("in_scope")]
    out_scope_samples = [s for s in samples if not s.get("in_scope")]
    
    in_scope_scores = [s.get("final_score", 0) for s in in_scope_samples if s.get("final_score") is not None]
    out_scope_scores = [s.get("final_score", 0) for s in out_scope_samples if s.get("final_score") is not None]

    by_scope = {
        "in_scope": {
            "total": len(in_scope_samples),
            "convergence_rate": sum(1 for s in in_scope_samples if s.get("converged")) / len(in_scope_samples) if in_scope_samples else 0,
            "decompose_accuracy": sum(1 for s in in_scope_samples if s.get("decompose_correct")) / len(in_scope_samples) if in_scope_samples else 0,
            "avg_score": mean(in_scope_scores) if in_scope_scores else 0,
        },
        "out_of_scope": {
            "total": len(out_scope_samples),
            "convergence_rate": sum(1 for s in out_scope_samples if s.get("converged")) / len(out_scope_samples) if out_scope_samples else 0,
            "avg_score": mean(out_scope_scores) if out_scope_scores else 0,
        },
    }

    return {
        "overall": overall,
        "by_tier": by_tier,
        "by_type": by_type,
        "by_scope": by_scope,
    }


def main():
    parser = argparse.ArgumentParser(description="VFX-Agent Benchmark Scorer")
    parser.add_argument("--results", required=True, help="Path to results JSON")
    parser.add_argument("--config", default=None, help="Path to config.json (default: same dir as results)")
    parser.add_argument("--verbose", action="store_true", help="Print per-sample details")
    args = parser.parse_args()

    # Load results
    results_path = Path(args.results)
    with open(results_path) as f:
        raw = json.load(f)

    # Extract results array (runner saves {"metadata": ..., "results": [...]})
    if isinstance(raw, dict):
        results = raw.get("results", [])
    elif isinstance(raw, list):
        results = raw
    else:
        results = []

    # Load config
    config_path = Path(args.config) if args.config else results_path.parent.parent / "config.json"
    with open(config_path) as f:
        config = json.load(f)

    # Score
    scored = score_results(results, config)

    # Print summary
    agg = scored["aggregates"]
    o = agg["overall"]

    print(f"\n{'='*50}")
    print(f"  VFX-Agent Benchmark Score Report")
    print(f"{'='*50}")
    print(f"  Samples: {o['total']}")
    print(f"  Convergence Rate: {o['convergence_rate']:.1%}")
    print(f"  Decompose Accuracy: {o['decompose_accuracy']:.1%}")
    print(f"  Avg Score: {o['avg_score']:.3f}")
    print(f"  Avg Iterations: {o['avg_iterations']:.1f}")

    print(f"\n  --- By Tier ---")
    for t_name, t_data in agg.get("by_tier", {}).items():
        print(f"  {t_name}: convergence={t_data['convergence_rate']:.1%}, accuracy={t_data['decompose_accuracy']:.1%}, avg_score={t_data['avg_score']:.3f}")

    print(f"\n  --- By Type ---")
    for type_name, type_data in agg.get("by_type", {}).items():
        print(f"  {type_name}: convergence={type_data['convergence_rate']:.1%}, accuracy={type_data['decompose_accuracy']:.1%}, avg_score={type_data['avg_score']:.3f}")

    print(f"\n  --- By Scope ---")
    for scope_name, scope_data in agg.get("by_scope", {}).items():
        print(f"  {scope_name}: total={scope_data['total']}, convergence={scope_data.get('convergence_rate', 0):.1%}, avg_score={scope_data.get('avg_score', 0):.3f}")

    if args.verbose:
        print(f"\n  --- Per-Sample ---")
        for s in scored["samples"]:
            status = "✓" if s.get("converged") else "✗"
            correct = "✓" if s.get("decompose_correct") else "✗"
            score_val = s.get('final_score') or 0
            print(f"  {status} {s['id']:<35} type: {s.get('effect_type','?'):<20} (expected: {s['expected_type']}) [{correct}] score: {score_val:.2f} iter: {s.get('iterations',0)}")

    # Save scored results
    output_path = results_path.parent / results_path.name.replace("_results.json", "_scored.json")
    with open(output_path, "w") as f:
        json.dump(scored, f, indent=2, ensure_ascii=False)
    print(f"\n  Scored results saved to: {output_path}")


if __name__ == "__main__":
    main()
