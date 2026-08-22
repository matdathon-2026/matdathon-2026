import type { Recommendation } from '../types';

const FIT_LABELS: Record<string, string> = {
  high: '🟢 잘 맞아요',
  medium: '🟡 확인이 필요해요',
  low: '⚪ 조건을 더 봐야 해요',
};
const FIT_CLASS: Record<string, string> = {
  high: 'fit-high',
  medium: 'fit-medium',
  low: 'fit-low',
};

interface Props {
  reco: Recommendation;
  onSelectPlan: (benefitId: string) => void;
}

export default function RecoCard({ reco, onSelectPlan }: Props) {
  return (
    <article className="reco-card">
      <div className="reco-card-header">
        <div>
          <div className="reco-card-title">{reco.title}</div>
          <div className="reco-card-provider">📍 {reco.provider} · {reco.category}</div>
        </div>
        <span className={`fit-badge ${FIT_CLASS[reco.fit] ?? 'fit-low'}`} aria-label={`적합도: ${FIT_LABELS[reco.fit]}`}>
          {FIT_LABELS[reco.fit] ?? reco.fit}
        </span>
      </div>

      {reco.reason.length > 0 && (
        <>
          <div className="reco-section-label">✅ 맞는 이유</div>
          <ul className="reco-list">
            {reco.reason.map((r, i) => <li key={i}>{r}</li>)}
          </ul>
        </>
      )}

      {reco.uncertainties.length > 0 && (
        <>
          <div className="reco-section-label">⚠️ 추가 확인 필요</div>
          <ul className="reco-list">
            {reco.uncertainties.map((u, i) => <li key={i}>{u}</li>)}
          </ul>
        </>
      )}

      <div className="reco-next-action">
        <strong>오늘 할 일 👉</strong> {reco.nextAction}
      </div>

      <div className="reco-meta">
        <a href={reco.sourceUrl} target="_blank" rel="noopener noreferrer">🔗 출처 보기</a>
        <span>🗓 마지막 확인일: {reco.verifiedAt}</span>
        {reco.deadline && <span className="deadline-badge">⏰ 마감: {reco.deadline}</span>}
      </div>

      <div className="reco-card-actions">
        <button className="btn-plan" onClick={() => onSelectPlan(reco.benefitId)}>
          📋 실행 계획 만들기
        </button>
      </div>
    </article>
  );
}
