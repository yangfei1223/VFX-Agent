"""Benchmark Report Generator - Markdown Report"""
import json
import argparse
from pathlib import Path
from datetime import datetime


SCORE_BINS = [(0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.01)]


def generate_report(scored: dict) -> str:
    """Generate Markdown report from scored data"""
    agg = scored.get("aggregates", {})
    samples = scored.get("samples", [])
    overall = agg.get("overall", {})
    by_tier = agg.get("by_tier", {})
    by_type = agg.get("by_type", {})
    by_scope = agg.get("by_scope", {})

    in_scope_total = by_scope.get("in_scope", {}).get("total", 0)
    out_scope_total = by_scope.get("out_of_scope", {}).get("total", 0)

    lines = []
    lines.append("# VFX-Agent Benchmark Report\n")
    lines.append(f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(
        f"**Samples**: {overall.get('total', 0)} "
        f"(In-scope: {in_scope_total}, Out-of-scope: {out_scope_total})"
    )
    lines.append("\n---\n")

    # Overall
    lines.append("## Overall\n")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    conv = overall.get("convergence_rate", 0)
    lines.append(f"| Convergence Rate | {conv:.1%} |")
    acc = overall.get("decompose_accuracy", 0)
    lines.append(f"| Decompose Accuracy | {acc:.1%} |")
    lines.append(f"| Avg Score | {overall.get('avg_score', 0):.3f} |")
    lines.append(f"| Median Score | {overall.get('median_score', 0):.3f} |")
    lines.append(f"| P75 Score | {overall.get('p75_score', 0):.3f} |")
    lines.append(f"| Avg Iterations | {overall.get('avg_iterations', 0):.1f} |")
    lines.append("")

    # By Tier
    lines.append("## By Tier\n")
    lines.append("| Tier | Samples | Convergence | Accuracy | Avg Score |")
    lines.append("|------|---------|-------------|----------|-----------|")
    for t in [1, 2, 3]:
        key = f"tier_{t}"
        td = by_tier.get(key, {})
        if td:
            lines.append(
                f"| Tier {t} | {td.get('total', 0)} "
                f"| {td.get('convergence_rate', 0):.1%} "
                f"| {td.get('decompose_accuracy', 0):.1%} "
                f"| {td.get('avg_score', 0):.3f} |"
            )
    lines.append("")

    # By Effect Type (in-scope only)
    in_scope_samples = [s for s in samples if s.get("in_scope")]
    lines.append("## By Effect Type (In-Scope Only)\n")
    lines.append("| Type | Samples | Convergence | Accuracy | Avg Score |")
    lines.append("|------|---------|-------------|----------|-----------|")
    for et in ["glow", "ripple", "frosted", "gradient", "flow"]:
        td = by_type.get(et, {})
        if td:
            lines.append(
                f"| {et} | {td.get('total', 0)} "
                f"| {td.get('convergence_rate', 0):.1%} "
                f"| {td.get('decompose_accuracy', 0):.1%} "
                f"| {td.get('avg_score', 0):.3f} |"
            )
    lines.append("")

    # Score Distribution
    in_scope_scores = [s.get("final_score") for s in in_scope_samples if s.get("final_score") is not None]
    lines.append("## Score Distribution (In-Scope)\n")
    lines.append("```")
    lines.append(f"{'Range':<12} | {'Count':>5} | Bar")
    for lo, hi in SCORE_BINS:
        count = sum(1 for sc in in_scope_scores if lo <= sc < hi)
        bar = "█" * count
        label = f"{lo:.1f}-{hi:.1f}"
        lines.append(f"{label:<12} | {count:>5} | {bar}")
    lines.append("```\n")

    # Failed Cases (in-scope)
    failed = [s for s in in_scope_samples if not s.get("converged")]
    if failed:
        lines.append("## Failed Cases (In-Scope)\n")
        lines.append("| ID | Expected | Predicted | Score | Issue |")
        lines.append("|----|----------|-----------|-------|-------|")
        for s in sorted(failed, key=lambda x: x.get("final_score", 0)):
            issue = "Wrong type" if not s.get("decompose_correct") else "Low score"
            pred = s.get("effect_type", "?")
            if len(pred) > 20:
                pred = pred[:20]
            lines.append(
                f"| {s['id']} "
                f"| {s.get('expected_type', '')} "
                f"| {pred} "
                f"| {s.get('final_score', 0):.2f} "
                f"| {issue} |"
            )
        lines.append("")

    # Out-of-scope samples
    oos_samples = [s for s in samples if not s.get("in_scope")]
    if oos_samples:
        lines.append("## Out-of-Scope Samples\n")
        lines.append("| ID | Predicted | Score | Notes |")
        lines.append("|----|-----------|-------|-------|")
        for s in sorted(
            oos_samples, key=lambda x: x.get("final_score", 0), reverse=True
        ):
            pred = s.get("effect_type", "?")
            if len(pred) > 20:
                pred = pred[:20]
            desc = s.get("description", "")
            notes = desc[:40] + "..." if len(desc) > 40 else desc
            lines.append(
                f"| {s['id']} "
                f"| {pred} "
                f"| {s.get('final_score', 0):.2f} "
                f"| {notes} |"
            )
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="VFX-Agent Benchmark Report Generator")
    parser.add_argument("--scored", required=True, help="Path to scored JSON")
    parser.add_argument(
        "--output",
        default=None,
        help="Output Markdown file (default: same dir, .md extension)",
    )
    args = parser.parse_args()

    scored_path = Path(args.scored)
    with open(scored_path) as f:
        scored = json.load(f)

    report = generate_report(scored)

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = scored_path.parent / scored_path.name.replace(
            "_scored.json", ".md"
        )

    with open(output_path, "w") as f:
        f.write(report)

    print(report)
    print(f"\nReport saved to: {output_path}")


if __name__ == "__main__":
    main()
