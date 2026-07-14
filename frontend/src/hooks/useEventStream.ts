import { useMemo } from "react";
import type {
  PipelineRecord,
  DisplayEvent,
  DisplayEventStatus,
  PipelineEvent,
} from "../types/pipeline";

function truncate(str: string, maxLen: number): string {
  if (str.length <= maxLen) return str;
  return str.slice(0, maxLen - 1) + "…";
}

function getItemStatus(event: PipelineEvent): DisplayEventStatus {
  if (event.type === "error") return "failed";
  if (event.type === "item.started" || event.type === "item.in_progress") {
    return "running";
  }
  if (event.type === "item.completed") {
    const item = (event.item as Record<string, unknown>) || {};
    if (item.status === "failed" || (item.exit_code !== undefined && item.exit_code !== 0 && item.exit_code !== null)) {
      return "failed";
    }
    if (item.status === "completed" || item.status === "success") return "completed";
    return "info";
  }
  if (event.type === "turn.completed" || event.type === "agent.completed" || event.type === "thread.completed") {
    return "completed";
  }
  return "info";
}

function buildDisplayEvent(event: PipelineEvent, index: number): DisplayEvent {
  const base: DisplayEvent = {
    id: `event-${index}-${Date.now()}`,
    type: "lifecycle",
    status: getItemStatus(event),
    title: event.type,
    detail: "",
    timestamp: Date.now(),
  };

  const item = (event.item as Record<string, unknown>) || {};

  if (event.type === "error") {
    return {
      ...base,
      type: "error",
      title: typeof event.message === "string" ? event.message : "Error",
      detail: typeof event.message === "string" ? event.message : JSON.stringify(event, null, 2),
    };
  }

  if (
    event.type.startsWith("item.") &&
    (item.type === "command_execution" || item.type === "command")
  ) {
    const command = typeof item.command === "string" ? item.command : "";
    const output = typeof item.aggregated_output === "string" ? item.aggregated_output : "";
    return {
      ...base,
      id: `cmd-${index}`,
      type: "command",
      title: truncate(command, 80),
      detail: output || command,
      command,
    };
  }

  if (item.type === "agent_message" && typeof item.text === "string") {
    return {
      ...base,
      id: `msg-${index}`,
      type: "agent_message",
      title: truncate(item.text, 80),
      detail: item.text,
    };
  }

  if (item.type === "file_change") {
    const changes = Array.isArray(item.changes)
      ? item.changes.map((c: { path?: string; kind?: string }) => `${c.kind || "change"} ${c.path || "?"}`).join("\n")
      : "";
    return {
      ...base,
      id: `file-${index}`,
      type: "file_change",
      title: changes ? truncate(changes, 80) : "File change",
      detail: changes || JSON.stringify(item, null, 2),
    };
  }

  if (item.type === "subagent" || (typeof item.command === "string" && item.command.includes("spawn_agent"))) {
    const command = typeof item.command === "string" ? item.command : "";
    return {
      ...base,
      id: `sub-${index}`,
      type: "subagent",
      title: command ? truncate(command, 80) : "Subagent",
      detail: command || JSON.stringify(item, null, 2),
    };
  }

  // Fallback lifecycle / generic
  const detail = JSON.stringify(event, null, 2);
  return {
    ...base,
    title: truncate(detail, 80),
    detail,
  };
}

export function useEventStream(record: PipelineRecord | null): DisplayEvent[] {
  return useMemo(() => {
    if (!record?.events) return [];
    return record.events.map((event, index) => buildDisplayEvent(event, index));
  }, [record]);
}

export default useEventStream;
