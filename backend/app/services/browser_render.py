"""Playwright 浏览器自动化截图服务：将 shader 注入 WebGL 预览页并截图"""

import asyncio
import base64
import tempfile
from pathlib import Path

from playwright.async_api import async_playwright
from playwright.sync_api import sync_playwright

from app.config import settings


# Path to standalone HTML renderer (no UI chrome)
STANDALONE_HTML_PATH = Path(__file__).parent / "shader_render_page.html"


async def render_and_screenshot(
    shader_code: str,
    time_seconds: float = 1.0,
    width: int | None = None,
    height: int | None = None,
) -> str:
    """
    在浏览器中渲染 shader 并截图，返回截图文件路径。

    v2.0: uses standalone HTML renderer (no UI chrome), not frontend dev server.
    v1.0 fallback retained for backward compatibility via render_via_frontend().

    Args:
        shader_code: Shadertoy 格式 GLSL 代码
        time_seconds: 渲染到第几秒时截图（用于动画效果）
        width: 截图宽度
        height: 截图高度

    Returns:
        截图 PNG 文件路径
    """
    width = width or settings.screenshot_width
    height = height or settings.screenshot_height

    # Use standalone HTML (file:// URL) for pure shader render
    shader_b64 = base64.urlsafe_b64encode(shader_code.encode()).decode()
    preview_url = (
        f"file://{STANDALONE_HTML_PATH.resolve()}"
        f"?shader={shader_b64}&t={time_seconds}&w={width}&h={height}"
    )

    async with async_playwright() as p:
        # Chromium args: force software WebGL (swiftshader) for stability under
        # repeated launches. Hardware GPU context leaks across back-to-back
        # invocations causing intermittent blank screenshots.
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--enable-unsafe-swiftshader",  # use software WebGL renderer
                "--disable-gpu",                # disable HW GPU entirely
                "--no-sandbox",                 # faster startup, no sandbox overhead
                "--use-gl=swiftshader",         # explicit GL backend
            ],
        )
        page = await browser.new_page(viewport={"width": width, "height": height})
        await page.goto(preview_url, wait_until="networkidle")

        # 等待 shader 编译和渲染
        await page.wait_for_timeout(500)

        # 等待渲染器标记就绪
        await page.wait_for_function(
            "() => window.__shaderReady === true",
            timeout=settings.render_timeout_ms,
        )

        # 额外 wait: 让 GPU 命令队列刷新 (swiftshader 软件渲染稍慢)
        await page.wait_for_timeout(300)

        # Bug A: Check if shader compile failed (HTML sets __shaderError on compile fail)
        shader_error = await page.evaluate("() => window.__shaderError === true")
        if shader_error:
            raise RuntimeError(
                "Shader failed to compile in standalone renderer. "
                "Check shader code or upgrade shader_render_page.html to WebGL2."
            )

        # 验证 canvas 真的渲染了内容 (中央像素非空白)
        # 避免"截图成功但内容是白色"的 silently-failure
        rendered = await page.evaluate(
            """() => {
                const c = document.querySelector('canvas');
                if (!c) return false;
                const gl = c.getContext('webgl2') || c.getContext('webgl');
                if (!gl) return false;
                const px = new Uint8Array(4);
                gl.readPixels(c.width/2 | 0, c.height/2 | 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, px);
                // Bug B: reject pure white (255,255,255,*) and pure black (0,0,0,*) — both are blank
                const isBlank = (px[0] === 255 && px[1] === 255 && px[2] === 255) ||
                                 (px[0] === 0 && px[1] === 0 && px[2] === 0);
                return !isBlank;
            }"""
        )
        if not rendered:
            # 重试一次: 重新触发渲染
            await page.evaluate(
                "(t) => { if (window.__setShaderTime) window.__setShaderTime(t); }",
                time_seconds,
            )
            await page.wait_for_timeout(500)

        # 截图
        screenshot_path = Path(tempfile.mktemp(suffix=".png", prefix="vfx_screenshot_"))
        await page.screenshot(path=str(screenshot_path), type="png")

        await browser.close()

    return str(screenshot_path)


def render_multiple_frames(
    shader_code: str,
    times: list[float] | None = None,
    width: int | None = None,
    height: int | None = None,
) -> list[str]:
    """
    渲染 shader 在多个时间点的截图，用于动画对比。

    Args:
        shader_code: Shadertoy 格式 GLSL 代码
        times: 截图时间点列表（秒），默认 [0, 0.5, 1.0, 1.5, 2.0]
        width: 截图宽度
        height: 截图高度

    Returns:
        截图文件路径列表
    """
    times = times or [0.0, 0.5, 1.0, 1.5, 2.0]
    screenshots = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            viewport={"width": width or settings.screenshot_width, "height": height or settings.screenshot_height}
        )

        shader_b64 = base64.urlsafe_b64encode(shader_code.encode()).decode()
        page.goto(f"{settings.frontend_url}?shader={shader_b64}", wait_until="networkidle")
        page.wait_for_timeout(500)
        page.wait_for_function(
            "() => window.__shaderReady === true",
            timeout=settings.render_timeout_ms,
        )

        for t in times:
            # 通过 JS 设置渲染器时间并等待一帧
            page.evaluate(f"window.__setShaderTime({t})")
            page.wait_for_timeout(100)

            path = Path(tempfile.mktemp(suffix=".png", prefix=f"vfx_t{t}_"))
            page.screenshot(path=str(path), type="png")
            screenshots.append(str(path))

        browser.close()

    return screenshots