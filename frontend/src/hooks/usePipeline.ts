// hooks/usePipeline.ts
import { useState, useCallback, useRef, useEffect } from "react";

export interface PipelineIteration {
  iteration: number;
  score: number;
  passed: boolean;
  feedback: string;
}

export interface PhaseLog {
  phase: string;
  timestamp: number;
  status: string;
  message: string;
  details?: string;
  duration_ms?: number;
  agent_response?: string;  // Agent's raw response for displaying reasoning
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
  // Phase tracking fields
  current_phase?: string;
  phase_status?: string;
  phase_message?: string;
  detailed_logs?: PhaseLog[];
  // Extended fields for detailed logging
  logs?: PipelineLogEntry[];
}

export interface PipelineLogEntry {
  id: string;
  timestamp: number;
  phase: 'extract_keyframes' | 'decompose' | 'generate' | 'render' | 'inspect' | 'system';
  iteration?: number;
  message: string;
  details?: string;
  status?: 'started' | 'running' | 'completed' | 'failed';
  duration_ms?: number;
  metadata?: Record<string, unknown>;
}

interface UsePipelineReturn {
  pipelineId: string | null;
  result: PipelineResult | null;
  loading: boolean;
  logs: PipelineLogEntry[];
  phaseLogs: PhaseLog[];
  currentPhase: string | null;
  phaseMessage: string | null;
  startPipeline: (formData: FormData) => Promise<void>;
  clearPipeline: () => void;
}

export function usePipeline(): UsePipelineReturn {
  const [pipelineId, setPipelineId] = useState<string | null>(null);
  const [result, setResult] = useState<PipelineResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [logs, setLogs] = useState<PipelineLogEntry[]>([]);
  const [phaseLogs, setPhaseLogs] = useState<PhaseLog[]>([]);
  const [currentPhase, setCurrentPhase] = useState<string | null>(null);
  const [phaseMessage, setPhaseMessage] = useState<string | null>(null);
  const pollingRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Use refs to track latest values for poll function (avoids stale closures)
  const resultRef = useRef<PipelineResult | null>(null);
  const logsRef = useRef<PipelineLogEntry[]>([]);
  const phaseLogsRef = useRef<PhaseLog[]>([]);
  const processedPhasesRef = useRef<Set<string>>(new Set());

  // Sync refs with state
  useEffect(() => {
    resultRef.current = result;
  }, [result]);

  useEffect(() => {
    logsRef.current = logs;
  }, [logs]);

  useEffect(() => {
    phaseLogsRef.current = phaseLogs;
  }, [phaseLogs]);

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
    setPhaseLogs([]);
    setCurrentPhase(null);
    setPhaseMessage(null);
    setLoading(false);
    processedPhasesRef.current = new Set();
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

      // Poll for status (500ms for better real-time updates)
      const poll = async () => {
        try {
          const statusRes = await fetch(`http://localhost:8000/pipeline/status/${data.pipeline_id}`);

          if (!statusRes.ok) {
            throw new Error(`Status check failed: ${statusRes.status}`);
          }

          const statusData: PipelineResult = await statusRes.json();

          // "not_found" means pipeline is still initializing, continue polling
          if (statusData.status === "not_found") {
            pollingRef.current = setTimeout(poll, 500);
            return;
          }

          // Update phase tracking
          if (statusData.current_phase) {
            setCurrentPhase(statusData.current_phase);
            setPhaseMessage(statusData.phase_message || null);
          }

          // Process detailed phase logs from backend
          if (statusData.detailed_logs && statusData.detailed_logs.length > 0) {
            const newPhaseLogs: PhaseLog[] = [];
            statusData.detailed_logs.forEach((log: PhaseLog) => {
              const logKey = `${log.phase}-${log.timestamp}`;
              if (!processedPhasesRef.current.has(logKey)) {
                processedPhasesRef.current.add(logKey);
                newPhaseLogs.push(log);

                // Add to UI logs (extract iteration from phase if possible, default to current iteration)
                const iteration = statusData.iteration ?? 0;
                addLog({
                  phase: log.phase as PipelineLogEntry['phase'],
                  iteration: iteration,
                  message: log.message,
                  details: log.details,
                  status: log.status as PipelineLogEntry['status'],
                  duration_ms: log.duration_ms,
                });
              }
            });
            if (newPhaseLogs.length > 0) {
              setPhaseLogs(prev => [...prev, ...newPhaseLogs]);
            }
          }

          // Add phase-specific logs for iterations (fallback if detailed_logs not present)
          if (!statusData.detailed_logs && statusData.iteration > (resultRef.current?.iteration || 0)) {
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

          // Inspect phase logs from history (fallback if detailed_logs not present)
          if (!statusData.detailed_logs && statusData.history && statusData.history.length > 0) {
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
            pollingRef.current = setTimeout(poll, 500); // Faster polling
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
    phaseLogs,
    currentPhase,
    phaseMessage,
    startPipeline,
    clearPipeline
  };
}
