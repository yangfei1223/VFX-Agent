// ShaderPreview.tsx
import { useEffect, useRef, useState, useCallback } from "react";
import { ShaderRenderer } from "../lib/shader-renderer";

interface ShaderPreviewProps {
  shaderCode: string | null;
  width?: number;
  height?: number;
}

// 为 Playwright 截图服务暴露全局函数
declare global {
  interface Window {
    __shaderReady: boolean;
    __setShaderTime: (t: number) => void;
  }
}

export default function ShaderPreview({ shaderCode, width = 512, height = 512 }: ShaderPreviewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const rendererRef = useRef<ShaderRenderer | null>(null);
  const [compileError, setCompileError] = useState<string | null>(null);
  const [isRendering, setIsRendering] = useState(false);

  // 初始化渲染器
  useEffect(() => {
    if (containerRef.current && !rendererRef.current) {
      rendererRef.current = new ShaderRenderer(containerRef.current);
    }
    
    // 暴露时间设置函数给 Playwright
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

  // Shader 代码变化时重新编译
  useEffect(() => {
    if (!rendererRef.current || !shaderCode) return;

    const result = rendererRef.current.compileShader(shaderCode);
    if (result.success) {
      setCompileError(null);
      rendererRef.current.startRendering();
      setIsRendering(true);
      // 标记 shader 就绪，供 Playwright 等待
      window.__shaderReady = true;
    } else {
      setCompileError(result.error);
      rendererRef.current.stopRendering();
      setIsRendering(false);
      window.__shaderReady = false;
    }
  }, [shaderCode]);

  // 鼠标交互
  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!rendererRef.current) return;
    const rect = e.currentTarget.getBoundingClientRect();
    rendererRef.current.updateMouse(e.clientX - rect.left, e.clientY - rect.top);
  }, []);

  return (
    <div className="flex flex-col items-center gap-2">
      <div
        ref={containerRef}
        style={{ width, height }}
        className="border border-gray-700 rounded-lg overflow-hidden bg-black"
        onMouseMove={handleMouseMove}
      />
      {compileError && (
        <div className="w-full p-2 bg-red-900/50 border border-red-700 rounded text-red-300 text-xs font-mono overflow-auto max-h-32">
          <p className="font-bold mb-1">Compile Error:</p>
          <pre>{compileError}</pre>
        </div>
      )}
      {!shaderCode && (
        <p className="text-gray-500 text-sm">等待生成着色器代码...</p>
      )}
      {isRendering && !compileError && (
        <p className="text-green-400 text-sm">✓ 着色器运行中</p>
      )}
    </div>
  );
}