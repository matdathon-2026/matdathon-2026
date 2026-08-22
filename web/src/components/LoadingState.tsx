interface Props {
  step: string;
  onCancel: () => void;
  onRetry: () => void;
  canRetry: boolean;
}

export default function LoadingState({ step, onCancel, onRetry, canRetry }: Props) {
  return (
    <div className="loading-state" role="status" aria-live="polite">
      <div className="loading-spinner" aria-hidden="true" />
      <div className="loading-step-text">{step}</div>
      <div className="loading-actions">
        <button className="btn-ghost" onClick={onCancel}>⛔ 취소</button>
        {canRetry && <button className="btn-secondary" onClick={onRetry}>🔄 다시 시도</button>}
      </div>
    </div>
  );
}
