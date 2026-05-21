#!/usr/bin/env python3
"""单样本端到端管线测试 + HTML 报告生成

使用方法:
    python test_e2e_single.py auroras
    python test_e2e_single.py auroras --max-iter 3
    python test_e2e_single.py cool-s-distance --threshold 0.85
"""

import sys
import json
import time
import base64
import argparse
from pathlib import Path
from urllib.parse import quote

import requests

BASE_URL = "http://localhost:8000"
SAMPLES_DIR = Path("/Users/yangfei/Code/VFX-Agent/test-samples")
REPORT_DIR = Path("/Users/yangfei/Code/VFX-Agent/backend/test_e2e_reports")


def run_single_sample(sample_name: str, max_iter: int = 3, threshold: float = 0.85):
    """运行单样本端到端测试，返回完整状态数据"""
    
    # 查找样本文件
    video_file = SAMPLES_DIR / f"{sample_name}.webm"
    image_file = SAMPLES_DIR / f"{sample_name}.png"
    desc_file = SAMPLES_DIR / f"{sample_name}.json"
    
    if not video_file.exists() and not image_file.exists():
        print(f"❌ Sample not found: {sample_name}")
        sys.exit(1)
    
    # 读取描述
    description = ""
    if desc_file.exists():
        with open(desc_file) as f:
            meta = json.load(f)
            description = meta.get("visual_description", "")
    print(f"📝 Description: {description[:80]}...")
    
    # 提交管线
    print(f"\n🚀 Submitting pipeline for '{sample_name}' (max_iter={max_iter}, threshold={threshold})...")
    
    files = {}
    if video_file.exists():
        files["video"] = (video_file.name, open(video_file, "rb"), "video/webm")
        print(f"  Video: {video_file.name}")
    elif image_file.exists():
        files["images"] = (image_file.name, open(image_file, "rb"), "image/png")
        print(f"  Image: {image_file.name}")
    
    data = {
        "notes": description,
        "max_iterations": max_iter,
        "passing_threshold": threshold,
    }
    
    resp = requests.post(f"{BASE_URL}/pipeline/run", files=files, data=data)
    
    # Close file handles
    for f in files.values():
        f[1].close()
    
    if resp.status_code != 200:
        print(f"❌ Pipeline submission failed: {resp.status_code} {resp.text}")
        sys.exit(1)
    
    result = resp.json()
    pipeline_id = result.get("pipeline_id")
    print(f"  Pipeline ID: {pipeline_id}")
    
    # 轮询等待完成
    print(f"\n⏳ Waiting for pipeline to complete...")
    start_time = time.time()
    last_phase = None
    
    while True:
        time.sleep(1)
        status_resp = requests.get(f"{BASE_URL}/pipeline/status/{pipeline_id}")
        if status_resp.status_code != 200:
            print(f"  ⚠️ Status check failed: {status_resp.status_code}")
            time.sleep(2)
            continue
        
        state = status_resp.json()
        current_phase = state.get("current_phase", "")
        phase_status = state.get("phase_status", "")
        iteration = state.get("snapshot", {}).get("iteration", 0)
        status = state.get("status", "running")
        
        if current_phase != last_phase:
            elapsed = time.time() - start_time
            print(f"  [{elapsed:.0f}s] Phase: {current_phase} ({phase_status}) iter={iteration}")
            last_phase = current_phase
        
        if status not in ("running",):
            elapsed = time.time() - start_time
            print(f"\n  ✅ Pipeline finished: {status} in {elapsed:.0f}s")
            break
    
    return state, pipeline_id


