/**
 * v2.0 PipelineOrchestrator-based polling hook.
 *
 * NOTE: Other components (App.tsx, AgentLog.tsx, etc.) currently use v1.0
 * PipelineState fields (current_shader, history, checkpoint, iteration, etc.).
 * Those will break visually after this rewrite because the v2.0
 * PipelineRecord has a different shape. Phase B/D will update each
 * component for the v2.0 shape.
 */

import { useState, useCallback, useRef, useEffect } from "react";
import { useTimelinePhases } from "./useTimelinePhases";
import { useEventStream } from "./useEventStream";
import { useRenderScreenshots } from "./useRenderScreenshots";
import type { PipelineRecord } from "../types/pipeline";

// Re-export for legacy consumers.
export type { PipelineRecord };

export interface UsePipelineReturn {
  pipelineId: string | null;
  record: PipelineRecord | null;
  isRunning: boolean;
  start: (formData: FormData) => Promise<void>;
  cancel: () => void;
  error: string | null;
  phases: ReturnType<typeof useTimelinePhases>;
  displayEvents: ReturnType<typeof useEventStream>;
  screenshots: ReturnType<typeof useRenderScreenshots>;
}

// ─── Hook ───────────────────────────────────────────────────────────────────

export function usePipeline(): UsePipelineReturn {
  const [pipelineId, setPipelineId] = useState<string | null>(null);
  const [record, setRecord] = useState<PipelineRecord | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollingRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Terminal statuses that stop polling
  const terminalStatuses = new Set([
    "passed", "failed", "timeout", "max_iterations", "not_found",
  ]);

  // ── Helper: poll a pipeline_id until terminal ────────────────────────────
  const startPolling = useCallback((pid: string) => {
    const poll = async () => {
      try {
        const statusRes = await fetch(
          `http://localhost:8000/pipeline/status/${pid}`,
        );
        if (!statusRes.ok) {
          throw new Error(`Poll failed: HTTP ${statusRes.status}`);
        }
        const statusData = (await statusRes.json()) as PipelineRecord;
        setRecord(statusData);
        if (terminalStatuses.has(statusData.status)) {
          setIsRunning(false);
          return;
        }
        pollingRef.current = setTimeout(poll, 1000);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Polling error");
        setIsRunning(false);
      }
    };
    poll();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Load existing pipeline from URL query param (e.g. ?pipeline_id=p123) ─
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const pid = params.get("pipeline_id");
    if (pid) {
      setPipelineId(pid);
      setIsRunning(true);
      startPolling(pid);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── start ────────────────────────────────────────────────────────────────
  const start = useCallback(async (formData: FormData) => {
    // Cancel any in-flight polling
    if (pollingRef.current) {
      clearTimeout(pollingRef.current);
      pollingRef.current = null;
    }

    setPipelineId(null);
    setRecord(null);
    setError(null);
    setIsRunning(true);

    try {
      const res = await fetch("http://localhost:8000/pipeline/run", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      }

      const data = await res.json();
      setPipelineId(data.pipeline_id);
      startPolling(data.pipeline_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Start failed");
      setIsRunning(false);
    }
  }, [startPolling]);

  // ── cancel ───────────────────────────────────────────────────────────────
  const cancel = useCallback(() => {
    if (pollingRef.current) {
      clearTimeout(pollingRef.current);
      pollingRef.current = null;
    }
    setIsRunning(false);
  }, []);

  // ── Cleanup on unmount ───────────────────────────────────────────────────
  useEffect(() => {
    return () => {
      if (pollingRef.current) {
        clearTimeout(pollingRef.current);
      }
    };
  }, []);

  // ── Legacy v1.0 aliases (will be removed in Phase B/D) ──────────────────
  // We expose these for now so App.tsx doesn't crash at compile time,
  // but they return dummy values.
  // const loading = isRunning;

  const phases = useTimelinePhases(record);
  const displayEvents = useEventStream(record);
  const screenshots = useRenderScreenshots(record);

  return { pipelineId, record, isRunning, start, cancel, error, phases, displayEvents, screenshots };
}
