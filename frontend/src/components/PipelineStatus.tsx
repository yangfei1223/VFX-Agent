// components/PipelineStatus.tsx
import type { PipelineResult } from "../hooks/usePipeline";

interface Props {
  result: PipelineResult | null;
  loading: boolean;
}

export default function PipelineStatus({ result, loading }: Props) {
  if (!result && !loading) {
    return <div className="text-gray-500 text-sm p-4">等待 Pipeline 启动...</div>;
  }

  return (
    <div className="flex flex-col gap-3 p-4 bg-gray-900 rounded-xl">
      <h2 className="text-lg font-semibold text-white">Pipeline 状态</h2>

      {loading && (
        <div className="flex items-center gap-2 text-blue-400">
          <div className="animate-spin h-4 w-4 border-2 border-blue-400 border-t-transparent rounded-full" />
          <span className="text-sm">Agent 迭代中...</span>
        </div>
      )}

      {result && (
        <>
          <div className="flex items-center gap-2">
            <span className={`inline-block w-3 h-3 rounded-full ${
              result.status === "passed" ? "bg-green-500" :
              result.status === "failed" ? "bg-red-500" :
              result.status === "max_iterations" ? "bg-yellow-500" :
              "bg-blue-500 animate-pulse"
            }`} />
            <span className="text-white text-sm capitalize">{result.status}</span>
            <span className="text-gray-400 text-sm">迭代 {result.iteration} 轮</span>
          </div>

          {result.history && result.history.length > 0 && (
            <div className="space-y-1">
              <p className="text-xs text-gray-400">迭代历史：</p>
              {result.history.map((h, i) => (
                <div key={i} className="flex items-center gap-2 text-xs">
                  <span className="text-gray-500">#{h.iteration + 1}</span>
                  <span className={`font-mono ${h.passed ? "text-green-400" : "text-yellow-400"}`}>
                    {h.score.toFixed(2)}
                  </span>
                  <span className="text-gray-600 truncate max-w-xs">{h.feedback.slice(0, 60)}</span>
                </div>
              ))}
            </div>
          )}

          {result.error && (
            <p className="text-red-400 text-sm">{result.error}</p>
          )}
        </>
      )}
    </div>
  );
}