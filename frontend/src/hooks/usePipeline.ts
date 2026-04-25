// hooks/usePipeline.ts
import { useState, useCallback, useRef, useEffect } from "react";

export interface PipelineIteration {
  iteration: number;
  score: number;
  passed: boolean;
  feedback: string;
}

export interface PipelineResult {
  status: string;
  current_shader: string;
  visual_description: Record<string, unknown>;
  iteration: number;
  passed: boolean;
  history: PipelineIteration[];
  inspect_result: Record<string, unknown> | null;
  error: string | null;
  // Extended fields for detailed logging
  logs?: PipelineLogEntry[];
}

export interface PipelineLogEntry {
  id: string;
  timestamp: number;
  phase: 'decompose' | 'generate' | 'inspect' | 'system';
  iteration?: number;
  message: string;
  details?: string;
  metadata?: Record<string, unknown>;
}

interface UsePipelineReturn {
  pipelineId: string | null;
  result: PipelineResult | null;
  loading: boolean;
  logs: PipelineLogEntry[];
  startPipeline: (formData: FormData) => Promise<void>;
  clearPipeline: () => void;
}

export function usePipeline(): UsePipelineReturn {
  const [pipelineId, setPipelineId] = useState<string | null>(null);
  const [result, setResult] = useState<PipelineResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [logs, setLogs] = useState<PipelineLogEntry[]>([]);
  const pollingRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Use refs to track latest values for poll function (avoids stale closures)
  const resultRef = useRef<PipelineResult | null>(null);
  const logsRef = useRef<PipelineLogEntry[]>([]);

  // Sync refs with state
  useEffect(() => {
    resultRef.current = result;
  }, [result]);

  useEffect(() => {
    logsRef.current = logs;
  }, [logs]);

  const addLog = useCallback((entry: Omit<PipelineLogEntry, 'id' | 'timestamp'>) => {
    setLogs(prev => [...prev, {
      ...entry,
      id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      timestamp: Date.now()
    }]);
  }, []);

  const clearPipeline = useCallback(() => {
    setPipelineId(null);
    setResult(null);
    setLogs([]);
    setLoading(false);
    if (pollingRef.current) {
      clearTimeout(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  const startPipeline = useCallback(async (formData: FormData) => {
    // Clear previous state
    clearPipeline();
    setLoading(true);

    addLog({
      phase: 'system',
      message: 'Starting pipeline...',
      details: 'Uploading media and initializing agent process'
    });

    try {
      const res = await fetch("http://localhost:8000/pipeline/run", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        throw new Error(`HTTP error! status: ${res.status}`);
      }

      const data = await res.json();
      setPipelineId(data.pipeline_id);

      addLog({
        phase: 'system',
        message: 'Pipeline initialized',
        details: `Pipeline ID: ${data.pipeline_id}`,
        metadata: { pipelineId: data.pipeline_id }
      });

      // Poll for status
      const poll = async () => {
        try {
          const statusRes = await fetch(`http://localhost:8000/pipeline/status/${data.pipeline_id}`);

          if (!statusRes.ok) {
            throw new Error(`Status check failed: ${statusRes.status}`);
          }

          const statusData: PipelineResult = await statusRes.json();

          // "not_found" means pipeline is still initializing, continue polling
          if (statusData.status === "not_found") {
            pollingRef.current = setTimeout(poll, 1000);
            return;
          }

          // Add phase-specific logs (use ref to avoid stale closure)
          if (statusData.iteration > (resultRef.current?.iteration || 0)) {
            const iteration = statusData.iteration;

            // Decompose phase
            addLog({
              phase: 'decompose',
              iteration,
              message: `Iteration ${iteration}: Decomposing visual description`,
              details: JSON.stringify(statusData.visual_description, null, 2)
            });

            // Generate phase
            addLog({
              phase: 'generate',
              iteration,
              message: `Iteration ${iteration}: Generating shader code`,
              details: statusData.current_shader
                ? `Generated ${statusData.current_shader.length} characters`
                : 'Generating...'
            });
          }

          // Inspect phase logs from history (use ref to avoid stale closure)
          if (statusData.history && statusData.history.length > 0) {
            const latestHistory = statusData.history[statusData.history.length - 1];
            const existingLog = logsRef.current.find(l =>
              l.phase === 'inspect' &&
              l.iteration === latestHistory.iteration
            );

            if (!existingLog) {
              addLog({
                phase: 'inspect',
                iteration: latestHistory.iteration,
                message: `Iteration ${latestHistory.iteration + 1}: Inspection complete`,
                details: `Score: ${latestHistory.score.toFixed(2)} | Passed: ${latestHistory.passed}`,
                metadata: {
                  score: latestHistory.score,
                  passed: latestHistory.passed,
                  feedback: latestHistory.feedback
                }
              });
            }
          }

          setResult(statusData);

          if (statusData.status === "running") {
            pollingRef.current = setTimeout(poll, 2000);
          } else {
            setLoading(false);
            addLog({
              phase: 'system',
              message: `Pipeline ${statusData.status}`,
              details: statusData.error || `Final status: ${statusData.status}`,
              metadata: { finalResult: statusData }
            });
          }
        } catch (err) {
          setLoading(false);
          const errorMessage = err instanceof Error ? err.message : 'Unknown error';
          addLog({
            phase: 'system',
            message: 'Polling error',
            details: errorMessage
          });
        }
      };

      poll();
    } catch (err) {
      setLoading(false);
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      addLog({
        phase: 'system',
        message: 'Pipeline failed to start',
        details: errorMessage
      });
    }
  }, [addLog, clearPipeline]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (pollingRef.current) {
        clearTimeout(pollingRef.current);
      }
    };
  }, []);

  return {
    pipelineId,
    result,
    loading,
    logs,
    startPipeline,
    clearPipeline
  };
}
