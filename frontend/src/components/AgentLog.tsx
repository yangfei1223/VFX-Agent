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
  Eye,
  Image,
  Play,
  Clock,
  Maximize2,
  Minimize2,
  MessageSquare
} from "lucide-react";
import type { PipelineResult, PipelineIteration, PipelineLogEntry, PhaseLog } from "../hooks/usePipeline";

interface AgentLogProps {
  result: PipelineResult | null;
  loading: boolean;
  logs?: PipelineLogEntry[];
  phaseLogs?: PhaseLog[];
  currentPhase?: string | null;
  phaseMessage?: string | null;
}

type LogEntryType = 'extract_keyframes' | 'decompose' | 'generate' | 'render' | 'inspect' | 'success' | 'error' | 'info' | 'system';

interface LogEntry {
  id: string;
  type: LogEntryType;
  timestamp: Date;
  iteration?: number;
  message: string;
  details?: string;
  score?: number;
  passed?: boolean;
  status?: 'started' | 'running' | 'completed' | 'failed';
  duration_ms?: number;
  agent_response?: string;  // Agent's raw response for displaying reasoning
  human_iteration?: boolean;  // Whether this was a human-triggered iteration
  human_feedback?: string;  // User feedback for human iterations
}

// Phase configuration for the timeline
const PHASES = [
  { id: 'extract_keyframes', name: 'Extract Keyframes', icon: Image, description: 'Extracting frames from video' },
  { id: 'decompose', name: 'Decompose', icon: Search, description: 'Analyzing visual content' },
  { id: 'generate', name: 'Generate', icon: Code2, description: 'Creating GLSL shader' },
  { id: 'render', name: 'Render', icon: Play, description: 'Rendering shader frames' },
  { id: 'inspect', name: 'Inspect', icon: Eye, description: 'Evaluating results' },
];

