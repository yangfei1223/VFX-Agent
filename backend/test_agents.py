#!/usr/bin/env python3
"""逐步调试各个 Agent"""

import json
import re
import sys
import time
import os
from pathlib import Path

# 设置工作目录为 backend 目录
backend_dir = Path(__file__).parent.resolve()
os.chdir(backend_dir)

# Add current dir to path
sys.path.insert(0, str(backend_dir))

from app.config import settings
from app.agents.decompose import DecomposeAgent
from app.agents.generate import GenerateAgent
from app.agents.inspect import InspectAgent
from app.services.video_extractor import extract_keyframes, get_video_info

# 项目根目录（用于访问 example 目录）
PROJECT_ROOT = backend_dir.parent


def print_separator(title: str = ""):
    """打印分隔线"""
    print("\n" + "=" * 60)
    if title:
        print(f" {title} ")
        print("=" * 60)


def print_json(data: dict, indent: int = 2):
    """打印 JSON 数据"""
    print(json.dumps(data, indent=indent, ensure_ascii=False))


def check_glsl_completeness(code: str) -> dict:
    """检查 GLSL 代码完整性"""
    result = {
        "has_main_image": "void mainImage" in code,
        "has_frag_color": "fragColor" in code,
        "line_count": code.count("\n") + 1,
        "is_complete": False,
        "issues": [],
    }

    if not result["has_main_image"]:
        result["issues"].append("缺少 mainImage 函数")

    if not result["has_frag_color"]:
        result["issues"].append("缺少 fragColor 输出")

    # 检查大括号是否匹配
    open_braces = code.count("{")
    close_braces = code.count("}")
    if open_braces != close_braces:
        result["issues"].append(f"大括号不匹配: {{ {open_braces} 个, }} {close_braces} 个")
    else:
        result["is_complete"] = True

    return result


