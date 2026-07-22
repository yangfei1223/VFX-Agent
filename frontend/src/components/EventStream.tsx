import { useRef, useEffect, useState, useCallback } from "react";
import {
  Terminal,
  MessageSquare,
  FileCode,
  Users,
  AlertCircle,
  Activity,
  Trash2,
  ChevronDown,
  ChevronRight,
  Cpu,
} from "lucide-react";
import type { DisplayEvent, DisplayEventType } from "../types/pipeline";

interface EventStreamProps {
  events: DisplayEvent[];
  isRunning: boolean;
  backend?: string;
}

const TYPE_CONFIG: Record<
  DisplayEventType,
  { icon: React.ElementType; label: string; color: string; bg: string }
> = {
  command: {
    icon: Terminal,
    label: "命令",
    color: "text-blue-400",
    bg: "bg-blue-400/10 border-blue-400/20",
  },
  agent_message: {
    icon: MessageSquare,
    label: "消息",
    color: "text-gray-400",
    bg: "bg-gray-400/10 border-gray-400/20",
  },
  file_change: {
    icon: FileCode,
    label: "文件",
    color: "text-green-400",
    bg: "bg-green-400/10 border-green-400/20",
  },
  subagent: {
    icon: Users,
    label: "子代理",
    color: "text-purple-400",
    bg: "bg-purple-400/10 border-purple-400/20",
  },
  error: {
    icon: AlertCircle,
    label: "错误",
    color: "text-red-400",
    bg: "bg-red-400/10 border-red-400/20",
  },
  lifecycle: {
    icon: Activity,
    label: "生命周期",
    color: "text-gray-500",
    bg: "bg-gray-500/10 border-gray-500/20",
  },
};

function StatusIcon({ status }: { status: DisplayEvent["status"] }) {
  if (status === "running") {
    return <div className="w-2 h-2 rounded-full bg-[var(--accent-primary)] animate-pulse" />;
  }
  if (status === "completed") {
    return <div className="w-2 h-2 rounded-full bg-emerald-500" />;
  }
  if (status === "failed") {
    return <div className="w-2 h-2 rounded-full bg-red-500" />;
  }
  return <div className="w-2 h-2 rounded-full bg-[var(--text-muted)]" />;
}

function EventCard({ event }: { event: DisplayEvent }) {
  const [expanded, setExpanded] = useState(false);
  const config = TYPE_CONFIG[event.type] || TYPE_CONFIG.lifecycle;
  const Icon = config.icon;

  return (
    <div className="group">
      <button
        onClick={() => setExpanded(!expanded)}
        className={`
          w-full text-left px-3 py-2 rounded-lg border transition-all duration-200
          ${config.bg}
          hover:bg-opacity-20
        `}
      >
        <div className="flex items-center gap-2">
          <Icon className={`w-3.5 h-3.5 ${config.color} flex-shrink-0`} />
          <span
            className={`
              text-[10px] px-1.5 py-0.5 rounded font-medium uppercase tracking-wide flex-shrink-0
              ${config.color} bg-black/20
            `}
          >
            {config.label}
          </span>
          <span className="text-xs text-[var(--text-primary)] font-medium truncate flex-1 min-w-0">
            {event.title}
          </span>
          <div className="flex items-center gap-1.5 flex-shrink-0">
            <StatusIcon status={event.status} />
            {expanded ? (
              <ChevronDown className="w-3.5 h-3.5 text-[var(--text-muted)]" />
            ) : (
              <ChevronRight className="w-3.5 h-3.5 text-[var(--text-muted)]" />
            )}
          </div>
        </div>
      </button>
      {expanded && (
        <div className="mt-1 px-3 py-2 bg-[var(--bg-tertiary)]/50 border border-[var(--border-color)] rounded-lg">
          <pre className="text-xs font-mono text-[var(--text-secondary)] whitespace-pre-wrap break-all max-h-64 overflow-auto">
            {event.detail}
          </pre>
          {event.command && (
            <div className="mt-2 pt-2 border-t border-[var(--border-color)]">
              <p className="text-[10px] text-[var(--text-muted)] uppercase tracking-wide mb-1">
                Command
              </p>
              <pre className="text-xs font-mono text-[var(--text-secondary)] whitespace-pre-wrap break-all">
                {event.command}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function BackendChip({ backend }: { backend: string }) {
  return (
    <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-[var(--bg-tertiary)] border border-[var(--border-color)] text-[var(--text-secondary)]">
      <Cpu className="w-3 h-3 text-[var(--accent-primary)]" />
      <span className="text-xs font-medium">{backend}</span>
    </div>
  );
}

export default function EventStream({ events, isRunning, backend }: EventStreamProps) {
  const [cleared, setCleared] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const isHoveredRef = useRef(false);

  const displayEvents = cleared ? [] : events;

  useEffect(() => {
    if (events.length > 0) {
      setCleared(false);
    }
  }, [events.length]);

  useEffect(() => {
    if (!isHoveredRef.current && !cleared) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [events, cleared]);

  const handleMouseEnter = useCallback(() => {
    isHoveredRef.current = true;
  }, []);

  const handleMouseLeave = useCallback(() => {
    isHoveredRef.current = false;
  }, []);

  const backendLabel = backend || "codex";
  const emptyText = isRunning ? `等待 ${backendLabel} 事件...` : "尚无事件";

  return (
    <div className="panel bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg overflow-hidden flex flex-col h-full min-h-0">
      <div className="px-4 py-2 border-b border-[var(--border-color)] flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-3 min-w-0">
          <h2 className="text-xs font-semibold text-[var(--text-primary)] uppercase tracking-wider">
            Event Stream
          </h2>
          <BackendChip backend={backendLabel} />
        </div>
        <button
          onClick={() => setCleared(true)}
          disabled={isRunning}
          className={`
            p-1.5 rounded-md transition-colors
            ${isRunning
              ? "text-[var(--text-muted)] cursor-not-allowed"
              : "text-[var(--text-muted)] hover:text-red-400 hover:bg-red-400/10"
            }
          `}
          title={isRunning ? "Running..." : "Clear stream"}
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>
      <div
        ref={containerRef}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        className="flex-1 min-h-0 overflow-y-auto p-3 space-y-2 font-mono"
      >
        {displayEvents.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center p-4">
            <Activity className="w-8 h-8 text-[var(--text-muted)]/30 mb-2" />
            <p className="text-sm text-[var(--text-muted)]">{emptyText}</p>
          </div>
        ) : (
          <>
            {displayEvents.map((event) => (
              <EventCard key={event.id} event={event} />
            ))}
            <div ref={bottomRef} className="h-0" />
          </>
        )}
      </div>
    </div>
  );
}
