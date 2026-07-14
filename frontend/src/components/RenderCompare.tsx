import { useState, useEffect } from "react";
import { Image as ImageIcon, ChevronLeft, ChevronRight } from "lucide-react";

interface RenderCompareProps {
  referencePath: string | null;
  screenshotPaths: string[];
  currentIndex: number;
  onIndexChange: (i: number) => void;
}

function SafeImage({
  src,
  alt,
  className,
}: {
  src: string;
  alt: string;
  className?: string;
}) {
  const [error, setError] = useState(false);
  if (error) {
    return (
      <div className={`bg-[var(--bg-tertiary)] flex flex-col items-center justify-center ${className}`}>
        <ImageIcon className="w-8 h-8 text-[var(--text-muted)]/30 mb-2" />
        <span className="text-xs text-[var(--text-muted)]">Failed to load</span>
      </div>
    );
  }
  return (
    <img
      src={src}
      alt={alt}
      className={className}
      onError={() => setError(true)}
    />
  );
}

export default function RenderCompare({
  referencePath,
  screenshotPaths,
  currentIndex,
  onIndexChange,
}: RenderCompareProps) {
  const hasScreenshots = screenshotPaths.length > 0;
  const safeIndex = Math.min(Math.max(0, currentIndex), Math.max(0, screenshotPaths.length - 1));

  useEffect(() => {
    onIndexChange(safeIndex);
  }, [safeIndex, onIndexChange]);

  const currentRenderPath = hasScreenshots ? screenshotPaths[safeIndex] : null;

  return (
    <div className="panel bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg overflow-hidden flex flex-col h-full min-h-0">
      <div className="px-4 py-2 border-b border-[var(--border-color)] flex items-center justify-between flex-shrink-0">
        <h2 className="text-xs font-semibold text-[var(--text-primary)] uppercase tracking-wider">
          Render Compare
        </h2>
        {hasScreenshots && (
          <div className="flex items-center gap-1">
            <button
              onClick={() => onIndexChange(Math.max(0, safeIndex - 1))}
              disabled={safeIndex === 0}
              className="p-1 rounded hover:bg-[var(--bg-tertiary)] text-[var(--text-muted)] disabled:opacity-30"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="text-xs text-[var(--text-muted)] min-w-[3rem] text-center">
              {safeIndex + 1}/{screenshotPaths.length}
            </span>
            <button
              onClick={() => onIndexChange(Math.min(screenshotPaths.length - 1, safeIndex + 1))}
              disabled={safeIndex >= screenshotPaths.length - 1}
              className="p-1 rounded hover:bg-[var(--bg-tertiary)] text-[var(--text-muted)] disabled:opacity-30"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>

      <div className="flex-1 min-h-0 p-3 flex gap-3 overflow-hidden">
        {/* Reference */}
        <div className="flex-1 min-w-0 flex flex-col">
          <span className="text-[10px] text-[var(--text-muted)] uppercase tracking-wide mb-1.5">
            Reference
          </span>
          <div className="flex-1 min-h-0 bg-black/40 rounded-lg border border-[var(--border-color)] overflow-hidden flex items-center justify-center">
            {referencePath ? (
              <SafeImage
                key={referencePath}
                src={`/file?path=${encodeURIComponent(referencePath)}`}
                alt="Reference"
                className="max-w-full max-h-full object-contain"
              />
            ) : (
              <div className="text-center p-4">
                <ImageIcon className="w-8 h-8 text-[var(--text-muted)]/30 mx-auto mb-2" />
                <span className="text-xs text-[var(--text-muted)]">等待渲染...</span>
              </div>
            )}
          </div>
        </div>

        {/* Render */}
        <div className="flex-1 min-w-0 flex flex-col">
          <span className="text-[10px] text-[var(--text-muted)] uppercase tracking-wide mb-1.5">
            {currentRenderPath ? `Render #${safeIndex + 1}` : "Render"}
          </span>
          <div className="flex-1 min-h-0 bg-black/40 rounded-lg border border-[var(--border-color)] overflow-hidden flex items-center justify-center">
            {currentRenderPath ? (
              <SafeImage
                key={currentRenderPath}
                src={`/file?path=${encodeURIComponent(currentRenderPath)}`}
                alt={`Render ${safeIndex + 1}`}
                className="max-w-full max-h-full object-contain"
              />
            ) : (
              <div className="text-center p-4">
                <ImageIcon className="w-8 h-8 text-[var(--text-muted)]/30 mx-auto mb-2" />
                <span className="text-xs text-[var(--text-muted)]">等待渲染...</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Thumbnail bar */}
      {screenshotPaths.length > 1 && (
        <div className="px-3 pb-3 flex gap-2 overflow-x-auto flex-shrink-0">
          {screenshotPaths.map((path, index) => (
            <button
              key={`${path}-${index}`}
              onClick={() => onIndexChange(index)}
              className={`
                flex-shrink-0 w-16 h-10 rounded-md border overflow-hidden transition-colors
                ${index === safeIndex
                  ? "border-[var(--accent-primary)] ring-1 ring-[var(--accent-primary)]"
                  : "border-[var(--border-color)] opacity-60 hover:opacity-100"
                }
              `}
            >
              <img
                src={`/file?path=${encodeURIComponent(path)}`}
                alt={`Thumbnail ${index + 1}`}
                className="w-full h-full object-cover"
                onError={(e) => {
                  e.currentTarget.style.display = "none";
                }}
              />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
