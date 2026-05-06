"""上下文装配器：为每个 Agent 组装专属视图

基于《视效 Agent 闭环上下文与状态机重构设计方案 (V2.0)》，
严格隔离各 Agent 的上下文，防止信息泄露和注意力稀释。

装配哲学：[超我：底线约束] -> [自我：技能字典] -> [本我：动态任务数据]
"""

import json
from pathlib import Path
from typing import Literal

from app.pipeline.state import PipelineState, GradientEntry
from app.services.skill_loader import SkillLoader


def load_prompt(prompt_name: str) -> str:
    """加载 system prompt"""
    prompt_path = Path(f"app/prompts/{prompt_name}.md")
    if prompt_path.exists():
        return prompt_path.read_text()
    return ""


def truncate_gradient_window(
    gradient_window: list[GradientEntry],
    max_size: int = 3
) -> list[GradientEntry]:
    """
    梯度记忆窗口裁剪
    
    仅保留最近 N 轮的梯度元数据，禁止存放完整代码。
    
    Args:
        gradient_window: 原始梯度窗口
        max_size: 最大长度（默认 3）
    
    Returns:
        裁剪后的梯度窗口（不含 shader 代码）
    """
    if not gradient_window:
        return []
    
    # 截取最近 N 轮
    truncated = gradient_window[-max_size:]
    
    # 确保不包含完整 shader（仅元数据）
    result = []
    for entry in truncated:
        # 仅保留元数据字段
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
    
    用于注入 Generate/Inspect Agent prompt。
    """
    if not gradient_window:
        return ""
    
    lines = []
    for entry in gradient_window:
        iteration = entry.get("iteration", 0)
        score = entry.get("score", 0)
        feedback = entry.get("feedback_summary", "")
        diff = entry.get("shader_diff_summary", "")
        issues_fixed = entry.get("issues_fixed", [])
        issues_remaining = entry.get("issues_remaining", [])
        
        lines.append(f"\n### 第 {iteration} 轮")
        lines.append(f"评分：{score:.2f}")
        
        if feedback:
            fb_preview = feedback[:100] + "..." if len(feedback) > 100 else feedback
            lines.append(f"反馈摘要：{fb_preview}")
        
        if diff:
            lines.append(f"修改摘要：{diff}")
        
        if issues_fixed:
            lines.append(f"解决的问题：{', '.join(issues_fixed)}")
        
        if issues_remaining:
            lines.append(f"未解决的问题：{', '.join(issues_remaining)}")
    
    return "\n".join(lines)


def build_failure_log(state: PipelineState) -> str:
    """
    构建 Re-decompose 时注入 Decompose 的失败日志
    
    包含：
    - 之前使用的 visual_description
    - Inspect Agent 的致命错误说明
    - 失败原因总结
    """
    snapshot = state.get("snapshot", {})
    gradient_window = state.get("gradient_window", [])
    checkpoint = state.get("checkpoint", {})
    
    # 提取失败信息
    last_feedback = snapshot.get("inspect_feedback", {})
    visual_issues = last_feedback.get("visual_issues", [])
    visual_goals = last_feedback.get("visual_goals", [])
    
    # 当前 visual_description
    visual_description = snapshot.get("visual_description", {})
    effect_name = visual_description.get("effect_name", "unknown")
    
    # 近期评分趋势
    recent_scores = [e.get("score", 0) for e in gradient_window[-3:]] if gradient_window else []
    
    failure_log = f"""
=== 重构阻断触发 ===

前一版效果 "{effect_name}" 未能收敛。

**失败原因**：
{chr(10).join(visual_issues[:5]) if visual_issues else '未能达到目标评分'}

**期望效果**：
{chr(10).join(visual_goals[:5]) if visual_goals else '无明确目标'}

**近 {len(recent_scores)} 轮评分**：{recent_scores}

**最高评分**：{checkpoint.get('best_score', 0):.2f}（第 {checkpoint.get('best_iteration', 0)} 轮）

**前一版 visual_description**：
```json
{json.dumps(visual_description, indent=2, ensure_ascii=False)[:500]}...
```

