// components/ShaderEditor.tsx
import { useState, useCallback, useEffect, useRef } from "react";
import { Code2, Copy, Check, Play, Pause, RotateCcw, Download, Maximize2, Minimize2 } from "lucide-react";

interface ShaderEditorProps {
  code: string | null;
  onChange?: (code: string) => void;
  onRun?: () => void;
  isRunning?: boolean;
}

// Simple GLSL syntax highlighter
function highlightGLSL(code: string): string {
  // Escape HTML
  let highlighted = code
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // Keywords
  const keywords = /\b(void|float|vec2|vec3|vec4|int|bool|mat2|mat3|mat4|sampler2D|uniform|const|in|out|inout|struct|if|else|for|while|do|return|break|continue|discard|true|false)\b/g;
  highlighted = highlighted.replace(keywords, '<span class="syntax-keyword">$1</span>');

  // Built-in functions
  const functions = /\b(sin|cos|tan|asin|acos|atan|sinh|cosh|tanh|pow|exp|log|exp2|log2|sqrt|inversesqrt|abs|sign|floor|ceil|fract|mod|min|max|clamp|mix|step|smoothstep|length|distance|dot|cross|normalize|faceforward|reflect|refract|matrixCompMult|lessThan|lessThanEqual|greaterThan|greaterThanEqual|equal|notEqual|any|all|not|texture2D|texture|mainImage)\b/g;
  highlighted = highlighted.replace(functions, '<span class="syntax-function">$1</span>');

  // Preprocessor directives
  const preprocessor = /^(#\s*(define|ifdef|ifndef|if|else|elif|endif|pragma|extension|version|include)\b)/gm;
  highlighted = highlighted.replace(preprocessor, '<span class="syntax-keyword">$1</span>');

  // Numbers
  const numbers = /\b(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?\b/g;
  highlighted = highlighted.replace(numbers, '<span class="syntax-number">$1$2</span>');

  // Comments
  const singleLineComments = /(\/\/.*$)/gm;
  highlighted = highlighted.replace(singleLineComments, '<span class="syntax-comment">$1</span>');

  const multiLineComments = /(\/\*[\s\S]*?\*\/)/g;
  highlighted = highlighted.replace(multiLineComments, '<span class="syntax-comment">$1</span>');

  return highlighted;
}

export default function ShaderEditor({ code, onChange, onRun, isRunning }: ShaderEditorProps) {
  const [localCode, setLocalCode] = useState(code || '');
  const [copied, setCopied] = useState(false);
  const [lineNumbers, setLineNumbers] = useState<number[]>([]);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const preRef = useRef<HTMLPreElement>(null);

  useEffect(() => {
    if (code !== null && code !== localCode) {
      setLocalCode(code);
    }
  }, [code]);

  // Update line numbers
  useEffect(() => {
    const lines = localCode.split('\n').length;
    setLineNumbers(Array.from({ length: Math.max(lines, 1) }, (_, i) => i + 1));
  }, [localCode]);

  const handleChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newCode = e.target.value;
    setLocalCode(newCode);
    onChange?.(newCode);
  }, [onChange]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Tab') {
      e.preventDefault();
      const target = e.target as HTMLTextAreaElement;
      const start = target.selectionStart;
      const end = target.selectionEnd;
      const newCode = localCode.substring(0, start) + '  ' + localCode.substring(end);
      setLocalCode(newCode);
      onChange?.(newCode);
      // Restore cursor position
      setTimeout(() => {
        target.selectionStart = target.selectionEnd = start + 2;
      }, 0);
    }
  }, [localCode, onChange]);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(localCode);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  }, [localCode]);

  const handleDownload = useCallback(() => {
    const blob = new Blob([localCode], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'shader.frag';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [localCode]);

  const handleReset = useCallback(() => {
    if (code !== null) {
      setLocalCode(code);
      onChange?.(code);
    }
  }, [code, onChange]);

  // Sync scroll between textarea and pre
  const handleScroll = useCallback(() => {
    if (textareaRef.current && preRef.current) {
      preRef.current.scrollTop = textareaRef.current.scrollTop;
      preRef.current.scrollLeft = textareaRef.current.scrollLeft;
    }
  }, []);

  const highlightedCode = highlightGLSL(localCode);

  return (
    <div className={`
      panel bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg overflow-hidden
      flex flex-col transition-all duration-300
      ${isFullscreen ? 'fixed inset-4 z-50' : 'h-full'}
    `}>
      {/* Header */}
      <div className="px-4 py-3 border-b border-[var(--border-color)] flex items-center justify-between bg-[var(--bg-secondary)]">
        <div className="flex items-center gap-2">
          <Code2 className="w-4 h-4 text-[var(--accent-primary)]" />
          <h2 className="text-sm font-semibold text-[var(--text-primary)] uppercase tracking-wider">
            GLSL Editor
          </h2>
          {code && (
            <span className="text-xs text-[var(--text-muted)]">
              {localCode.split('\n').length} lines
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          {onRun && (
            <button
              onClick={onRun}
              disabled={isRunning}
              className={`
                p-2 rounded-lg transition-all duration-200
                ${isRunning
                  ? 'text-yellow-400 bg-yellow-400/10'
                  : 'text-green-400 hover:bg-green-400/10'
                }
              `}
              title={isRunning ? 'Running' : 'Run shader'}
            >
              {isRunning ? (
                <Pause className="w-4 h-4" />
              ) : (
                <Play className="w-4 h-4" />
              )}
            </button>
          )}
          <button
            onClick={handleReset}
            disabled={!code}
            className="p-2 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-secondary)]
                     hover:bg-[var(--bg-tertiary)] transition-all duration-200 disabled:opacity-50"
            title="Reset to original"
          >
            <RotateCcw className="w-4 h-4" />
          </button>
          <button
            onClick={handleCopy}
            className="p-2 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-secondary)]
                     hover:bg-[var(--bg-tertiary)] transition-all duration-200"
            title="Copy code"
          >
            {copied ? (
              <Check className="w-4 h-4 text-green-400" />
            ) : (
              <Copy className="w-4 h-4" />
            )}
          </button>
          <button
            onClick={handleDownload}
            disabled={!localCode}
            className="p-2 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-secondary)]
                     hover:bg-[var(--bg-tertiary)] transition-all duration-200 disabled:opacity-50"
            title="Download shader"
          >
            <Download className="w-4 h-4" />
          </button>
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

      {/* Editor */}
      <div className="flex-1 flex overflow-hidden">
        {/* Line Numbers */}
        <div className="w-12 bg-[var(--bg-tertiary)] border-r border-[var(--border-color)]
                      overflow-hidden select-none flex-shrink-0">
          <div className="py-4 text-right pr-2">
            {lineNumbers.map((num) => (
              <div
                key={num}
                className="text-xs text-[var(--text-muted)] font-mono leading-5"
              >
                {num}
              </div>
            ))}
          </div>
        </div>

        {/* Code Area */}
        <div className="flex-1 relative code-editor">
          {/* Highlighted Code Layer */}
          <pre
            ref={preRef}
            className="absolute inset-0 p-4 m-0 font-mono text-sm leading-5
                     text-[var(--text-primary)] overflow-auto pointer-events-none
                     whitespace-pre"
            dangerouslySetInnerHTML={{ __html: highlightedCode + '<br>' }}
          />

          {/* Input Layer */}
          <textarea
            ref={textareaRef}
            value={localCode}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            onScroll={handleScroll}
            spellCheck={false}
            placeholder={!code ? "Shader code will appear here after generation..." : ""}
            className="absolute inset-0 w-full h-full p-4 m-0 font-mono text-sm leading-5
                     text-transparent caret-[var(--accent-primary)] bg-transparent
                     resize-none outline-none overflow-auto whitespace-pre
                     selection:bg-[var(--accent-primary)]/30"
            style={{
              // Ensure textarea and pre have same dimensions
              tabSize: 2,
            }}
          />
        </div>
      </div>

      {/* Status Bar */}
      <div className="px-4 py-2 border-t border-[var(--border-color)] bg-[var(--bg-tertiary)]/50
                    flex items-center justify-between text-xs">
        <div className="flex items-center gap-4">
          <span className="text-[var(--text-muted)]">
            {localCode.length} chars
          </span>
          <span className="text-[var(--text-muted)]">
            GLSL
          </span>
        </div>
        {code && localCode !== code && (
          <span className="text-yellow-400/80">
            Modified
          </span>
        )}
      </div>
    </div>
  );
}
