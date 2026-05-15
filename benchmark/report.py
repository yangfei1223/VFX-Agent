#!/usr/bin/env python3
"""Benchmark Report Generator - Markdown Report.

Highlights 3 core metrics:
1. First Generation Quality (first_score)
2. Convergence Speed (iterations)
3. Final Score (final_score)
"""

import json
import argparse
from pathlib import Path
from datetime import datetime


def generate_report(scored: dict) -> str:
    agg = scored.get("aggregates", {})
    samples = scored.get("samples", [])
    o = agg.get("overall", {})

    in_scope = [s for s in samples if s.get("in_scope")]
    out_scope = [s for s in samples if not s.get("in_scope")]

    lines = []
    lines.append("# VFX-Agent Benchmark Report\n")
    lines.append(f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**Samples**: {o.get('total', 0)} (In-scope: {len(in_scope)}, Out-of-scope: {len(out_scope)})")
    lines.append("\n---\n")

    # Core Metrics
    lines.append("## Core Metrics\n")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| **1st Gen Quality** (avg) | {o.get('first_score_avg', 0):.3f} |")
    lines.append(f"| **1st Gen Quality** (median) | {o.get('first_score_median', 0):.3f} |")
    lines.append(f"| **Convergence Rate** | {o.get('convergence_rate', 0):.1%} |")
    lines.append(f"| **Avg Iterations** | {o.get('avg_iterations', 0):.1f} |")
    lines.append(f"| **Final Quality** (avg) | {o.get('final_score_avg', 0):.3f} |")
    lines.append(f"| **Final Quality** (p75) | {o.get('final_score_p75', 0):.3f} |")
    lines.append(f"| Decompose Accuracy | {o.get('decompose_accuracy', 0):.1%} |")
    lines.append("")

    # By Tier
    by_tier = agg.get("by_tier", {})
    if by_tier:
        lines.append("## By Tier\n")
        lines.append("| Tier | Samples | 1st Gen | Final | Convergence | Avg Iter |")
        lines.append("|------|---------|---------|-------|-------------|----------|")
        for t in [1, 2, 3]:
            td = by_tier.get(f"tier_{t}")
            if td:
                lines.append(f"| Tier {t} | {td['total']} | {td['first_score_avg']:.3f} | {td['final_score_avg']:.3f} | {td['convergence_rate']:.1%} | {td['avg_iterations']:.1f} |")
        lines.append("")

    # By Effect Type
    by_type = agg.get("by_type", {})
    if by_type:
        lines.append("## By Effect Type\n")
        lines.append("| Type | Samples | 1st Gen | Final | Convergence | Avg Iter | Accuracy |")
        lines.append("|------|---------|---------|-------|-------------|----------|----------|")
        for et in ["glow", "ripple", "frosted", "gradient", "flow"]:
            td = by_type.get(et)
            if td:
                lines.append(f"| {et} | {td['total']} | {td['first_score_avg']:.3f} | {td['final_score_avg']:.3f} | {td['convergence_rate']:.1%} | {td['avg_iterations']:.1f} | {td['decompose_accuracy']:.1%} |")
        lines.append("")

    # 1st Gen vs Final comparison (in-scope, sorted by improvement)
    improvements = []
    for s in in_scope:
        first = s.get("first_score")
        final = s.get("final_score")
        if first is not None and final is not None:
            improvements.append((s["id"], first, final, final - first, s.get("converged", False)))
    improvements.sort(key=lambda x: x[3], reverse=True)

    if improvements:
        lines.append("## 1st Gen → Final Score\n")
        lines.append("| ID | 1st Gen | Final | Δ | Converged |")
        lines.append("|----|---------|-------|---|-----------|")
        for sid, first, final, delta, conv in improvements:
            conv_str = "✓" if conv else "✗"
            delta_str = f"+{delta:.2f}" if delta >= 0 else f"{delta:.2f}"
            lines.append(f"| {sid} | {first:.2f} | {final:.2f} | {delta_str} | {conv_str} |")
        lines.append("")

    # Out-of-scope
    if out_scope:
        lines.append("## Out-of-Scope Samples\n")
        lines.append("| ID | Predicted | Final Score |")
        lines.append("|----|-----------|-------------|")
        for s in out_scope:
            pred = s.get("effect_type", "?") or "?"
            final = s.get("final_score")
            final_str = f"{final:.2f}" if final is not None else "N/A"
            lines.append(f"| {s['id']} | {pred} | {final_str} |")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="VFX-Agent Benchmark Report Generator")
    parser.add_argument("--scored", required=True, help="Path to scored JSON")
    parser.add_argument("--output", default=None, help="Output Markdown file")
    args = parser.parse_args()

    scored_path = Path(args.scored)
    with open(scored_path) as f:
        scored = json.load(f)

    report = generate_report(scored)

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = scored_path.parent / scored_path.name.replace("_scored.json", ".md")

    with open(output_path, "w") as f:
        f.write(report)

    print(report)
    print(f"\nReport saved to: {output_path}")


if __name__ == "__main__":
    main()
