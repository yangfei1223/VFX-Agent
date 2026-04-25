// hooks/usePipeline.ts
import { useState, useCallback } from "react";

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
}

export function usePipeline() {
  const [pipelineId, setPipelineId] = useState<string | null>(null);
  const [result, setResult] = useState<PipelineResult | null>(null);
  const [loading, setLoading] = useState(false);

  const startPipeline = useCallback(async (formData: FormData) => {
    setLoading(true);
    setResult(null);
    try {
      const res = await fetch("http://localhost:8000/pipeline/run", {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      setPipelineId(data.pipeline_id);

      // 轮询状态
      const poll = async () => {
        const statusRes = await fetch(`http://localhost:8000/pipeline/status/${data.pipeline_id}`);
        const statusData = await statusRes.json();
        setResult(statusData);
        if (statusData.status === "running") {
          setTimeout(poll, 2000);
        } else {
          setLoading(false);
        }
      };
      poll();
    } catch (err) {
      setLoading(false);
      console.error("Pipeline error:", err);
    }
  }, []);

  return { pipelineId, result, loading, startPipeline };
}