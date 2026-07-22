#!/usr/bin/env python3
"""VFX-Agent v2.0 codex OD Test Report Generator.

Reads collected v2.0 results (collect_v2_results.py output) + generates
a visual HTML report comparing v2.0 vs v1.0 baseline.

Usage:
    python tests/e2e/generate_v2_report.py [--input /tmp/v2_report_data.json] [--output REPORT.html]
"""
import argparse
import base64
import json
import sys
from datetime import datetime
from html import escape
from pathlib import Path


def status_badge(status: str) -> str:
    colors = {
        "passed": "#16a34a", "acceptable": "#ca8a04", "failed": "#dc2626",
        "timeout": "#7c3aed", "max_iterations": "#ea580c", "missing": "#6b7280",
    }
    color = colors.get(status, "#6b7280")
    return f'<span class="badge" style="background:{color}">{escape(status)}</span>'


def delta_color(delta: float) -> str:
    if delta > 0.05: return "#16a34a"
    if delta > -0.05: return "#6b7280"
    if delta > -0.15: return "#ca8a04"
    return "#dc2626"


def score_tier(score: float) -> str:
    if score >= 0.85: return "PASS"
    if score >= 0.80: return "ACCEPT"
    if score > 0: return "FAIL"
    return "—"


def render_sample_card(sample: dict, backend_name: str = "codex") -> str:
    """One sample's full comparison card."""
    name = sample["sample_name"]
    v1 = sample["v1_baseline"]
    v2 = sample["v2"]
    images = sample["images"]

    v1_score = v1.get("score", -1)
    v2_score = v2.get("score", 0)
    delta = v2_score - v1_score if v1_score >= 0 else 0
    delta_str = f"{delta:+.3f}" if v1_score >= 0 else "n/a"
    delta_c = delta_color(delta)

    v2_status = v2.get("status", "missing")
    v1_status = v1.get("status", "unknown")

    ref_img = images.get("reference")
    render_img = images.get("render")
    ui_pre_img = images.get("ui_pre")
    ui_post_img = images.get("ui_post")

    vd = sample.get("visual_description") or {}
    effect_type = vd.get("effect_type", "?")
    eval_data = sample.get("evaluation") or {}

    visual_issues = eval_data.get("visual_issues", [])[:3]
    correct_aspects = eval_data.get("correct_aspects", [])[:2]

    ref_html = f'<img src="{ref_img}" alt="reference" />' if ref_img else '<div class="img-placeholder">No reference</div>'
    render_html = f'<img src="{render_img}" alt="render" />' if render_img else '<div class="img-placeholder">No render</div>'
    ui_pre_html = f'<img src="{ui_pre_img}" alt="ui_pre" />' if ui_pre_img else '<div class="img-placeholder">No UI pre</div>'
    ui_post_html = f'<img src="{ui_post_img}" alt="ui_post" />' if ui_post_img else '<div class="img-placeholder">No UI post</div>'

    issues_html = "".join(f"<li>{escape(i)}</li>" for i in visual_issues) or "<li class='muted'>(none)</li>"
    correct_html = "".join(f"<li>{escape(i)}</li>" for i in correct_aspects) or "<li class='muted'>(none)</li>"

    shader_lines = v2.get("shader_lines", 0)
    duration = v2.get("duration_s", 0)
    iters = v2.get("iterations", 0)

    return f"""
    <div class="sample-card" id="sample-{escape(name)}">
      <div class="sample-header">
        <h3>{escape(name)}</h3>
        <div class="sample-meta">
          <span class="effect-tag">{escape(effect_type)}</span>
          {status_badge(v2_status)}
        </div>
      </div>
      <div class="sample-scores">
        <div class="score-block">
          <div class="score-label">v1.0 baseline</div>
          <div class="score-value">{v1_score:.3f}</div>
          <div class="score-tier tier-{v1_status}">{v1_status}</div>
        </div>
        <div class="score-block">
          <div class="score-label">v2.0 {backend_name}</div>
          <div class="score-value v2-score">{v2_score:.3f}</div>
          <div class="score-tier tier-{score_tier(v2_score).lower()}">{score_tier(v2_score)}</div>
        </div>
        <div class="score-block">
          <div class="score-label">delta</div>
          <div class="score-value" style="color:{delta_c}">{delta_str}</div>
        </div>
        <div class="score-block">
          <div class="score-label">iters / lines / dur</div>
          <div class="score-value">{iters} / {shader_lines} / {duration}s</div>
        </div>
      </div>
      <div class="image-comparison">
        <div class="image-cell">
          <div class="image-label">Reference</div>
          {ref_html}
        </div>
        <div class="image-cell">
          <div class="image-label">v2.0 Render</div>
          {render_html}
        </div>
      </div>
      <details class="evaluation-details">
        <summary>Frontend UI screenshots (pre / post)</summary>
        <div class="image-comparison">
          <div class="image-cell">
            <div class="image-label">UI before run</div>
            {ui_pre_html}
          </div>
          <div class="image-cell">
            <div class="image-label">UI after run</div>
            {ui_post_html}
          </div>
        </div>
      </details>
      <details class="evaluation-details">
        <summary>Subagent evaluation (8-dim)</summary>
        <div class="eval-grid">
          {render_dimension_scores(eval_data.get("dimension_scores", {}))}
        </div>
        <div class="eval-section">
          <strong>Issues (top 3):</strong>
          <ul>{issues_html}</ul>
        </div>
        <div class="eval-section">
          <strong>Correct aspects (top 2):</strong>
          <ul>{correct_html}</ul>
        </div>
        {render_pixel_evidence(eval_data.get("pixel_evidence"))}
      </details>
    </div>
    """


