"""Pipeline State Definition - V3.0 4-Region Architecture

Based on design doc: Visual Effect Agent Context & State Machine Refactoring (V2.0)

Architecture changes:
- Deprecate DSL AST, use natural language structured description
- 4-region partition: baseline / snapshot / gradient_window / checkpoint
- Physical rollback: prevent quality degradation accumulation
- Gradient truncation: no full shader in history

V2.0 Enhancement:
- VisualDescriptionV2: Closed Vocabulary + Required Fields
- Required: primary_rgb, duration, edge_width, strict
"""

from typing import TypedDict


# === Visual Description V2.0 TypedDicts (Required Fields) ===


class ShapeDefinitionV2(TypedDict, total=False):
    """Shape Definition (V2.0 - Required edge_width)
    
    Required fields enforced by Self-check.
    """
    sdf_type: str  # Must use Token: {sdf.circle}, {sdf.box}, etc.
    center: str  # e.g., "vec2(0.5, 0.5)"
    radius: float | None
    size: str | None
    edge_type: str  # {edge.soft_medium}, {edge.hard}, etc.
    edge_width: str  # REQUIRED: e.g., "0.02-0.03 UV"


class ColorDefinitionV2(TypedDict, total=False):
    """Color Definition (V2.0 - Required primary_rgb)
    
    Required fields enforced by Self-check.
    """
    primary_color: str  # Color name: "blue", "coral", etc.
    primary_rgb: str  # REQUIRED: e.g., "(0.2, 0.5, 1.0)"
    gradient_type: str | None  # {gradient.radial}, {gradient.linear}
    gradient_direction: str | None


class AnimationDefinitionV2(TypedDict, total=False):
    """Animation Definition (V2.0 - Required duration)
    
    Required fields enforced by Self-check.
    """
    animation_type: str  # expand, pulse, flow, static
    duration: str  # REQUIRED: e.g., "3s", "4s"
    easing: str | None  # ease-out, sin, linear
    loop_type: str | None  # fract(t/duration), continuous


class BackgroundDefinitionV2(TypedDict, total=False):
    """Background Definition (V2.0 - Required strict)
    
    Required fields enforced by Self-check.
    strict=true means RGB error <0.05 (inspect dimension weight doubled)
    """
    background_type: str  # {bg.white_strict}, {bg.flexible}, etc.
    background_rgb: str  # REQUIRED if strict=true: e.g., "(1.0, 1.0, 1.0)"
    strict: bool  # REQUIRED: true/false (user requirement)
    error_tolerance: str | None  # e.g., "<0.05"


class LightingDefinitionV2(TypedDict, total=False):
    """Lighting Definition (Optional)
    
    No required fields, but recommended for glow/fresnel effects.
    """
    lighting_types: list[str]  # ["fresnel", "glow", "rim"]
    fresnel_intensity: float | None
    glow_radius: str | None


class VisualDescriptionV2(TypedDict, total=False):
    """Visual Description V2.0 - Closed Vocabulary + Required Fields
    
    All values must come from VFX Effect Catalog.
    Required fields enforced by Self-check (Decompose Agent).
    
    Required:
    - color_definition.primary_rgb
    - animation_definition.duration
    - shape_definition.edge_width
    - background_definition.strict
    """
    effect_type: str  # REQUIRED: must be from Closed Vocabulary (ripple/glow/etc.)
    shape_definition: ShapeDefinitionV2
    color_definition: ColorDefinitionV2
    animation_definition: AnimationDefinitionV2
    background_definition: BackgroundDefinitionV2
    lighting_definition: LightingDefinitionV2 | None
    anti_patterns: list[str] | None  # ["raymarching", "texture_fetch_gt8"]


class DimensionScore(TypedDict, total=False):
    """Single dimension score entry"""
    score: float
    notes: str


class InspectFeedbackV2(TypedDict, total=False):
    """Inspect Feedback V2.0 - 8 Dimensions + Quantified Feedback
    
    Required:
    - 8 dimension scores (all must be present)
    - visual_issues: specific and quantified (no vague descriptions)
    """
    overall_score: float
    dimension_scores: dict[str, DimensionScore]  # 8 dimensions
    visual_issues: list[str]  # Quantified: "颜色偏差 RGB(0.5,0.3,0.8) → RGB(0.2,0.5,1.0)"
    visual_goals: list[str]  # Actionable: "颜色调整为 RGB(0.2, 0.5, 1.0)"
    correct_aspects: list[str] | None
    re_decompose_trigger: bool | None


# === Phase Log ===


class PhaseLog(TypedDict, total=False):
    """Phase execution log entry"""
    phase: str
    timestamp: float
    status: str
    message: str
    details: str | None
    duration_ms: int | None
    agent_response: str | None
    # Inspect 结构化反馈
    visual_issues: list[str] | None
    visual_goals: list[str] | None
    correct_aspects: list[str] | None
    re_decompose_triggered: bool | None
    rollback_triggered: bool | None


