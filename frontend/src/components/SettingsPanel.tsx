// components/SettingsPanel.tsx
import { useState, useEffect, useCallback } from 'react';
import { X, RotateCcw, Settings, Check, AlertCircle, Sparkles } from 'lucide-react';

interface SettingsPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

interface Settings {
  maxIterations: number;
  passingThreshold: number;
}

const DEFAULT_SETTINGS: Settings = {
  maxIterations: 3,
  passingThreshold: 0.85,
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
            setSettings({
              maxIterations: data.max_iterations,
              passingThreshold: data.passing_threshold,
            });
            setSavedSettings({
              maxIterations: data.max_iterations,
              passingThreshold: data.passing_threshold,
            });
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
          max_iterations: settings.maxIterations,
          passing_threshold: settings.passingThreshold,
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

  const handleClose = useCallback(() => {
    const hasChanges = 
      settings.maxIterations !== savedSettings.maxIterations ||
      settings.passingThreshold !== savedSettings.passingThreshold;
    
    if (hasChanges) {
      if (window.confirm('Discard unsaved changes?')) {
        onClose();
      }
    } else {
      onClose();
    }
  }, [settings, savedSettings, onClose]);

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

  const hasChanges = 
    settings.maxIterations !== savedSettings.maxIterations ||
    settings.passingThreshold !== savedSettings.passingThreshold;

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
        className="relative w-full max-w-lg bg-[var(--bg-secondary)] border border-[var(--border-color)]
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
                Configure pipeline parameters
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
        <div className="px-6 py-5 space-y-5">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <div className="w-8 h-8 border-2 border-[var(--accent-primary)]/30 
                            border-t-[var(--accent-primary)] rounded-full animate-spin" />
            </div>
          ) : (
            <>
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
                        style={{ width: `${((settings.maxIterations - 1) / 4) * 100}%` }}
                      />
                      <input
                        type="range"
                        min={1}
                        max={5}
                        step={1}
                        value={settings.maxIterations}
                        onChange={(e) => setSettings(s => ({ ...s, maxIterations: parseInt(e.target.value) }))}
                        className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                      />
                    </div>
                    <span className="text-xs text-[var(--text-muted)]">5</span>
                  </div>
                </div>
                <div className="flex items-center justify-between">
                  <p className="text-xs text-[var(--text-muted)]">
                    Maximum shader generation cycles
                  </p>
                  <span className="text-sm font-bold text-[var(--accent-primary)] font-mono">
                    {settings.maxIterations}
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
                        style={{ width: `${((settings.passingThreshold - 0.5) / 0.5) * 100}%` }}
                      />
                      <input
                        type="range"
                        min={0.5}
                        max={1.0}
                        step={0.05}
                        value={settings.passingThreshold}
                        onChange={(e) => setSettings(s => ({ ...s, passingThreshold: parseFloat(e.target.value) }))}
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
                    {settings.passingThreshold.toFixed(2)}
                  </span>
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