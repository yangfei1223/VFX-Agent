"""Playwright 浏览器自动化截图服务：将 shader 注入 WebGL 预览页并截图"""

import asyncio
import base64
import tempfile
from pathlib import Path

from playwright.async_api import async_playwright

from app.config import settings


async def render_and_screenshot(
    shader_code: str,
    time_seconds: float = 1.0,
    width: int | None = None,
    height: int | None = None,
) -> str:
    """
    在浏览器中渲染 shader 并截图，返回截图文件路径。

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

    # 将 shader 代码编码为 URL-safe base64，通过 URL 参数传给前端
    shader_b64 = base64.urlsafe_b64encode(shader_code.encode()).decode()

    preview_url = f"{settings.frontend_url}?shader={shader_b64}&t={time_seconds}"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": width, "height": height})
        await page.goto(preview_url, wait_until="networkidle")

        # 等待 shader 编译和渲染
        await page.wait_for_timeout(500)

        # 等待渲染器标记就绪
        await page.wait_for_function(
            "() => window.__shaderReady === true",
            timeout=settings.render_timeout_ms,
        )

        # 截图
        screenshot_path = Path(tempfile.mktemp(suffix=".png", prefix="vfx_screenshot_"))
        await page.screenshot(path=str(screenshot_path), type="png")

        await browser.close()

    return str(screenshot_path)


async def render_multiple_frames(
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

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(
            viewport={"width": width or settings.screenshot_width, "height": height or settings.screenshot_height}
        )

        shader_b64 = base64.urlsafe_b64encode(shader_code.encode()).decode()
        await page.goto(f"{settings.frontend_url}?shader={shader_b64}", wait_until="networkidle")
        await page.wait_for_timeout(500)
        await page.wait_for_function(
            "() => window.__shaderReady === true",
            timeout=settings.render_timeout_ms,
        )

        for t in times:
            # 通过 JS 设置渲染器时间并等待一帧
            await page.evaluate(f"window.__setShaderTime({t})")
            await page.wait_for_timeout(100)

            path = Path(tempfile.mktemp(suffix=".png", prefix=f"vfx_t{t}_"))
            await page.screenshot(path=str(path), type="png")
            screenshots.append(str(path))

        await browser.close()

    return screenshots