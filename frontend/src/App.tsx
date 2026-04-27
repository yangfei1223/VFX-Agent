// App.tsx
import { useState, useEffect, useCallback } from "react";
import InputPanel from "./components/InputPanel";
import AgentLog from "./components/AgentLog";
import ShaderEditor from "./components/ShaderEditor";
import ParameterPanel from "./components/ParameterPanel";
import ShaderPreview from "./components/ShaderPreview";
import SettingsPanel from "./components/SettingsPanel";
import { usePipeline } from "./hooks/usePipeline";
import {
  Terminal,
  Zap,
  Settings,
  Info
} from "lucide-react";

function App() {
  const { result, loading, logs, phaseLogs, currentPhase, phaseMessage, startPipeline } = usePipeline();
  const [showSettings, setShowSettings] = useState(false);
  const [shaderCode, setShaderCode] = useState<string | null>(null);
  const [editedCode, setEditedCode] = useState<string | null>(null);

  // Support direct shader rendering via URL params (for Playwright screenshots)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const shaderParam = params.get("shader");
    if (shaderParam) {
      try {
        const code = atob(shaderParam.replace(/-/g, "+").replace(/_/g, "/"));
        setShaderCode(code);
        setEditedCode(code);
      } catch (e) {
        console.error("Failed to decode shader from URL", e);
      }
    }
  }, []);

  // Update shader when pipeline produces result
  useEffect(() => {
    if (result?.current_shader) {
      setShaderCode(result.current_shader);
      setEditedCode(result.current_shader);
    }
  }, [result?.current_shader]);

  // Handle code edits from the editor
  const handleCodeChange = useCallback((code: string) => {
    setEditedCode(code);
  }, []);

  // Handle parameter changes
  const handleParamChange = useCallback((_name: string, _value: number | number[], _category: 'define' | 'uniform') => {
    // Update shader code if it's a #define
    if (_category === 'define' && editedCode) {
      // The ParameterPanel already updates the code via onCodeUpdate
      // This is for additional side effects if needed
    }
  }, [editedCode]);

  // Handle code updates from parameter panel
  const handleCodeUpdate = useCallback((code: string) => {
    setEditedCode(code);
  }, []);

  // Handle pipeline submission (settings are now fetched from backend)
  const handleSubmit = useCallback((formData: FormData) => {
    startPipeline(formData);
  }, [startPipeline]);

  // Determine which code to use for preview
  const previewCode = editedCode || shaderCode;

  return (
    <div className="min-h-screen bg-[var(--bg-primary)] text-[var(--text-primary)] font-sans">
      {/* Header */}
      <header className="border-b border-[var(--border-color)] bg-[var(--bg-secondary)]/80 backdrop-blur-sm sticky top-0 z-40">
        <div className="px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[var(--accent-primary)] to-[var(--accent-secondary)]
                          flex items-center justify-center">
              <Zap className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-[var(--text-primary)] tracking-tight">
                VFX Agent
              </h1>
              <p className="text-xs text-[var(--text-muted)]">
                AI-Powered Shader Generation
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <a
              href="https://github.com"
              target="_blank"
              rel="noopener noreferrer"
              className="p-2 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)]
                       hover:bg-[var(--bg-tertiary)] transition-all duration-200"
              title="View on GitHub"
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
              </svg>
            </a>
<button
              onClick={() => setShowSettings(true)}
              className="p-2 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)]
                        hover:bg-[var(--bg-tertiary)] transition-all duration-200"
              title="Settings"
            >
              <Settings className="w-5 h-5" />
            </button>
            <button
              className="p-2 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)]
                       hover:bg-[var(--bg-tertiary)] transition-all duration-200"
              title="About"
            >
              <Info className="w-5 h-5" />
            </button>
          </div>
        </div>
      </header>

      {/* Main Content - Three Column Layout */}
      <main className="h-[calc(100vh-64px)] p-4">
        <div className="grid grid-cols-12 gap-4 h-full">

          {/* Left Column: Input + Agent Log */}
          <div className="col-span-3 flex flex-col gap-4 h-full overflow-hidden">
            {/* Input Panel */}
            <div className="flex-shrink-0">
              <InputPanel onSubmit={handleSubmit} loading={loading} />
            </div>

            {/* Agent Process Log */}
            <div className="flex-1 min-h-0">
              <AgentLog
                result={result}
                loading={loading}
                logs={logs}
                phaseLogs={phaseLogs}
                currentPhase={currentPhase}
                phaseMessage={phaseMessage}
              />
            </div>
          </div>

          {/* Center Column: Parameter Panel + Shader Editor */}
          <div className="col-span-5 flex flex-col gap-4 h-full overflow-hidden">
            {/* Parameter Panel */}
            <div className="flex-shrink-0">
              <ParameterPanel
                code={previewCode}
                onParamChange={handleParamChange}
                onCodeUpdate={handleCodeUpdate}
              />
            </div>

            {/* Shader Editor */}
            <div className="flex-1 min-h-0">
              <ShaderEditor
                code={previewCode}
                onChange={handleCodeChange}
                isRunning={loading}
              />
            </div>
          </div>

          {/* Right Column: Shader Preview */}
          <div className="col-span-4 h-full overflow-hidden">
            <ShaderPreview
              shaderCode={previewCode}
              width={600}
              height={600}
            />
          </div>

        </div>
      </main>

      {/* Mobile/Tablet Warning */}
      <div className="fixed inset-0 bg-[var(--bg-primary)] z-50 flex items-center justify-center lg:hidden">
        <div className="text-center p-8">
          <div className="w-16 h-16 rounded-xl bg-[var(--bg-tertiary)] flex items-center justify-center mx-auto mb-4">
            <Terminal className="w-8 h-8 text-[var(--text-muted)]" />
          </div>
          <h2 className="text-xl font-bold text-[var(--text-primary)] mb-2">
            Desktop Only
          </h2>
          <p className="text-sm text-[var(--text-muted)] max-w-xs">
            VFX Agent is designed for desktop use with a large screen.
            Please use a device with a screen width of at least 1024px.
          </p>
        </div>
      </div>

      {/* Settings Panel */}
      <SettingsPanel isOpen={showSettings} onClose={() => setShowSettings(false)} />
    </div>
  );
}

export default App;
