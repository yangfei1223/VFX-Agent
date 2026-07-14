import { useMemo } from "react";
import type { PipelineRecord, PhaseInfo, PhaseStatus, PipelineEvent } from "../types/pipeline";

const PHASES: { id: string; label: string }[] = [
  { id: "analyse", label: "分析" },
  { id: "generate", label: "生成" },
  { id: "validate", label: "验证" },
  { id: "render", label: "渲染" },
  { id: "evaluate", label: "评分" },
  { id: "finalize", label: "收尾" },
];

function getCommandPhase(command: string): string | null {
  if (!command) return null;
  const lower = command.toLowerCase();
  if (lower.includes("visual_description") || lower.includes("analyze_pixels") || lower.includes("analyse")) {
    return "analyse";
  }
  if (lower.includes("validate_shader.py")) return "validate";
  if (lower.includes("render_shader.py")) return "render";
  if (lower.includes("spawn_agent") || lower.includes("evaluation.json")) return "evaluate";
  if (lower.includes("shader.glsl") && !lower.includes("final_shader.glsl")) return "generate";
  if (lower.includes("final_shader.glsl")) return "finalize";
  return null;
}

function getFilePhase(path: string): string | null {
  if (!path) return null;
  const lower = path.toLowerCase();
  if (lower.includes("visual_description.json")) return "analyse";
  if (lower.includes("shader.glsl") && !lower.includes("final_shader.glsl")) return "generate";
  if (lower.includes("evaluation.json")) return "evaluate";
  if (lower.includes("final_shader.glsl")) return "finalize";
  return null;
}

function inferPhaseFromEvent(event: PipelineEvent): string | null {
  const type = event.type;
  if (type === "item.started" || type === "item.completed") {
    const item = (event.item as Record<string, unknown>) || {};
    if (item.type === "command_execution" && typeof item.command === "string") {
      return getCommandPhase(item.command);
    }
    if (item.type === "file_change" && Array.isArray(item.changes)) {
      for (const change of item.changes as Array<{ path?: string }>) {
        const phase = getFilePhase(change.path || "");
        if (phase) return phase;
      }
    }
    if (typeof item.path === "string") {
      return getFilePhase(item.path);
    }
  }
  if (type === "item.in_progress") {
    const item = (event.item as Record<string, unknown>) || {};
    if (typeof item.command === "string") {
      return getCommandPhase(item.command);
    }
  }
  return null;
}

function isFailedEvent(event: PipelineEvent): boolean {
  if (event.type === "error") return true;
  if (event.type === "item.completed") {
    const item = (event.item as Record<string, unknown>) || {};
    return item.status === "failed" || item.exit_code !== undefined && item.exit_code !== 0 && item.exit_code !== null;
  }
  return false;
}

function isCompletedEvent(event: PipelineEvent): boolean {
  if (event.type === "item.completed") {
    const item = (event.item as Record<string, unknown>) || {};
    return item.status === "completed" || item.status === "success";
  }
  if (event.type === "turn.completed") return true;
  return false;
}

function isInProgressEvent(event: PipelineEvent): boolean {
  if (event.type === "item.started") return true;
  if (event.type === "item.in_progress") return true;
  if (event.type === "turn.started") return true;
  return false;
}

export function useTimelinePhases(record: PipelineRecord | null): PhaseInfo[] {
  return useMemo(() => {
    const phaseMap = new Map<string, PhaseStatus>();

    // Default all pending
    for (const phase of PHASES) {
      phaseMap.set(phase.id, "pending");
    }

    if (!record?.events?.length) {
      return PHASES.map((p) => ({ ...p, status: "pending" as PhaseStatus }));
    }

    const events = record.events;

    for (const event of events) {
      const phase = inferPhaseFromEvent(event);
      if (!phase) continue;

      if (isFailedEvent(event)) {
        phaseMap.set(phase, "failed");
      } else if (isInProgressEvent(event)) {
        if (phaseMap.get(phase) !== "failed") {
          phaseMap.set(phase, "running");
        }
      } else if (isCompletedEvent(event)) {
        if (phaseMap.get(phase) !== "failed" && phaseMap.get(phase) !== "running") {
          phaseMap.set(phase, "completed");
        }
      }
    }

    // If the pipeline is still running, the last non-pending phase with any
    // in-progress activity should be marked running; later phases remain pending.
    if (record.status === "running") {
      let lastActivePhaseIndex = -1;
      for (let i = PHASES.length - 1; i >= 0; i--) {
        const status = phaseMap.get(PHASES[i].id);
        if (status && status !== "pending") {
          lastActivePhaseIndex = i;
          break;
        }
      }
      if (lastActivePhaseIndex >= 0) {
        const currentStatus = phaseMap.get(PHASES[lastActivePhaseIndex].id);
        if (currentStatus !== "failed") {
          phaseMap.set(PHASES[lastActivePhaseIndex].id, "running");
        }
      }
    }

    // If the pipeline has reached a terminal state, ensure no phase is left
    // running unless it failed.
    if (
      record.status === "passed" ||
      record.status === "failed" ||
      record.status === "timeout" ||
      record.status === "max_iterations"
    ) {
      for (const phase of PHASES) {
        const status = phaseMap.get(phase.id);
        if (status === "running") {
          phaseMap.set(phase.id, "completed");
        }
      }
    }

    return PHASES.map((p) => ({ ...p, status: phaseMap.get(p.id) || "pending" }));
  }, [record]);
}

export default useTimelinePhases;
