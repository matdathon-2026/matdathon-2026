interface Props {
  message: string;
  onRetry: () => void;
}

export default function ErrorState({ message, onRetry }: Props) {
  return (
    <div className="error-state" role="alert">
      <div className="error-icon">⚠️</div>
      <div className="error-title">문제가 발생했어요</div>
      <div className="error-message">{message}</div>
      <button className="btn-secondary" onClick={onRetry}>🔄 다시 시도</button>
    </div>
  );
}