def render_dimension_scores(dim_scores: dict) -> str:
    if not dim_scores:
        return "<div class='muted'>(no dimension scores)</div>"
    rows = []
    weights = {
        "composition": 0.10, "geometry": 0.15, "lighting": 0.15, "color": 0.15,
        "texture": 0.10, "animation": 0.15, "background": 0.10, "vfx_details": 0.10,
    }
    for dim, data in dim_scores.items():
        score = data.get("score", 0) if isinstance(data, dict) else 0
        weight = weights.get(dim, 0)
        bar_w = int(score * 100)
        bar_color = "#16a34a" if score >= 0.85 else ("#ca8a04" if score >= 0.7 else "#dc2626")
        rows.append(f"""
          <div class="dim-row">
            <div class="dim-name">{escape(dim)} <span class="dim-weight">(w={weight})</span></div>
            <div class="dim-bar"><div class="dim-bar-fill" style="width:{bar_w}%;background:{bar_color}"></div></div>
            <div class="dim-score">{score:.2f}</div>
          </div>
        """)
    return "".join(rows)


def render_pixel_evidence(px: dict | None) -> str:
    if not px:
        return ""
    avg = px.get("avg_color_distance", "?")
    samples = px.get("sample_differences", "")
    # sample_differences may be dict (per-position) or string; coerce to string
    if isinstance(samples, dict):
        samples = "; ".join(f"{k}: {v}" for k, v in samples.items())
    elif not isinstance(samples, str):
        samples = str(samples)
    return f"""
      <div class="eval-section pixel-evidence">
        <strong>Pixel evidence:</strong>
        <div>avg_color_distance = <code>{avg}</code></div>
        <div class="muted small">{escape(samples)}</div>
      </div>
    """


def render_summary_panel(summary: dict) -> str:
    total = summary["total_samples"]
    present = summary["present"]
    passed = summary["passed"]
    v2_avg = summary["v2_avg_score"]
    v1_avg = summary["v1_avg_score"]
    delta = summary["delta_avg"]
    pass_rate = (passed / present * 100) if present else 0
    delta_c = delta_color(delta)

    return f"""
    <section class="summary-panel">
      <h2>📊 Summary</h2>
      <div class="summary-grid">
        <div class="stat-card">
          <div class="stat-label">Samples run</div>
          <div class="stat-value">{present} / {total}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Passed (≥0.85)</div>
          <div class="stat-value">{passed} / {present}</div>
          <div class="stat-sub">{pass_rate:.1f}% pass rate</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">v2.0 avg score</div>
          <div class="stat-value">{v2_avg:.3f}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">v1.0 baseline avg</div>
          <div class="stat-value">{v1_avg:.3f}</div>
        </div>
        <div class="stat-card highlight">
          <div class="stat-label">Δ (v2 − v1)</div>
          <div class="stat-value" style="color:{delta_c}">{delta:+.3f}</div>
          <div class="stat-sub">{'✅ v2.0 leads' if delta > 0 else '⚠️ v2.0 trails' if delta < 0 else '–'}</div>
        </div>
      </div>
    </section>
    """


