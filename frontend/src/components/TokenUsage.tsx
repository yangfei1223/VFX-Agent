import { ArrowRightLeft, ArrowUp, Database, Clock, Repeat } from "lucide-react";
import type { CodexUsage } from "../types/pipeline";

interface TokenUsageProps {
  usage: CodexUsage | null;
  durationMs: number;
  iterationCount: number;
}

function formatNumber(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
  return String(n);
}

function formatDuration(ms: number): string {
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  return `${m}m ${s % 60}s`;
}

export default function TokenUsage({ usage, durationMs, iterationCount }: TokenUsageProps) {
  const cachedPercent = usage
    ? usage.input_tokens > 0
      ? ((usage.cached_input_tokens / usage.input_tokens) * 100).toFixed(1) + "%"
      : "0%"
    : "—";

  return (
    <div className="panel bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg overflow-hidden">
      <div className="px-4 py-2 border-b border-[var(--border-color)]">
        <h2 className="text-xs font-semibold text-[var(--text-primary)] uppercase tracking-wider">
          Usage
        </h2>
      </div>
      <div className="p-4 grid grid-cols-2 gap-x-4 gap-y-3">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-[var(--bg-tertiary)] flex items-center justify-center flex-shrink-0">
            <ArrowRightLeft className="w-4 h-4 text-[var(--text-secondary)]" />
          </div>
          <div className="min-w-0">
            <p className="text-[10px] text-[var(--text-muted)] uppercase tracking-wide">Input tokens</p>
            <p className="text-sm font-medium text-[var(--text-primary)] tabular-nums">
              {usage ? formatNumber(usage.input_tokens) : "—"}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-[var(--bg-tertiary)] flex items-center justify-center flex-shrink-0">
            <ArrowUp className="w-4 h-4 text-[var(--text-secondary)]" />
          </div>
          <div className="min-w-0">
            <p className="text-[10px] text-[var(--text-muted)] uppercase tracking-wide">Output tokens</p>
            <p className="text-sm font-medium text-[var(--text-primary)] tabular-nums">
              {usage ? formatNumber(usage.output_tokens) : "—"}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-[var(--bg-tertiary)] flex items-center justify-center flex-shrink-0">
            <Database className="w-4 h-4 text-[var(--text-secondary)]" />
          </div>
          <div className="min-w-0">
            <p className="text-[10px] text-[var(--text-muted)] uppercase tracking-wide">Cached</p>
            <p className="text-sm font-medium text-[var(--text-primary)] tabular-nums">
              {usage ? (
                <span>
                  {formatNumber(usage.cached_input_tokens)}
                  <span className="text-[10px] text-[var(--text-muted)] ml-1">({cachedPercent})</span>
                </span>
              ) : (
                "—"
              )}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-[var(--bg-tertiary)] flex items-center justify-center flex-shrink-0">
            <Clock className="w-4 h-4 text-[var(--text-secondary)]" />
          </div>
          <div className="min-w-0">
            <p className="text-[10px] text-[var(--text-muted)] uppercase tracking-wide">Duration</p>
            <p className="text-sm font-medium text-[var(--text-primary)] tabular-nums">
              {formatDuration(durationMs)}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2.5 col-span-2">
          <div className="w-8 h-8 rounded-lg bg-[var(--bg-tertiary)] flex items-center justify-center flex-shrink-0">
            <Repeat className="w-4 h-4 text-[var(--text-secondary)]" />
          </div>
          <div className="min-w-0">
            <p className="text-[10px] text-[var(--text-muted)] uppercase tracking-wide">Iterations</p>
            <p className="text-sm font-medium text-[var(--text-primary)] tabular-nums">
              {iterationCount} turns
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
