"""上下文装配器：为每个 Agent 组装 prompt

VFX-Agent V2.0：
- Prompt Stack 层叠：System Prompt + Shared Constraints + Effect Catalog + User Prompt
- Shared Constraints: P0/P1/P2 禁止项（三 Agent 共享）
- Effect Catalog: Closed Vocabulary Token 库（Decompose/Generate 共享）
"""

import json
from pathlib import Path
from typing import Literal

from app.pipeline.state import PipelineState, GradientEntry


def load_prompt(prompt_name: str) -> str:
    """加载 system prompt（已包含 skill 内容）
    
    V2.0: Prompt 文件缺失时打印警告而非静默返回空字符串
    """
    prompt_path = Path(f"app/prompts/{prompt_name}.md")
    if prompt_path.exists():
        return prompt_path.read_text()
    
    # Prompt 文件缺失警告
    print(f"WARNING: Prompt file not found: {prompt_path}")
    print(f"  Agent will receive empty system prompt!")
    return ""


def truncate_gradient_window(
    gradient_window: list[GradientEntry],
    max_size: int = 3
) -> list[GradientEntry]:
    """
    梯度记忆窗口裁剪
    
    仅保留最近 N 轮的梯度元数据，禁止存放完整代码。
    """
    if not gradient_window:
        return []
    
    # 截取最近 N 轮
    truncated = gradient_window[-max_size:]
    
    # 确保不包含完整 shader（仅元数据）
    result = []
    for entry in truncated:
        safe_entry: GradientEntry = {
            "iteration": entry.get("iteration", 0),
            "score": entry.get("score", 0),
            "feedback_summary": entry.get("feedback_summary", ""),
            "shader_diff_summary": entry.get("shader_diff_summary"),
            "issues_fixed": entry.get("issues_fixed"),
            "issues_remaining": entry.get("issues_remaining"),
            "duration_ms": entry.get("duration_ms", 0),
            "human_iteration": entry.get("human_iteration", False),
        }
        result.append(safe_entry)
    
    return result


def format_gradient_history(gradient_window: list[GradientEntry]) -> str:
    """
    格式化梯度历史为自然语言
    """
    if not gradient_window:
        return ""
    
    lines = []
    for entry in gradient_window:
        iteration = entry.get("iteration", 0)
        score = entry.get("score", 0)
        feedback = entry.get("feedback_summary", "")
        issues_remaining = entry.get("issues_remaining", [])
        
        lines.append(f"\n### 第 {iteration} 轮")
        lines.append(f"评分：{score:.2f}")
        
        if feedback:
            fb_preview = feedback[:100] + "..." if len(feedback) > 100 else feedback
            lines.append(f"反馈摘要：{fb_preview}")
        
        if issues_remaining:
            lines.append(f"未解决的问题：{', '.join(issues_remaining)}")
    
    return "\n".join(lines)


def build_failure_log(state: PipelineState) -> str:
    """
    构建 Re-decompose 时注入 Decompose 的失败日志
    
    V2.0: 包含多轮失败历史（从 gradient_window 提取）
    """
    snapshot = state.get("snapshot", {})
    gradient_window = state.get("gradient_window", [])
    checkpoint = state.get("checkpoint", {})
    
    last_feedback = snapshot.get("inspect_feedback", {})
    visual_issues = last_feedback.get("visual_issues", [])
    visual_goals = last_feedback.get("visual_goals", [])
    
    visual_description = snapshot.get("visual_description", {})
    # V2.0: 优先使用 effect_type，兼容旧版 effect_name
    effect_type = visual_description.get("effect_type") or visual_description.get("effect_name", "unknown")
    
    # V2.0: 提取多轮失败历史
    recent_scores = [e.get("score", 0) for e in gradient_window[-3:]] if gradient_window else []
    recent_issues = []
    for entry in gradient_window[-3:]:
        issues = entry.get("issues_remaining", [])
        if issues:
            recent_issues.extend(issues)
    
    # 构建失败日志
    failure_log = f"""
=== 重构阻断触发 ===

前一版效果 "{effect_type}" 未能收敛。

**本轮失败原因**：
{chr(10).join(visual_issues[:5]) if visual_issues else '未能达到目标评分'}

**期望效果**：
{chr(10).join(visual_goals[:5]) if visual_goals else '无明确目标'}

**历史评分趋势**：{recent_scores}
（近 {len(recent_scores)} 轮评分变化）

**累积未解决问题**：
{chr(10).join(recent_issues[:8]) if recent_issues else '无历史记录'}

**最高评分**：{checkpoint.get('best_score', 0):.2f}（第 {checkpoint.get('best_iteration', 0)} 轮）

**建议**：
- 重新分析设计参考，可能需要更换底层技术方向
- 避免重复之前的失败方向：{chr(10).join([f"  - {issue}" for issue in recent_issues[:3]]) if recent_issues else '无历史记录'}
- 如果最高评分 >0.6，可参考第 {checkpoint.get('best_iteration', 0)} 轮的成功参数
"""
    return failure_log


