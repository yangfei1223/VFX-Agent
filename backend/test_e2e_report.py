#!/usr/bin/env python3
"""VFX-Agent E2E Test HTML Report Generator

Reads test results and sample classifications, generates a visual HTML report
with reference vs rendered screenshot comparisons.

Usage:
    python test_e2e_report.py
"""

import base64
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

RESULTS_DIR = Path(__file__).parent / "test_e2e_results"
CLASSIFICATIONS_FILE = RESULTS_DIR / "sample_classifications.json"
TEST_RESULTS_FILE = RESULTS_DIR / "test_results.json"
REPORT_FILE = RESULTS_DIR / "index.html"


def load_data():
    classifications = {}
    if CLASSIFICATIONS_FILE.exists():
        classifications = json.loads(CLASSIFICATIONS_FILE.read_text())
    
    test_results = {}
    if TEST_RESULTS_FILE.exists():
        test_results = json.loads(TEST_RESULTS_FILE.read_text())
    
    return classifications, test_results


def encode_image(path: str) -> str | None:
    p = Path(path)
    if not p.exists():
        return None
    data = p.read_bytes()
    return f"data:image/png;base64,{base64.b64encode(data).decode()}"


def get_sample_images(sample_name: str):
    """Get reference and rendered images for a sample"""
    sample_dir = RESULTS_DIR / sample_name
    
    ref = encode_image(str(sample_dir / "reference_frame.png")) if (sample_dir / "reference_frame.png").exists() else None
    
    renders = []
    for f in sorted(sample_dir.glob("render_*.png")):
        renders.append(encode_image(str(f)))
    
    # Also check classification frame
    class_frame = encode_image(str(Path("/tmp/vfx-frames") / f"{sample_name}.png"))
    
    return ref or class_frame, renders


