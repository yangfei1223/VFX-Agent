"""Pipeline 状态定义 - V3.0 四区划分架构

基于《视效 Agent 闭环上下文与状态机重构设计方案 (V2.0)》，
采用中心化状态总线，物理划分为四个隔离数据区。

架构变更：
- 弃用 DSL AST，改为自然语言结构化描述
- 四区划分：baseline / snapshot / gradient_window / checkpoint
- 物理回滚机制：防止劣化累积
- 梯度裁剪：禁止历史注入完整代码
"""

from typing import TypedDict


class PhaseLog(TypedDict, total=False):
    """Phase execution log entry"""
    phase: str                          # "extract_keyframes" | "decompose" | "generate" | "render" | "inspect" | "validate_shader"
    timestamp: float                    # Unix timestamp
    status: str                         # "started" | "running" | "completed" | "failed"
    message: str                        # Human-readable progress message
    details: str | None                 # Additional details
    duration_ms: int | None             # Phase duration in milliseconds
    agent_response: str | None          # Agent's raw response


class BaselineRegion(TypedDict, total=False):
    """只读基线区 (Read-Only Baseline)
    
    存放原始设计参考、初始文本指令、全局约束。
    单次任务内不可变。
    """
    input_type: str                     # "video" | "image" | "text"
    video_path: str | None              # 视频文件路径
    image_paths: list[str]              # 图片路径列表
    user_notes: str                     # 用户附加参数标注
    video_info: dict | None             # 视频元信息
    keyframe_paths: list[str]           # 提取的关键帧路径
    constraints: dict                   # 性能约束 {max_alu, target_fps}


class SnapshotRegion(TypedDict, total=False):
    """当前快照区 (Current Snapshot)
    
    存放最新单步状态：DSL、shader、截图、反馈。
    每轮迭代更新。
    """
    visual_description: dict            # Decompose 输出（自然语言结构化）
    shader: str                         # 当前 GLSL 代码
    render_screenshots: list[str]       # 渲染截图路径
    inspect_feedback: dict | None       # Inspect 输出
    iteration: int                      # 当前迭代轮次
    compile_error: str | None           # 编译/渲染错误
    validation_errors: str | None       # 验证错误


class GradientEntry(TypedDict, total=False):
    """梯度记忆条目
    
    仅存放梯度元数据，禁止存放完整代码。
    """
    iteration: int                      # 迭代轮次
    score: float                        # 评分
    feedback_summary: str               # 反馈摘要（前 100 字）
    shader_diff_summary: str | None     # 本轮修改摘要（不存完整代码）
    issues_fixed: list[str] | None      # 解决的问题
    issues_remaining: list[str] | None  # 未解决的问题
    duration_ms: int                    # 耗时
    human_iteration: bool               # 是否为人工迭代


class CheckpointRegion(TypedDict, total=False):
    """回滚锚点区 (Checkpointing)
    
    记录 best_score 与 best_shader。
    作为防劣化的物理隔离备份。
    """
    best_score: float                   # 最高评分
    best_shader: str                    # 最优 shader 代码
    best_iteration: int                 # 最优迭代轮次
    best_visual_description: dict       # 最优 visual_description
    best_render_screenshots: list[str]  # 最优渲染截图


class PipelineConfig(TypedDict, total=False):
    """Pipeline 配置参数（可调）"""
    max_iterations: int                 # 最大迭代次数（默认 5）
    passing_threshold: float            # 通过阈值（默认 0.85）
    re_decompose_threshold: float       # 重构触发阈值（默认 0.5）
    gradient_window_size: int           # 梯度窗口长度（默认 3）
    stagnation_variance: float          # 停滞判定波动阈值（默认 0.05）
    stagnation_window: int              # 停滞检测窗口（默认 3）
    render_timeout_ms: int              # 渲染超时（默认 2000）
    screenshot_width: int               # 截图宽度（默认 1024）
    screenshot_height: int              # 截图高度（默认 1024)


