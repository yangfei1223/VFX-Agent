// components/FeedbackPanel.tsx
import { useState } from 'react';
import { MessageSquare, Play, X, User } from 'lucide-react';

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

  // 判断是否有活跃的 pipeline
  const hasActivePipeline = !!pipelineId;
  
  // 判断是否正在运行（Proceed 需要 pipeline 完成才能点击）
  const isRunning = status === 'running';
  
  // 没有 pipeline 或正在运行时，禁用所有操作
  const isDisabled = !hasActivePipeline || isRunning;

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
    <div className="panel bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg overflow-hidden flex flex-col">
      {/* Header */}
      <div className="px-4 py-3 border-b border-[var(--border-color)] flex items-center justify-between bg-[var(--bg-secondary)]">
        <div className="flex items-center gap-2">
          <User className="w-4 h-4 text-[var(--accent-primary)]" />
          <h2 className="text-sm font-semibold text-[var(--text-primary)] uppercase tracking-wider">
            User Inspect
          </h2>
        </div>
        <div className="flex items-center gap-2 px-2 py-1 rounded bg-[var(--bg-tertiary)]">
          <MessageSquare className="w-3 h-3 text-[var(--text-muted)]" />
          <span className="text-xs font-medium text-[var(--text-muted)]">
            {!hasActivePipeline ? 'No Active Pipeline' : isRunning ? 'Pipeline Running' : 'Ready for Feedback'}
          </span>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 p-4">
        {/* Input */}
        <textarea
          className="w-full bg-[var(--bg-tertiary)] border border-[var(--border-color)] rounded-lg p-3
                     text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)]
                     focus:outline-none focus:border-[var(--accent-primary)] resize-none"
          placeholder="描述您想要的修改，如：让颜色更鲜艳，光晕范围更大..."
          rows={3}
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          disabled={disabled || isSubmitting || isDisabled}
        />

        {/* Actions */}
        <div className="flex items-center gap-3 mt-3">
          <button
            className={`
              flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium
              transition-colors
              ${disabled || isSubmitting || !feedback.trim() || isDisabled
                ? 'bg-[var(--bg-tertiary)] text-[var(--text-muted)] cursor-not-allowed'
                : 'bg-gradient-to-r from-[var(--accent-primary)] to-[var(--accent-secondary)] text-white hover:shadow-lg'
              }
            `}
            onClick={handleProceed}
            disabled={disabled || isSubmitting || !feedback.trim() || isDisabled}
          >
            <Play className="w-3.5 h-3.5" />
            {isSubmitting ? 'Processing...' : 'Proceed'}
          </button>

          <button
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm
                       text-[var(--text-muted)] hover:text-[var(--text-primary)]
                       hover:bg-[var(--bg-tertiary)] transition-colors"
            onClick={handleEndSession}
            disabled={isSubmitting || !hasActivePipeline}
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
    </div>
  );
}