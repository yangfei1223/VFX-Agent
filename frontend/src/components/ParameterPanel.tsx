// components/ParameterPanel.tsx
import { useState, useEffect, useCallback, useMemo } from "react";
import {
  SlidersHorizontal,
  RotateCcw,
  ChevronDown,
  ChevronRight,
  Hash,
  Box,
  Info
} from "lucide-react";
import { parseShader, updateShaderParam, type ShaderParameter } from "../lib/glsl-parser";

interface ParameterPanelProps {
  code: string | null;
  onParamChange?: (name: string, value: number | number[], category: 'define' | 'uniform') => void;
  onCodeUpdate?: (code: string) => void;
}

interface ParameterGroup {
  name: string;
  params: ShaderParameter[];
}

// Single parameter control component
function ParameterControl({
  param,
  value,
  onChange
}: {
  param: ShaderParameter;
  value: number | number[];
  onChange: (val: number | number[]) => void;
}) {
  const handleNumberChange = useCallback((newVal: number) => {
    onChange(newVal);
  }, [onChange]);

  const handleVecChange = useCallback((index: number, newVal: number) => {
    const current = Array.isArray(value) ? value : [value];
    const newArr = [...current];
    newArr[index] = newVal;
    onChange(newArr);
  }, [value, onChange]);

  // Render float/int control
  if (param.type === 'float' || param.type === 'int') {
    const numValue = typeof value === 'number' ? value : Number(value);
    const isInt = param.type === 'int';

    return (
      <div className="space-y-2">
        <div className="flex items-center gap-3">
          <input
            type="range"
            min={param.min}
            max={param.max}
            step={isInt ? 1 : (param.step || 0.01)}
            value={numValue}
            onChange={(e) => handleNumberChange(isInt ? parseInt(e.target.value) : parseFloat(e.target.value))}
            className="flex-1 h-1 bg-[var(--border-color)] rounded-lg appearance-none cursor-pointer"
          />
          <input
            type="number"
            value={isInt ? Math.round(numValue) : numValue.toFixed(3)}
            onChange={(e) => handleNumberChange(isInt ? parseInt(e.target.value) : parseFloat(e.target.value))}
            className="w-20 px-2 py-1 bg-[var(--bg-tertiary)] border border-[var(--border-color)]
                     rounded text-xs font-mono text-[var(--text-primary)] text-right
                     focus:border-[var(--accent-primary)] focus:outline-none"
            step={isInt ? 1 : (param.step || 0.01)}
          />
        </div>
      </div>
    );
  }

  // Render vec2 control
  if (param.type === 'vec2') {
    const vecValue = Array.isArray(value) ? value : [value, value];
    return (
      <div className="grid grid-cols-2 gap-2">
        {['X', 'Y'].map((label, i) => (
          <div key={label} className="flex items-center gap-2">
            <span className="text-xs text-[var(--text-muted)] w-4">{label}</span>
            <input
              type="number"
              value={vecValue[i] || 0}
              onChange={(e) => handleVecChange(i, parseFloat(e.target.value))}
              className="flex-1 px-2 py-1 bg-[var(--bg-tertiary)] border border-[var(--border-color)]
                       rounded text-xs font-mono text-[var(--text-primary)]
                       focus:border-[var(--accent-primary)] focus:outline-none"
              step={param.step || 0.01}
            />
          </div>
        ))}
      </div>
    );
  }

  // Render vec3 control (with color preview)
  if (param.type === 'vec3') {
    const vecValue = Array.isArray(value) ? value : [value, value, value];
    const colorString = `rgb(${Math.round((vecValue[0] || 0) * 255)}, ${Math.round((vecValue[1] || 0) * 255)}, ${Math.round((vecValue[2] || 0) * 255)})`;

    return (
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <div
            className="w-8 h-8 rounded border border-[var(--border-color)] flex-shrink-0"
            style={{ backgroundColor: colorString }}
          />
          <div className="flex-1 grid grid-cols-3 gap-1">
            {['R', 'G', 'B'].map((label, i) => (
              <div key={label} className="flex items-center gap-1">
                <span className="text-[10px] text-[var(--text-muted)]">{label}</span>
                <input
                  type="number"
                  value={(vecValue[i] || 0).toFixed(2)}
                  onChange={(e) => handleVecChange(i, parseFloat(e.target.value))}
                  className="w-full px-1.5 py-1 bg-[var(--bg-tertiary)] border border-[var(--border-color)]
                           rounded text-[10px] font-mono text-[var(--text-primary)]
                           focus:border-[var(--accent-primary)] focus:outline-none"
                  step={0.01}
                  min={0}
                  max={1}
                />
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  // Render vec4 control
  if (param.type === 'vec4') {
    const vecValue = Array.isArray(value) ? value : [value, value, value, value];
    const colorString = `rgba(${Math.round((vecValue[0] || 0) * 255)}, ${Math.round((vecValue[1] || 0) * 255)}, ${Math.round((vecValue[2] || 0) * 255)}, ${vecValue[3] || 1})`;

    return (
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <div
            className="w-8 h-8 rounded border border-[var(--border-color)] flex-shrink-0"
            style={{ backgroundColor: colorString }}
          />
          <div className="flex-1 grid grid-cols-4 gap-1">
            {['R', 'G', 'B', 'A'].map((label, i) => (
              <div key={label} className="flex items-center gap-1">
                <span className="text-[10px] text-[var(--text-muted)]">{label}</span>
                <input
                  type="number"
                  value={(vecValue[i] || 0).toFixed(2)}
                  onChange={(e) => handleVecChange(i, parseFloat(e.target.value))}
                  className="w-full px-1 py-1 bg-[var(--bg-tertiary)] border border-[var(--border-color)]
                           rounded text-[10px] font-mono text-[var(--text-primary)]
                           focus:border-[var(--accent-primary)] focus:outline-none"
                  step={0.01}
                  min={0}
                  max={1}
                />
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  // Render bool control
  if (param.type === 'bool') {
    const boolValue = typeof value === 'number' ? value > 0 : Boolean(value);
    return (
      <label className="flex items-center gap-2 cursor-pointer">
        <div className={`
          w-10 h-5 rounded-full transition-colors duration-200 relative
          ${boolValue ? 'bg-[var(--accent-primary)]' : 'bg-[var(--border-color)]'}
        `}>
          <div className={`
            w-4 h-4 rounded-full bg-white absolute top-0.5 transition-all duration-200
            ${boolValue ? 'left-5' : 'left-0.5'}
          `} />
        </div>
        <input
          type="checkbox"
          checked={boolValue}
          onChange={(e) => onChange(e.target.checked ? 1 : 0)}
          className="hidden"
        />
        <span className="text-xs text-[var(--text-secondary)]">
          {boolValue ? 'ON' : 'OFF'}
        </span>
      </label>
    );
  }

  return null;
}

export default function ParameterPanel({ code, onParamChange, onCodeUpdate }: ParameterPanelProps) {
  const [parsedParams, setParsedParams] = useState<ShaderParameter[]>([]);
  const [paramValues, setParamValues] = useState<Map<string, number | number[]>>(new Map());
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set(['defines', 'uniforms']));
  const [originalCode, setOriginalCode] = useState<string>('');

  // Parse shader when code changes
  useEffect(() => {
    if (!code) {
      setParsedParams([]);
      setParamValues(new Map());
      return;
    }

    const parsed = parseShader(code);
    setParsedParams(parsed.parameters);
    setOriginalCode(code);

    // Initialize parameter values
    const values = new Map<string, number | number[]>();
    parsed.parameters.forEach(p => {
      values.set(p.name, p.value);
    });
    setParamValues(values);
  }, [code]);

  // Group parameters by category
  const groups = useMemo((): ParameterGroup[] => {
    const defines = parsedParams.filter(p => p.category === 'define');
    const uniforms = parsedParams.filter(p => p.category === 'uniform');

    return [
      { name: 'defines', params: defines },
      { name: 'uniforms', params: uniforms }
    ].filter(g => g.params.length > 0);
  }, [parsedParams]);

  const handleParamChange = useCallback((param: ShaderParameter, newValue: number | number[]) => {
    setParamValues(prev => {
      const next = new Map(prev);
      next.set(param.name, newValue);
      return next;
    });

    // Notify parent
    onParamChange?.(param.name, newValue, param.category);

    // Update code if it's a #define
    if (param.category === 'define' && code) {
      const updatedParam = { ...param, value: newValue };
      const newCode = updateShaderParam(code, updatedParam, newValue);
      onCodeUpdate?.(newCode);
    }
  }, [code, onParamChange, onCodeUpdate]);

  const handleReset = useCallback(() => {
    const values = new Map<string, number | number[]>();
    parsedParams.forEach(p => {
      values.set(p.name, p.value);
    });
    setParamValues(values);

    // Reset code to original
    if (originalCode) {
      onCodeUpdate?.(originalCode);
    }
  }, [parsedParams, originalCode, onCodeUpdate]);

  const toggleGroup = useCallback((name: string) => {
    setExpandedGroups(prev => {
      const next = new Set(prev);
      if (next.has(name)) {
        next.delete(name);
      } else {
        next.add(name);
      }
      return next;
    });
  }, []);

  const hasModifiedValues = useCallback(() => {
    return parsedParams.some(p => {
      const current = paramValues.get(p.name);
      return JSON.stringify(current) !== JSON.stringify(p.value);
    });
  }, [parsedParams, paramValues]);

  if (!code) {
    return (
      <div className="panel bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg overflow-hidden">
        <div className="px-4 py-3 border-b border-[var(--border-color)] flex items-center gap-2">
          <SlidersHorizontal className="w-4 h-4 text-[var(--accent-primary)]" />
          <h2 className="text-sm font-semibold text-[var(--text-primary)] uppercase tracking-wider">
            Parameters
          </h2>
        </div>
        <div className="p-8 text-center">
          <Info className="w-8 h-8 text-[var(--text-muted)]/30 mx-auto mb-2" />
          <p className="text-sm text-[var(--text-muted)]">
            Parameters will be extracted from shader code
          </p>
          <p className="text-xs text-[var(--text-muted)]/60 mt-1">
            Supports #define constants and uniform variables
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="panel bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-[var(--border-color)] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <SlidersHorizontal className="w-4 h-4 text-[var(--accent-primary)]" />
          <h2 className="text-sm font-semibold text-[var(--text-primary)] uppercase tracking-wider">
            Parameters
          </h2>
          <span className="text-xs text-[var(--text-muted)]">
            ({parsedParams.length})
          </span>
        </div>
        {hasModifiedValues() && (
          <button
            onClick={handleReset}
            className="p-1.5 rounded hover:bg-[var(--bg-tertiary)] text-[var(--text-muted)]
                     hover:text-[var(--text-secondary)] transition-colors"
            title="Reset all parameters"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {/* Parameter Groups */}
      <div className="divide-y divide-[var(--border-color)]">
        {groups.map((group) => (
          <div key={group.name}>
            {/* Group Header */}
            <button
              onClick={() => toggleGroup(group.name)}
              className="w-full px-4 py-2.5 flex items-center gap-2 hover:bg-[var(--bg-tertiary)]/50
                       transition-colors"
            >
              {expandedGroups.has(group.name) ? (
                <ChevronDown className="w-4 h-4 text-[var(--text-muted)]" />
              ) : (
                <ChevronRight className="w-4 h-4 text-[var(--text-muted)]" />
              )}
              {group.name === 'defines' ? (
                <Hash className="w-4 h-4 text-[var(--accent-secondary)]" />
              ) : (
                <Box className="w-4 h-4 text-[var(--accent-primary)]" />
              )}
              <span className="text-sm font-medium text-[var(--text-primary)] capitalize">
                {group.name}
              </span>
              <span className="text-xs text-[var(--text-muted)]">
                ({group.params.length})
              </span>
            </button>

            {/* Group Content */}
            {expandedGroups.has(group.name) && (
              <div className="px-4 pb-3 space-y-3">
                {group.params.map((param) => {
                  const currentValue = paramValues.get(param.name) ?? param.value;
                  const isModified = JSON.stringify(currentValue) !== JSON.stringify(param.value);

                  return (
                    <div
                      key={param.name}
                      className={`
                        p-3 rounded-lg border transition-all duration-200
                        ${isModified
                          ? 'bg-[var(--accent-primary)]/5 border-[var(--accent-primary)]/20'
                          : 'bg-[var(--bg-tertiary)]/50 border-[var(--border-color)]'
                        }
                      `}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-mono text-[var(--text-primary)]">
                            {param.name}
                          </span>
                          <span className="text-xs px-1.5 py-0.5 rounded bg-[var(--bg-tertiary)]
                                       text-[var(--text-muted)]">
                            {param.type}
                          </span>
                        </div>
                        {isModified && (
                          <button
                            onClick={() => handleParamChange(param, param.value)}
                            className="text-[10px] text-[var(--accent-primary)] hover:underline"
                          >
                            Reset
                          </button>
                        )}
                      </div>
                      <ParameterControl
                        param={param}
                        value={currentValue}
                        onChange={(val) => handleParamChange(param, val)}
                      />
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Empty State */}
      {groups.length === 0 && (
        <div className="p-6 text-center">
          <p className="text-sm text-[var(--text-muted)]">
            No parameters found in shader
          </p>
          <p className="text-xs text-[var(--text-muted)]/60 mt-1">
            Add #define or uniform declarations to enable controls
          </p>
        </div>
      )}
    </div>
  );
}