def render_score_distribution(samples: list) -> str:
    """Score distribution table sorted by v2 score."""
    present = [s for s in samples if s["v2"]["present"]]
    sorted_samples = sorted(present, key=lambda s: s["v2"]["score"], reverse=True)

    rows = []
    for s in sorted_samples:
        name = s["sample_name"]
        v2 = s["v2"]["score"]
        v1 = s["v1_baseline"]["score"]
        delta = v2 - v1 if v1 >= 0 else 0
        delta_c = delta_color(delta)
        delta_str = f"{delta:+.3f}" if v1 >= 0 else "n/a"
        status = s["v2"]["status"]
        vd = s.get("visual_description") or {}
        effect = vd.get("effect_type", "?")

        bar_w = int(v2 * 100)
        bar_color = "#16a34a" if v2 >= 0.85 else ("#ca8a04" if v2 >= 0.7 else "#dc2626")
        v1_bar_w = int(v1 * 100) if v1 >= 0 else 0

        rows.append(f"""
          <tr>
            <td><a href="#sample-{escape(name)}">{escape(name)}</a></td>
            <td><code>{escape(effect)}</code></td>
            <td>{status_badge(status)}</td>
            <td>
              <div class="bar-container">
                <div class="bar bar-v2" style="width:{bar_w}%;background:{bar_color}">{v2:.3f}</div>
              </div>
            </td>
            <td>
              <div class="bar-container">
                <div class="bar bar-v1" style="width:{v1_bar_w}%;background:#94a3b8">{v1:.3f}</div>
              </div>
            </td>
            <td style="color:{delta_c}"><strong>{delta_str}</strong></td>
          </tr>
        """)
    return f"""
    <section class="distribution-panel">
      <h2>📈 Score Distribution (sorted by v2.0 score)</h2>
      <table class="score-table">
        <thead>
          <tr><th>Sample</th><th>Effect</th><th>Status</th><th>v2.0 Score</th><th>v1.0 Baseline</th><th>Δ</th></tr>
        </thead>
        <tbody>
          {''.join(rows)}
        </tbody>
      </table>
    </section>
    """


def _detect_backend_name(samples: list) -> str:
    """Extract backend name from sample data (first sample with backend field)."""
    for s in samples:
        b = s.get("backend")
        if b:
            return b
    return "codex"


def generate_html(data: dict) -> str:
    summary = data["summary"]
    samples = data["samples"]
    backend_name = _detect_backend_name(samples)
    display_name = {"codex": "codex OD", "claude-code": "claude-code", "kimi": "Kimi K3"}.get(backend_name, backend_name)
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Render cards with backend-aware labeling
    cards_html = "".join(render_sample_card(s, backend_name) for s in samples)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>VFX-Agent v2.0 {display_name} — 测试报告</title>