# === 4-Region Architecture ===


class BaselineRegion(TypedDict, total=False):
    """Read-Only Baseline
    
    Original design reference, initial text instructions, global constraints.
    Immutable within a single task.
    """
    input_type: str
    video_path: str | None
    image_paths: list[str]
    user_notes: str
    video_info: dict | None
    keyframe_paths: list[str]
    constraints: dict


class SnapshotRegion(TypedDict, total=False):
    """Current Snapshot
    
    Latest single-step state: visual_description, shader, screenshots, feedback.
    Updated each iteration.
    
    V2.0: visual_description uses VisualDescriptionV2 (required fields enforced)
    """
    visual_description: VisualDescriptionV2 | dict  # V2.0 TypedDict or legacy dict
    shader: str
    render_screenshots: list[str]
    inspect_feedback: InspectFeedbackV2 | dict | None  # V2.0 TypedDict or legacy dict
    iteration: int
    compile_error: str | None
    validation_errors: str | None


class GradientEntry(TypedDict, total=False):
    """Gradient Memory Entry
    
    Only gradient metadata, no full shader code allowed.
    """
    iteration: int
    score: float
    feedback_summary: str
    shader_diff_summary: str | None
    issues_fixed: list[str] | None
    issues_remaining: list[str] | None
    duration_ms: int
    human_iteration: bool


class CheckpointRegion(TypedDict, total=False):
    """Rollback Anchor
    
    Records best_score and best_shader.
    Physical isolated backup for anti-degradation.
    """
    best_score: float
    best_shader: str
    best_iteration: int
    best_visual_description: dict
    best_render_screenshots: list[str]


class AgentModelConfig(TypedDict, total=False):
    """Agent 模型配置"""
    temperature: float
    max_tokens: int


class PipelineConfig(TypedDict, total=False):
    """Pipeline Config Parameters (Adjustable)"""
    max_iterations: int
    passing_threshold: float
    re_decompose_threshold: float
    gradient_window_size: int
    stagnation_variance: float
    stagnation_window: int
    render_timeout_ms: int
    screenshot_width: int
    screenshot_height: int
    decompose_agent: AgentModelConfig
    generate_agent: AgentModelConfig
    inspect_agent: AgentModelConfig


class PipelineState(TypedDict, total=False):
    """Pipeline State - V3.0 4-Region Architecture"""
    
    # 1. Read-Only Baseline
    baseline: BaselineRegion
    
    # 2. Current Snapshot
    snapshot: SnapshotRegion
    
    # 3. Gradient Memory Window
    gradient_window: list[GradientEntry]
    
    # 4. Checkpoint
    checkpoint: CheckpointRegion
    
    # Config
    config: PipelineConfig
    
    # Pipeline Metadata
    pipeline_id: str
    status: str
    error: str | None
    
    # Phase tracking
    current_phase: str
    phase_status: str
    phase_message: str
    phase_start_time: float | None
    detailed_logs: list[PhaseLog]
    
    # Human intervention
    human_feedback: str | None
    human_iteration_mode: bool
    human_iteration_count: int
    human_iteration_processed: bool
    
    # Backward compatibility (migration phase)
    video_info: dict | None
    keyframe_paths: list[str]
    design_screenshots: list[str]
    current_shader: str
    validation_errors: str | None
    validation_warnings: str | None
    compile_error: str | None
    compile_retry_count: int
    iteration: int
    passed: bool
    history: list[dict]
    generate_history: list[dict]
    inspect_history: list[dict]


# Default config
DEFAULT_CONFIG: PipelineConfig = {
    "max_iterations": 5,
    "passing_threshold": 0.85,
    "re_decompose_threshold": 0.5,
    "gradient_window_size": 3,
    "stagnation_variance": 0.05,
    "stagnation_window": 3,
    "render_timeout_ms": 2000,
    "screenshot_width": 1024,
    "screenshot_height": 1024,
    "decompose_agent": {"temperature": 0.3, "max_tokens": 4096},
    "generate_agent": {"temperature": 0.5, "max_tokens": 8192},
    "inspect_agent": {"temperature": 0.3, "max_tokens": 4096},
}


def create_initial_state(
    pipeline_id: str,
    input_type: str,
    video_path: str | None = None,
    image_paths: list[str] | None = None,
    user_notes: str = "",
    config: PipelineConfig | None = None,
) -> PipelineState:
    """Create initial Pipeline State (4-region version)"""
    
    image_paths = image_paths or []
    
    # Initialize 4 regions
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
        # 4 regions
        "baseline": baseline,
        "snapshot": snapshot,
        "gradient_window": [],
        "checkpoint": checkpoint,
        
        # Config
        "config": config or DEFAULT_CONFIG,
        
        # Metadata
        "pipeline_id": pipeline_id,
        "status": "running",
        "error": None,
        
        # Phase tracking
        "current_phase": "extract_keyframes",
        "phase_status": "running",
        "phase_message": "Initializing pipeline...",
        "phase_start_time": None,
        "detailed_logs": [],
        
        # Human intervention
        "human_feedback": None,
        "human_iteration_mode": False,
        "human_iteration_count": 0,
        
        # Backward compatibility
        "design_screenshots": image_paths,
        "passed": False,
        "history": [],
        "generate_history": [],
        "inspect_history": [],
    }


