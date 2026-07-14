/**
 * v2.0 Pipeline types.
 *
 * These types mirror the JSON shape produced by the Python orchestrator's
 * PipelineState and are consumed by the React frontend.
 */

export type PipelineStatus =
  | "running"
  | "passed"
  | "failed"
  | "timeout"
  | "max_iterations"
  | "not_found";

export interface DimensionScore {
  score: number;
  notes: string;
}

export interface PixelEvidence {
  avg_color_distance: number;
  sample_differences: string;
}

export interface Evaluation {
  passed: boolean;
  overall_score: number;
  visual_issues: string[];
  visual_goals: string[];
  correct_aspects: string[];
  dimension_scores: Record<string, DimensionScore>;
  pixel_evidence?: PixelEvidence;
}

export interface CodexUsage {
  input_tokens: number;
  cached_input_tokens: number;
  output_tokens: number;
  reasoning_output_tokens?: number;
}

// Raw event types emitted by the Python orchestrator.
export type PipelineEventType =
  | "thread.started"
  | "turn.started"
  | "turn.completed"
  | "error"
  | "item.started"
  | "item.completed"
  | "item.in_progress"
  | "agent.started"
  | "agent.completed"
  | "agent_message_delta"
  | string;

export interface PipelineEvent {
  type: PipelineEventType;
  [key: string]: unknown;
}

export interface PipelineRecord {
  pipeline_id: string;
  status: PipelineStatus;
  workdir: string;
  keyframe_paths: string[];
  final_shader: string;
  final_score: number;
  evaluation: Evaluation | null;
  codex_usage: CodexUsage | null;
  duration_ms: number;
  error: string | null;
  events: PipelineEvent[];
}

// Timeline phase derived by useTimelinePhases.
export type PhaseStatus = "pending" | "running" | "completed" | "failed";

export interface PhaseInfo {
  id: string;
  label: string;
  status: PhaseStatus;
}

// Display event derived by useEventStream.
export type DisplayEventType =
  | "command"
  | "agent_message"
  | "file_change"
  | "subagent"
  | "error"
  | "lifecycle";

export type DisplayEventStatus = "pending" | "running" | "completed" | "failed" | "info";

export interface DisplayEvent {
  id: string;
  type: DisplayEventType;
  status: DisplayEventStatus;
  title: string;
  detail: string;
  command?: string;
  timestamp: number;
}
