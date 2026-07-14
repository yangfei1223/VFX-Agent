// App.tsx — v2.0 codex OD 前端全量适配
import { useState, useEffect, useCallback, useMemo } from "react";
import { Zap, Settings, Info, X, Clock, Trophy, AlertCircle } from "lucide-react";

import { usePipeline } from "./hooks/usePipeline";
import type { PipelineStatus } from "./types/pipeline";

import InputPanel from "./components/InputPanel";
import ShaderEditor from "./components/ShaderEditor";
import ShaderPreview from "./components/ShaderPreview";

import PhaseTimeline from "./components/PhaseTimeline";
import EventStream from "./components/EventStream";
import ScorePanel from "./components/ScorePanel";
import TokenUsage from "./components/TokenUsage";

import {
  ResizableGroup,
  ResizablePanel,
  ResizableSeparator,
} from "./components/Resizable";

function formatDuration(ms: number): string {
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  return `${m}m ${s % 60}s`;
}

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
      return { label: "就绪", className: "bg-[var(--bg-tertiary)] text-[var(--text-muted)] border-[var(--border-color)]" };
  }
}

interface StatusCardProps {
  status: PipelineStatus;
  score: number;
  durationMs: number;
  error: string | null;
}

function StatusCard({ status, score, durationMs, error }: StatusCardProps) {
  const badge = getStatusBadge(status);
  return (
    <div className="panel bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg overflow-hidden">
      <div className="px-5 py-3 border-b border-[var(--border-color)]">
        <h2 className="text-xs font-semibold text-[var(--text-primary)] uppercase tracking-wider">
          Status
        </h2>
      </div>
      <div className="p-5 space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-sm text-[var(--text-muted)]">状态</span>
          <span className={`px-2.5 py-1 rounded text-xs font-medium border ${badge.className}`}>
            {badge.label}
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm text-[var(--text-muted)]">评分</span>
          <div className="flex items-center gap-1.5">
            <Trophy className="w-4 h-4 text-[var(--text-muted)]" />
            <span className="text-sm font-medium text-[var(--text-primary)] tabular-nums">
              {score.toFixed(2)}
            </span>
          </div>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm text-[var(--text-muted)]">耗时</span>
          <div className="flex items-center gap-1.5">
            <Clock className="w-4 h-4 text-[var(--text-muted)]" />
            <span className="text-sm font-medium text-[var(--text-primary)] tabular-nums">
              {formatDuration(durationMs)}
            </span>
          </div>
        </div>
        {error && (
          <div className="flex items-start gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
            <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
            <p className="text-xs text-red-300 leading-relaxed">{error}</p>
          </div>
        )}
      </div>
    </div>
  );
}

interface KeyframeThumbnailsProps {
  paths: string[];
}

function KeyframeThumbnails({ paths }: KeyframeThumbnailsProps) {
  if (!paths || paths.length === 0) return null;
  return (
    <div className="panel bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg overflow-hidden">
      <div className="px-5 py-3 border-b border-[var(--border-color)]">
        <h2 className="text-xs font-semibold text-[var(--text-primary)] uppercase tracking-wider">
          Keyframes
        </h2>
      </div>
      <div className="p-5 grid grid-cols-3 gap-3 max-h-56 overflow-y-auto">
        {paths.map((path, index) => (
          <div
            key={`${path}-${index}`}
            className="aspect-square rounded-lg border border-[var(--border-color)] overflow-hidden bg-black/40"
          >
            <img
              src={`/file?path=${encodeURIComponent(path)}`}
              alt={`Keyframe ${index + 1}`}
              className="w-full h-full object-cover"
              onError={(e) => {
                e.currentTarget.style.display = "none";
              }}
            />
          </div>
        ))}
      </div>
    </div>
  );
}

function AboutModal({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  if (!isOpen) return null;
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-6"
      onClick={onClose}
    >
      <div
        className="bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-xl max-w-lg w-full p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-[var(--text-primary)]">关于 VFX-Agent</h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)] transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="space-y-3 text-sm text-[var(--text-secondary)] leading-relaxed">
          <p>
            <strong className="text-[var(--text-primary)]">VFX-Agent v2.0 (codex OD mode)</strong>
          </p>
          <p>
            从 UX 视频/图片输入自动生成 Shadertoy 格式 GLSL 着色器，并通过隔离子代理评分反馈迭代直至收敛。
          </p>
          <p>v2.0 采用 codex OD（Orchestrated Dispatch）动态编排替代 v1.0 的 LangGraph 静态编排：</p>
          <ol className="list-decimal list-inside space-y-1 ml-1">
            <li>分析关键帧 → visual_description.json</li>
            <li>生成 shader → shader.glsl</li>
            <li>验证编译 → validate_shader.py</li>
            <li>渲染截图 → render_shader.py + Playwright</li>
            <li>子代理评分 → spawn_agent (fork_turns=&quot;none&quot;)</li>
            <li>迭代或收尾</li>
          </ol>
        </div>
        <div className="mt-6 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg bg-[var(--accent-primary)] text-white text-sm font-medium hover:bg-[var(--accent-primary)]/90 transition-colors"
          >
            关闭
          </button>
        </div>
      </div>
    </div>
  );
}

