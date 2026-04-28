// components/ShaderPreview.tsx
import { useEffect, useRef, useState, useCallback } from "react";
import {
  Maximize2,
  Minimize2,
  Play,
  Pause,
  RotateCcw,
  AlertCircle,
  CheckCircle2,
  Loader2,
  Download,
  Image as ImageIcon
} from "lucide-react";
import { ShaderRenderer } from "../lib/shader-renderer";

interface ShaderPreviewProps {
  shaderCode: string | null;
  width?: number;
  height?: number;
  customUniforms?: Record<string, number | number[]>;
}

// Global type declarations for Playwright
declare global {
  interface Window {
    __shaderReady: boolean;
    __setShaderTime: (t: number) => void;
  }
}

type RenderStatus = 'idle' | 'compiling' | 'running' | 'error';

export default function ShaderPreview({
  shaderCode,
  width = 512,
  height = 512,
  customUniforms
}: ShaderPreviewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const rendererRef = useRef<ShaderRenderer | null>(null);
  const [compileError, setCompileError] = useState<string | null>(null);
  const [status, setStatus] = useState<RenderStatus>('idle');
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [fps, setFps] = useState(0);
  const frameCountRef = useRef(0);
  const lastTimeRef = useRef(Date.now());

  // Initialize renderer
  useEffect(() => {
    if (containerRef.current && !rendererRef.current) {
      rendererRef.current = new ShaderRenderer(containerRef.current);
    }

    // Expose time setting function for Playwright
    window.__setShaderTime = (t: number) => {
      if (rendererRef.current) {
        rendererRef.current.setTime(t);
      }
    };

    return () => {
      rendererRef.current?.dispose();
      rendererRef.current = null;
      window.__shaderReady = false;
    };
  }, []);

  // Update FPS counter
  useEffect(() => {
    if (status !== 'running') {
      setFps(0);
      return;
    }

    const interval = setInterval(() => {
      const now = Date.now();
      const elapsed = (now - lastTimeRef.current) / 1000;
      if (elapsed > 0) {
        setFps(Math.round(frameCountRef.current / elapsed));
      }
      frameCountRef.current = 0;
      lastTimeRef.current = now;
    }, 1000);

    return () => clearInterval(interval);
  }, [status]);

  // Compile shader when code changes
  useEffect(() => {
    if (!rendererRef.current || !shaderCode) {
      setStatus('idle');
      return;
    }

    setStatus('compiling');
    setCompileError(null);

    const result = rendererRef.current.compileShader(shaderCode);
    if (result.success) {
      setCompileError(null);
      rendererRef.current.startRendering();
      setStatus('running');
      window.__shaderReady = true;
      frameCountRef.current = 0;
      lastTimeRef.current = Date.now();
    } else {
      setCompileError(result.error);
      rendererRef.current.stopRendering();
      setStatus('error');
      window.__shaderReady = false;
    }
  }, [shaderCode]);

  // Update custom uniforms
  useEffect(() => {
    if (!rendererRef.current || !customUniforms || status !== 'running') return;

    // Custom uniforms would be set here if the renderer supports them
    // This is a placeholder for future enhancement
  }, [customUniforms, status]);

  // Mouse interaction
  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!rendererRef.current) return;
    const rect = e.currentTarget.getBoundingClientRect();
    rendererRef.current.updateMouse(e.clientX - rect.left, e.clientY - rect.top);
  }, []);

  const handleTogglePlayback = useCallback(() => {
    if (!rendererRef.current) return;

    if (status === 'running') {
      rendererRef.current.stopRendering();
      setStatus('idle');
    } else if (shaderCode) {
      rendererRef.current.startRendering();
      setStatus('running');
    }
  }, [status, shaderCode]);

  const handleReset = useCallback(() => {
    if (!rendererRef.current) return;
    rendererRef.current.setTime(0);
  }, []);

  const handleScreenshot = useCallback(() => {
    if (!rendererRef.current || !containerRef.current) return;

    const canvas = containerRef.current.querySelector('canvas');
    if (canvas) {
      const link = document.createElement('a');
      link.download = `shader-${Date.now()}.png`;
      link.href = canvas.toDataURL('image/png');
      link.click();
    }
  }, []);

  const getStatusIcon = () => {
    switch (status) {
      case 'compiling':
        return <Loader2 className="w-4 h-4 animate-spin text-yellow-400" />;
      case 'running':
        return <CheckCircle2 className="w-4 h-4 text-green-400" />;
      case 'error':
        return <AlertCircle className="w-4 h-4 text-red-400" />;
      default:
        return <div className="w-4 h-4 rounded-full bg-gray-500" />;
    }
  };

  const getStatusText = () => {
    switch (status) {
      case 'compiling':
        return 'Compiling...';
      case 'running':
        return `Running • ${fps} FPS`;
      case 'error':
        return 'Error';
      default:
        return 'Idle';
    }
  };

  return (
    <div className={`
      panel bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg overflow-hidden
      flex flex-col h-full transition-all duration-300
      ${isFullscreen ? 'fixed inset-4 z-50' : ''}
    `}>
      {/* Header */}
      <div className="px-4 py-3 border-b border-[var(--border-color)] flex items-center justify-between bg-[var(--bg-secondary)]">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <ImageIcon className="w-4 h-4 text-[var(--accent-primary)]" />
            <h2 className="text-sm font-semibold text-[var(--text-primary)] uppercase tracking-wider">
              Preview
            </h2>
          </div>
          <div className="flex items-center gap-2 px-2 py-1 rounded bg-[var(--bg-tertiary)]">
            {getStatusIcon()}
            <span className={`
              text-xs font-medium
              ${status === 'running' ? 'text-green-400' : ''}
              ${status === 'error' ? 'text-red-400' : ''}
              ${status === 'compiling' ? 'text-yellow-400' : ''}
              ${status === 'idle' ? 'text-[var(--text-muted)]' : ''}
            `}>
              {getStatusText()}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-1">
          {shaderCode && (
            <>
              <button
                onClick={handleTogglePlayback}
                className="p-2 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-secondary)]
                         hover:bg-[var(--bg-tertiary)] transition-all duration-200"
                title={status === 'running' ? 'Pause' : 'Play'}
              >
                {status === 'running' ? (
                  <Pause className="w-4 h-4" />
                ) : (
                  <Play className="w-4 h-4" />
                )}
              </button>
              <button
                onClick={handleReset}
                className="p-2 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-secondary)]
                         hover:bg-[var(--bg-tertiary)] transition-all duration-200"
                title="Reset time"
              >
                <RotateCcw className="w-4 h-4" />
              </button>
              <button
                onClick={handleScreenshot}
                className="p-2 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-secondary)]
                         hover:bg-[var(--bg-tertiary)] transition-all duration-200"
                title="Save screenshot"
              >
                <Download className="w-4 h-4" />
              </button>
            </>
          )}
          <div className="w-px h-5 bg-[var(--border-color)] mx-1" />
          <button
            onClick={() => setIsFullscreen(!isFullscreen)}
            className="p-2 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-secondary)]
                     hover:bg-[var(--bg-tertiary)] transition-all duration-200"
            title={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'}
          >
            {isFullscreen ? (
              <Minimize2 className="w-4 h-4" />
            ) : (
              <Maximize2 className="w-4 h-4" />
            )}
          </button>
        </div>
      </div>

      {/* Canvas Container */}
      <div className="flex-1 min-h-0 flex items-center justify-center p-4 bg-black/50 overflow-hidden">
        <div
          ref={containerRef}
          style={{
            width: isFullscreen ? '100%' : '100%',
            height: isFullscreen ? '100%' : '100%',
            maxWidth: width + 'px',
            maxHeight: height + 'px'
          }}
          className="relative border border-[var(--border-color)] rounded-lg overflow-hidden bg-black
                   cursor-crosshair transition-all duration-200"
          onMouseMove={handleMouseMove}
        >
          {!shaderCode && (
            <div className="absolute inset-0 flex flex-col items-center justify-center text-center p-6">
              <div className="w-16 h-16 rounded-xl bg-[var(--bg-tertiary)] flex items-center justify-center mb-4">
                <ImageIcon className="w-8 h-8 text-[var(--text-muted)]/30" />
              </div>
              <p className="text-sm text-[var(--text-muted)]">
                Waiting for shader code...
              </p>
              <p className="text-xs text-[var(--text-muted)]/60 mt-1">
                Generate or paste GLSL code to see preview
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Error Display */}
      {compileError && (
        <div className="px-4 py-3 border-t border-red-500/30 bg-red-500/10">
          <div className="flex items-start gap-2">
            <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-red-400 mb-1">Compilation Error</p>
              <pre className="text-xs text-red-300/80 font-mono overflow-auto max-h-32 whitespace-pre-wrap">
                {compileError}
              </pre>
            </div>
          </div>
        </div>
      )}

      {/* Info Footer */}
      {shaderCode && status === 'running' && (
        <div className="px-4 py-2 border-t border-[var(--border-color)] bg-[var(--bg-tertiary)]/30">
          <div className="flex items-center justify-between text-xs text-[var(--text-muted)]">
            <span>WebGL 2.0</span>
            <span>Mouse interaction enabled</span>
            <span>{width}x{height}</span>
          </div>
        </div>
      )}
    </div>
  );
}