**建议**：
- 重新分析设计参考，可能需要更换底层技术方向
- 注意背景处理要求（如有特殊约束）
- 避免重复之前的失败方向
"""
    return failure_log


class ContextAssembler:
    """Agent 上下文装配器"""
    
    @staticmethod
    def assemble_decompose(
        state: PipelineState,
        mode: Literal["cold_start", "re_decompose"] = "cold_start"
    ) -> dict:
        """
        Decompose Agent 上下文装配
        
        装配顺序：
        1. [System Prompt]：解构约束规则
        2. [Skill Context]：visual-effect-decomposition skill
        3. [UX Reference]：原始设计参考
        4. [Failure Log]（仅重构时注入）：失败负样本
        
        禁止注入：
        - 代码片段
        - 代码级报错
        
        Args:
            state: PipelineState
            mode: "cold_start" | "re_decompose"
        
        Returns:
            dict: {system_prompt, skill_context, user_prompt_parts}
        """
        baseline = state.get("baseline", {})
        
        context = {
            "system_prompt": load_prompt("decompose_system"),
            "skill_context": SkillLoader.build_decompose_context(),
            "ux_reference": {
                "image_paths": baseline.get("image_paths", []),
                "video_info": baseline.get("video_info"),
                "user_notes": baseline.get("user_notes", ""),
            },
        }
        
        # 构建 user_prompt_parts
        user_parts = []
        
        # 1. Skill context 注入
        user_parts.append("--- Skill 知识库参考 ---\n")
        user_parts.append(context["skill_context"])
        user_parts.append("\n---\n\n")
        
        # 2. UX Reference 注入
        video_info = baseline.get("video_info")
        image_paths = baseline.get("image_paths", [])
        user_notes = baseline.get("user_notes", "")
        
        if video_info:
            user_parts.append(f"视频信息：时长 {video_info['duration']:.1f}s，帧率 {video_info['fps']:.0f}fps。")
            user_parts.append(f"以下 {len(image_paths)} 张图片是从视频中均匀提取的关键帧。")
        elif image_paths:
            user_parts.append(f"以下是 {len(image_paths)} 张设计稿图片。")
        else:
            user_parts.append("用户仅提供文本描述，没有图片参考。请根据用户描述直接生成视效语义描述。")
        
        if user_notes:
            user_parts.append(f"\n用户附加标注：{user_notes}")
        
        # 3. Failure Log 注入（仅重构时）
        if mode == "re_decompose":
            failure_log = build_failure_log(state)
            user_parts.append(f"\n---\n{failure_log}")
        
        context["user_prompt_parts"] = user_parts
        context["image_paths"] = image_paths
        
        return context
    
    @staticmethod
    def assemble_generate(state: PipelineState) -> dict:
        """
        Generate Agent 上下文装配
        
        装配顺序：
        1. [System Prompt]：代码结构规范与红线
        2. [Skill Context]：effect-dev skill
        3. [Baseline Blueprint]：visual_description（自然语言）
        4. [Current State]：上一轮 shader 代码
        5. [Feedback]：Inspect 语义反馈
        6. [Short-term Memory]：梯度历史（裁剪后）
        
        禁止注入：
        - 原始图片
        - 渲染截图
        
        Args:
            state: PipelineState
        
        Returns:
            dict: {system_prompt, skill_context, user_prompt_parts}
        """
        snapshot = state.get("snapshot", {})
        config = state.get("config", {})
        
        context = {
            "system_prompt": load_prompt("generate_system"),
            "skill_context": SkillLoader.build_generate_context(),
        }
        
        # 构建 user_prompt_parts
        user_parts = []
        
        # 1. Skill context 注入
        user_parts.append("--- Skill 知识库参考 ---\n")
        user_parts.append(context["skill_context"])
        user_parts.append("\n---\n\n")
        
        # 2. Visual description 注入（自然语言）
        visual_description = snapshot.get("visual_description", {})
        if visual_description:
            user_parts.append("请根据以下视效语义描述生成 GLSL 着色器代码：\n")
            user_parts.append(f"```json\n{json.dumps(visual_description, indent=2, ensure_ascii=False)}\n```")
        
        # 3. Current shader 注入（上一轮代码）
        shader = snapshot.get("shader", "")
        iteration = snapshot.get("iteration", 0)
        if shader and iteration > 0:
            user_parts.append(f"\n---\n上一轮生成的着色器代码（第 {iteration} 轮）：")
            user_parts.append(f"```glsl\n{shader}\n```")
        
        # 4. Inspect feedback 注入（语义反馈）
        inspect_feedback = snapshot.get("inspect_feedback")
        if inspect_feedback:
            visual_issues = inspect_feedback.get("visual_issues", [])
            visual_goals = inspect_feedback.get("visual_goals", [])
            previous_score = inspect_feedback.get("previous_score_reference", {})
            
            if visual_issues:
                issues_text = "\n".join([f"- {issue}" for issue in visual_issues])
                user_parts.append(f"\n---\n[视觉问题]\n{issues_text}")
            
            if visual_goals:
                goals_text = "\n".join([f"- {goal}" for goal in visual_goals])
                user_parts.append(f"\n[期望效果]\n{goals_text}")
            
            if previous_score:
                user_parts.append(f"\n[评分参考] 上轮 {previous_score.get('previous_score', 0):.2f} → 本轮 {previous_score.get('delta', 0):+.2f}")
        
        # 5. 梯度历史注入（裁剪后）
        gradient_window = truncate_gradient_window(
            state.get("gradient_window", []),
            config.get("gradient_window_size", 3)
        )
        if gradient_window:
            history_text = format_gradient_history(gradient_window)
            user_parts.append(f"\n---\n[近期修改记录]\n{history_text}")
            user_parts.append("\n请参考近期记录，避免重复已尝试但无效的修改方向。")
        
        # 6. 用户人工反馈注入
        if state.get("human_feedback"):
            user_parts.append(f"\n---\n[用户检视指令]\n{state['human_feedback']}\n请根据用户指令调整着色器效果。")
        
        context["user_prompt_parts"] = user_parts
        context["visual_description"] = visual_description
        context["current_shader"] = shader
        
        return context
    
    @staticmethod
    def assemble_inspect(state: PipelineState) -> dict:
        """
        Inspect Agent 上下文装配
        
        装配顺序：
        1. [System Prompt]：评分标准与反馈输出要求
        2. [Skill Context]：visual-effect-critique skill
        3. [UX Reference]：原始设计稿基准
        4. [Current Render]：渲染截图
        5. [Current Shader]：完整代码（不截断）
        6. [Momentum State]：评分趋势
        
        禁止注入：
        - DSL AST
        - 参数约束
        
        Args:
            state: PipelineState
        
        Returns:
            dict: {system_prompt, skill_context, user_prompt_parts, image_paths}
        """
        baseline = state.get("baseline", {})
        snapshot = state.get("snapshot", {})
        config = state.get("config", {})
        
        context = {
            "system_prompt": load_prompt("inspect_system"),
            "skill_context": SkillLoader.build_inspect_context(),
        }
        
        # 构建 user_prompt_parts
        user_parts = []
        
        # 1. Skill context 注入
        user_parts.append("--- Skill 知识库参考 ---\n")
        user_parts.append(context["skill_context"])
        user_parts.append("\n---\n\n")
        
        # 2. 任务描述
        iteration = snapshot.get("iteration", 0)
        user_parts.append(f"请对比以下渲染结果与设计参考，进行第 {iteration + 1} 次评估。")
        
        # 3. Visual description 注入（作为对比基准）
        visual_description = snapshot.get("visual_description", {})
        if visual_description:
            effect_name = visual_description.get("effect_name", "")
            user_parts.append(f"\n---\n期望效果：{effect_name}")
            
            # 注入关键定义（背景重点关注）
            background_def = visual_description.get("background_definition", {})
            if background_def:
                user_parts.append(f"\n[背景要求] {background_def.get('description', '')}")
                if background_def.get("important"):
                    user_parts.append(f"⚠️ {background_def['important']}")
        
        # 4. 梯度历史注入（评分趋势）
        gradient_window = truncate_gradient_window(
            state.get("gradient_window", []),
            config.get("gradient_window_size", 3)
        )
        if gradient_window:
            recent_scores = [e.get("score", 0) for e in gradient_window[-3:]]
            user_parts.append(f"\n---\n[评分趋势] 近 3 轮评分：{recent_scores}")
            
            # 停滞检测提示
            variance_threshold = config.get("stagnation_variance", 0.05)
            if len(recent_scores) >= 3:
                variance = max(recent_scores) - min(recent_scores)
                if variance < variance_threshold:
                    user_parts.append(f"\n⚠️ 评分停滞（波动 < {variance_threshold}），可能需要触发重构或更换方向。")
        
        # 5. 用户人工迭代提示
        if state.get("human_iteration_mode") and state.get("human_feedback"):
            user_parts.append(f"\n---\n[人工迭代模式]\n用户反馈：{state['human_feedback']}")
            user_parts.append("\n请根据用户反馈评估当前效果是否满足要求。")
        
        # 6. Shader 注入（完整代码，不截断）
        shader = snapshot.get("shader", "")
        if shader:
            user_parts.append(f"\n---\n当前 Shader 代码：\n```glsl\n{shader}\n```")
        
        context["user_prompt_parts"] = user_parts
        
        # 收集图片路径
        design_images = baseline.get("image_paths", [])
        render_screenshots = snapshot.get("render_screenshots", [])
        all_image_paths = design_images[:3] + render_screenshots[:3]
        context["image_paths"] = all_image_paths
        
        return context


# === 辅助函数：构建完整 prompt ===

def build_decompose_prompt(state: PipelineState, mode: str = "cold_start") -> tuple[str, str, list[str]]:
    """
    构建 Decompose Agent 的完整 prompt
    
    Returns:
        (system_prompt, user_prompt, image_paths)
    """
    context = ContextAssembler.assemble_decompose(state, mode)
    user_prompt = "\n".join(context["user_prompt_parts"])
    return context["system_prompt"], user_prompt, context.get("image_paths", [])


def build_generate_prompt(state: PipelineState) -> tuple[str, str]:
    """
    构建 Generate Agent 的完整 prompt
    
    Returns:
        (system_prompt, user_prompt)
    """
    context = ContextAssembler.assemble_generate(state)
    user_prompt = "\n".join(context["user_prompt_parts"])
    return context["system_prompt"], user_prompt


def build_inspect_prompt(state: PipelineState) -> tuple[str, str, list[str]]:
    """
    构建 Inspect Agent 的完整 prompt
    
    Returns:
        (system_prompt, user_prompt, image_paths)
    """
    context = ContextAssembler.assemble_inspect(state)
    user_prompt = "\n".join(context["user_prompt_parts"])
    return context["system_prompt"], user_prompt, context.get("image_paths", [])