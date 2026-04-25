// lib/glsl-parser.ts
// Simple GLSL parser for extracting parameters from shader code

export interface ShaderParameter {
  name: string;
  type: 'float' | 'vec2' | 'vec3' | 'vec4' | 'int' | 'bool';
  value: number | number[];
  min?: number;
  max?: number;
  step?: number;
  category: 'define' | 'uniform';
}

export interface ParsedShader {
  parameters: ShaderParameter[];
  uniforms: string[];
  defines: Map<string, string>;
}

// Parse #define constants
function parseDefines(code: string): ShaderParameter[] {
  const parameters: ShaderParameter[] = [];
  const defineRegex = /^\s*#define\s+(\w+)\s+(.+)$/gm;
  let match;

  while ((match = defineRegex.exec(code)) !== null) {
    const name = match[1];
    const valueStr = match[2].trim();

    // Try to parse as number
    const numValue = parseFloat(valueStr);
    if (!isNaN(numValue)) {
      // Determine appropriate range based on value
      const absValue = Math.abs(numValue);
      let min = 0;
      let max = absValue * 2;
      let step = absValue / 100;

      if (numValue < 0) {
        min = -absValue * 2;
        max = absValue * 2;
      }

      // Adjust ranges for common shader parameters
      if (name.toLowerCase().includes('speed') || name.toLowerCase().includes('time')) {
        min = 0;
        max = 5;
        step = 0.01;
      } else if (name.toLowerCase().includes('intensity') || name.toLowerCase().includes('strength')) {
        min = 0;
        max = 2;
        step = 0.01;
      } else if (name.toLowerCase().includes('count') || name.toLowerCase().includes('iter')) {
        min = 1;
        max = Math.max(100, numValue * 2);
        step = 1;
      } else if (name.toLowerCase().includes('radius') || name.toLowerCase().includes('size')) {
        min = 0.001;
        max = Math.max(1, numValue * 2);
        step = 0.001;
      }

      parameters.push({
        name,
        type: 'float',
        value: numValue,
        min,
        max,
        step,
        category: 'define'
      });
    }
  }

  return parameters;
}

// Parse uniform declarations
function parseUniforms(code: string): ShaderParameter[] {
  const parameters: ShaderParameter[] = [];
  const uniformRegex = /^\s*uniform\s+(\w+)\s+(\w+)\s*;?\s*$/gm;
  let match;

  while ((match = uniformRegex.exec(code)) !== null) {
    const type = match[1] as ShaderParameter['type'];
    const name = match[2];

    let value: number | number[];
    let min = 0;
    let max = 1;
    let step = 0.01;

    switch (type) {
      case 'float':
        value = 0.5;
        break;
      case 'int':
        value = 1;
        min = 0;
        max = 100;
        step = 1;
        break;
      case 'bool':
        value = 1;
        min = 0;
        max = 1;
        step = 1;
        break;
      case 'vec2':
        value = [0.5, 0.5];
        break;
      case 'vec3':
        value = [0.5, 0.5, 0.5];
        break;
      case 'vec4':
        value = [0.5, 0.5, 0.5, 1.0];
        break;
      default:
        continue;
    }

    // Adjust ranges based on parameter name patterns
    const lowerName = name.toLowerCase();
    if (lowerName.includes('color') || lowerName.includes('rgb')) {
      min = 0;
      max = 1;
      step = 0.01;
    } else if (lowerName.includes('position') || lowerName.includes('offset')) {
      min = -1;
      max = 1;
      step = 0.01;
    } else if (lowerName.includes('scale') || lowerName.includes('zoom')) {
      min = 0.1;
      max = 10;
      step = 0.1;
    }

    parameters.push({
      name,
      type,
      value,
      min,
      max,
      step,
      category: 'uniform'
    });
  }

  return parameters;
}

// Main parse function
export function parseShader(code: string): ParsedShader {
  const defines = parseDefines(code);
  const uniforms = parseUniforms(code);

  // Extract all uniform names for the renderer
  const uniformNames: string[] = [];
  const uniformRegex = /^\s*uniform\s+\w+\s+(\w+)\s*;?\s*$/gm;
  let match;
  while ((match = uniformRegex.exec(code)) !== null) {
    uniformNames.push(match[1]);
  }

  // Extract all defines
  const definesMap = new Map<string, string>();
  const defineRegex = /^\s*#define\s+(\w+)\s+(.+)$/gm;
  while ((match = defineRegex.exec(code)) !== null) {
    definesMap.set(match[1], match[2].trim());
  }

  return {
    parameters: [...defines, ...uniforms],
    uniforms: uniformNames,
    defines: definesMap
  };
}

// Update shader code with new parameter value
export function updateShaderParam(
  code: string,
  param: ShaderParameter,
  newValue: number | number[]
): string {
  if (param.category === 'define') {
    // Replace #define value
    const defineRegex = new RegExp(`^(\\s*#define\\s+${param.name}\\s+).+$`, 'm');
    const valueStr = Array.isArray(newValue) ? newValue.join(', ') : String(newValue);
    return code.replace(defineRegex, `$1${valueStr}`);
  }
  // For uniforms, we don't modify the code - they're set at runtime
  return code;
}

// Generate uniform declarations for custom parameters
export function generateUniformDeclarations(params: ShaderParameter[]): string {
  return params
    .filter(p => p.category === 'uniform')
    .map(p => `uniform ${p.type} ${p.name};`)
    .join('\n');
}
