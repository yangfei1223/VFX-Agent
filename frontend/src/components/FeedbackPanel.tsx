// components/FeedbackPanel.tsx
import { useState } from 'react';
import { MessageSquare, Play, X } from 'lucide-react';

interface FeedbackPanelProps {
  pipelineId: string | null;
  status: string;
  disabled: boolean;
  onHumanIterate: (feedback: string, modifiedShader: string | null) => Promise<void>;
  onEndSession: () => void;
  getModifiedShader: () => string | null;
}

export default function FeedbackPanel({
  pipelineId,
  status,
  disabled,
  onHumanIterate,
  onEndSession,
  getModifiedShader,
}: FeedbackPanelProps) {
  const [feedback, setFeedback] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // 不显示的条件：运行中、不存在、错误、无 pipelineId
  if (status === 'running' || status === 'not_found' || status === 'error' || !pipelineId) {
    return null;
  }

  const handleProceed = async () => {
    if (!feedback.trim()) return;

    setIsSubmitting(true);
    try {
      const modifiedShader = getModifiedShader();
      await onHumanIterate(feedback.trim(), modifiedShader);
      setFeedback('');
    } catch (e) {
      console.error('Human iterate failed:', e);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleEndSession = () => {
    setFeedback('');
    onEndSession();
  };

  return (
    <div className="panel bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg p-4 mt-4">
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <MessageSquare className="w-4 h-4 text-[var(--accent-primary)]" />
        <h3 className="text-sm font-semibold text-[var(--text-primary)]">
          人工迭代反馈
        </h3>
      </div>

      {/* Input */}
      <textarea
        className="w-full bg-[var(--bg-tertiary)] border border-[var(--border-color)] rounded-lg p-3
                   text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)]
                   focus:outline-none focus:border-[var(--accent-primary)] resize-none"
        placeholder="描述您想要的修改，如：让颜色更鲜艳，光晕范围更大..."
        rows={3}
        value={feedback}
        onChange={(e) => setFeedback(e.target.value)}
        disabled={disabled || isSubmitting}
      />

      {/* Actions */}
      <div className="flex items-center gap-3 mt-3">
        <button
          className={`
            flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium
            transition-colors
            ${disabled || isSubmitting || !feedback.trim()
              ? 'bg-[var(--bg-tertiary)] text-[var(--text-muted)] cursor-not-allowed'
              : 'bg-gradient-to-r from-[var(--accent-primary)] to-[var(--accent-secondary)] text-white hover:shadow-lg'
            }
          `}
          onClick={handleProceed}
          disabled={disabled || isSubmitting || !feedback.trim()}
        >
          <Play className="w-3.5 h-3.5" />
          {isSubmitting ? '处理中...' : 'Proceed'}
        </button>

        <button
          className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm
                     text-[var(--text-muted)] hover:text-[var(--text-primary)]
                     hover:bg-[var(--bg-tertiary)] transition-colors"
          onClick={handleEndSession}
          disabled={disabled || isSubmitting}
        >
          <X className="w-3.5 h-3.5" />
          End Session
        </button>
      </div>

      {/* Hint */}
      <p className="text-xs text-[var(--text-muted)] mt-3">
        您也可以直接在代码编辑器中修改代码，或在参数面板调整参数，然后点击 Proceed
      </p>
    </div>
  );
}