def update_gradient_window(
    gradient_window: list[GradientEntry],
    new_entry: GradientEntry,
    max_size: int = 3,
) -> list[GradientEntry]:
    """Update gradient window with truncation
    
    Remove shader code from entries, keep only metadata.
    """
    # Add new entry
    window = gradient_window + [new_entry]
    
    # Truncate to max_size
    window = window[-max_size:]
    
    # Remove shader code if present
    for entry in window:
        entry.pop("shader", None)
        entry.pop("previous_shader", None)
    
    return window


def should_trigger_re_decompose(state: PipelineState) -> bool:
    """Check if re-decompose should be triggered
    
    Conditions:
    1. score < re_decompose_threshold
    2. or stagnation detected (variance < threshold for N rounds)
    """
    config = state.get("config", DEFAULT_CONFIG)
    snapshot = state.get("snapshot", {})
    gradient_window = state.get("gradient_window", [])
    
    # Condition 1: score below threshold
    current_score = 0.0
    inspect_feedback = snapshot.get("inspect_feedback")
    if inspect_feedback:
        current_score = inspect_feedback.get("overall_score", 0.0)
    
    threshold = config.get("re_decompose_threshold", 0.5)
    if current_score < threshold:
        return True
    
    # Condition 2: stagnation
    window_size = config.get("stagnation_window", 3)
    variance_threshold = config.get("stagnation_variance", 0.05)
    
    if len(gradient_window) >= window_size:
        recent_scores = [e.get("score", 0.0) for e in gradient_window[-window_size:]]
        if recent_scores:
            variance = max(recent_scores) - min(recent_scores)
            if variance < variance_threshold:
                return True
    
    return False


def detect_score_regression(state: PipelineState) -> bool:
    """Check if current score < best score (regression)"""
    snapshot = state.get("snapshot", {})
    checkpoint = state.get("checkpoint", {})
    
    current_score = 0.0
    inspect_feedback = snapshot.get("inspect_feedback")
    if inspect_feedback:
        current_score = inspect_feedback.get("overall_score", 0.0)
    
    best_score = checkpoint.get("best_score", 0.0)
    
    return current_score < best_score and best_score > 0


def rollback_to_checkpoint(state: PipelineState) -> dict:
    """Physical rollback: restore snapshot from checkpoint
    
    Returns update dict for state.
    """
    checkpoint = state.get("checkpoint", {})
    snapshot = state.get("snapshot", {})
    
    # Restore best version
    rollback_shader = checkpoint.get("best_shader", "")
    rollback_iteration = checkpoint.get("best_iteration", 0)
    rollback_visual_description = checkpoint.get("best_visual_description", {})
    
    # Inject rollback instruction into feedback
    best_score = checkpoint.get("best_score", 0.0)
    current_score = 0.0
    inspect_feedback = snapshot.get("inspect_feedback")
    if inspect_feedback:
        current_score = inspect_feedback.get("overall_score", 0.0)
    
    rollback_instruction = f"""
[SYSTEM ROLLBACK]
Score dropped from {best_score:.2f} to {current_score:.2f}.
System has rolled back to iteration {rollback_iteration} (best version).

Please discard previous modification direction and explore new parameters.
"""
    
    # Append rollback instruction to visual_issues
    visual_issues = inspect_feedback.get("visual_issues", []) if inspect_feedback else []
    visual_issues.append(rollback_instruction)
    
    return {
        "snapshot": {
            **snapshot,
            "shader": rollback_shader,
            "iteration": rollback_iteration,
            "visual_description": rollback_visual_description,
            "inspect_feedback": {
                **(inspect_feedback or {}),
                "visual_issues": visual_issues,
            },
        },
    }


def update_checkpoint(state: PipelineState) -> dict:
    """Update checkpoint if current score > best score
    
    Returns update dict for state.
    """
    snapshot = state.get("snapshot", {})
    checkpoint = state.get("checkpoint", {})
    
    current_score = 0.0
    inspect_feedback = snapshot.get("inspect_feedback")
    if inspect_feedback:
        current_score = inspect_feedback.get("overall_score", 0.0)
    
    best_score = checkpoint.get("best_score", 0.0)
    
    if current_score > best_score:
        return {
            "checkpoint": {
                "best_score": current_score,
                "best_shader": snapshot.get("shader", ""),
                "best_iteration": snapshot.get("iteration", 0),
                "best_visual_description": snapshot.get("visual_description", {}),
                "best_render_screenshots": snapshot.get("render_screenshots", []),
            },
        }
    
    return {}