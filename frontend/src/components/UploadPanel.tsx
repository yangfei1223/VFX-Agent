// components/UploadPanel.tsx
import { useRef, useState } from "react";

interface UploadPanelProps {
  onSubmit: (formData: FormData) => void;
  loading: boolean;
}

export default function UploadPanel({ onSubmit, loading }: UploadPanelProps) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [notes, setNotes] = useState("");
  const [previews, setPreviews] = useState<string[]>([]);

  const handleFileChange = () => {
    const files = fileRef.current?.files;
    if (!files) return;
    const urls = Array.from(files).map((f) => URL.createObjectURL(f));
    setPreviews(urls);
  };

  const handleSubmit = () => {
    const formData = new FormData();
    const files = fileRef.current?.files;
    if (files) {
      Array.from(files).forEach((f) => formData.append("images", f));
    }
    formData.append("notes", notes);
    onSubmit(formData);
  };

  return (
    <div className="flex flex-col gap-4 p-4 bg-gray-900 rounded-xl">
      <h2 className="text-lg font-semibold text-white">视觉参考输入</h2>

      <div>
        <label className="block text-sm text-gray-400 mb-1">
          上传视频或图片（支持多选）
        </label>
        <input
          ref={fileRef}
          type="file"
          accept="video/*,image/*"
          multiple
          onChange={handleFileChange}
          className="block w-full text-sm text-gray-400 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:bg-blue-600 file:text-white hover:file:bg-blue-500"
        />
      </div>

      {previews.length > 0 && (
        <div className="flex gap-2 overflow-x-auto">
          {previews.map((src, i) => (
            <img key={i} src={src} className="h-20 rounded border border-gray-700" />
          ))}
        </div>
      )}

      <div>
        <label className="block text-sm text-gray-400 mb-1">
          附加参数标注（可选）
        </label>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="e.g. 循环周期2s，缓动曲线ease-in-out，主色#1a1a2e"
          className="w-full h-20 bg-gray-800 text-white rounded p-2 text-sm border border-gray-700 focus:border-blue-500 focus:outline-none"
        />
      </div>

      <button
        onClick={handleSubmit}
        disabled={loading || previews.length === 0}
        className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? "生成中..." : "开始生成"}
      </button>
    </div>
  );
}