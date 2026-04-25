// App.tsx
import { useState, useEffect } from "react";
import UploadPanel from "./components/UploadPanel";
import ShaderPreview from "./components/ShaderPreview";
import PipelineStatus from "./components/PipelineStatus";
import CodeView from "./components/CodeView";
import { usePipeline } from "./hooks/usePipeline";

export default function App() {
  const { result, loading, startPipeline } = usePipeline();
  const [shaderCode, setShaderCode] = useState<string | null>(null);

  // 支持通过 URL 参数直接渲染（供 Playwright 截图服务使用）
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const shaderParam = params.get("shader");
    if (shaderParam) {
      try {
        const code = atob(shaderParam.replace(/-/g, "+").replace(/_/g, "/"));
        setShaderCode(code);
      } catch (e) {
        console.error("Failed to decode shader from URL", e);
      }
    }
  }, []);

  // Pipeline 产出 shader 时更新预览
  useEffect(() => {
    if (result?.current_shader) {
      setShaderCode(result.current_shader);
    }
  }, [result?.current_shader]);

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <header className="border-b border-gray-800 px-6 py-4">
        <h1 className="text-xl font-bold">VFX Agent</h1>
        <p className="text-sm text-gray-400">AI 驱动的视觉效果自动生成</p>
      </header>

      <main className="max-w-7xl mx-auto p-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左列：输入 + 状态 */}
        <div className="space-y-6">
          <UploadPanel onSubmit={startPipeline} loading={loading} />
          <PipelineStatus result={result} loading={loading} />
        </div>

        {/* 中列：Shader 预览 */}
        <div className="space-y-4">
          <ShaderPreview shaderCode={shaderCode} width={512} height={512} />
        </div>

        {/* 右列：代码查看 */}
        <div>
          <CodeView code={shaderCode} />
        </div>
      </main>
    </div>
  );
}