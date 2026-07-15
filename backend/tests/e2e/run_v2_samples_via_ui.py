"""Run v2.0 samples via UI (Playwright) - mimics real user path.

Usage:
    python tests/e2e/run_v2_samples_via_ui.py [sample1 sample2 ...]
    python tests/e2e/run_v2_samples_via_ui.py --all

Default (no args) runs all 20 samples.
"""
import argparse
import asyncio
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import requests
from playwright.async_api import async_playwright

BACKEND_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:5173"
TEST_SAMPLES = Path("/Users/yangfei/Code/VFX-Agent/test-samples/data")
ARCHIVE_ROOT = Path("/tmp/vfx_v2_runs")
MAP_FILE = ARCHIVE_ROOT / "sample_pipeline_map.json"

# 20 samples (v1.0 baseline 19 + windows-95)
DEFAULT_SAMPLES = [
    "4-col-grad", "auroras", "buffer-bloom", "cool-s-distance", "electron",
    "happy-diwali-2019", "heart-2d", "hypnotic-ripples", "liquid-galss-test",
    "liquid-glass-ui", "moon-distance-2d", "plasma-waves", "shiny-circle",
    "sparks-drifting", "supah-frosted-glass", "twitter-blue-check",
    "vortex-street", "warp-speed2", "water-color-blending", "windows-95",
]


def extract_keyframe(sample: str) -> Path | None:
    """Extract webm first frame as keyframe to ARCHIVE_ROOT/<sample>_keyframe.png."""
    webm = TEST_SAMPLES / f"{sample}.webm"
    if not webm.exists():
        print(f"[ui-runner] WARN: {webm} not found")
        return None
    ARCHIVE_ROOT.mkdir(parents=True, exist_ok=True)
    kf = ARCHIVE_ROOT / f"{sample}_keyframe.png"
    result = subprocess.run(
        ["ffmpeg", "-i", str(webm), "-vframes", "1", "-q:v", "2",
         "-update", "1", str(kf), "-y"],
        capture_output=True,
    )
    if result.returncode != 0 or not kf.exists():
        print(f"[ui-runner] ffmpeg failed: {result.stderr.decode()[-300:]}")
        return None
    return kf


def load_notes(sample: str) -> str:
    """Read visual_description + effect_name from sample.json as user notes."""
    j = TEST_SAMPLES / f"{sample}.json"
    if not j.exists():
        return f"[Test sample: {sample}]"
    data = json.loads(j.read_text())
    parts = [f"[Test sample: {sample}]"]
    desc = data.get("visual_description", "")
    if desc:
        parts.append(desc)
    if data.get("effect_name"):
        parts.append(f"Effect type: {data['effect_name']}")
    return "\n".join(parts)


async def capture_pipeline_id(page) -> str | None:
    """Capture pipeline_id from POST /pipeline/run response.

    Uses page.on('response') to observe the response without interfering
    with the request/response flow (avoids OPTIONS preflight conflicts).
    """
    future = asyncio.get_event_loop().create_future()

    async def on_response(response):
        if response.request.method != "POST":
            return
        if not response.url.rstrip("/").endswith("/pipeline/run"):
            return
        try:
            data = await response.json()
            pid = data.get("pipeline_id")
            if pid and not future.done():
                future.set_result(pid)
        except Exception:
            pass

    page.on("response", on_response)
    try:
        return await asyncio.wait_for(future, timeout=5.0)
    except asyncio.TimeoutError:
        return None
    finally:
        page.remove_listener("response", on_response)