def generate_html(classifications: dict, test_results: dict) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # === Stats ===
    total = len(test_results)
    statuses = Counter(r.get("status", "unknown") for r in test_results.values())
    scores = [(n, r.get("score", 0)) for n, r in test_results.items() if r.get("score", 0) > 0]
    avg_score = sum(s for _, s in scores) / len(scores) if scores else 0
    
    all_issues = []
    for name, r in test_results.items():
        for issue in r.get("issues", []):
            all_issues.append((name, issue))
    
    issue_by_id = Counter(iid for _, i in all_issues for iid in [i["id"]])
    issue_by_severity = Counter(i.get("severity", "?") for _, i in all_issues)
    issue_by_stage = Counter(i.get("id", "?")[0] for _, i in all_issues)
    
    # By category
    cat_results = defaultdict(list)
    for name, r in test_results.items():
        cat = classifications.get(name, {}).get("effect_category", "unknown")
        cat_results[cat].append(r)
    
    # === Build HTML ===
    sections = []
    
    # --- Header ---
    sections.append(f"""
    <div class="header">
        <h1>VFX-Agent E2E Test Report</h1>
        <p>Generated: {now} | Samples: {total} | Avg Score: {avg_score:.2f}</p>
    </div>""")
    
    # --- Overview Dashboard ---
    status_rows = "".join(f'<div class="stat-card"><div class="stat-value">{cnt}</div><div class="stat-label">{s}</div></div>' for s, cnt in statuses.most_common())
    
    cat_rows = ""
    for cat in sorted(cat_results.keys()):
        results_list = cat_results[cat]
        cat_scores = [r.get("score", 0) for r in results_list if r.get("score", 0) > 0]
        cat_avg = sum(cat_scores) / len(cat_scores) if cat_scores else 0
        cat_rows += f'<tr><td>{cat}</td><td>{len(results_list)}</td><td>{cat_avg:.2f}</td></tr>'
    
    issue_rows = ""
    for iid, cnt in issue_by_id.most_common(15):
        severity = "?"
        for _, i in all_issues:
            if i["id"] == iid:
                severity = i.get("severity", "?")
                break
        color = {"P0": "#ff4444", "P1": "#ff8800", "P2": "#ffcc00", "P3": "#44bb44"}.get(severity, "#999")
        issue_rows += f'<tr><td><span class="badge" style="background:{color}">{severity}</span></td><td>{iid}</td><td>{cnt}</td></tr>'
    
    sections.append(f"""
    <div class="dashboard">
        <h2>Overview</h2>
        <div class="stats-row">{status_rows}</div>
        
        <div class="two-col">
            <div>
                <h3>Score by Category</h3>
                <table><tr><th>Category</th><th>Count</th><th>Avg Score</th></tr>{cat_rows}</table>
            </div>
            <div>
                <h3>Top Issues</h3>
                <table><tr><th>Sev</th><th>Issue ID</th><th>Count</th></tr>{issue_rows}</table>
            </div>
        </div>
    </div>""")
    
    # --- Per-sample details ---
    sample_cards = ""
    for name in sorted(test_results.keys()):
        r = test_results[name]
        cls = classifications.get(name, {})
        ref_img, render_imgs = get_sample_images(name)
        
        status = r.get("status", "?")
        score = r.get("score", 0)
        iteration = r.get("iteration", 0)
        elapsed = r.get("elapsed_seconds", 0)
        effect_type = r.get("effect_type", "") or cls.get("effect_category", "?")
        issues = r.get("issues", [])
        
        status_color = {"passed": "#4caf50", "max_iterations": "#ff9800", "failed": "#f44336", "timeout": "#9c27b0"}.get(status, "#999")
        
        ref_img_tag = f'<img src="{ref_img}" loading="lazy">' if ref_img else '<div class="no-img">No ref</div>'
        render_tags = "".join(f'<img src="{img}" loading="lazy">' for img in render_imgs[:2]) if render_imgs else '<div class="no-img">No render</div>'
        
        issue_tags = ""
        for iss in issues:
            sev = iss.get("severity", "?")
            color = {"P0": "#ff4444", "P1": "#ff8800", "P2": "#ffcc00"}.get(sev, "#999")
            issue_tags += f'<span class="badge" style="background:{color}" title="{iss.get("desc","")}">{iss["id"]}</span> '
        
        sample_cards += f"""
        <div class="sample-card" id="{name}">
            <div class="sample-header">
                <h3>{name}</h3>
                <div>
                    <span class="badge" style="background:{status_color}">{status}</span>
                    <span class="badge">score: {score:.2f}</span>
                    <span class="badge">iter: {iteration}</span>
                    <span class="badge">{elapsed}s</span>
                </div>
            </div>
            <div class="sample-body">
                <div class="sample-images">
                    <div class="img-group"><div class="img-label">Reference</div>{ref_img_tag}</div>
                    <div class="img-group"><div class="img-label">Rendered</div>{render_tags}</div>
                </div>
                <div class="sample-meta">
                    <p><b>Category:</b> {cls.get('effect_category', '?')} | <b>Expected:</b> {cls.get('effect_name', '?')}</p>
                    <p><b>Decompose effect_type:</b> {effect_type or 'N/A'}</p>
                    <p><b>Complexity:</b> {cls.get('complexity', '?')} | <b>is_2d:</b> {cls.get('is_2d', '?')} | <b>fill_type:</b> {cls.get('fill_type', '?')}</p>
                    {f'<p><b>Issues:</b> {issue_tags}</p>' if issues else ''}
                    {f'<p class="cls-desc">{cls.get("visual_description", "")}</p>' if cls.get("visual_description") else ''}
                </div>
            </div>
        </div>"""
    
    sections.append(f"""
    <div class="samples">
        <h2>Sample Details ({total})</h2>
        {sample_cards}
    </div>""")
    
    # --- Score bar chart (simple CSS) ---
    sorted_scores = sorted(scores, key=lambda x: x[1], reverse=True)
    score_bars = ""
    max_score = max(s for _, s in scores) if scores else 1
    for name, score in sorted_scores:
        width = (score / max_score * 100) if max_score > 0 else 0
        color = "#4caf50" if score >= 0.7 else "#ff9800" if score >= 0.4 else "#f44336"
        score_bars += f'<div class="bar-row"><span class="bar-label">{name}</span><div class="bar" style="width:{width}%;background:{color}">{score:.2f}</div></div>'
    
    sections.append(f"""
    <div class="scores">
        <h2>Score Ranking</h2>
        <div class="bar-chart">{score_bars}</div>
    </div>""")
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>VFX-Agent E2E Test Report</title>
<style>
:root {{ --bg: #0d1117; --card: #161b22; --border: #30363d; --text: #e6edf3; --text2: #8b949e; --accent: #58a6ff; }}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); padding: 20px; max-width: 1400px; margin: 0 auto; }}
.header {{ text-align: center; padding: 30px 0; border-bottom: 1px solid var(--border); margin-bottom: 30px; }}
.header h1 {{ font-size: 28px; margin-bottom: 8px; }}
.header p {{ color: var(--text2); }}
h2 {{ font-size: 20px; margin-bottom: 16px; color: var(--accent); }}
h3 {{ font-size: 16px; margin-bottom: 8px; }}
.stats-row {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 24px; }}
.stat-card {{ background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 16px 24px; text-align: center; min-width: 100px; }}
.stat-value {{ font-size: 28px; font-weight: bold; color: var(--accent); }}
.stat-label {{ font-size: 12px; color: var(--text2); margin-top: 4px; }}
.two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 24px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th, td {{ padding: 6px 10px; border-bottom: 1px solid var(--border); text-align: left; }}
th {{ color: var(--text2); font-weight: 500; }}
.badge {{ display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; margin: 1px 2px; background: #30363d; color: #fff; }}
.sample-card {{ background: var(--card); border: 1px solid var(--border); border-radius: 8px; margin-bottom: 16px; overflow: hidden; }}
.sample-header {{ display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; border-bottom: 1px solid var(--border); }}
.sample-header h3 {{ margin: 0; }}
.sample-body {{ padding: 16px; }}
.sample-images {{ display: flex; gap: 16px; margin-bottom: 12px; }}
.img-group {{ flex: 1; }}
.img-label {{ font-size: 11px; color: var(--text2); margin-bottom: 4px; text-transform: uppercase; }}
.img-group img {{ width: 100%; border-radius: 4px; border: 1px solid var(--border); }}
.no-img {{ background: var(--border); border-radius: 4px; height: 150px; display: flex; align-items: center; justify-content: center; color: var(--text2); }}
.sample-meta {{ font-size: 13px; color: var(--text2); }}
.sample-meta p {{ margin: 4px 0; }}
.sample-meta b {{ color: var(--text); }}
.cls-desc {{ font-style: italic; color: var(--text2); margin-top: 8px; }}
.bar-chart {{ max-width: 800px; }}
.bar-row {{ display: flex; align-items: center; margin: 4px 0; }}
.bar-label {{ width: 200px; font-size: 12px; text-align: right; padding-right: 10px; flex-shrink: 0; overflow: hidden; text-overflow: ellipsis; }}
.bar {{ height: 20px; border-radius: 3px; min-width: 40px; display: flex; align-items: center; padding-left: 8px; font-size: 11px; color: #fff; }}
.dashboard, .samples, .scores {{ margin-bottom: 40px; }}
</style>
</head>
<body>
{"".join(sections)}
</body>
</html>"""
    
    return html


def main():
    classifications, test_results = load_data()
    
    if not test_results:
        print("No test results found. Run test_e2e_batch.py first.")
        sys.exit(1)
    
    print(f"Generating report from {len(test_results)} test results...")
    
    html = generate_html(classifications, test_results)
    REPORT_FILE.write_text(html)
    
    print(f"Report saved to: {REPORT_FILE}")
    
    # Quick summary
    statuses = Counter(r.get("status") for r in test_results.values())
    scores = [r.get("score", 0) for r in test_results.values() if r.get("score", 0) > 0]
    print(f"\nSummary:")
    for s, c in statuses.most_common():
        print(f"  {s}: {c}")
    if scores:
        print(f"  Avg score: {sum(scores)/len(scores):.2f}")
    
    # Auto-open
    import subprocess
    subprocess.run(["open", str(REPORT_FILE)])


if __name__ == "__main__":
    main()
