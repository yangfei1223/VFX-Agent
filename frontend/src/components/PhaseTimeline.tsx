import { Check, X } from "lucide-react";
import type { PhaseInfo, PhaseStatus } from "../types/pipeline";

interface PhaseTimelineProps {
  phases: PhaseInfo[];
  isRunning: boolean;
}

function StatusDot({ status }: { status: PhaseStatus }) {
  if (status === "completed") {
    return (
      <div className="w-5 h-5 rounded-full bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center">
        <Check className="w-3 h-3 text-emerald-500" />
      </div>
    );
  }
  if (status === "failed") {
    return (
      <div className="w-5 h-5 rounded-full bg-red-500/20 border border-red-500/40 flex items-center justify-center">
        <X className="w-3 h-3 text-red-500" />
      </div>
    );
  }
  if (status === "running") {
    return (
      <div className="w-5 h-5 rounded-full bg-[var(--accent-primary)]/20 border border-[var(--accent-primary)] flex items-center justify-center animate-pulse">
        <div className="w-2 h-2 rounded-full bg-[var(--accent-primary)] ring-2 ring-[var(--accent-primary)]/30" />
      </div>
    );
  }
  return (
    <div className="w-5 h-5 rounded-full bg-[var(--bg-tertiary)] border border-[var(--border-color)]" />
  );
}

export default function PhaseTimeline({ phases, isRunning }: PhaseTimelineProps) {
  return (
    <div className="panel bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg overflow-hidden">
      <div className="px-4 py-2 border-b border-[var(--border-color)] flex items-center justify-between">
        <h2 className="text-xs font-semibold text-[var(--text-primary)] uppercase tracking-wider">
          Pipeline Progress
        </h2>
        {isRunning && (
          <span className="text-[10px] text-[var(--accent-primary)] animate-pulse">
            running
          </span>
        )}
      </div>
      <div className="px-4 py-3 overflow-x-auto">
        <div className="flex items-center min-w-max">
          {phases.map((phase, index) => {
            const isLast = index === phases.length - 1;
            const isRunningPhase = phase.status === "running";
            return (
              <div key={phase.id} className="flex items-center">
                <div
                  className={`
                    flex items-center gap-2 px-2.5 py-1.5 rounded-md transition-colors
                    ${isRunningPhase ? "bg-[var(--accent-primary)]/10" : "bg-transparent"}
                  `}
                >
                  <StatusDot status={phase.status} />
                  <span
                    className={`
                      text-xs whitespace-nowrap
                      ${isRunningPhase ? "font-bold text-[var(--text-primary)]" : "text-[var(--text-secondary)]"}
                    `}
                  >
                    {phase.label}
                  </span>
                </div>
                {!isLast && (
                  <div className="w-4 h-px bg-[var(--border-color)] mx-1 flex-shrink-0" />
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
