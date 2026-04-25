// components/InputPanel.tsx
import { useRef, useState, useCallback } from "react";
import { Upload, Image as ImageIcon, Film, FileText, X, Sparkles } from "lucide-react";

interface InputPanelProps {
  onSubmit: (formData: FormData) => void;
  loading: boolean;
}

interface MediaFile {
  id: string;
  file: File;
  preview: string;
  type: 'image' | 'video';
}

export default function InputPanel({ onSubmit, loading }: InputPanelProps) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [description, setDescription] = useState("");
  const [mediaFiles, setMediaFiles] = useState<MediaFile[]>([]);
  const [dragActive, setDragActive] = useState(false);

  const generateId = () => Math.random().toString(36).substring(2, 9);

  const handleFileChange = useCallback((files: FileList | null) => {
    if (!files) return;

    const newFiles: MediaFile[] = [];
    Array.from(files).forEach((file) => {
      const isVideo = file.type.startsWith('video/');
      const isImage = file.type.startsWith('image/');

      if (isVideo || isImage) {
        const preview = URL.createObjectURL(file);
        newFiles.push({
          id: generateId(),
          file,
          preview,
          type: isVideo ? 'video' : 'image'
        });
      }
    });

    setMediaFiles((prev) => [...prev, ...newFiles]);
  }, []);

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    handleFileChange(e.dataTransfer.files);
  }, [handleFileChange]);

  const removeFile = useCallback((id: string) => {
    setMediaFiles((prev) => {
      const file = prev.find(f => f.id === id);
      if (file) {
        URL.revokeObjectURL(file.preview);
      }
      return prev.filter(f => f.id !== id);
    });
  }, []);

  const handleSubmit = useCallback(() => {
    const formData = new FormData();
    mediaFiles.forEach((mf) => {
      formData.append(mf.type === 'video' ? "video" : "images", mf.file);
    });
    formData.append("notes", description);
    onSubmit(formData);
  }, [mediaFiles, description, onSubmit]);

  const hasContent = mediaFiles.length > 0 || description.trim().length > 0;

  return (
    <div className="panel bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-[var(--border-color)] flex items-center gap-2">
        <Upload className="w-4 h-4 text-[var(--accent-primary)]" />
        <h2 className="text-sm font-semibold text-[var(--text-primary)] uppercase tracking-wider">
          Input
        </h2>
      </div>

      <div className="p-4 space-y-4">
        {/* Media Upload Area */}
        <div
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          onClick={() => fileRef.current?.click()}
          className={`
            relative border-2 border-dashed rounded-lg p-6 cursor-pointer
            transition-all duration-200
            ${dragActive
              ? 'border-[var(--accent-primary)] bg-[var(--accent-primary)]/5'
              : 'border-[var(--border-color)] hover:border-[var(--border-hover)] hover:bg-[var(--bg-tertiary)]'
            }
          `}
        >
          <input
            ref={fileRef}
            type="file"
            accept="video/mp4,video/webm,image/png,image/jpeg,image/webp"
            multiple
            onChange={(e) => handleFileChange(e.target.files)}
            className="hidden"
          />

          <div className="flex flex-col items-center gap-3 text-center">
            <div className="flex gap-3">
              <div className="w-10 h-10 rounded-lg bg-[var(--bg-tertiary)] flex items-center justify-center">
                <Film className="w-5 h-5 text-[var(--text-secondary)]" />
              </div>
              <div className="w-10 h-10 rounded-lg bg-[var(--bg-tertiary)] flex items-center justify-center">
                <ImageIcon className="w-5 h-5 text-[var(--text-secondary)]" />
              </div>
            </div>
            <div>
              <p className="text-sm text-[var(--text-primary)] font-medium">
                Drop media here or click to browse
              </p>
              <p className="text-xs text-[var(--text-muted)] mt-1">
                Supports MP4, WebM, PNG, JPG, WebP
              </p>
            </div>
          </div>
        </div>

        {/* Media Previews */}
        {mediaFiles.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs text-[var(--text-muted)] uppercase tracking-wider">
              Uploaded ({mediaFiles.length})
            </p>
            <div className="grid grid-cols-3 gap-2">
              {mediaFiles.map((mf) => (
                <div
                  key={mf.id}
                  className="relative group aspect-square rounded-lg overflow-hidden bg-[var(--bg-tertiary)] border border-[var(--border-color)]"
                >
                  {mf.type === 'video' ? (
                    <video
                      src={mf.preview}
                      className="w-full h-full object-cover"
                      muted
                      loop
                      playsInline
                      onMouseEnter={(e) => e.currentTarget.play()}
                      onMouseLeave={(e) => { e.currentTarget.pause(); e.currentTarget.currentTime = 0; }}
                    />
                  ) : (
                    <img
                      src={mf.preview}
                      alt="Preview"
                      className="w-full h-full object-cover"
                    />
                  )}
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      removeFile(mf.id);
                    }}
                    className="absolute top-1 right-1 w-5 h-5 rounded-full bg-red-500/80 text-white
                             flex items-center justify-center opacity-0 group-hover:opacity-100
                             transition-opacity hover:bg-red-500"
                  >
                    <X className="w-3 h-3" />
                  </button>
                  <div className="absolute bottom-1 left-1 px-1.5 py-0.5 rounded bg-black/60 text-[10px] text-white">
                    {mf.type === 'video' ? 'VIDEO' : 'IMG'}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Text Description */}
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <FileText className="w-4 h-4 text-[var(--text-secondary)]" />
            <label className="text-xs text-[var(--text-muted)] uppercase tracking-wider">
              Description
            </label>
          </div>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Describe the visual effect you want to create..."
            className="w-full h-24 bg-[var(--bg-tertiary)] text-[var(--text-primary)] text-sm
                     rounded-lg p-3 border border-[var(--border-color)]
                     focus:border-[var(--accent-primary)] focus:outline-none focus:ring-1 focus:ring-[var(--accent-primary)]/30
                     resize-none placeholder:text-[var(--text-muted)]/50
                     transition-all"
          />
        </div>

        {/* Submit Button */}
        <button
          onClick={handleSubmit}
          disabled={loading || !hasContent}
          className={`
            w-full py-3 px-4 rounded-lg font-medium text-sm
            flex items-center justify-center gap-2
            transition-all duration-200
            ${loading || !hasContent
              ? 'bg-[var(--bg-tertiary)] text-[var(--text-muted)] cursor-not-allowed'
              : 'btn-primary text-white hover:shadow-lg hover:shadow-[var(--accent-primary)]/20'
            }
          `}
        >
          {loading ? (
            <>
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              <span>Processing...</span>
            </>
          ) : (
            <>
              <Sparkles className="w-4 h-4" />
              <span>Generate Shader</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
}