def build_decompose_prompt(
    state: PipelineState,
    mode: Literal["cold_start", "re_decompose"] = "cold_start"
) -> tuple[str, str, list[str]]:
    """
    构建 Decompose Agent 的 prompt
    
    Prompt Stack:
    - Layer 1: Shared VFX Constraints (P0 禁止项)
    - Layer 2: VFX Effect Catalog (Closed Vocabulary)
    - Layer 3: Decompose System Prompt (强制步骤 + Self-check)
    
    Returns:
        (system_prompt, user_prompt, image_paths)
    """
    baseline = state.get("baseline", {})
    
    # Prompt Stack 层叠注入
    constraints = load_prompt("shared_vfx_constraints")
    catalog = load_prompt("vfx_effect_catalog")
    base_system = load_prompt("decompose_system")
    
    # 组装 System Prompt（按 Layer 顺序）
    system_prompt = f"{base_system}\n\n---\n\n{constraints}\n\n---\n\n{catalog}"
    
    # User prompt
    user_parts = []
    
    # 1. UX Reference
    image_paths = baseline.get("image_paths", [])
    user_notes = baseline.get("user_notes", "")
    
    if image_paths:
        user_parts.append(f"### 设计参考图片\n以下是需要分析的图片：\n{chr(10).join(image_paths)}")
    
    if user_notes:
        user_parts.append(f"### 用户描述\n{user_notes}")
    
    # 2. Failure log (仅 re_decompose 模式)
    if mode == "re_decompose":
        failure_log = build_failure_log(state)
        user_parts.append(failure_log)
    
    user_prompt = "\n\n".join(user_parts)
    
    return system_prompt, user_prompt, image_paths