async def poll_pipeline_status(pipeline_id: str, timeout: int = 700) -> dict:
    """Poll /pipeline/status/ via direct HTTP until terminal or timeout.

    Uses direct requests to avoid browser context timing issues and
    bypass system proxy for localhost connections.

    timeout default 700s > backend orchestrator CODEX_TIMEOUT (600s) + 100s buffer,
    to ensure backend has updated terminal status before we stop polling.
    Otherwise we'd race with backend state writes and miss the final score/workdir.
    """
    start = time.time()
    terminal = {"passed", "failed", "timeout", "max_iterations"}
    session = requests.Session()
    # Bypass system proxy for localhost
    session.trust_env = False
    last_result = None
    while time.time() - start < timeout:
        try:
            r = session.get(
                f"{BACKEND_URL}/pipeline/status/{pipeline_id}",
                timeout=10,
            )
            r.raise_for_status()
            result = r.json()
            last_result = result
            status = result.get("status")
            if status in terminal:
                return result
        except requests.RequestException as exc:
            print(f"[ui-runner] WARN: poll error for {pipeline_id}: {exc}")
        await asyncio.sleep(3)
    # Fallback: poll timed out. Last attempt to grab real data from backend
    # (backend orchestrator may have just finished writing terminal state).
    for _ in range(5):  # retry up to 5 times over ~15s
        try:
            r = session.get(
                f"{BACKEND_URL}/pipeline/status/{pipeline_id}",
                timeout=10,
            )
            r.raise_for_status()
            result = r.json()
            if result.get("status") in terminal:
                print(f"[ui-runner] recovered final state for {pipeline_id} on fallback retry")
                return result
        except requests.RequestException:
            pass
        await asyncio.sleep(3)
    # True fallback: only if backend never returned terminal status
    print(f"[ui-runner] WARN: giving up on {pipeline_id} after {timeout}s + 15s retry")
    return last_result or {"status": "timeout", "pipeline_id": pipeline_id, "final_score": 0, "workdir": None}


async def run_one_sample(page, sample: str) -> dict:
    """Run a single sample via the frontend UI."""
    print(f"\n[ui-runner] === {sample} ===")
    start_time = time.time()

    result = {
        "sample": sample,
        "pipeline_id": None,
        "status": "failed",
        "score": 0.0,
        "elapsed_s": 0,
        "workdir": None,
        "error": None,
        "ui_pre_screenshot": None,
        "ui_post_screenshot": None,
    }

    # 1. Extract keyframe
    kf = extract_keyframe(sample)
    if kf is None:
        result["error"] = "keyframe extraction failed"
        return result

    # 2. Reload frontend to avoid state contamination from previous sample
    try:
        await page.goto(FRONTEND_URL, wait_until="networkidle", timeout=15000)
    except Exception as e:
        result["error"] = f"frontend load failed: {e}"
        return result
    await page.wait_for_timeout(800)

    # 3. Upload keyframe via the (hidden) file input
    try:
        await page.set_input_files("input[type=file]", str(kf))
        await page.wait_for_timeout(800)
    except Exception as e:
        result["error"] = f"file upload failed: {e}"
        return result

    # 4. Fill description textarea
    try:
        notes = load_notes(sample)
        await page.fill("textarea[placeholder*='Describe']", notes[:500])
    except Exception as e:
        result["error"] = f"fill notes failed: {e}"
        return result

    # 5. Screenshot before triggering pipeline
    pre_path = ARCHIVE_ROOT / f"{sample}_ui_pre.png"
    try:
        await page.screenshot(path=str(pre_path), full_page=True)
        result["ui_pre_screenshot"] = str(pre_path)
    except Exception as e:
        print(f"[ui-runner] WARN: pre screenshot failed: {e}")

    # 6. Capture pipeline_id via route interception, then click Generate
    capture_task = asyncio.create_task(capture_pipeline_id(page))

    try:
        generate_btn = page.locator("button:has-text('Generate Shader'):not([disabled])")
        await generate_btn.click(timeout=5000)
    except Exception as e:
        result["error"] = f"click Generate failed: {e}"
        capture_task.cancel()
        return result

    # 7. Wait for pipeline_id from intercepted response
    try:
        pipeline_id = await asyncio.wait_for(capture_task, timeout=10.0)
    except asyncio.TimeoutError:
        result["error"] = "no pipeline_id captured (POST /pipeline/run not detected)"
        return result

    if not pipeline_id:
        result["error"] = "POST /pipeline/run returned empty pipeline_id"
        return result

    result["pipeline_id"] = pipeline_id
    print(f"[ui-runner] {sample}: pipeline_id={pipeline_id}")

    # 8. Poll pipeline until completion
    final_state = await poll_pipeline_status(pipeline_id, timeout=600)
    result["status"] = final_state.get("status", "unknown")
    result["score"] = final_state.get("final_score", 0)
    result["workdir"] = final_state.get("workdir")
    result["elapsed_s"] = round(time.time() - start_time, 1)

    # 9. Screenshot after completion
    await page.wait_for_timeout(2000)
    post_path = ARCHIVE_ROOT / f"{sample}_ui_post.png"
    try:
        await page.screenshot(path=str(post_path), full_page=True)
        result["ui_post_screenshot"] = str(post_path)
    except Exception as e:
        print(f"[ui-runner] WARN: post screenshot failed: {e}")

    print(f"[ui-runner] {sample}: status={result['status']} score={result['score']} elapsed={result['elapsed_s']}s")
    return result