const StepIcon = ({ type, className }: { type: LogEntryType; className?: string }) => {
  switch (type) {
    case 'extract_keyframes':
      return <Image className={className} />;
    case 'decompose':
      return <Search className={className} />;
    case 'generate':
      return <Code2 className={className} />;
    case 'render':
      return <Play className={className} />;
    case 'inspect':
      return <Eye className={className} />;
    case 'success':
      return <CheckCircle2 className={className} />;
    case 'error':
      return <XCircle className={className} />;
    case 'system':
      return <Terminal className={className} />;
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

export default function AgentLog({
  result,
  loading,
  logs: externalLogs,
  phaseLogs,
  currentPhase,
  phaseMessage
}: AgentLogProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [expandedLog, setExpandedLog] = useState<string | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);

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
        status: log.status,
        duration_ms: log.duration_ms,
        agent_response: (log as unknown as { agent_response?: string }).agent_response,
        human_iteration: (log as unknown as { human_iteration?: boolean }).human_iteration,
        human_feedback: (log as unknown as { human_feedback?: string }).human_feedback,
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
      case 'extract_keyframes':
        return 'text-cyan-400';
      case 'decompose':
        return 'text-purple-400';
      case 'generate':
        return 'text-blue-400';
      case 'render':
        return 'text-orange-400';
      case 'inspect':
        return 'text-yellow-400';
      case 'success':
        return 'text-green-400';
      case 'error':
        return 'text-red-400';
      case 'system':
        return 'text-gray-400';
      default:
        return 'text-gray-400';
    }
  };

  const getLogBorderColor = (type: LogEntryType) => {
    switch (type) {
      case 'extract_keyframes':
        return 'border-l-cyan-500';
      case 'decompose':
        return 'border-l-purple-500';
      case 'generate':
        return 'border-l-blue-500';
      case 'render':
        return 'border-l-orange-500';
      case 'inspect':
        return 'border-l-yellow-500';
      case 'success':
        return 'border-l-green-500';
      case 'error':
        return 'border-l-red-500';
      case 'system':
        return 'border-l-gray-500';
      default:
        return 'border-l-gray-500';
    }
  };

  // Determine phase status for the timeline
  const getPhaseStatus = (phaseId: string): 'pending' | 'running' | 'completed' | 'failed' => {
    if (!currentPhase) return 'pending';

    const phaseLogsForPhase = phaseLogs?.filter(p => p.phase === phaseId) || [];
    if (phaseLogsForPhase.length > 0) {
      const lastLog = phaseLogsForPhase[phaseLogsForPhase.length - 1];
      return lastLog.status as 'completed' | 'failed' | 'running';
    }

    const phaseOrder = PHASES.map(p => p.id);
    const currentIndex = phaseOrder.indexOf(currentPhase);
    const phaseIndex = phaseOrder.indexOf(phaseId);

    if (phaseIndex < currentIndex) return 'completed';
    if (phaseIndex === currentIndex) return 'running';
    return 'pending';
  };

  return (
    <div className={`
      panel bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg overflow-hidden flex flex-col
      ${isFullscreen 
        ? 'fixed inset-4 z-50 max-h-none' 
        : 'h-full min-h-[300px]'
      }
    `}>
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
          <button
            onClick={() => setIsFullscreen(!isFullscreen)}
            className="p-1.5 rounded hover:bg-[var(--bg-tertiary)] text-[var(--text-muted)]
                     hover:text-[var(--text-secondary)] transition-colors"
            title={isFullscreen ? "Minimize" : "Maximize"}
          >
            {isFullscreen ? (
              <Minimize2 className="w-3.5 h-3.5" />
            ) : (
              <Maximize2 className="w-3.5 h-3.5" />
            )}
          </button>
        </div>
      </div>

      {/* Phase Timeline */}
      {(loading || result) && (
        <div className="px-4 py-3 bg-[var(--bg-tertiary)]/50 border-b border-[var(--border-color)]">
          {/* Progress message */}
          {phaseMessage && loading && (
            <div className="flex items-center gap-2 mb-2 text-xs text-[var(--accent-primary)]">
              <Loader2 className="w-3 h-3 animate-spin" />
              <span>{phaseMessage}</span>
            </div>
          )}

          {/* Phase timeline */}
          <div className="flex items-center gap-1">
            {PHASES.map((phase, index) => {
              const status = getPhaseStatus(phase.id);
              const isActive = status === 'running';
              const isCompleted = status === 'completed';
              const isFailed = status === 'failed';

              return (
                <div key={phase.id} className="flex items-center">
                  <div className={`
                    flex items-center gap-1.5 px-2 py-1 rounded text-xs font-medium
                    transition-all duration-300 border
                    ${isActive
                      ? 'bg-[var(--accent-primary)]/20 text-[var(--accent-primary)] border-[var(--accent-primary)]/40 shadow-sm'
                      : isCompleted
                        ? 'bg-green-500/20 text-green-400 border-green-500/30'
                        : isFailed
                          ? 'bg-red-500/20 text-red-400 border-red-500/30'
                          : 'text-[var(--text-muted)] border-transparent'
                    }
                  `}>
                    {isActive && <Loader2 className="w-3 h-3 animate-spin" />}
                    {isCompleted && <CheckCircle2 className="w-3 h-3" />}
                    {isFailed && <XCircle className="w-3 h-3" />}
                    {!isActive && !isCompleted && !isFailed && <phase.icon className="w-3 h-3" />}
                    <span>{phase.name}</span>
                  </div>
                  {index < PHASES.length - 1 && (
                    <ChevronRight className={`
                      w-3 h-3 mx-0.5
                      ${isCompleted ? 'text-green-400' : 'text-[var(--text-muted)]'}
                    `} />
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
              ${log.status === 'running' ? 'animate-pulse' : ''}
            `}
          >
            <div className="flex items-start gap-2.5">
              <div className={`mt-0.5 ${getLogIconColor(log.type)}`}>
                {log.status === 'running' && <Loader2 className="w-4 h-4 animate-spin" />}
                {log.status === 'completed' && <CheckCircle2 className="w-4 h-4" />}
                {log.status === 'failed' && <XCircle className="w-4 h-4" />}
                {!log.status && <StepIcon type={log.type} className="w-4 h-4" />}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-[var(--text-primary)]">
                    {log.message}
                  </span>
                  {log.duration_ms !== undefined && log.duration_ms !== null && (
                    <span className="text-xs text-[var(--text-muted)] font-mono">
                      {log.duration_ms > 1000
                        ? `${(log.duration_ms / 1000).toFixed(1)}s`
                        : `${log.duration_ms}ms`}
                    </span>
                  )}
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
                <div className="flex items-center gap-2 mt-0.5">
                  <p className="text-xs text-[var(--text-muted)]">
                    <Clock className="w-3 h-3 inline mr-1" />
                    {log.timestamp.toLocaleTimeString()}
                  </p>
                  {log.iteration !== undefined && (
                    <span className={`text-xs ${log.human_iteration ? 'bg-orange-500/20 text-orange-400' : 'text-[var(--accent-primary)]'} px-1.5 py-0.5 rounded`}>
                      {log.human_iteration ? `人工迭代 ${log.iteration + 1}` : `Iteration ${log.iteration + 1}`}
                    </span>
                  )}
                </div>

                {/* Expandable Details */}
                {log.details && (
                  <div className={`
                    mt-2 text-xs text-[var(--text-secondary)] font-mono
                    bg-[var(--bg-primary)]/50 rounded p-2
                    overflow-hidden transition-all duration-200
                    ${expandedLog === log.id ? 'max-h-48 overflow-y-auto' : 'max-h-0 opacity-0'}
                  `}>
                    <pre className="whitespace-pre-wrap break-words">
                      {log.details}
                    </pre>
                  </div>
                )}

                {/* Agent Reasoning (raw response) */}
                {log.agent_response && expandedLog === log.id && (
                  <div className="mt-2">
                    <div className="flex items-center gap-1.5 text-xs text-[var(--accent-primary)] mb-1">
                      <Sparkles className="w-3 h-3" />
                      <span className="font-medium">Agent Reasoning</span>
                    </div>
                    <div className={`
                      text-xs text-[var(--text-secondary)] font-mono
                      bg-[var(--bg-primary)]/70 rounded p-2 max-h-64 overflow-y-auto
                      border border-[var(--border-color)]/50
                    `}>
                      <pre className="whitespace-pre-wrap break-words">
                        {log.agent_response}
                      </pre>
                    </div>
                  </div>
                )}

                {/* User Feedback (for human iterations) */}
                {log.human_feedback && expandedLog === log.id && (
                  <div className="mt-2">
                    <div className="flex items-center gap-1.5 text-xs text-orange-400 mb-1">
                      <MessageSquare className="w-3 h-3" />
                      <span className="font-medium">用户指令</span>
                    </div>
                    <div className="text-xs text-[var(--text-secondary)] bg-orange-500/10 rounded p-2">
                      {log.human_feedback}
                    </div>
                  </div>
                )}
              </div>
              {(log.details || log.agent_response) && (
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
