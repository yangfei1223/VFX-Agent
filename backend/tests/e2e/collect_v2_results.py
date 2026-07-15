"""Collect v2.0 run results + v1.0 baselines into a single JSON for report generator.

Usage:
    python tests/e2e/collect_v2_results.py [--runs-dir /tmp/vfx_v2_runs] [--output /tmp/v2_report_data.json]
"""
import argparse
import base64
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

# v1.0 V2 baseline (from AGENTS.md, 2026-05-18)
V1_BASELINES = {
    "4-col-grad": {"score": 0.95, "status": "passed", "shader_lines": 19, "effect_type": "{effect.gradient}"},
    "shiny-circle": {"score": 0.88, "status": "passed", "shader_lines": 72, "effect_type": "{effect.glow}"},
    "twitter-blue-check": {"score": 0.87, "status": "passed", "shader_lines": 83, "effect_type": "{effect.shape}"},
    "water-color-blending": {"score": 0.86, "status": "passed", "shader_lines": 80, "effect_type": "{effect.flow}"},
    "hypnotic-ripples": {"score": 0.86, "status": "passed", "shader_lines": 56, "effect_type": "{effect.ripple}"},
    "plasma-waves": {"score": 0.83, "status": "acceptable", "shader_lines": 66, "effect_type": "{effect.flow}"},
    "supah-frosted-glass": {"score": 0.82, "status": "acceptable", "shader_lines": 66, "effect_type": "{effect.frosted}"},
    "vortex-street": {"score": 0.81, "status": "acceptable", "shader_lines": 109, "effect_type": "{effect.warp}"},
    "warp-speed2": {"score": 0.81, "status": "acceptable", "shader_lines": 112, "effect_type": "{effect.particle}"},
    "buffer-bloom": {"score": 0.74, "status": "failed", "shader_lines": 96, "effect_type": "{effect.glow}"},
    "happy-diwali-2019": {"score": 0.78, "status": "failed", "shader_lines": 112, "effect_type": "{effect.particle}"},
    "heart-2d": {"score": 0.78, "status": "failed", "shader_lines": 68, "effect_type": "{effect.shape}"},
    "moon-distance-2d": {"score": 0.72, "status": "failed", "shader_lines": 106, "effect_type": "{effect.warp}"},
    "liquid-glass-ui": {"score": 0.73, "status": "failed", "shader_lines": 155, "effect_type": "{effect.liquid}"},
    "electron": {"score": 0.68, "status": "failed", "shader_lines": 145, "effect_type": "{effect.particle}"},
    "liquid-galss-test": {"score": 0.52, "status": "failed", "shader_lines": 106, "effect_type": "{effect.liquid}"},
    "cool-s-distance": {"score": 0.52, "status": "failed", "shader_lines": 109, "effect_type": "{effect.warp}"},
    "auroras": {"score": 0.42, "status": "failed", "shader_lines": 121, "effect_type": "{effect.flow}"},
    "sparks-drifting": {"score": 0.00, "status": "timeout", "shader_lines": 0, "effect_type": "{effect.particle}"},
    "windows-95": {"score": -1, "status": "n/a", "shader_lines": 0, "effect_type": "{effect.particle}"},
}

# Effect category metadata
EFFECT_META = {
    "{effect.gradient}": {"name": "Gradient", "difficulty": "simple"},
    "{effect.glow}": {"name": "Glow", "difficulty": "simple"},
    "{effect.shape}": {"name": "Solid Shape", "difficulty": "simple"},
    "{effect.ripple}": {"name": "Ripple", "difficulty": "simple"},
    "{effect.frosted}": {"name": "Frosted Glass", "difficulty": "simple"},
    "{effect.flow}": {"name": "Flow", "difficulty": "medium"},
    "{effect.particle}": {"name": "Particle", "difficulty": "complex"},
    "{effect.liquid}": {"name": "Liquid Glass", "difficulty": "medium"},
    "{effect.warp}": {"name": "Domain Warp", "difficulty": "medium"},
}


def encode_image_b64(path: Path) -> str | None:
    if not path.exists():
        return None
    return f"data:image/png;base64,{base64.b64encode(path.read_bytes()).decode()}"