def build_generate_prompt(state: PipelineState) -> tuple[str, str]:
    """
    构建 Generate Agent 的 prompt
    
    Prompt Stack:
    - Layer 1: Shared VFX Constraints (P0: raymarching, texture >8)
    - Layer 2: VFX Effect Catalog (算子映射)
    - Layer 3: Generate System Prompt (强制步骤 + Self-check)
    
    V2.0: 注入回滚标记（如果触发）
    """
    snapshot = state.get("snapshot", {})
    config = state.get("config", {})
    
    # Prompt Stack 层叠注入
    constraints = load_prompt("shared_vfx_constraints")
    catalog = load_prompt("vfx_effect_catalog")
    base_system = load_prompt("generate_system")
    
    # 组装 System Prompt（按 Layer 顺序）
    system_prompt = f"{base_system}\n\n---\n\n{constraints}\n\n---\n\n{catalog}"
    
    # User prompt
    user_parts = []
    
    # V2.0: 回滚标记注入（如果触发）
    if state.get("rollback_triggered"):
        checkpoint = state.get("checkpoint", {})
        rollback_info = f"""
[SYSTEM ROLLBACK]
系统已回滚到第 {checkpoint.get('best_iteration', 0)} 轮的优质代码。

**回滚原因**：当前评分低于上一轮，质量退化
**回滚前评分**：{snapshot.get('inspect_feedback', {}).get('overall_score', 0):.2f}
**回滚后评分**：{checkpoint.get('best_score', 0):.2f}

**建议**：
- 废弃刚才尝试的方向
- 探索新的参数组合（而非继续微调）
- 参考 best_iteration 的成功参数
"""
        user_parts.append(rollback_info)
    
    # 1. Visual Description
    visual_description = snapshot.get("visual_description", {})
    if visual_description:
        user_parts.append(f"### Visual Description\n```json\n{json.dumps(visual_description, indent=2, ensure_ascii=False)}\n```")
    
    # 2. Previous Shader (仅修正模式)
    previous_shader = snapshot.get("shader", "")
    iteration = snapshot.get("iteration", 0)
    
    if previous_shader and iteration > 0:
        user_parts.append(f"### 当前 Shader（第 {iteration} 轮）\n```glsl\n{previous_shader}\n```")
    
    # 3. Feedback (仅修正模式)
    inspect_feedback = snapshot.get("inspect_feedback")
    if inspect_feedback and iteration > 0:
        visual_issues = inspect_feedback.get("visual_issues", [])
        visual_goals = inspect_feedback.get("visual_goals", [])
        
        if visual_issues:
            issues_text = chr(10).join([f"- {issue}" for issue in visual_issues])
            user_parts.append(f"### 视觉问题\n{issues_text}")
        
        if visual_goals:
            goals_text = chr(10).join([f"- {goal}" for goal in visual_goals])
            user_parts.append(f"### 期望效果\n{goals_text}")
    
    # 4. Human Feedback (如有)
    human_feedback = state.get("human_feedback")
    if human_feedback:
        user_parts.append(f"### 用户反馈\n{human_feedback}")
    
    # 5. Gradient History (如有)
    gradient_window = truncate_gradient_window(
        state.get("gradient_window", []),
        config.get("gradient_window_size", 3)
    )
    
    if gradient_window:
        history_text = format_gradient_history(gradient_window)
        user_parts.append(f"### 修改历史\n{history_text}")
    
    user_prompt = "\n\n".join(user_parts)
    
    return system_prompt, user_prompt


def build_inspect_prompt(state: PipelineState) -> tuple[str, str, list[str]]:
    """
    构建 Inspect Agent 的 prompt
    
    Prompt Stack:
    - Layer 1: Shared VFX Constraints (P0: 模糊反馈)
    - Layer 2: VFX Effect Catalog (对比基准 - V2.0 新增)
    - Layer 3: Inspect System Prompt (强制步骤 + Self-check)
    
    Returns:
        (system_prompt, user_prompt, image_paths)
    """
    baseline = state.get("baseline", {})
    snapshot = state.get("snapshot", {})
    
    # Prompt Stack 层叠注入
    # V2.0: Inspect 也注入 Effect Catalog，用于验证 effect_type、sdf_type 等 Token
    constraints = load_prompt("shared_vfx_constraints")
    catalog = load_prompt("vfx_effect_catalog")
    base_system = load_prompt("inspect_system")
    
    # 组装 System Prompt
    system_prompt = f"{base_system}\n\n---\n\n{constraints}\n\n---\n\n{catalog}"
    
    # User prompt
    user_parts = []
    
    # 1. UX Reference
    design_screenshots = baseline.get("keyframe_paths", [])
    if design_screenshots:
        user_parts.append(f"### 设计参考\n{chr(10).join(design_screenshots)}")
    
    # 2. Render Screenshots
    render_screenshots = snapshot.get("render_screenshots", [])
    if render_screenshots:
        user_parts.append(f"### 渲染截图\n{chr(10).join(render_screenshots)}")
    
    # 3. Visual Description
    visual_description = snapshot.get("visual_description", {})
    if visual_description:
        user_parts.append(f"### Visual Description\n```json\n{json.dumps(visual_description, indent=2, ensure_ascii=False)}\n```")
    
    # 4. Current Shader
    shader = snapshot.get("shader", "")
    if shader:
        user_parts.append(f"### 当前 Shader\n```glsl\n{shader}\n```")
    
    # 5. Human Feedback (如有)
    human_feedback = state.get("human_feedback")
    if human_feedback:
        user_parts.append(f"### 用户反馈\n{human_feedback}")
    
    user_prompt = "\n\n".join(user_parts)
    
    # 合并图片路径（设计参考 + 渲染截图）
    image_paths = design_screenshots + render_screenshots
    
    return system_prompt, user_prompt, image_paths