async def main():
    parser = argparse.ArgumentParser(description="Run v2.0 samples via UI (Playwright)")
    parser.add_argument("samples", nargs="*", help="Sample names (default: all 20)")
    parser.add_argument("--all", action="store_true", help="Run all 20 samples")
    args = parser.parse_args()

    if args.all or not args.samples:
        samples = DEFAULT_SAMPLES
    else:
        samples = args.samples

    ARCHIVE_ROOT.mkdir(parents=True, exist_ok=True)

    print(f"[ui-runner] Running {len(samples)} samples via UI")
    print(f"[ui-runner] Frontend: {FRONTEND_URL}")
    print(f"[ui-runner] Backend:  {BACKEND_URL}")

    # Health check: verify backend is reachable
    # NOTE: Use requests with proxies={'http': '', 'https': ''} to bypass
    # system proxy that may interfere with localhost connections.
    try:
        r = requests.get(
            f"{BACKEND_URL}/pipeline/status/health-check",
            timeout=5,
            proxies={"http": "", "https": ""},
        )
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"[ui-runner] ERROR: backend not reachable: {e}")
        sys.exit(1)

    results = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=1,
        )
        page = await context.new_page()

        for i, sample in enumerate(samples, start=1):
            print(f"\n[ui-runner] >>> Progress: {i}/{len(samples)}")
            try:
                r = await run_one_sample(page, sample)
            except Exception as e:
                r = {
                    "sample": sample,
                    "pipeline_id": None,
                    "status": "exception",
                    "score": 0,
                    "elapsed_s": 0,
                    "workdir": None,
                    "error": f"{type(e).__name__}: {e}",
                    "ui_pre_screenshot": None,
                    "ui_post_screenshot": None,
                }
            results.append(r)

            # Write after each sample in case of interruption
            MAP_FILE.write_text(json.dumps(results, indent=2, ensure_ascii=False))
            print(f"[ui-runner] Map updated: {MAP_FILE}")

        await browser.close()

    # Summary
    print(f"\n[ui-runner] ===== SUMMARY =====")
    print(f"{'Sample':<25} {'Status':<15} {'Score':<8} {'Time':<8}")
    print("-" * 65)
    for r in results:
        print(f"{r['sample']:<25} {r.get('status', '?'):<15} {r.get('score', 0):<8.3f} {r.get('elapsed_s', 0):<8.1f}")
    print(f"\n[ui-runner] Total: {len(results)} samples")
    passed = sum(1 for r in results if r.get("status") == "passed")
    print(f"[ui-runner] Passed: {passed}/{len(results)}")
    print(f"[ui-runner] Map saved: {MAP_FILE}")


if __name__ == "__main__":
    asyncio.run(main())
