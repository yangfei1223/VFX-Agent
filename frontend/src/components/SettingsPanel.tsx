// components/SettingsPanel.tsx
import { useState, useEffect, useCallback } from 'react';
import { X, RotateCcw, Settings, Check, AlertCircle, Sparkles } from 'lucide-react';

interface SettingsPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

interface Settings {
  // Backend
  backend: 'codex' | 'claude-code';
  codex_proxy: string;
  codex_timeout: number;
  claude_code_proxy: string;
  claude_code_timeout: number;
  // Pipeline
  max_iterations: number;
  passing_threshold: number;
  // Render
  screenshot_width: number;
  screenshot_height: number;
  render_timeout_ms: number;
  // System
  workdir_root: string;
}

const DEFAULT_SETTINGS: Settings = {
  backend: 'codex',
  codex_proxy: 'http://127.0.0.1:7890',
  codex_timeout: 600,
  claude_code_proxy: '',
  claude_code_timeout: 600,
  max_iterations: 5,
  passing_threshold: 0.85,
  screenshot_width: 1280,
  screenshot_height: 720,
  render_timeout_ms: 2000,
  workdir_root: '/tmp/vfx_workdirs',
};

const API_BASE = 'http://localhost:8000';

export default function SettingsPanel({ isOpen, onClose }: SettingsPanelProps) {
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS);
  const [savedSettings, setSavedSettings] = useState<Settings>(DEFAULT_SETTINGS);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch settings on open
  useEffect(() => {
    if (isOpen) {
      const fetchSettings = async () => {
        setIsLoading(true);
        setError(null);
        try {
          const res = await fetch(`${API_BASE}/config`);
          if (res.ok) {
            const data = await res.json();
            const fetched: Settings = {
              backend: data.backend ?? DEFAULT_SETTINGS.backend,
              codex_proxy: data.codex_proxy ?? DEFAULT_SETTINGS.codex_proxy,
              codex_timeout: data.codex_timeout ?? DEFAULT_SETTINGS.codex_timeout,
              claude_code_proxy: data.claude_code_proxy ?? DEFAULT_SETTINGS.claude_code_proxy,
              claude_code_timeout: data.claude_code_timeout ?? DEFAULT_SETTINGS.claude_code_timeout,
              max_iterations: data.max_iterations ?? DEFAULT_SETTINGS.max_iterations,
              passing_threshold: data.passing_threshold ?? DEFAULT_SETTINGS.passing_threshold,
              screenshot_width: data.screenshot_width ?? DEFAULT_SETTINGS.screenshot_width,
              screenshot_height: data.screenshot_height ?? DEFAULT_SETTINGS.screenshot_height,
              render_timeout_ms: data.render_timeout_ms ?? DEFAULT_SETTINGS.render_timeout_ms,
              workdir_root: data.workdir_root ?? DEFAULT_SETTINGS.workdir_root,
            };
            setSettings(fetched);
            setSavedSettings(fetched);
          }
        } catch (e) {
          console.warn('Failed to fetch settings:', e);
        } finally {
          setIsLoading(false);
        }
      };
      fetchSettings();
    }
  }, [isOpen]);

  const handleSave = useCallback(async () => {
    setIsSaving(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          backend: settings.backend,
          codex_proxy: settings.codex_proxy,
          codex_timeout: settings.codex_timeout,
          claude_code_proxy: settings.claude_code_proxy,
          claude_code_timeout: settings.claude_code_timeout,
          max_iterations: settings.max_iterations,
          passing_threshold: settings.passing_threshold,
          screenshot_width: settings.screenshot_width,
          screenshot_height: settings.screenshot_height,
          render_timeout_ms: settings.render_timeout_ms,
          workdir_root: settings.workdir_root,
        }),
      });
      if (!res.ok) throw new Error(`Failed: ${res.statusText}`);
      setSavedSettings(settings);
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save');
    } finally {
      setIsSaving(false);
    }
  }, [settings, onClose]);

  const handleReset = useCallback(() => {
    setSettings(DEFAULT_SETTINGS);
    setError(null);
  }, []);

  const hasChanges = Object.keys(settings).some(
    (key) => settings[key as keyof Settings] !== savedSettings[key as keyof Settings]
  );

  const handleClose = useCallback(() => {
    if (hasChanges) {
      if (window.confirm('Discard unsaved changes?')) {
        onClose();
      }
    } else {
      onClose();
    }
  }, [hasChanges, onClose]);

  // Close on Escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        handleClose();
      }
    };
    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [isOpen, handleClose]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) handleClose();
      }}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />

      {/* Dialog */}
      <div
        className="relative w-full max-w-2xl bg-[var(--bg-secondary)] border border-[var(--border-color)]
                   rounded-2xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-5 border-b border-[var(--border-color)]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[var(--accent-primary)] to-[var(--accent-secondary)]
                          flex items-center justify-center shadow-lg shadow-[var(--accent-primary)]/20">
              <Settings className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-[var(--text-primary)]">
                System Settings
              </h2>
              <p className="text-xs text-[var(--text-muted)]">
                Configure runtime parameters
              </p>
            </div>
          </div>
          <button
            onClick={handleClose}
            className="p-2 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)]
                     hover:bg-[var(--bg-tertiary)] transition-colors"
            aria-label="Close"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="px-6 py-5 space-y-6 max-h-[70vh] overflow-y-auto">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <div className="w-8 h-8 border-2 border-[var(--accent-primary)]/30
                            border-t-[var(--accent-primary)] rounded-full animate-spin" />
            </div>
          ) : (
            <>
              {/* Backend Group */}
              <div className="space-y-4">
                <h3 className="text-sm font-semibold text-[var(--text-primary)] uppercase tracking-wider border-b border-[var(--border-color)] pb-2">
                  Backend
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-2 sm:col-span-2">
                    <label className="text-sm font-medium text-[var(--text-primary)]">Backend</label>
                    <select
                      value={settings.backend}
                      onChange={(e) => setSettings(s => ({ ...s, backend: e.target.value as Settings['backend'] }))}
                      className="w-full px-3 py-2 bg-[var(--bg-tertiary)] border border-[var(--border-color)] rounded-lg
                               text-sm text-[var(--text-primary)] focus:border-[var(--accent-primary)] focus:outline-none
                               focus:ring-1 focus:ring-[var(--accent-primary)]/30"
                    >
                      <option value="codex">codex</option>
                      <option value="claude-code">claude-code</option>
                    </select>
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-[var(--text-primary)]">Codex Proxy</label>
                    <input
                      type="text"
                      value={settings.codex_proxy}
                      onChange={(e) => setSettings(s => ({ ...s, codex_proxy: e.target.value }))}
                      className="w-full px-3 py-2 bg-[var(--bg-tertiary)] border border-[var(--border-color)] rounded-lg
                               text-sm text-[var(--text-primary)] font-mono focus:border-[var(--accent-primary)]
                               focus:outline-none focus:ring-1 focus:ring-[var(--accent-primary)]/30"
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-[var(--text-primary)]">Codex Timeout (s)</label>
                    <input
                      type="number"
                      min={1}
                      max={3600}
                      value={settings.codex_timeout}
                      onChange={(e) => setSettings(s => ({ ...s, codex_timeout: parseInt(e.target.value) || 0 }))}
                      className="w-full px-3 py-2 bg-[var(--bg-tertiary)] border border-[var(--border-color)] rounded-lg
                               text-sm text-[var(--text-primary)] font-mono focus:border-[var(--accent-primary)]
                               focus:outline-none focus:ring-1 focus:ring-[var(--accent-primary)]/30"
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-[var(--text-primary)]">Claude Code Proxy</label>
                    <input
                      type="text"
                      value={settings.claude_code_proxy}
                      onChange={(e) => setSettings(s => ({ ...s, claude_code_proxy: e.target.value }))}
                      className="w-full px-3 py-2 bg-[var(--bg-tertiary)] border border-[var(--border-color)] rounded-lg
                               text-sm text-[var(--text-primary)] font-mono focus:border-[var(--accent-primary)]
                               focus:outline-none focus:ring-1 focus:ring-[var(--accent-primary)]/30"
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-[var(--text-primary)]">Claude Code Timeout (s)</label>
                    <input
                      type="number"
                      min={1}
                      max={3600}
                      value={settings.claude_code_timeout}
                      onChange={(e) => setSettings(s => ({ ...s, claude_code_timeout: parseInt(e.target.value) || 0 }))}
                      className="w-full px-3 py-2 bg-[var(--bg-tertiary)] border border-[var(--border-color)] rounded-lg
                               text-sm text-[var(--text-primary)] font-mono focus:border-[var(--accent-primary)]
                               focus:outline-none focus:ring-1 focus:ring-[var(--accent-primary)]/30"
                    />
                  </div>
                </div>
              </div>

              {/* Pipeline Group */}
              <div className="space-y-4">
                <h3 className="text-sm font-semibold text-[var(--text-primary)] uppercase tracking-wider border-b border-[var(--border-color)] pb-2">
                  Pipeline
                </h3>
                <div className="space-y-5">
                  {/* Max Iterations */}
                  <div className="group">
                    <div className="flex items-center justify-between mb-2">
                      <label className="text-sm font-medium text-[var(--text-primary)]">
                        Max Iterations
                      </label>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-[var(--text-muted)]">1</span>
                        <div className="relative w-24 h-2 bg-[var(--bg-tertiary)] rounded-full overflow-hidden">
                          <div
                            className="absolute left-0 top-0 h-full bg-gradient-to-r from-[var(--accent-primary)]
                                      to-[var(--accent-secondary)] rounded-full transition-all duration-150"
                            style={{ width: `${((settings.max_iterations - 1) / 19) * 100}%` }}
                          />
                          <input
                            type="range"
                            min={1}
                            max={20}
                            step={1}
                            value={settings.max_iterations}
                            onChange={(e) => setSettings(s => ({ ...s, max_iterations: parseInt(e.target.value) }))}
                            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                          />
                        </div>
                        <span className="text-xs text-[var(--text-muted)]">20</span>
                      </div>
                    </div>
                    <div className="flex items-center justify-between">
                      <p className="text-xs text-[var(--text-muted)]">
                        Maximum shader generation cycles
                      </p>
                      <span className="text-sm font-bold text-[var(--accent-primary)] font-mono">
                        {settings.max_iterations}
                      </span>
                    </div>
                  </div>

                  {/* Passing Threshold */}
                  <div className="group">
                    <div className="flex items-center justify-between mb-2">
                      <label className="text-sm font-medium text-[var(--text-primary)]">
                        Passing Threshold
                      </label>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-[var(--text-muted)]">0.50</span>
                        <div className="relative w-24 h-2 bg-[var(--bg-tertiary)] rounded-full overflow-hidden">
                          <div
                            className="absolute left-0 top-0 h-full bg-gradient-to-r from-emerald-500
                                      to-emerald-400 rounded-full transition-all duration-150"
                            style={{ width: `${((settings.passing_threshold - 0.5) / 0.5) * 100}%` }}
                          />
                          <input
                            type="range"
                            min={0.5}
                            max={1.0}
                            step={0.01}
                            value={settings.passing_threshold}
                            onChange={(e) => setSettings(s => ({ ...s, passing_threshold: parseFloat(e.target.value) }))}
                            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                          />
                        </div>
                        <span className="text-xs text-[var(--text-muted)]">1.00</span>
                      </div>
                    </div>
                    <div className="flex items-center justify-between">
                      <p className="text-xs text-[var(--text-muted)]">
                        Minimum similarity score to pass inspection
                      </p>
                      <span className="text-sm font-bold text-emerald-400 font-mono">
                        {settings.passing_threshold.toFixed(2)}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Render Group */}
              <div className="space-y-4">
                <h3 className="text-sm font-semibold text-[var(--text-primary)] uppercase tracking-wider border-b border-[var(--border-color)] pb-2">
                  Render
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-[var(--text-primary)]">Screenshot Width</label>
                    <input
                      type="number"
                      min={256}
                      max={2048}
                      value={settings.screenshot_width}
                      onChange={(e) => setSettings(s => ({ ...s, screenshot_width: parseInt(e.target.value) || 0 }))}
                      className="w-full px-3 py-2 bg-[var(--bg-tertiary)] border border-[var(--border-color)] rounded-lg
                               text-sm text-[var(--text-primary)] font-mono focus:border-[var(--accent-primary)]
                               focus:outline-none focus:ring-1 focus:ring-[var(--accent-primary)]/30"
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-[var(--text-primary)]">Screenshot Height</label>
                    <input
                      type="number"
                      min={256}
                      max={2048}
                      value={settings.screenshot_height}
                      onChange={(e) => setSettings(s => ({ ...s, screenshot_height: parseInt(e.target.value) || 0 }))}
                      className="w-full px-3 py-2 bg-[var(--bg-tertiary)] border border-[var(--border-color)] rounded-lg
                               text-sm text-[var(--text-primary)] font-mono focus:border-[var(--accent-primary)]
                               focus:outline-none focus:ring-1 focus:ring-[var(--accent-primary)]/30"
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-[var(--text-primary)]">Render Timeout (ms)</label>
                    <input
                      type="number"
                      min={500}
                      max={10000}
                      step={100}
                      value={settings.render_timeout_ms}
                      onChange={(e) => setSettings(s => ({ ...s, render_timeout_ms: parseInt(e.target.value) || 0 }))}
                      className="w-full px-3 py-2 bg-[var(--bg-tertiary)] border border-[var(--border-color)] rounded-lg
                               text-sm text-[var(--text-primary)] font-mono focus:border-[var(--accent-primary)]
                               focus:outline-none focus:ring-1 focus:ring-[var(--accent-primary)]/30"
                    />
                  </div>
                </div>
              </div>

              {/* System Group */}
              <div className="space-y-4">
                <h3 className="text-sm font-semibold text-[var(--text-primary)] uppercase tracking-wider border-b border-[var(--border-color)] pb-2">
                  System
                </h3>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-[var(--text-primary)]">Workdir Root</label>
                  <input
                    type="text"
                    value={settings.workdir_root}
                    onChange={(e) => setSettings(s => ({ ...s, workdir_root: e.target.value }))}
                    className="w-full px-3 py-2 bg-[var(--bg-tertiary)] border border-[var(--border-color)] rounded-lg
                             text-sm text-[var(--text-primary)] font-mono focus:border-[var(--accent-primary)]
                             focus:outline-none focus:ring-1 focus:ring-[var(--accent-primary)]/30"
                  />
                </div>
              </div>

              {/* Error */}
              {error && (
                <div className="flex items-center gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                  <AlertCircle className="w-4 h-4 text-red-400" />
                  <p className="text-sm text-red-400">{error}</p>
                </div>
              )}

              {/* Unsaved Indicator */}
              {hasChanges && !isSaving && (
                <div className="flex items-center gap-2 text-xs text-[var(--accent-primary)]">
                  <Sparkles className="w-3 h-3" />
                  <span>Unsaved changes</span>
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-[var(--border-color)]
                      bg-[var(--bg-tertiary)]/30">
          <button
            onClick={handleReset}
            disabled={isLoading || isSaving}
            className="flex items-center gap-2 px-3 py-2 text-sm text-[var(--text-muted)]
                     hover:text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)]
                     rounded-lg transition-colors disabled:opacity-50"
          >
            <RotateCcw className="w-4 h-4" />
            Defaults
          </button>
          <div className="flex items-center gap-3">
            <button
              onClick={handleClose}
              disabled={isSaving}
              className="px-4 py-2 text-sm font-medium text-[var(--text-secondary)]
                       hover:text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)]
                       rounded-lg transition-colors disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={isSaving || isLoading}
              className={`
                flex items-center gap-2 px-5 py-2 text-sm font-semibold rounded-lg
                transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed
                ${isSaving || isLoading
                  ? 'bg-[var(--bg-tertiary)] text-[var(--text-muted)]'
                  : 'bg-gradient-to-r from-[var(--accent-primary)] to-[var(--accent-secondary)] text-white hover:shadow-lg hover:shadow-[var(--accent-primary)]/30'
                }
              `}
            >
              {isSaving ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>Saving...</span>
                </>
              ) : (
                <>
                  <Check className="w-4 h-4" />
                  <span>Apply</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