def collect_sample(
    runs_root: Path,
    sample_name: str,
    pipeline_id: str | None = None,
    workdir_override: Path | None = None,
    ui_pre_screenshot: str | None = None,
    ui_post_screenshot: str | None = None,
) -> dict:
    """Collect v2.0 run data for one sample.

    If pipeline_id/workdir_override provided, use them directly (UI-driven mode).
    Otherwise fall back to legacy workdir candidate matching (orchestrator-driven mode).
    """
    # Workdir: override wins, otherwise try candidates
    workdir = None
    if workdir_override is not None and workdir_override.exists() and (workdir_override / "shader.glsl").exists():
        workdir = workdir_override
    else:
        candidates = [
            runs_root / sample_name,
            Path("/tmp/vfx_" + sample_name),
            Path("/tmp/vfx_" + sample_name.replace("-", "_")),
        ]
        workdir = next((c for c in candidates if c.exists() and (c / "shader.glsl").exists()), None)

    entry = {
        "sample_name": sample_name,
        "v1_baseline": V1_BASELINES.get(sample_name, {"score": -1, "status": "unknown"}),
        "v2": {"present": False, "status": "missing", "score": 0.0, "duration_s": 0, "shader_lines": 0},
        "images": {"reference": None, "render": None},
        "visual_description": None,
        "evaluation": None,
        "shader_code": None,
        "ui_pre_screenshot": ui_pre_screenshot,
        "ui_post_screenshot": ui_post_screenshot,
    }

    if workdir is None:
        return entry

    entry["v2"]["present"] = True
    entry["v2"]["workdir"] = str(workdir)
    if pipeline_id:
        entry["v2"]["pipeline_id"] = pipeline_id

    # Pull iteration/usage data from pipeline state file (if exists)
    entry["v2"]["iterations"] = 0
    entry["v2"]["duration_s"] = 0
    entry["v2"]["codex_usage"] = None
    # State files are in backend/app/pipeline_states/
    backend_root = Path(__file__).resolve().parents[2]
    states_dir = backend_root / "app" / "pipeline_states"

    # Try exact pipeline_id match first (UI-driven mode)
    state_data = None
    if pipeline_id:
        sf = states_dir / f"{pipeline_id}.json"
        if sf.exists():
            try:
                state_data = json.loads(sf.read_text())
            except Exception:
                pass

    # Fallback: fuzzy workdir.name matching (orchestrator-driven mode)
    if state_data is None:
        state_candidates = sorted(
            states_dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for sf in state_candidates:
            try:
                st = json.loads(sf.read_text())
                wd = st.get("workdir", "")
                if workdir and (workdir.name in wd or wd.endswith(workdir.name)):
                    state_data = st
                    break
            except Exception:
                continue

    if state_data:
        iters = 0
        for ev in state_data.get("events", []):
            if ev.get("type") != "item.completed":
                continue
            item = ev.get("item", {})
            if isinstance(item, dict) and item.get("type") == "collab_tool_call" and item.get("tool") == "wait":
                iters += 1
        entry["v2"]["iterations"] = iters
        entry["v2"]["duration_s"] = state_data.get("duration_ms", 0) // 1000
        entry["v2"]["codex_usage"] = state_data.get("codex_usage")

    # Find reference image
    kf_dir = workdir / "keyframes"
    if kf_dir.exists():
        kfs = sorted(kf_dir.glob("*.png"))
        if kfs:
            entry["images"]["reference"] = encode_image_b64(kfs[0])

    # Find render image (priority: render_final.png > render_iter*.png > render_iteration*.png)
    render_candidates: list[Path] = []
    render_candidates.append(workdir / "render_final.png")
    render_candidates.append(workdir / "render_output.png")
    render_candidates.extend(sorted(workdir.glob("render_iter*.png"), reverse=True))
    render_candidates.extend(sorted(workdir.glob("render_iteration*.png"), reverse=True))
    for cand in render_candidates:
        if cand.exists():
            entry["images"]["render"] = encode_image_b64(cand)
            break

    # Read visual_description.json
    vd_path = workdir / "visual_description.json"
    if vd_path.exists():
        entry["visual_description"] = json.loads(vd_path.read_text())

    # Read evaluation.json (v2.0 subagent output)
    eval_path = workdir / "evaluation.json"
    if eval_path.exists():
        ev = json.loads(eval_path.read_text())
        entry["evaluation"] = ev
        entry["v2"]["score"] = ev.get("overall_score", 0.0)
        entry["v2"]["status"] = "passed" if ev.get("passed") else (
            "timeout" if ev.get("_timeout_flag") else "max_iterations"
        )

    # Read shader
    shader_path = workdir / "final_shader.glsl"
    if not shader_path.exists():
        shader_path = workdir / "shader.glsl"
    if shader_path.exists():
        code = shader_path.read_text()
        entry["shader_code"] = code
        entry["v2"]["shader_lines"] = len(code.splitlines())

    # Duration from state file if available
    return entry


def write_codex_events_md(state_file: Path, output_md: Path, sample_name: str) -> None:
    """Extract codex events from pipeline_state.json into a markdown timeline.

    Designed for human review to identify pipeline bottlenecks, codex reasoning patterns,
    and iteration effectiveness.
    """
    state = json.loads(state_file.read_text())
    events = state.get("events", [])

    pipeline_id = state.get("pipeline_id", "?")
    status = state.get("status", "?")
    duration_ms = state.get("duration_ms", 0)
    final_score = state.get("final_score", 0)
    total = len(events)

    lines = [
        f"# Codex Events: {sample_name}",
        "",
        f"**Pipeline ID**: `{pipeline_id}`  ",
        f"**Status**: {status}  ",
        f"**Duration**: {duration_ms / 1000:.1f}s  ",
        f"**Final Score**: {final_score:.3f}  ",
        f"**Total Events**: {total}",
        "",
        "## Event Timeline",
        "",
    ]

    for i, ev in enumerate(events, start=1):
        ev_type = ev.get("type", "?")
        item = ev.get("item", {})
        usage = ev.get("usage")

        if not isinstance(item, dict):
            item = {}

        item_type = item.get("type", "")
        position = f"[{i}/{total}]"

        if ev_type == "turn.completed" and usage:
            in_t = usage.get("input_tokens", 0)
            out_t = usage.get("output_tokens", 0)
            cached = usage.get("cached_input_tokens", 0)
            cache_pct = (cached * 100 // in_t) if in_t else 0
            lines.append(f"### [{i:03d}] {ev_type} {position}")
            lines.append("")
            lines.append(f"**Usage**: {in_t:,} in / {out_t:,} out / {cached:,} cached ({cache_pct}%)")
            lines.append("")
        elif item_type == "agent_message":
            text = item.get("text", "").strip()
            if text:
                preview = text[:500] + ("..." if len(text) > 500 else "")
                lines.append(f"### [{i:03d}] 💬 agent_message {position}")
                lines.append("")
                lines.append(f"> {preview}")
                lines.append("")
        elif item_type == "command_execution":
            cmd = item.get("command", "")
            exit_code = item.get("exit_code")
            agg_output = item.get("aggregated_output", "") or ""

            lines.append(f"### [{i:03d}] 🖥️ command_execution {position}")
            lines.append("")
            lines.append(f"```bash")
            lines.append(cmd[:1000])
            lines.append("```")
            if exit_code is not None:
                lines.append(f"**Exit code**: {exit_code}")
            if agg_output:
                preview = agg_output[:600] + ("..." if len(agg_output) > 600 else "")
                lines.append(f"**Output**:")
                lines.append("```")
                lines.append(preview)
                lines.append("```")
            lines.append("")
        elif item_type == "collab_tool_call":
            tool = item.get("tool", "?")
            lines.append(f"### [{i:03d}] 🤝 collab_tool_call: {tool} {position}")
            lines.append("")
            if tool == "wait":
                lines.append("> Subagent evaluation spawned (fork_turns=\"none\")")
                lines.append("")
        elif item_type == "file_change":
            changes = item.get("changes", [])
            if changes:
                lines.append(f"### [{i:03d}] 📁 file_change {position}")
                lines.append("")
                for ch in changes[:5]:
                    action = ch.get("action", "?")
                    path = ch.get("path", "?")
                    lines.append(f"- `{action}` {path}")
                if len(changes) > 5:
                    lines.append(f"- ... and {len(changes) - 5} more")
                lines.append("")
        elif ev_type in ("thread.started", "turn.started"):
            lines.append(f"### [{i:03d}] 🔵 {ev_type} {position}")
            lines.append("")

    output_md.write_text("\n".join(lines))


def persist_to_test_results(
    report_data: dict,
    runs_root: Path,
    output_dir: Path | None = None,
) -> Path:
    """Persist complete test_results archive to disk.

    Creates:
        <output_dir>/
        ├── test_results.json           # AGENTS.md schema
        ├── sample_classifications.json # 元数据汇总
        └── <sample_name>/              # 每 sample 子目录
            ├── pipeline_state.json
            ├── reference_frame.png
            ├── visual_description.json
            ├── shader.glsl
            ├── evaluation.json
            ├── render_final.png
            ├── render_iter_*.png        # 各迭代（如有）
            └── codex_events.md          # 提取的关键事件
    """
    if output_dir is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
        backend_root = Path(__file__).resolve().parents[2]
        output_dir = backend_root / "test_results" / f"{date_str}_v2-codex-od-20samples"
    output_dir.mkdir(parents=True, exist_ok=True)

    backend_root = Path(__file__).resolve().parents[2]
    states_dir = backend_root / "app" / "pipeline_states"
    vfx_root = backend_root.parent.parent.parent
    test_samples_data = vfx_root / "test-samples" / "data"

    samples = report_data.get("samples", [])

    # Build test_results.json
    test_results = {}
    sample_classifications = {}

    for entry in samples:
        sample_name = entry["sample_name"]

        # Find pipeline_id from entry (UI-driven mode) first, fallback to state scan
        pipeline_id = entry.get("v2", {}).get("pipeline_id") if isinstance(entry.get("v2"), dict) else None
        if not pipeline_id:
            try:
                for sf in sorted(states_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
                    try:
                        st = json.loads(sf.read_text())
                        wd = st.get("workdir", "")
                        if sample_name in wd or wd.endswith(sample_name):
                            pipeline_id = st.get("pipeline_id", sf.stem)
                            break
                    except Exception:
                        continue
            except Exception:
                pass

        if pipeline_id is None:
            pipeline_id = f"v2-{sample_name}"

        # Determine status
        status = entry.get("v2", {}).get("status", "missing")

        # Determine effect_type (priority: visual_description > V1_BASELINES)
        vd = entry.get("visual_description")
        v1_info = entry.get("v1_baseline", {})
        if vd and isinstance(vd, dict):
            effect_type = vd.get("effect_type", v1_info.get("effect_type", "unknown"))
        else:
            effect_type = v1_info.get("effect_type", "unknown")

        # Determine issues from evaluation
        eval_data = entry.get("evaluation")
        issues = []
        if eval_data and isinstance(eval_data, dict):
            visual_issues = eval_data.get("visual_issues", [])
            if isinstance(visual_issues, list):
                for i, iss in enumerate(visual_issues):
                    if isinstance(iss, dict):
                        sev = iss.get("severity", "low")
                        desc = iss.get("description", iss.get("desc", ""))
                    else:
                        sev = "low"
                        desc = str(iss)
                    sev_map = {"high": "P0", "medium": "P1", "low": "P2"}
                    severity = sev_map.get(sev.lower(), "P2")
                    issues.append({
                        "id": f"{severity[0]}{i + 1}",
                        "severity": severity,
                        "desc": desc[:200],
                    })

        # v1 baseline and delta
        v1_score = entry.get("v1_baseline", {}).get("score", -1)
        v1_status = entry.get("v1_baseline", {}).get("status", "unknown")
        v2_score = entry.get("v2", {}).get("score", 0.0)

        test_results[sample_name] = {
            "sample_name": sample_name,
            "pipeline_id": pipeline_id,
            "status": status,
            "elapsed_seconds": entry.get("v2", {}).get("duration_s", 0),
            "score": v2_score,
            "iteration": entry.get("v2", {}).get("iterations", 0),
            "effect_type": effect_type,
            "shader_lines": entry.get("v2", {}).get("shader_lines", 0),
            "issues": issues,
            "issue_count": len(issues),
            "timestamp": datetime.now().isoformat(),
            "v1_baseline_score": v1_score if v1_score >= 0 else None,
            "v1_baseline_status": v1_status if v1_score >= 0 else None,
            "delta_vs_v1": (v2_score - v1_score) if v1_score >= 0 else None,
        }

        # Build sample_classifications.json entry
        classification_info = {}
        sample_data_file = test_samples_data / f"{sample_name}.json"
        if sample_data_file.exists():
            try:
                sd = json.loads(sample_data_file.read_text())
                classification_info = {
                    "effect_category": sd.get("effect_category", ""),
                    "effect_name": sd.get("effect_name", ""),
                    "visual_description": sd.get("visual_description", ""),
                    "dominant_colors": sd.get("dominant_colors", []),
                    "has_animation": sd.get("has_animation", False),
                    "complexity": sd.get("complexity", ""),
                    "is_2d": sd.get("is_2d", True),
                    "key_elements": sd.get("key_elements", []),
                    "shape_type": sd.get("shape_type", ""),
                    "fill_type": sd.get("fill_type", ""),
                    "animation_type": sd.get("animation_type", ""),
                }
            except Exception:
                pass
        sample_classifications[sample_name] = classification_info

        # Per-sample subdirectory
        sample_dir = output_dir / sample_name
        sample_dir.mkdir(exist_ok=True)

        workdir = Path(entry.get("v2", {}).get("workdir", ""))
        if not workdir.exists():
            continue

        # 1. reference_frame.png
        try:
            kf_dir = workdir / "keyframes"
            kfs = sorted(kf_dir.glob("*.png")) if kf_dir.exists() else []
            if kfs:
                shutil.copy(kfs[0], sample_dir / "reference_frame.png")
        except Exception:
            pass

        # 2. visual_description.json
        try:
            vd_path = workdir / "visual_description.json"
            if vd_path.exists():
                shutil.copy(vd_path, sample_dir / "visual_description.json")
        except Exception:
            pass

        # 3. shader.glsl (priority: final_shader.glsl > shader.glsl)
        try:
            for name in ["final_shader.glsl", "shader.glsl"]:
                p = workdir / name
                if p.exists():
                    shutil.copy(p, sample_dir / "shader.glsl")
                    break
        except Exception:
            pass

        # 4. evaluation.json
        try:
            ev_path = workdir / "evaluation.json"
            if ev_path.exists():
                shutil.copy(ev_path, sample_dir / "evaluation.json")
        except Exception:
            pass

        # 5. Render images (priority: render_final.png > render_output.png > render_iter*)
        try:
            for p in [workdir / "render_final.png", workdir / "render_output.png"]:
                if p.exists():
                    shutil.copy(p, sample_dir / "render_final.png")
                    break
        except Exception:
            pass

        try:
            iter_imgs = sorted(
                list(workdir.glob("render_iter*.png")) + list(workdir.glob("render_iteration*.png"))
            )
            for i, p in enumerate(iter_imgs):
                shutil.copy(p, sample_dir / f"render_iter_{i}.png")
        except Exception:
            pass

        # 6. pipeline_state.json (precise pipeline_id match first, fuzzy workdir.name fallback)
        entry_pid = entry.get("v2", {}).get("pipeline_id") if isinstance(entry.get("v2"), dict) else None
        try:
            copied = False
            # Precise pipeline_id match
            if entry_pid:
                sf = states_dir / f"{entry_pid}.json"
                if sf.exists():
                    shutil.copy(sf, sample_dir / "pipeline_state.json")
                    copied = True
            # Fallback: fuzzy workdir.name matching
            if not copied:
                for sf in sorted(states_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
                    try:
                        st = json.loads(sf.read_text())
                        wd = st.get("workdir", "")
                        if sample_name in wd or wd.endswith(sample_name):
                            shutil.copy(sf, sample_dir / "pipeline_state.json")
                            copied = True
                            break
                    except Exception:
                        continue
        except Exception:
            pass

        # 7. codex_events.md (from pipeline_state.json)
        try:
            state_file_for_events = sample_dir / "pipeline_state.json"
            if state_file_for_events.exists():
                write_codex_events_md(state_file_for_events, sample_dir / "codex_events.md", sample_name)
        except Exception:
            pass

        # 8. UI screenshots (前端运行界面截图 from UI-driven mode)
        for source_path, target_name in [
            (entry.get("ui_pre_screenshot"), "ui_pre.png"),
            (entry.get("ui_post_screenshot"), "ui_post.png"),
        ]:
            if source_path and Path(source_path).exists():
                try:
                    shutil.copy(Path(source_path), sample_dir / target_name)
                except Exception:
                    pass

    # Write test_results.json
    tr_path = output_dir / "test_results.json"
    tr_path.write_text(json.dumps(test_results, indent=2, ensure_ascii=False, default=str))

    # Write sample_classifications.json
    sc_path = output_dir / "sample_classifications.json"
    sc_path.write_text(json.dumps(sample_classifications, indent=2, ensure_ascii=False, default=str))

    print(f"[collect] Archive: {output_dir}", file=sys.stderr)
    print(f"[collect]  ├─ test_results.json ({len(test_results)} samples)", file=sys.stderr)
    print(f"[collect]  ├─ sample_classifications.json", file=sys.stderr)
    print(f"[collect]  └─ {len([s for s in samples if Path(s.get('v2',{}).get('workdir','')).exists()])}/"
          f"{len(samples)} sample dirs with assets", file=sys.stderr)
    return output_dir


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs-dir", default="/tmp/vfx_v2_runs",
                        help="Root dir of v2.0 sample workdirs")
    parser.add_argument("--output", default="/tmp/v2_report_data.json",
                        help="Output JSON path")
    parser.add_argument(
        "--map-file",
        default="/tmp/vfx_v2_runs/sample_pipeline_map.json",
        help="Path to sample_pipeline_map.json produced by run_v2_samples_via_ui.py",
    )
    args = parser.parse_args()

    runs_root = Path(args.runs_dir)

    # 优先用 map-file 的 sample 列表（前端 UI 触发模式）
    map_data = []
    map_by_sample = {}
    if Path(args.map_file).exists():
        try:
            map_data = json.loads(Path(args.map_file).read_text())
            map_by_sample = {m["sample"]: m for m in map_data if "sample" in m}
            print(f"[collect] Loaded map: {len(map_by_sample)} samples from {args.map_file}", file=sys.stderr)
        except Exception as e:
            print(f"[collect] WARN: failed to read map file: {e}", file=sys.stderr)

    # Sample 列表：map-file 优先，否则 V1_BASELINES.keys()
    if map_by_sample:
        samples = sorted(map_by_sample.keys())
    else:
        samples = sorted(V1_BASELINES.keys())

    results = []
    for s in samples:
        print(f"[collect] {s}...", file=sys.stderr)
        m = map_by_sample.get(s, {})
        results.append(collect_sample(
            runs_root,
            s,
            pipeline_id=m.get("pipeline_id"),
            workdir_override=Path(m["workdir"]) if m.get("workdir") else None,
            ui_pre_screenshot=m.get("ui_pre_screenshot"),
            ui_post_screenshot=m.get("ui_post_screenshot"),
        ))

    # Aggregate stats
    present = [r for r in results if r["v2"]["present"]]
    passed = [r for r in present if r["v2"]["status"] == "passed"]
    v2_scores = [r["v2"]["score"] for r in present]
    v1_scores = [r["v1_baseline"]["score"] for r in present if r["v1_baseline"]["score"] >= 0]

    summary = {
        "total_samples": len(samples),
        "present": len(present),
        "passed": len(passed),
        "v2_avg_score": sum(v2_scores) / len(v2_scores) if v2_scores else 0,
        "v1_avg_score": sum(v1_scores) / len(v1_scores) if v1_scores else 0,
        "delta_avg": (sum(v2_scores) / len(v2_scores) - sum(v1_scores) / len(v1_scores))
                     if v2_scores and v1_scores else 0,
    }
    print(f"[collect] summary: {summary}", file=sys.stderr)

    out = {
        "generated_at": str(Path().resolve()),
        "summary": summary,
        "samples": results,
    }
    Path(args.output).write_text(json.dumps(out, indent=2, default=str))
    print(f"[collect] Wrote {args.output} ({len(results)} samples, {len(present)} present)")

    # Persist complete archive to test_results/
    archive_dir = persist_to_test_results(out, runs_root)
    print(f"[collect] Archive persisted: {archive_dir}")


if __name__ == "__main__":
    main()
