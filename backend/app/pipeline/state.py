"""Pipeline 状态定义"""

from typing import TypedDict


class PhaseLog(TypedDict, total=False):
    """Phase execution log entry"""
    phase: str                          # "extract_keyframes" | "decompose" | "generate" | "render" | "inspect" | "validate_shader"
    timestamp: float                    # Unix timestamp
    status: str                         # "started" | "running" | "completed" | "failed"
    message: str                        # Human-readable progress message
    details: str | None                 # Additional details (e.g., agent thinking, tool output)
    duration_ms: int | None             # Phase duration in milliseconds
    agent_response: str | None          # Agent's raw response (for displaying reasoning)


class PipelineState(TypedDict, total=False):
    # Pipeline identification
    pipeline_id: str                    # Pipeline UUID
    
    # 输入
    input_type: str                     # "video" | "image"
    video_path: str | None              # 视频文件路径
    image_paths: list[str]              # 图片路径列表
    user_notes: str                     # 用户附加参数标注
    video_info: dict | None             # 视频元信息

    # 关键帧（视频输入时由 extractor 生成）
    keyframe_paths: list[str]           # 提取的关键帧路径

    # Decompose Agent 产出
    visual_description: dict            # 视效语义描述

    # 迭代状态
    iteration: int                      # 当前迭代轮次（从 0 开始）
    max_iterations: int                 # 最大迭代次数
    current_shader: str                 # 当前 GLSL 代码
    compile_error: str | None           # 编译/渲染错误信息
    validation_errors: str | None       # Shader 验证错误信息（静态检查）
    validation_warnings: str | None     # Shader 验证警告（不影响渲染）
    compile_retry_count: int            # [DEPRECATED] 编译错误次数记录（仅用于日志，不控制流程）

    # Inspect Agent 产出
    inspect_result: dict | None         # 评估结果
    passed: bool                        # 是否通过检视

    # 截图
    render_screenshots: list[str]       # 渲染截图路径
    design_screenshots: list[str]       # 设计参考截图路径

    # Pipeline 状态
    status: str                         # "running" | "passed" | "failed" | "max_iterations"
    error: str | None                   # 错误信息
    history: list[dict]                 # Pipeline 级别的迭代历史记录

    # Agent 专属上下文历史（每个 Agent 保留自己的工作记录）
    generate_history: list[dict]        # Generate Agent 历史：[{iteration, feedback_received, shader_preview, duration_ms}]
    inspect_history: list[dict]         # Inspect Agent 历史：[{iteration, score, feedback, issues_summary}]

    # 用户人工干预相关
    human_feedback: str | None           # 用户自然语言检视命令
    human_modified_shader: str | None    # 用户在编辑器中修改的代码（可选）
    human_iteration_mode: bool           # 是否处于人工迭代模式
    human_iteration_count: int           # 人工迭代计数（用于日志区分）

    # Phase tracking (new fields for enhanced logging)
    current_phase: str                  # Current pipeline phase
    phase_status: str                   # Phase status: "running" | "completed" | "failed"
    phase_message: str                  # Human-readable progress message
    phase_start_time: float | None      # Phase start timestamp
    detailed_logs: list[PhaseLog]       # Detailed execution logs