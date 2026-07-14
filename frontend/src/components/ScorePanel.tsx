import { useState, useMemo } from "react";
import { Check, AlertTriangle, ChevronDown, ChevronRight } from "lucide-react";
import type { Evaluation, PipelineStatus } from "../types/pipeline";

interface ScorePanelProps {
  score: number;
  status: PipelineStatus;
  evaluation: Evaluation | null;
}

interface Dimension {
  key: string;
  label: string;
  abbreviation: string;
  score: number;
  notes: string;
}

const DIMENSION_KEYS = [
  { key: "composition", label: "构图", abbreviation: "构图" },
  { key: "geometry", label: "几何", abbreviation: "几何" },
  { key: "lighting", label: "光照", abbreviation: "光照" },
  { key: "color", label: "颜色", abbreviation: "颜色" },
  { key: "texture", label: "纹理", abbreviation: "纹理" },
  { key: "animation", label: "动画", abbreviation: "动画" },
  { key: "background", label: "背景", abbreviation: "背景" },
  { key: "vfx_details", label: "视效细节", abbreviation: "细节" },
];

function getStatusBadge(status: PipelineStatus) {
  switch (status) {
    case "passed":
      return { label: "通过", className: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30" };
    case "failed":
      return { label: "失败", className: "bg-red-500/20 text-red-400 border-red-500/30" };
    case "timeout":
      return { label: "超时", className: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30" };
    case "max_iterations":
      return { label: "达上限", className: "bg-orange-500/20 text-orange-400 border-orange-500/30" };
    case "running":
      return { label: "运行中", className: "bg-blue-500/20 text-blue-400 border-blue-500/30" };
    default:
      return { label: status, className: "bg-[var(--bg-tertiary)] text-[var(--text-muted)] border-[var(--border-color)]" };
  }
}

function CollapsibleSection({
  title,
  icon: Icon,
  iconColor,
  items,
  defaultOpen = false,
}: {
  title: string;
  icon: React.ElementType;
  iconColor: string;
  items: string[];
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  if (!items || items.length === 0) return null;
  return (
    <div className="border-t border-[var(--border-color)]">
      <button
        onClick={() => setOpen(!open)}
        className="w-full px-4 py-2.5 flex items-center justify-between hover:bg-[var(--bg-tertiary)]/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Icon className={`w-4 h-4 ${iconColor}`} />
          <span className="text-xs font-medium text-[var(--text-primary)]">{title}</span>
          <span className="text-[10px] text-[var(--text-muted)]">({items.length})</span>
        </div>
        {open ? (
          <ChevronDown className="w-3.5 h-3.5 text-[var(--text-muted)]" />
        ) : (
          <ChevronRight className="w-3.5 h-3.5 text-[var(--text-muted)]" />
        )}
      </button>
      {open && (
        <ul className="px-4 pb-3 space-y-2">
          {items.map((item, index) => (
            <li key={index} className="flex items-start gap-2 text-xs text-[var(--text-secondary)]">
              <span className={`mt-0.5 ${iconColor}`}>•</span>
              <span className="leading-relaxed">{item}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function ScorePanel({ score, status, evaluation }: ScorePanelProps) {
  const [hoveredDimension, setHoveredDimension] = useState<Dimension | null>(null);

  const dimensions: Dimension[] = useMemo(() => {
    const map = evaluation?.dimension_scores || {};
    return DIMENSION_KEYS.map((dim) => ({
      ...dim,
      score: map[dim.key]?.score ?? 0,
      notes: map[dim.key]?.notes || "",
    }));
  }, [evaluation]);

  const badge = getStatusBadge(status);

  const size = 180;
  const center = size / 2;
  const maxRadius = size * 0.35;
  const angleStep = (Math.PI * 2) / DIMENSION_KEYS.length;

  const points = useMemo(() => {
    return dimensions.map((dim, index) => {
      const angle = index * angleStep - Math.PI / 2;
      const radius = dim.score * maxRadius;
      return {
        x: center + radius * Math.cos(angle),
        y: center + radius * Math.sin(angle),
      };
    });
  }, [dimensions, center, maxRadius, angleStep]);

  const polygonPoints = points.map((p) => `${p.x},${p.y}`).join(" ");

  return (
    <div className="panel bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg overflow-hidden">
      <div className="px-4 py-2 border-b border-[var(--border-color)]">
        <h2 className="text-xs font-semibold text-[var(--text-primary)] uppercase tracking-wider">
          Evaluation
        </h2>
      </div>

      <div className="p-4">
        {!evaluation ? (
          <div className="text-center py-8 text-[var(--text-muted)] text-sm">等待评估...</div>
        ) : (
          <>
            {/* Score header */}
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-baseline gap-2">
                <span className="text-5xl font-bold text-[var(--text-primary)] tabular-nums">
                  {score.toFixed(2)}
                </span>
                <span className="text-sm text-[var(--text-muted)]">score</span>
              </div>
              <span
                className={`
                  px-2.5 py-1 rounded-md text-xs font-medium border
                  ${badge.className}
                `}
              >
                {badge.label}
              </span>
            </div>

            {/* Radar chart */}
            <div className="relative mb-4">
              <svg width={size} height={size} className="mx-auto block">
                {/* Background grid circles */}
                {[0.25, 0.5, 0.75, 1].map((level) => (
                  <circle
                    key={level}
                    cx={center}
                    cy={center}
                    r={maxRadius * level}
                    fill="none"
                    stroke="var(--border-color)"
                    strokeWidth={0.5}
                    opacity={0.5}
                  />
                ))}
                {/* Axis lines */}
                {DIMENSION_KEYS.map((_, index) => {
                  const angle = index * angleStep - Math.PI / 2;
                  const x = center + maxRadius * Math.cos(angle);
                  const y = center + maxRadius * Math.sin(angle);
                  return (
                    <line
                      key={index}
                      x1={center}
                      y1={center}
                      x2={x}
                      y2={y}
                      stroke="var(--border-color)"
                      strokeWidth={0.5}
                      opacity={0.5}
                    />
                  );
                })}
                {/* Data polygon */}
                <polygon
                  points={polygonPoints}
                  fill="var(--accent-primary)"
                  fillOpacity={0.2}
                  stroke="var(--accent-primary)"
                  strokeWidth={1.5}
                />
                {/* Data points */}
                {points.map((point, index) => (
                  <g key={index}>
                    <circle
                      cx={point.x}
                      cy={point.y}
                      r={3}
                      fill="var(--accent-primary)"
                      className="cursor-pointer hover:r-4"
                      onMouseEnter={() => setHoveredDimension(dimensions[index])}
                      onMouseLeave={() => setHoveredDimension(null)}
                    />
                  </g>
                ))}
                {/* Labels */}
                {DIMENSION_KEYS.map((dim, index) => {
                  const angle = index * angleStep - Math.PI / 2;
                  const labelRadius = maxRadius + 16;
                  const x = center + labelRadius * Math.cos(angle);
                  const y = center + labelRadius * Math.sin(angle);
                  return (
                    <text
                      key={index}
                      x={x}
                      y={y}
                      textAnchor="middle"
                      dominantBaseline="middle"
                      className="text-[9px] fill-[var(--text-secondary)] cursor-pointer"
                      onMouseEnter={() => setHoveredDimension(dimensions[index])}
                      onMouseLeave={() => setHoveredDimension(null)}
                    >
                      {dim.abbreviation}
                    </text>
                  );
                })}
              </svg>

              {/* Hover tooltip */}
              {hoveredDimension && (
                <div className="absolute top-2 left-1/2 -translate-x-1/2 bg-[var(--bg-tertiary)] border border-[var(--border-color)] rounded-lg px-3 py-2 shadow-lg max-w-[220px]">
                  <p className="text-xs font-medium text-[var(--text-primary)]">
                    {hoveredDimension.label}: {hoveredDimension.score.toFixed(2)}
                  </p>
                  <p className="text-[10px] text-[var(--text-secondary)] mt-1 leading-relaxed">
                    {hoveredDimension.notes}
                  </p>
                </div>
              )}
            </div>

            {/* Collapsible sections */}
            <CollapsibleSection
              title="正确方面"
              icon={Check}
              iconColor="text-emerald-400"
              items={evaluation.correct_aspects || []}
            />
            <CollapsibleSection
              title="视觉问题"
              icon={AlertTriangle}
              iconColor="text-red-400"
              items={evaluation.visual_issues || []}
            />
          </>
        )}
      </div>
    </div>
  );
}
