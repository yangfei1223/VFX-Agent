// components/AgentLog.tsx
import { useRef, useEffect, useState } from "react";
import {
  Terminal,
  ChevronRight,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Loader2,
  Sparkles,
  RotateCcw,
  Search,
  Code2,
  Eye
} from "lucide-react";
import type { PipelineResult, PipelineIteration, PipelineLogEntry } from "../hooks/usePipeline";

interface AgentLogProps {
  result: PipelineResult | null;
  loading: boolean;
  logs?: PipelineLogEntry[];
}

type LogEntryType = 'decompose' | 'generate' | 'inspect' | 'success' | 'error' | 'info';

interface LogEntry {
  id: string;
  type: LogEntryType;
  timestamp: Date;
  iteration?: number;
  message: string;
  details?: string;
  score?: number;
  passed?: boolean;
}

const StepIcon = ({ type, className }: { type: LogEntryType; className?: string }) => {
  switch (type) {
    case 'decompose':
      return <Search className={className} />;
    case 'generate':
      return <Code2 className={className} />;
    case 'inspect':
      return <Eye className={className} />;
    case 'success':
      return <CheckCircle2 className={className} />;
    case 'error':
      return <XCircle className={className} />;
    default:
      return <AlertCircle className={className} />;
  }
};

const StepStatus = ({ status }: { status: string }) => {
  const getStatusColor = () => {
    switch (status) {
      case 'running':
        return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
      case 'passed':
        return 'bg-green-500/20 text-green-400 border-green-500/30';
      case 'failed':
        return 'bg-red-500/20 text-red-400 border-red-500/30';
      case 'max_iterations':
        return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
      default:
        return 'bg-gray-500/20 text-gray-400 border-gray-500/30';
    }
  };

  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium border ${getStatusColor()}`}>
      {status}
    </span>
  );
};

export default function AgentLog({ result, loading, logs: externalLogs }: AgentLogProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [expandedLog, setExpandedLog] = useState<string | null>(null);

  // Sync with external logs from usePipeline
  useEffect(() => {
    if (externalLogs && externalLogs.length > 0) {
      const convertedLogs: LogEntry[] = externalLogs.map(log => ({
        id: log.id,
        type: log.phase as LogEntryType,
        timestamp: new Date(log.timestamp),
        iteration: log.iteration,
        message: log.message,
        details: log.details,
      }));
      setLogs(convertedLogs);
    }
  }, [externalLogs]);

  // Generate logs from pipeline result (fallback)
  useEffect(() => {
    if (!result) return;

    const newLogs: LogEntry[] = [];

    // Add iteration logs
    if (result.history && result.history.length > 0) {
      result.history.forEach((h: PipelineIteration) => {
        const existingIndex = logs.findIndex(l => l.iteration === h.iteration);
        if (existingIndex === -1) {
          newLogs.push({
            id: `iter-${h.iteration}`,
            type: h.passed ? 'success' : 'inspect',
            timestamp: new Date(),
            iteration: h.iteration,
            message: `Iteration ${h.iteration + 1} completed`,
            details: h.feedback,
            score: h.score,
            passed: h.passed
          });
        }
      });
    }

    // Add current iteration info
    if (result.iteration > 0 && result.status === 'running') {
      const currentIterLog = logs.find(l => l.id === 'current-iter');
      if (!currentIterLog) {
        newLogs.push({
          id: 'current-iter',
          type: 'generate',
          timestamp: new Date(),
          iteration: result.iteration,
          message: `Running iteration ${result.iteration}...`,
        });
      }
    }

    // Add error log
    if (result.error) {
      newLogs.push({
        id: `error-${Date.now()}`,
        type: 'error',
        timestamp: new Date(),
        message: 'Pipeline error',
        details: result.error
      });
    }

    if (newLogs.length > 0) {
      setLogs(prev => [...prev, ...newLogs]);
    }
  }, [result]);

  // Auto-scroll to bottom
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  // Clear logs when pipeline resets
  useEffect(() => {
    if (!result && !loading) {
      setLogs([]);
    }
  }, [result, loading]);

  const clearLogs = () => setLogs([]);

  const getLogIconColor = (type: LogEntryType) => {
    switch (type) {
      case 'decompose':
        return 'text-purple-400';
      case 'generate':
        return 'text-blue-400';
      case 'inspect':
        return 'text-yellow-400';
      case 'success':
        return 'text-green-400';
      case 'error':
        return 'text-red-400';
      default:
        return 'text-gray-400';
    }
  };

  const getLogBorderColor = (type: LogEntryType) => {
    switch (type) {
      case 'decompose':
        return 'border-l-purple-500';
      case 'generate':
        return 'border-l-blue-500';
      case 'inspect':
        return 'border-l-yellow-500';
      case 'success':
        return 'border-l-green-500';
      case 'error':
        return 'border-l-red-500';
      default:
        return 'border-l-gray-500';
    }
  };

  return (
    <div className="panel bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg overflow-hidden flex flex-col h-full min-h-[300px]">
      {/* Header */}
      <div className="px-4 py-3 border-b border-[var(--border-color)] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-[var(--accent-primary)]" />
          <h2 className="text-sm font-semibold text-[var(--text-primary)] uppercase tracking-wider">
            Agent Process
          </h2>
        </div>
        <div className="flex items-center gap-2">
          {loading && (
            <div className="flex items-center gap-1.5 text-xs text-[var(--accent-primary)]">
              <Loader2 className="w-3 h-3 animate-spin" />
              <span>Running</span>
            </div>
          )}
          {result && (
            <StepStatus status={result.status} />
          )}
          <button
            onClick={clearLogs}
            className="p-1.5 rounded hover:bg-[var(--bg-tertiary)] text-[var(--text-muted)]
                     hover:text-[var(--text-secondary)] transition-colors"
            title="Clear logs"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Process Steps Indicator */}
      {loading && (
        <div className="px-4 py-3 bg-[var(--bg-tertiary)]/50 border-b border-[var(--border-color)]">
          <div className="flex items-center gap-2">
            {['Decompose', 'Generate', 'Inspect'].map((step, index) => {
              const isActive = result?.status === 'running' &&
                (result.iteration === 0 ? index === 0 :
                 result.iteration === 1 ? index <= 1 :
                 index <= 2);
              return (
                <div key={step} className="flex items-center">
                  <div className={`
                    flex items-center gap-1.5 px-2 py-1 rounded text-xs font-medium
                    transition-all duration-300
                    ${isActive
                      ? 'bg-[var(--accent-primary)]/20 text-[var(--accent-primary)]'
                      : 'text-[var(--text-muted)]'
                    }
                  `}>
                    {index === 0 && <Search className="w-3 h-3" />}
                    {index === 1 && <Code2 className="w-3 h-3" />}
                    {index === 2 && <Eye className="w-3 h-3" />}
                    <span>{step}</span>
                  </div>
                  {index < 2 && (
                    <ChevronRight className="w-3 h-3 text-[var(--text-muted)] mx-1" />
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Log Content */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-3 space-y-2 code-editor"
      >
        {logs.length === 0 && !loading && !result && (
          <div className="flex flex-col items-center justify-center h-full text-center py-8">
            <Sparkles className="w-8 h-8 text-[var(--text-muted)]/30 mb-2" />
            <p className="text-sm text-[var(--text-muted)]">
              Waiting for pipeline to start...
            </p>
            <p className="text-xs text-[var(--text-muted)]/60 mt-1">
              Upload media and click Generate to begin
            </p>
          </div>
        )}

        {logs.map((log) => (
          <div
            key={log.id}
            onClick={() => setExpandedLog(expandedLog === log.id ? null : log.id)}
            className={`
              log-entry group relative pl-3 pr-3 py-2.5 rounded-lg cursor-pointer
              border-l-2 ${getLogBorderColor(log.type)}
              bg-[var(--bg-tertiary)]/50 hover:bg-[var(--bg-tertiary)]
              transition-all duration-200
              ${expandedLog === log.id ? 'ring-1 ring-[var(--border-hover)]' : ''}
            `}
          >
            <div className="flex items-start gap-2.5">
              <div className={`mt-0.5 ${getLogIconColor(log.type)}`}>
                <StepIcon type={log.type} className="w-4 h-4" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-[var(--text-primary)]">
                    {log.message}
                  </span>
                  {log.score !== undefined && (
                    <span className={`
                      text-xs px-1.5 py-0.5 rounded font-mono
                      ${log.passed
                        ? 'bg-green-500/20 text-green-400'
                        : 'bg-yellow-500/20 text-yellow-400'
                      }
                    `}>
                      {log.score.toFixed(2)}
                    </span>
                  )}
                </div>
                <p className="text-xs text-[var(--text-muted)] mt-0.5">
                  {log.timestamp.toLocaleTimeString()}
                  {log.iteration !== undefined && (
                    <span className="ml-2 text-[var(--accent-primary)]">
                      Iteration {log.iteration + 1}
                    </span>
                  )}
                </p>

                {/* Expandable Details */}
                {log.details && (
                  <div className={`
                    mt-2 text-xs text-[var(--text-secondary)] font-mono
                    bg-[var(--bg-primary)]/50 rounded p-2
                    overflow-hidden transition-all duration-200
                    ${expandedLog === log.id ? 'max-h-48' : 'max-h-0 opacity-0'}
                  `}>
                    <pre className="whitespace-pre-wrap break-words">
                      {log.details}
                    </pre>
                  </div>
                )}
              </div>
              {log.details && (
                <ChevronRight className={`
                  w-4 h-4 text-[var(--text-muted)] transition-transform duration-200
                  ${expandedLog === log.id ? 'rotate-90' : ''}
                `} />
              )}
            </div>
          </div>
        ))}

        {/* Current Activity Indicator */}
        {loading && logs.length > 0 && (
          <div className="flex items-center gap-2 py-2 px-3 text-xs text-[var(--text-muted)]">
            <Loader2 className="w-3 h-3 animate-spin" />
            <span>Processing...</span>
          </div>
        )}
      </div>

      {/* Footer Stats */}
      {(result || logs.length > 0) && (
        <div className="px-4 py-2 border-t border-[var(--border-color)] bg-[var(--bg-tertiary)]/30">
          <div className="flex items-center justify-between text-xs text-[var(--text-muted)]">
            <span>{logs.length} entries</span>
            {result?.iteration && (
              <span>Iteration {result.iteration}</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