function App() {
  const {
    record,
    isRunning,
    start,
    error,
    phases,
    displayEvents,
  } = usePipeline();

  const [showAbout, setShowAbout] = useState(false);
  const [editedCode, setEditedCode] = useState<string | null>(null);

  // Keep editedCode in sync with the pipeline result, but don't override local edits.
  useEffect(() => {
    if (record?.final_shader && editedCode === null) {
      setEditedCode(record.final_shader);
    }
  }, [record?.final_shader, editedCode]);

  const handleSubmit = useCallback(
    (formData: FormData) => {
      const notes = (formData.get("notes") as string) || "";
      const images = formData
        .getAll("images")
        .filter((f): f is File => f instanceof File);
      start(notes, images);
    },
    [start]
  );

  const handleCodeChange = useCallback((code: string) => {
    setEditedCode(code);
  }, []);

  const previewCode = editedCode || record?.final_shader || null;

  const iterationCount = useMemo(() => {
    if (!record?.events) return 0;
    // Count turn.completed events as iteration count.
    // Use String(event.type) to guard against non-string type values in raw events.
    const count = record.events.filter(
      (event) => String(event.type) === "turn.completed"
    ).length;
    return Number.isFinite(count) ? count : 0;
  }, [record?.events]);

  const status = record?.status || "not_found";

  return (
    <div className="min-h-screen bg-[var(--bg-primary)] text-[var(--text-primary)] font-sans">
      {/* Header */}
      <header className="border-b border-[var(--border-color)] bg-[var(--bg-secondary)]/80 backdrop-blur-sm sticky top-0 z-40">
        <div className="px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[var(--accent-primary)] to-[var(--accent-secondary)] flex items-center justify-center">
              <Zap className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-[var(--text-primary)] tracking-tight">
                VFX Agent
              </h1>
              <p className="text-xs text-[var(--text-muted)]">AI-Powered Shader Generation</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => alert("v2.0 配置编辑待实现")}
              className="p-2 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)] transition-all duration-200"
              title="Settings"
            >
              <Settings className="w-5 h-5" />
            </button>
            <button
              onClick={() => setShowAbout(true)}
              className="p-2 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)] transition-all duration-200"
              title="About"
            >
              <Info className="w-5 h-5" />
            </button>
          </div>
        </div>
      </header>

      {/* Main Content - Three Resizable Column Layout */}
      <main className="h-[calc(100vh-64px)] p-6">
        <ResizableGroup
          orientation="horizontal"
          storageKey="vfx-layout-horizontal"
          className="h-full min-h-0"
        >
          {/* Left Column */}
          <ResizablePanel defaultSize={20} minSize={15} maxSize={30}>
            <ResizableGroup
              orientation="vertical"
              storageKey="vfx-layout-left"
              className="h-full"
            >
              <ResizablePanel defaultSize={60} minSize={35} maxSize={75}>
                <InputPanel onSubmit={handleSubmit} loading={isRunning} />
              </ResizablePanel>
              <ResizableSeparator />
              <ResizablePanel defaultSize={15} minSize={10} maxSize={25}>
                <StatusCard
                  status={status}
                  score={record?.final_score ?? 0}
                  durationMs={record?.duration_ms ?? 0}
                  error={error}
                />
              </ResizablePanel>
              <ResizableSeparator />
              <ResizablePanel defaultSize={25} minSize={15} maxSize={35}>
                <KeyframeThumbnails paths={record?.keyframe_paths || []} />
              </ResizablePanel>
            </ResizableGroup>
          </ResizablePanel>

          <ResizableSeparator />

          {/* Center Column */}
          <ResizablePanel defaultSize={50} minSize={30} maxSize={70}>
            <ResizableGroup
              orientation="vertical"
              storageKey="vfx-layout-center"
              className="h-full"
            >
              <ResizablePanel defaultSize={12} minSize={8} maxSize={20}>
                <PhaseTimeline phases={phases} isRunning={isRunning} />
              </ResizablePanel>
              <ResizableSeparator />
              <ResizablePanel defaultSize={58} minSize={35} maxSize={75}>
                <EventStream events={displayEvents} isRunning={isRunning} />
              </ResizablePanel>
              <ResizableSeparator />
              <ResizablePanel defaultSize={30} minSize={15} maxSize={45}>
                <ShaderEditor code={record?.final_shader || null} onChange={handleCodeChange} isRunning={isRunning} />
              </ResizablePanel>
            </ResizableGroup>
          </ResizablePanel>

          <ResizableSeparator />

          {/* Right Column */}
          <ResizablePanel defaultSize={30} minSize={20} maxSize={40}>
            <ResizableGroup
              orientation="vertical"
              storageKey="vfx-layout-right"
              className="h-full"
            >
              <ResizablePanel defaultSize={35} minSize={20} maxSize={45}>
                <ScorePanel
                  score={record?.final_score ?? 0}
                  status={status}
                  evaluation={record?.evaluation || null}
                />
              </ResizablePanel>
              <ResizableSeparator />
              <ResizablePanel defaultSize={45} minSize={25} maxSize={60}>
                <ShaderPreview shaderCode={previewCode} />
              </ResizablePanel>
              <ResizableSeparator />
              <ResizablePanel defaultSize={20} minSize={12} maxSize={30}>
                <TokenUsage
                  usage={record?.codex_usage || null}
                  durationMs={record?.duration_ms ?? 0}
                  iterationCount={iterationCount}
                />
              </ResizablePanel>
            </ResizableGroup>
          </ResizablePanel>
        </ResizableGroup>
      </main>

      <AboutModal isOpen={showAbout} onClose={() => setShowAbout(false)} />
    </div>
  );
}

export default App;