class PipelineState(TypedDict, total=False):
    """Pipeline 状态 - V3.0 四区划分架构
    
    === 1. 只读基线区 (Read-Only Baseline) ===
    baseline: BaselineRegion            # 单次任务不可变
    
    === 2. 当前快照区 (Current Snapshot) ===
    snapshot: SnapshotRegion            # 每轮更新
    
    === 3. 梯度记忆窗口 (Sliding Window History) ===
    gradient_window: list[GradientEntry]  # 最大长度 N (可配置)
    
    === 4. 回滚锚点区 (Checkpointing) ===
    checkpoint: CheckpointRegion        # 物理隔离备份
    
    === 配置参数 ===
    config: PipelineConfig              # 可调参数
    
    === Pipeline 元数据 ===
    pipeline_id: str
    status: str                         # "running" | "passed" | "failed" | "re_decompose" | "max_iterations"
    error: str | None
    
    === Phase tracking ===
    current_phase: str
    phase_status: str
    phase_message: str
    phase_start_time: float | None
    detailed_logs: list[PhaseLog]
    
    === 用户人工干预 ===
    human_feedback: str | None
    human_iteration_mode: bool
    human_iteration_count: int
    
    === 向后兼容字段（迁移阶段保留） ===
    # 以下字段将在迁移完成后废弃，当前保留以便逐步迁移
    design_screenshots: list[str]       # → baseline.image_paths
    passed: bool                        # → snapshot.inspect_feedback.passed
    history: list[dict]                 # → gradient_window
    generate_history: list[dict]        # → gradient_window (Generate Agent)
    inspect_history: list[dict]         # → gradient_window (Inspect Agent)


def create_initial_state(
    pipeline_id: str,
    input_type: str,
    video_path: str | None = None,
    image_paths: list[str] = [],
    user_notes: str = "",
    config: PipelineConfig | None = None,
) -> PipelineState:
    """创建初始 Pipeline State（四区划分版）
    
    Args:
        pipeline_id: Pipeline UUID
        input_type: 输入类型 ("video" | "image" | "text")
        video_path: 视频路径（可选）
        image_paths: 图片路径列表
        user_notes: 用户标注
        config: Pipeline 配置（可选，使用默认值）
    
    Returns:
        初始化的四区划分 PipelineState
    """
    # 默认配置
    default_config: PipelineConfig = {
        "max_iterations": 5,
        "passing_threshold": 0.85,
        "re_decompose_threshold": 0.5,
        "gradient_window_size": 3,
        "stagnation_variance": 0.05,
        "stagnation_window": 3,
        "render_timeout_ms": 2000,
        "screenshot_width": 1024,
        "screenshot_height": 1024,
    }
    
    # 初始化四区
    baseline: BaselineRegion = {
        "input_type": input_type,
        "video_path": video_path,
        "image_paths": image_paths,
        "user_notes": user_notes,
        "video_info": None,
        "keyframe_paths": [],
        "constraints": {
            "max_alu": 256,
            "target_fps": 60,
        },
    }
    
    snapshot: SnapshotRegion = {
        "visual_description": {},
        "shader": "",
        "render_screenshots": [],
        "inspect_feedback": None,
        "iteration": 0,
        "compile_error": None,
        "validation_errors": None,
    }
    
    checkpoint: CheckpointRegion = {
        "best_score": 0.0,
        "best_shader": "",
        "best_iteration": 0,
        "best_visual_description": {},
        "best_render_screenshots": [],
    }
    
    return {
        # 四区
        "baseline": baseline,
        "snapshot": snapshot,
        "gradient_window": [],
        "checkpoint": checkpoint,
        
        # 配置
        "config": config or default_config,
        
        # 元数据
        "pipeline_id": pipeline_id,
        "status": "running",
        "error": None,
        
        # Phase tracking
        "current_phase": "extract_keyframes",
        "phase_status": "running",
        "phase_message": "Initializing pipeline...",
        "phase_start_time": None,
        "detailed_logs": [],
        
        # 用户人工干预
        "human_feedback": None,
        "human_iteration_mode": False,
        "human_iteration_count": 0,
        
        # 向后兼容（迁移阶段）
        "design_screenshots": image_paths,
        "passed": False,
        "history": [],
        "generate_history": [],
        "inspect_history": [],
    }


def migrate_legacy_state(old_state: dict) -> PipelineState:
    """迁移旧版 PipelineState 到四区划分版
    
    Args:
        old_state: 旧版扁平 state dict
    
    Returns:
        四区划分 PipelineState
    """
    # 提取 baseline 字段
    baseline: BaselineRegion = {
        "input_type": old_state.get("input_type", "text"),
        "video_path": old_state.get("video_path"),
        "image_paths": old_state.get("image_paths", []),
        "user_notes": old_state.get("user_notes", ""),
        "video_info": old_state.get("video_info"),
        "keyframe_paths": old_state.get("keyframe_paths", []),
        "constraints": {
            "max_alu": 256,
            "target_fps": 60,
        },
    }
    
    # 提取 snapshot 字段
    snapshot: SnapshotRegion = {
        "visual_description": old_state.get("visual_description", {}),
        "shader": old_state.get("current_shader", ""),
        "render_screenshots": old_state.get("render_screenshots", []),
        "inspect_feedback": old_state.get("inspect_result"),
        "iteration": old_state.get("iteration", 0),
        "compile_error": old_state.get("compile_error"),
        "validation_errors": old_state.get("validation_errors"),
    }
    
    # 提取 gradient_window（从 history 或 generate_history）
    old_history = old_state.get("history", [])
    old_generate_history = old_state.get("generate_history", [])
    gradient_window: list[GradientEntry] = []
    
    # 合并历史记录（优先使用 generate_history）
    if old_generate_history:
        for entry in old_generate_history:
            gradient_window.append({
                "iteration": entry.get("iteration", 0),
                "score": old_state.get("inspect_history", [{}])[entry.get("iteration", 0)].get("score", 0) if entry.get("iteration", 0) < len(old_state.get("inspect_history", [])) else 0,
                "feedback_summary": entry.get("feedback_received", "")[:100] if entry.get("feedback_received") else "",
                "shader_diff_summary": None,
                "issues_fixed": None,
                "issues_remaining": None,
                "duration_ms": entry.get("duration_ms", 0),
                "human_iteration": entry.get("human_iteration", False),
            })
    elif old_history:
        for entry in old_history:
            gradient_window.append({
                "iteration": entry.get("iteration", 0),
                "score": entry.get("score", 0),
                "feedback_summary": entry.get("feedback", "")[:100] if entry.get("feedback") else "",
                "shader_diff_summary": None,
                "issues_fixed": None,
                "issues_remaining": None,
                "duration_ms": 0,
                "human_iteration": entry.get("human_iteration", False),
            })
    
    # 提取 checkpoint（从历史中找最高分）
    best_score = 0.0
    best_shader = ""
    best_iteration = 0
    best_visual_description = {}
    
    if gradient_window:
        best_entry = max(gradient_window, key=lambda x: x.get("score", 0))
        best_score = best_entry.get("score", 0)
        best_iteration = best_entry.get("iteration", 0)
        # best_shader 需要从其他来源获取（如果有的话）
    
    checkpoint: CheckpointRegion = {
        "best_score": best_score,
        "best_shader": old_state.get("current_shader", ""),  # 当前作为初始备份
        "best_iteration": best_iteration,
        "best_visual_description": old_state.get("visual_description", {}),
        "best_render_screenshots": [],
    }
    
    # 提取 config
    config: PipelineConfig = {
        "max_iterations": old_state.get("max_iterations", 5),
        "passing_threshold": 0.85,
        "re_decompose_threshold": 0.5,
        "gradient_window_size": 3,
        "stagnation_variance": 0.05,
        "stagnation_window": 3,
        "render_timeout_ms": old_state.get("render_timeout_ms", 2000),
        "screenshot_width": old_state.get("screenshot_width", 1024),
        "screenshot_height": old_state.get("screenshot_height", 1024),
    }
    
    return {
        "baseline": baseline,
        "snapshot": snapshot,
        "gradient_window": gradient_window,
        "checkpoint": checkpoint,
        "config": config,
        "pipeline_id": old_state.get("pipeline_id", ""),
        "status": old_state.get("status", "running"),
        "error": old_state.get("error"),
        "current_phase": old_state.get("current_phase", ""),
        "phase_status": old_state.get("phase_status", ""),
        "phase_message": old_state.get("phase_message", ""),
        "phase_start_time": old_state.get("phase_start_time"),
        "detailed_logs": old_state.get("detailed_logs", []),
        "human_feedback": old_state.get("human_feedback"),
        "human_iteration_mode": old_state.get("human_iteration_mode", False),
        "human_iteration_count": old_state.get("human_iteration_count", 0),
        # 向后兼容
        "design_screenshots": old_state.get("design_screenshots", []),
        "passed": old_state.get("passed", False),
        "history": old_history,
        "generate_history": old_generate_history,
        "inspect_history": old_state.get("inspect_history", []),
    }