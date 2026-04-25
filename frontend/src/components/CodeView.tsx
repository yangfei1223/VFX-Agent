// components/CodeView.tsx
interface Props {
  code: string | null;
}

export default function CodeView({ code }: Props) {
  if (!code) {
    return <div className="text-gray-500 text-sm p-4">等待着色器代码生成...</div>;
  }

  return (
    <div className="p-4 bg-gray-900 rounded-xl">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-lg font-semibold text-white">GLSL 代码</h2>
        <button
          onClick={() => navigator.clipboard.writeText(code)}
          className="text-xs text-gray-400 hover:text-white px-2 py-1 border border-gray-700 rounded"
        >
          复制
        </button>
      </div>
      <pre className="bg-gray-950 text-green-300 text-xs font-mono p-3 rounded overflow-auto max-h-96 leading-relaxed">
        {code}
      </pre>
    </div>
  );
}