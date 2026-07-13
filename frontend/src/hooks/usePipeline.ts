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

// ─── Types ──────────────────────────────────────────────────────────────────

export interface PipelineRecord {
  pipeline_id: string;
  status: "running" | "passed" | "failed" | "timeout" | "max_iterations" | "not_found";
  workdir: string;
  keyframe_paths: string[];
  final_shader: string;
  final_score: number;
  evaluation: Record<string, unknown> | null;
  codex_usage: Record<string, unknown> | null;
  duration_ms: number;
  error: string | null;
  events: Record<string, unknown>[];
}

export interface UsePipelineReturn {
  pipelineId: string | null;
  record: PipelineRecord | null;
  isRunning: boolean;
  start: (notes: string, images: File[]) => Promise<void>;
  cancel: () => void;
  error: string | null;
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

  // ── start ────────────────────────────────────────────────────────────────
  const start = useCallback(async (notes: string, images: File[]) => {
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
      const formData = new FormData();
      formData.append("notes", notes);
      for (const img of images) {
        formData.append("images", img);
      }

      const res = await fetch("http://localhost:8000/pipeline/run", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      }

      const data = await res.json();
      setPipelineId(data.pipeline_id);

      // ── Poll status ──
      const poll = async () => {
        try {
          const statusRes = await fetch(
            `http://localhost:8000/pipeline/status/${data.pipeline_id}`,
          );

          if (!statusRes.ok) {
            throw new Error(`Poll failed: HTTP ${statusRes.status}`);
          }

          const statusData: PipelineRecord = await statusRes.json();
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
    } catch (err) {
      setError(err instanceof Error ? err.message : "Start failed");
      setIsRunning(false);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

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

  return { pipelineId, record, isRunning, start, cancel, error };
}