def main():
    print_separator("VFX-Agent 逐步调试测试")

    # 显示配置
    print("\n[配置信息]")
    print(f"  Decompose Agent: {settings.decompose_model} @ {settings.decompose_base_url}")
    print(f"  Generate Agent:  {settings.generate_model} @ {settings.generate_base_url}")
    print(f"  Inspect Agent:   {settings.inspect_model} @ {settings.inspect_base_url}")
    print(f"  Proxy: {settings.proxy or 'None'}")

    # 视频路径
    video_path = PROJECT_ROOT / "example" / "demo.webm"
    if not video_path.exists():
        print(f"\n[错误] 视频文件不存在: {video_path}")
        sys.exit(1)

    # 结果追踪
    results = {
        "step1_keyframes": False,
        "step2_decompose": False,
        "step3_generate": False,
        "decompose_truncated": False,
        "generate_truncated": False,
    }

    # ========================================
    # Step 1: Extract keyframes
    # ========================================
    print_separator("Step 1: 提取关键帧")

    keyframe_paths = []
    video_info = {}
    try:
        print(f"\n视频路径: {video_path}")
        video_info = get_video_info(str(video_path))
        print(f"视频信息:")
        print_json(video_info)

        print(f"\n正在提取关键帧...")
        keyframe_paths = extract_keyframes(str(video_path), max_frames=4)
        print(f"提取了 {len(keyframe_paths)} 张关键帧:")
        for i, path in enumerate(keyframe_paths):
            print(f"  [{i+1}] {path}")
        results["step1_keyframes"] = True
    except Exception as e:
        print(f"\n[错误] 关键帧提取失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # ========================================
    # Step 2: Decompose Agent
    # ========================================
    print_separator("Step 2: Decompose Agent 分析")

    visual_description = None
    try:
        print("\n初始化 Decompose Agent...")
        decompose_agent = DecomposeAgent()
        print(f"模型: {decompose_agent.model}")

        print("\n正在分析关键帧...")
        start_time = time.time()

        # 直接调用 chat 方法，使用更大的 max_tokens
        parts = ["请分析以下视觉参考，解构出视效语义描述。"]
        parts.append(
            f"视频信息：时长 {video_info['duration']:.1f}s，"
            f"帧率 {video_info['fps']:.0f}fps，"
            f"分辨率 {video_info['width']}x{video_info['height']}。"
        )
        parts.append(
            f"以下 {len(keyframe_paths)} 张图片是从视频中均匀提取的关键帧。"
        )
        user_prompt = "\n".join(parts)

        response = decompose_agent.chat(
            system_prompt=decompose_agent.system_prompt,
            user_prompt=user_prompt,
            image_paths=keyframe_paths,
            temperature=0.3,
            max_tokens=4096,
        )
        visual_description = DecomposeAgent._parse_json(response)
        elapsed = time.time() - start_time

        # 检查是否被截断
        if "parse_error" in visual_description:
            print(f"\n[警告] JSON 解析可能不完整: {visual_description.get('parse_error')}")
            results["decompose_truncated"] = True

        print(f"\n分析完成 (耗时 {elapsed:.2f}s)")
        print("\n视觉描述 JSON:")
        print_json(visual_description)
        results["step2_decompose"] = True
    except Exception as e:
        print(f"\n[错误] Decompose Agent 失败: {e}")
        import traceback
        traceback.print_exc()

    # 保存视觉描述
    output_dir = Path(__file__).parent / "debug_output"
    if visual_description:
        output_dir.mkdir(exist_ok=True)

        visual_desc_path = output_dir / "visual_description.json"
        visual_desc_path.write_text(json.dumps(visual_description, indent=2, ensure_ascii=False))
        print(f"\n视觉描述已保存至: {visual_desc_path}")

    # ========================================
    # Step 3: Generate Agent
    # ========================================
    print_separator("Step 3: Generate Agent 生成 GLSL")

    glsl_code = None
    if visual_description:
        try:
            print("\n初始化 Generate Agent...")
            generate_agent = GenerateAgent()
            print(f"模型: {generate_agent.model}")

            print("\n正在生成 GLSL 着色器代码...")
            start_time = time.time()

            # 直接调用 chat 方法，使用更大的 max_tokens
            user_prompt = (
                "请根据以下视效语义描述生成 GLSL 着色器代码：\n"
                f"```json\n{json.dumps(visual_description, indent=2, ensure_ascii=False)}\n```"
            )
            response = generate_agent.chat(
                system_prompt=generate_agent.system_prompt,
                user_prompt=user_prompt,
                temperature=0.5,
                max_tokens=8192,
            )
            glsl_code = GenerateAgent._extract_glsl(response)
            elapsed = time.time() - start_time

            # 检查代码完整性
            glsl_check = check_glsl_completeness(glsl_code)
            if not glsl_check["is_complete"]:
                print(f"\n[警告] GLSL 代码可能不完整:")
                for issue in glsl_check["issues"]:
                    print(f"  - {issue}")
                results["generate_truncated"] = True

            print(f"\n生成完成 (耗时 {elapsed:.2f}s)")
            print(f"\nGLSL 代码 ({glsl_check['line_count']} 行):")
            print("-" * 40)
            print(glsl_code)
            print("-" * 40)
            results["step3_generate"] = True

            # 保存 GLSL 代码
            glsl_path = output_dir / "generated_shader.glsl"
            glsl_path.write_text(glsl_code)
            print(f"\nGLSL 代码已保存至: {glsl_path}")
        except Exception as e:
            print(f"\n[错误] Generate Agent 失败: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("\n[跳过] 无视觉描述数据，跳过生成步骤")

    # ========================================
    # Step 4: Render & Screenshot (Optional)
    # ========================================
    print_separator("Step 4: 渲染与截图 (可选)")

    print("\n此步骤需要 WebGL 环境，在命令行中无法执行。")
    print("如需测试渲染，请启动前端服务并使用 Web 界面。")

    # ========================================
    # Step 5: Inspect Agent (Optional)
    # ========================================
    print_separator("Step 5: Inspect Agent 对比 (可选)")

    print("\n此步骤需要渲染截图，在命令行中无法执行。")
    print("如需测试对比，请启动前端服务并使用 Web 界面。")

    # ========================================
    # Summary
    # ========================================
    print_separator("测试总结")

    print()
    if results["step1_keyframes"]:
        print("✅ Step 1: 关键帧提取 - 成功")
        print(f"   提取了 {len(keyframe_paths)} 张关键帧")
    else:
        print("❌ Step 1: 关键帧提取 - 失败")

    if results["step2_decompose"]:
        status = "成功" if not results["decompose_truncated"] else "成功 (JSON 可能截断)"
        print(f"✅ Step 2: Decompose Agent - {status}")
        if visual_description:
            print(f"   效果名称: {visual_description.get('effect_name', 'N/A')}")
    else:
        print("❌ Step 2: Decompose Agent - 失败")

    if results["step3_generate"]:
        status = "成功" if not results["generate_truncated"] else "成功 (代码可能截断)"
        print(f"✅ Step 3: Generate Agent - {status}")
        if glsl_code:
            print(f"   GLSL 代码长度: {len(glsl_code)} 字符, {glsl_check['line_count']} 行")
    else:
        print("❌ Step 3: Generate Agent - 失败")

    print("\n⏭️  Step 4: 渲染与截图 - 需要 WebGL 环境")
    print("⏭️  Step 5: Inspect Agent - 需要渲染截图")

    if output_dir.exists():
        print(f"\n调试输出目录: {output_dir}")
        for f in output_dir.iterdir():
            print(f"  - {f.name}")

    print_separator("测试完成")


if __name__ == "__main__":
    main()