<style>
  :root {{
    --bg: #0f172a;
    --panel: #1e293b;
    --panel-2: #334155;
    --text: #f1f5f9;
    --muted: #94a3b8;
    --accent: #3b82f6;
    --border: #475569;
    --pass: #16a34a;
    --warn: #ca8a04;
    --fail: #dc2626;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
    margin: 0;
    padding: 32px;
    line-height: 1.5;
  }}
  h1 {{ margin: 0 0 8px; font-size: 28px; }}
  h2 {{ margin: 32px 0 16px; font-size: 22px; border-bottom: 1px solid var(--border); padding-bottom: 8px; }}
  h3 {{ margin: 0; font-size: 18px; }}
  .header {{ margin-bottom: 32px; }}
  .header .meta {{ color: var(--muted); font-size: 13px; }}
  .header .subtitle {{ color: var(--accent); margin-top: 4px; }}

  .summary-panel, .distribution-panel {{ margin-bottom: 40px; }}

  .summary-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 16px;
  }}
  .stat-card {{
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px;
  }}
  .stat-card.highlight {{ border-color: var(--accent); }}
  .stat-label {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; }}
  .stat-value {{ font-size: 28px; font-weight: 700; margin-top: 8px; }}
  .stat-sub {{ color: var(--muted); font-size: 12px; margin-top: 4px; }}

  table.score-table {{
    width: 100%;
    border-collapse: collapse;
    background: var(--panel);
    border-radius: 8px;
    overflow: hidden;
  }}
  .score-table th, .score-table td {{
    padding: 10px 12px;
    text-align: left;
    border-bottom: 1px solid var(--border);
  }}
  .score-table th {{ background: var(--panel-2); font-weight: 600; font-size: 13px; }}
  .score-table tr:last-child td {{ border-bottom: none; }}
  .score-table a {{ color: var(--accent); text-decoration: none; }}
  .score-table a:hover {{ text-decoration: underline; }}

  .bar-container {{ min-width: 140px; height: 22px; background: rgba(0,0,0,0.3); border-radius: 4px; position: relative; overflow: hidden; }}
  .bar {{ height: 100%; display: flex; align-items: center; padding: 0 8px; color: white; font-size: 11px; font-weight: 600; }}

  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; color: white; font-size: 11px; font-weight: 600; text-transform: uppercase; }}
  .effect-tag {{ display: inline-block; padding: 2px 8px; border-radius: 4px; background: var(--panel-2); color: var(--muted); font-size: 11px; font-family: monospace; }}

  .sample-card {{
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 24px;
  }}
  .sample-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }}
  .sample-meta {{ display: flex; gap: 8px; align-items: center; }}
  .sample-scores {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px; }}
  .score-block {{ background: var(--panel-2); border-radius: 6px; padding: 12px; text-align: center; }}
  .score-label {{ color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; }}
  .score-value {{ font-size: 22px; font-weight: 700; margin-top: 4px; }}
  .v2-score {{ color: var(--accent); }}
  .score-tier {{ font-size: 10px; color: var(--muted); margin-top: 4px; text-transform: uppercase; }}
  .tier-passed, .tier-pass {{ color: var(--pass); }}
  .tier-failed, .tier-fail {{ color: var(--fail); }}
  .tier-acceptable, .tier-accept {{ color: var(--warn); }}

  .image-comparison {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 12px; }}
  .image-cell {{ background: var(--panel-2); border-radius: 6px; padding: 8px; }}
  .image-label {{ color: var(--muted); font-size: 11px; text-transform: uppercase; margin-bottom: 6px; }}
  .image-cell img {{ width: 100%; height: auto; display: block; border-radius: 4px; background: #000; }}
  .img-placeholder {{ padding: 60px 20px; text-align: center; color: var(--muted); background: rgba(0,0,0,0.3); border-radius: 4px; }}

  details.evaluation-details {{ background: var(--panel-2); border-radius: 6px; padding: 12px; }}
  details.evaluation-details summary {{ cursor: pointer; font-weight: 600; color: var(--accent); }}
  .eval-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin: 12px 0; }}
  .dim-row {{ display: grid; grid-template-columns: 130px 1fr 40px; align-items: center; gap: 8px; font-size: 12px; }}
  .dim-name {{ color: var(--text); }}
  .dim-weight {{ color: var(--muted); font-size: 10px; }}
  .dim-bar {{ height: 14px; background: rgba(0,0,0,0.3); border-radius: 3px; overflow: hidden; }}
  .dim-bar-fill {{ height: 100%; }}
  .dim-score {{ font-weight: 600; text-align: right; }}
  .eval-section {{ margin-top: 10px; font-size: 12px; }}
  .eval-section ul {{ margin: 4px 0; padding-left: 20px; }}
  .eval-section li {{ margin: 2px 0; }}
  .pixel-evidence {{ background: rgba(0,0,0,0.2); padding: 8px; border-radius: 4px; }}
  .pixel-evidence code {{ background: var(--bg); padding: 2px 6px; border-radius: 3px; color: var(--accent); }}

  .muted {{ color: var(--muted); }}
  .small {{ font-size: 11px; }}
  code {{ font-family: "SF Mono", Menlo, monospace; font-size: 12px; }}

  @media (max-width: 800px) {{
    .image-comparison, .sample-scores, .eval-grid {{ grid-template-columns: 1fr; }}
  }}
</style>
</head>
<body>
  <div class="header">
    <h1>VFX-Agent v2.0 {display_name} — 全样本测试报告</h1>
    <div class="subtitle">Backend: {backend_name} with 6-phase workflow + isolated subagent evaluator</div>
    <div class="meta">
      Generated: {generated}<br>
      Compare against: <a href="../../test_results/2026-05-18_e2e-v2-baseline-19samples/index.html">v1.0 V2 baseline (2026-05-18)</a>
    </div>
  </div>

  {render_summary_panel(summary)}

  {render_score_distribution(samples)}

  <section>
    <h2>🎨 Per-Sample Comparison</h2>
    {cards_html}
  </section>

  <footer style="margin-top:40px;padding-top:20px;border-top:1px solid var(--border);color:var(--muted);font-size:12px;">
    Generated by <code>backend/tests/e2e/generate_v2_report.py</code>.
    Source data: <code>collect_v2_results.py</code> output.
    v2.0 architecture: {display_name} backend with 6-phase workflow + isolated subagent evaluator.
  </footer>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="/tmp/v2_report_data.json")
    parser.add_argument("--output", default=None,
                        help="Output HTML path (default: backend/test_results/<auto>/index.html)")
    args = parser.parse_args()

    data = json.loads(Path(args.input).read_text())

    # Auto-name output dir by date + sample count + backend
    if args.output is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
        num_samples = len(data.get("samples", []))
        backend_name = _detect_backend_name(data.get("samples", []))
        archive_suffix = "codex-od" if backend_name == "codex" else backend_name
        out_dir = Path("test_results") / f"{date_str}_v2-{archive_suffix}-{num_samples}samples"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "index.html"
    else:
        out_path = Path(args.output)

    html = generate_html(data)
    out_path.write_text(html)
    print(f"[report] Wrote {out_path} ({len(html)} bytes, {len(data['samples'])} samples)")


if __name__ == "__main__":
    main()