def generate_html_report(state: dict, sample_name: str, pipeline_id: str):
    """生成包含所有中间数据的 HTML 报告"""
    
    snapshot = state.get("snapshot", {})
    baseline = state.get("baseline", {})
    
    # 收集所有数据
    report_dir = REPORT_DIR / sample_name
    report_dir.mkdir(parents=True, exist_ok=True)
    
    # === 收集图片数据 ===
    def image_to_data_url(path_or_none):
        if not path_or_none or not Path(path_or_none).exists():
            return ""
        with open(path_or_none, "rb") as f:
            data = base64.b64encode(f.read()).decode()
        return f"data:image/png;base64,{data}"
    
    # 参考帧
    ref_images = baseline.get("keyframe_paths", []) + baseline.get("image_paths", [])
    ref_data_urls = [image_to_data_url(p) for p in ref_images]
    
    # 渲染帧
    render_images = snapshot.get("render_screenshots", [])
    render_data_urls = [image_to_data_url(p) for p in render_images]
    
    # CV 特征
    cv_features = baseline.get("cv_features", {})
    
    # CV 对比
    cv_comparison = snapshot.get("cv_comparison", {})
    
    # Visual Description
    visual_description = snapshot.get("visual_description", {})
    
    # Shader
    shader = snapshot.get("shader", "")
    
    # Inspect feedback
    inspect_feedback = snapshot.get("inspect_feedback", {})
    
    # Gradient window
    gradient_window = state.get("gradient_window", [])
    
    # Pipeline logs
    logs = state.get("detailed_logs", [])
    
    # Status
    status = state.get("status", "?")
    iteration = snapshot.get("iteration", 0)
    passed = state.get("passed", False)
    score = inspect_feedback.get("overall_score", 0) if inspect_feedback else 0
    
    # 生成 HTML
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>E2E Report: {sample_name}</title>
<style>
:root {{
    --bg: #0f172a;
    --card: #1e293b;
    --border: #334155;
    --text: #e2e8f0;
    --muted: #94a3b8;
    --accent: #38bdf8;
    --green: #4ade80;
    --red: #f87171;
    --yellow: #fbbf24;
    --purple: #a78bfa;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ 
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: var(--bg); color: var(--text); 
    line-height: 1.6;
    padding: 20px;
}}
.container {{ max-width: 1400px; margin: 0 auto; }}
h1 {{ font-size: 24px; margin-bottom: 8px; }}
h2 {{ font-size: 18px; color: var(--accent); margin: 24px 0 12px; border-bottom: 1px solid var(--border); padding-bottom: 8px; }}
h3 {{ font-size: 14px; color: var(--muted); margin: 16px 0 8px; text-transform: uppercase; letter-spacing: 1px; }}
.grid {{ display: grid; gap: 16px; }}
.grid-2 {{ grid-template-columns: 1fr 1fr; }}
.grid-3 {{ grid-template-columns: 1fr 1fr 1fr; }}
.card {{ 
    background: var(--card); border: 1px solid var(--border); border-radius: 12px; 
    padding: 16px; 
}}
.badge {{
    display: inline-block; padding: 4px 12px; border-radius: 20px;
    font-size: 13px; font-weight: 600;
}}
.badge-pass {{ background: #065f46; color: var(--green); }}
.badge-fail {{ background: #7f1d1d; color: var(--red); }}
.badge-running {{ background: #78350f; color: var(--yellow); }}
.score {{ font-size: 48px; font-weight: 700; }}
.score-high {{ color: var(--green); }}
.score-mid {{ color: var(--yellow); }}
.score-low {{ color: var(--red); }}
.stat {{ text-align: center; }}
.stat-label {{ font-size: 12px; color: var(--muted); text-transform: uppercase; }}
.stat-value {{ font-size: 20px; font-weight: 600; }}
img.ref-img {{ 
    max-width: 100%; max-height: 300px; border-radius: 8px; 
    border: 1px solid var(--border); object-fit: contain;
    background: #000;
}}
pre {{ 
    background: #0d1117; border: 1px solid var(--border); border-radius: 8px;
    padding: 12px; font-size: 12px; overflow-x: auto; white-space: pre-wrap;
    font-family: 'SF Mono', 'Fira Code', monospace;
}}
.json-key {{ color: var(--accent); }}
.json-str {{ color: var(--green); }}
.json-num {{ color: var(--yellow); }}
.log-entry {{ 
    padding: 8px 12px; border-left: 3px solid var(--border); margin: 4px 0;
    background: rgba(255,255,255,0.02); border-radius: 0 8px 8px 0;
    font-size: 13px;
}}
.log-entry.completed {{ border-left-color: var(--green); }}
.log-entry.failed {{ border-left-color: var(--red); }}
.log-entry.started {{ border-left-color: var(--yellow); }}
.cv-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }}
.cv-item {{ background: rgba(255,255,255,0.03); border-radius: 8px; padding: 12px; }}
.cv-item-title {{ font-size: 13px; color: var(--accent); font-weight: 600; margin-bottom: 6px; }}
.cv-item-value {{ font-size: 13px; color: var(--text); }}
.color-swatch {{
    display: inline-block; width: 16px; height: 16px; border-radius: 4px;
    vertical-align: middle; margin-right: 6px; border: 1px solid var(--border);
}}
.metric-bar-container {{ background: #0d1117; border-radius: 4px; height: 20px; overflow: hidden; position: relative; }}
.metric-bar {{ height: 100%; border-radius: 4px; transition: width 0.3s; }}
.metric-bar-label {{ position: absolute; right: 8px; top: 2px; font-size: 11px; font-weight: 600; }}
.timeline {{ position: relative; padding-left: 24px; }}
.timeline::before {{ content: ''; position: absolute; left: 8px; top: 0; bottom: 0; width: 2px; background: var(--border); }}
.timeline-item {{ position: relative; margin-bottom: 12px; }}
.timeline-item::before {{ 
    content: ''; position: absolute; left: -20px; top: 6px; width: 10px; height: 10px; 
    border-radius: 50%; background: var(--accent); border: 2px solid var(--bg);
}}
</style>
</head>
<body>
<div class="container">

<!-- Header -->
<h1>🧪 E2E Pipeline Report: <span style="color:var(--accent)">{sample_name}</span></h1>
<p style="color:var(--muted)">Pipeline ID: {pipeline_id} · Generated at {time.strftime('%Y-%m-%d %H:%M:%S')}</p>

<!-- Summary -->
<div class="grid grid-3" style="margin-top:20px">
    <div class="card stat">
        <div class="stat-label">Status</div>
        <div style="margin-top:8px">
            <span class="badge {'badge-pass' if passed else 'badge-fail'}">
                {'✅ PASSED' if passed else '❌ ' + status.upper()}
            </span>
        </div>
    </div>
    <div class="card stat">
        <div class="stat-label">Final Score</div>
        <div class="score {'score-high' if score >= 0.85 else ('score-mid' if score >= 0.7 else 'score-low')}">
            {score:.2f}
        </div>
    </div>
    <div class="card stat">
        <div class="stat-label">Iterations</div>
        <div class="stat-value">{iteration}</div>
    </div>
</div>

<!-- Images Comparison -->
<h2>🖼️ Image Comparison</h2>
<div class="grid grid-2">
    <div class="card">
        <h3>Reference (Input)</h3>
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px">
            {"".join(f'<img class="ref-img" src="{url}" />' for url in ref_data_urls if url)}
        </div>
    </div>
    <div class="card">
        <h3>Rendered Output</h3>
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px">
            {"".join(f'<img class="ref-img" src="{url}" />' for url in render_data_urls if url)}
        </div>
    </div>
</div>

<!-- Visual Description -->
<h2>📋 Visual Description (DSL)</h2>
<div class="card">
    <pre>{_format_json(visual_description)}</pre>
</div>

<!-- CV Features -->
<h2>🔬 CV Features (Reference Frame)</h2>
{_render_cv_features(cv_features)}

<!-- CV Comparison -->
<h2>📊 CV Comparison (Semantic)</h2>
{_render_cv_comparison(cv_comparison)}

<!-- Shader Code -->
<h2>💻 Generated Shader</h2>
<div class="card">
    <pre><code>{_escape_html(shader)}</code></pre>
</div>

<!-- Inspect Feedback -->
<h2>🔍 Inspect Feedback</h2>
<div class="card">
    {_render_inspect_feedback(inspect_feedback)}
</div>

<!-- Gradient Window -->
<h2>📈 Iteration History</h2>
<div class="card">
    {_render_gradient_window(gradient_window)}
</div>

<!-- Pipeline Logs -->
<h2>📝 Pipeline Logs</h2>
<div class="card">
    <div style="max-height:400px;overflow-y:auto">
        {_render_logs(logs)}
    </div>
</div>

</div>
</body>
</html>
"""
    
    report_path = report_dir / "report.html"
    report_path.write_text(html, encoding="utf-8")
    print(f"\n📄 Report saved to: {report_path}")
    return str(report_path)


def _format_json(obj) -> str:
    if not obj:
        return "(empty)"
    try:
        formatted = json.dumps(obj, indent=2, ensure_ascii=False)
        # Syntax highlight
        import re
        formatted = re.sub(r'"([^"]+)":', r'<span class="json-key">"\1"</span>:', formatted)
        formatted = re.sub(r': "([^"]*)"', r': <span class="json-str">"\1"</span>', formatted)
        formatted = re.sub(r': (\d+\.?\d*)', r': <span class="json-num">\1</span>', formatted)
        return formatted
    except:
        return str(obj)


def _escape_html(text) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _render_cv_features(cv_features: dict) -> str:
    if not cv_features:
        return '<div class="card"><p style="color:var(--muted)">No CV features extracted</p></div>'
    
    primary = cv_features.get("primary", cv_features)
    cards = []
    
    # Color
    color = primary.get("color", {})
    if color:
        palette_html = ""
        for c in color.get("palette", [])[:5]:
            rgb = c.get("rgb", [0,0,0])
            palette_html += f'<span class="color-swatch" style="background:rgb({rgb[0]},{rgb[1]},{rgb[2]})"></span>'
            palette_html += f'{c.get("hex","")} ({c.get("percentage",0)}%)<br>'
        
        grad = color.get("gradient", {})
        subj = color.get("subject_color", {})
        bg = color.get("background_color", {})
        
        cards.append(f"""
        <div class="cv-item">
            <div class="cv-item-title">🎨 Color</div>
            <div class="cv-item-value">
                <b>Palette:</b><br>{palette_html}
                <b>Gradient:</b> {grad.get('type','?')} {grad.get('direction','')} (strength={grad.get('strength',0)})<br>
                <b>Subject:</b> RGB{subj.get('rgb',[])} ({subj.get('percentage',0)}%)<br>
                <b>Background:</b> RGB{bg.get('rgb',[])} ({bg.get('percentage',0)}%)
            </div>
        </div>""")
    
    # Geometry
    geo = primary.get("geometry", {})
    if geo:
        edges = geo.get("edges", {})
        shape = geo.get("shape", {})
        fill = geo.get("fill", {})
        cards.append(f"""
        <div class="cv-item">
            <div class="cv-item-title">📐 Geometry</div>
            <div class="cv-item-value">
                <b>Edges:</b> density={edges.get('density',0):.3f} sharpness={edges.get('sharpness','?')} angle={edges.get('dominant_angle','?')}<br>
                <b>Shape:</b> circularity={shape.get('circularity',0)} convexity={shape.get('convexity',0)} type={shape.get('estimated_type','?')}<br>
                <b>Fill:</b> ratio={fill.get('edge_interior_ratio',0):.3f} → {fill.get('estimated_fill','?')}
            </div>
        </div>""")
    
    # Luminance
    lum = primary.get("luminance", {})
    if lum:
        dist = lum.get("distribution", {})
        glow = lum.get("glow", {})
        glow_text = ""
        if glow.get("detected"):
            glow_text = f"<b>Glow:</b> center={glow.get('center',[])} radius={glow.get('radius',0)} intensity={glow.get('intensity',0):.1f}x ✅<br>"
        else:
            glow_text = "<b>Glow:</b> Not detected<br>"
        
        cards.append(f"""
        <div class="cv-item">
            <div class="cv-item-title">💡 Luminance</div>
            <div class="cv-item-value">
                <b>Distribution:</b> mean={dist.get('mean',0):.2f} std={dist.get('std',0):.2f} type={dist.get('distribution','?')}<br>
                {glow_text}
                <b>Peaks:</b> {dist.get('peaks',[])}
            </div>
        </div>""")
    
    # Frequency
    freq = primary.get("frequency", {})
    if freq:
        cards.append(f"""
        <div class="cv-item">
            <div class="cv-item-title">🌊 Frequency</div>
            <div class="cv-item-value">
                <b>Texture:</b> {freq.get('texture_level','?')}<br>
                <b>High freq ratio:</b> {freq.get('high_freq_ratio',0):.3f}<br>
                <b>Direction:</b> {freq.get('dominant_direction','?')}
            </div>
        </div>""")
    
    # Spatial
    spatial = primary.get("spatial", {})
    if spatial:
        subj = spatial.get("subject", {})
        cards.append(f"""
        <div class="cv-item">
            <div class="cv-item-title">📍 Spatial</div>
            <div class="cv-item-value">
                <b>Center:</b> ({subj.get('center',[0,0])[0]:.2f}, {subj.get('center',[0,0])[1]:.2f})<br>
                <b>Area:</b> {subj.get('area_pct',0)}%
            </div>
        </div>""")
    
    return f'<div class="card"><div class="cv-grid">{"".join(cards)}</div></div>'


def _render_cv_comparison(cv_comparison: dict) -> str:
    if not cv_comparison:
        return '<div class="card"><p style="color:var(--muted)">No CV comparison data</p></div>'
    
    items = []
    
    def metric_bar(value, max_val=1.0, label="", color="var(--accent)"):
        pct = min(value / max_val * 100, 100)
        return f"""
        <div style="margin:4px 0">
            <div style="display:flex;justify-content:space-between;font-size:12px">
                <span>{label}</span><span>{value:.3f}</span>
            </div>
            <div class="metric-bar-container">
                <div class="metric-bar" style="width:{pct}%;background:{color}"></div>
            </div>
        </div>"""
    
    # Color
    color = cv_comparison.get("color", {})
    if color:
        sim = color.get("distribution_similarity", 0)
        overlap = color.get("palette_overlap", 0)
        bar_color = "var(--green)" if sim > 0.8 else ("var(--yellow)" if sim > 0.6 else "var(--red)")
        items.append(f"""
        <div class="cv-item">
            <div class="cv-item-title">🎨 Color & Tone</div>
            {metric_bar(sim, label="Distribution Similarity", color=bar_color)}
            {metric_bar(overlap, label="Palette Overlap", color="var(--purple)")}
            <div style="font-size:12px;margin-top:4px;color:var(--muted)">
                Dominant: {color.get('dominant_color_match','?')} (dist={color.get('dominant_color_dist',0):.0f})<br>
                {color.get('diff_detail','')}
            </div>
        </div>""")
    
    # Luminance
    lum = cv_comparison.get("luminance", {})
    if lum:
        sim = lum.get("distribution_similarity", 0)
        bar_color = "var(--green)" if sim > 0.8 else ("var(--yellow)" if sim > 0.6 else "var(--red)")
        items.append(f"""
        <div class="cv-item">
            <div class="cv-item-title">💡 Lighting</div>
            {metric_bar(sim, label="Distribution Similarity", color=bar_color)}
            <div style="font-size:12px;margin-top:4px;color:var(--muted)">
                Mean diff: {lum.get('mean_diff',0):+.3f} · Highlight diff: {lum.get('highlight_area_diff',0):+.3f}<br>
                {lum.get('diff_detail','')}
            </div>
        </div>""")
    
    # Texture
    tex = cv_comparison.get("texture", {})
    if tex:
        match = tex.get("overall_match", "?")
        match_color = {"good": "var(--green)", "acceptable": "var(--yellow)", "poor": "var(--red)"}.get(match, "var(--muted)")
        items.append(f"""
        <div class="cv-item">
            <div class="cv-item-title">🌊 Texture</div>
            <div style="font-size:14px;margin:4px 0">
                <span class="badge" style="background:{match_color}22;color:{match_color}">{match.upper()}</span>
            </div>
            <div style="font-size:12px;color:var(--muted)">
                Complexity diff: {tex.get('complexity_diff',0):.3f}<br>
                {tex.get('texture_level_match','')}<br>
                {tex.get('diff_detail','')}
            </div>
        </div>""")
    
    # Spatial
    spatial = cv_comparison.get("spatial", {})
    if spatial:
        cd = spatial.get("center_distance", 0)
        edge_sim = spatial.get("edge_distribution_similarity", 0)
        cd_color = "var(--green)" if cd < 0.1 else ("var(--yellow)" if cd < 0.3 else "var(--red)")
        items.append(f"""
        <div class="cv-item">
            <div class="cv-item-title">📍 Spatial Layout</div>
            <div style="font-size:12px">
                <b>Center distance:</b> <span style="color:{cd_color}">{cd:.3f}</span><br>
                Ref: {spatial.get('ref_center',[0,0])} → Render: {spatial.get('rnd_center',[0,0])}<br>
                <b>Area:</b> ref={spatial.get('ref_area_pct',0):.0f}% render={spatial.get('rnd_area_pct',0):.0f}% (diff={spatial.get('area_ratio_diff',0):+.0f}%)<br>
                <b>Edge distribution:</b> {edge_sim:.3f}
            </div>
            <div style="font-size:12px;margin-top:4px;color:var(--muted)">
                {spatial.get('diff_detail','')}
            </div>
        </div>""")
    
    return f'<div class="card"><div class="cv-grid">{"".join(items)}</div></div>'


def _render_inspect_feedback(feedback: dict) -> str:
    if not feedback:
        return '<p style="color:var(--muted)">No inspect feedback</p>'
    
    parts = []
    score = feedback.get("overall_score", 0)
    passed = feedback.get("passed", False)
    
    parts.append(f'<p><b>Score:</b> {score:.2f} · <b>Passed:</b> {"✅" if passed else "❌"}</p>')
    
    summary = feedback.get("feedback_summary", "")
    if summary:
        parts.append(f'<p style="margin-top:8px">{summary}</p>')
    
    issues = feedback.get("visual_issues", [])
    if issues:
        parts.append('<p style="margin-top:8px"><b>Issues:</b></p><ul>')
        for issue in issues:
            parts.append(f'<li style="color:var(--red);font-size:13px">{issue}</li>')
        parts.append('</ul>')
    
    goals = feedback.get("visual_goals", [])
    if goals:
        parts.append('<p style="margin-top:8px"><b>Goals:</b></p><ul>')
        for goal in goals:
            parts.append(f'<li style="color:var(--green);font-size:13px">{goal}</li>')
        parts.append('</ul>')
    
    correct = feedback.get("correct_aspects", [])
    if correct:
        parts.append('<p style="margin-top:8px"><b>Correct Aspects:</b></p><ul>')
        for c in correct:
            parts.append(f'<li style="font-size:13px">{c}</li>')
        parts.append('</ul>')
    
    return "".join(parts)


def _render_gradient_window(window: list) -> str:
    if not window:
        return '<p style="color:var(--muted)">No iteration history</p>'
    
    items = []
    for entry in window:
        it = entry.get("iteration", "?")
        score = entry.get("score", 0)
        fb = entry.get("feedback_summary", "")[:100]
        score_color = "var(--green)" if score >= 0.85 else ("var(--yellow)" if score >= 0.7 else "var(--red)")
        
        issues_fixed = entry.get("issues_fixed", [])
        issues_remaining = entry.get("issues_remaining", [])
        
        items.append(f"""
        <div class="timeline-item">
            <div style="font-size:14px">
                <b>Iteration {it}</b> — 
                <span style="color:{score_color};font-weight:600">{score:.2f}</span>
            </div>
            <div style="font-size:12px;color:var(--muted);margin-top:4px">
                {fb}
                {'· Fixed: ' + ', '.join(issues_fixed[:3]) if issues_fixed else ''}
            </div>
            {'<div style="font-size:12px;color:var(--red);margin-top:2px">Remaining: ' + ', '.join(issues_remaining[:3]) + '</div>' if issues_remaining else ''}
        </div>""")
    
    return f'<div class="timeline">{"".join(items)}</div>'


def _render_logs(logs: list) -> str:
    if not logs:
        return '<p style="color:var(--muted)">No logs</p>'
    
    items = []
    for log in logs:
        phase = log.get("phase", "")
        status = log.get("status", "")
        message = log.get("message", "")
        duration = log.get("duration_ms")
        iteration = log.get("iteration")
        
        duration_text = f" ({duration}ms)" if duration else ""
        iter_text = f" [Iter {iteration}]" if iteration else ""
        
        items.append(f'<div class="log-entry {status}">{phase}{iter_text}: {message}{duration_text}</div>')
    
    return "".join(items)


def main():
    parser = argparse.ArgumentParser(description="Single sample E2E pipeline test")
    parser.add_argument("sample", help="Sample name (e.g. auroras)")
    parser.add_argument("--max-iter", type=int, default=3, help="Max iterations")
    parser.add_argument("--threshold", type=float, default=0.85, help="Passing threshold")
    args = parser.parse_args()
    
    state, pipeline_id = run_single_sample(args.sample, args.max_iter, args.threshold)
    report_path = generate_html_report(state, args.sample, pipeline_id)
    
    # Print summary
    snapshot = state.get("snapshot", {})
    score = snapshot.get("inspect_feedback", {}).get("overall_score", 0)
    passed = state.get("passed", False)
    
    print(f"\n{'='*60}")
    print(f"  Sample: {args.sample}")
    print(f"  Score:  {score:.2f}")
    print(f"  Passed: {'✅' if passed else '❌'}")
    print(f"  Report: file://{report_path}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
