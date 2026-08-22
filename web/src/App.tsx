import React from 'react';
import type { Profile, RecommendationsResponse, Plan, HeartsResponse, ImpactResponse } from './types';
import { fetchRecommendations, fetchPlan, completeStep, fetchHearts, fetchImpact, ApiCallError } from './api';
import ProfileForm from './components/ProfileForm';
import RecoCard from './components/RecoCard';
import LoadingState from './components/LoadingState';
import ErrorState from './components/ErrorState';

type Screen = 'profile' | 'recommendations' | 'plan' | 'hearts';

const STEPS: { id: Screen; label: string }[] = [
  { id: 'profile', label: '프로필' },
  { id: 'recommendations', label: '추천' },
  { id: 'plan', label: '실행 계획' },
  { id: 'hearts', label: '하트' },
];

function stepIndex(s: Screen) { return STEPS.findIndex(x => x.id === s); }

export default function App() {
  const [screen, setScreen] = React.useState<Screen>('profile');
  const [sessionId, setSessionId] = React.useState<string | null>(null);
  const [profile, setProfile] = React.useState<Profile | null>(null);

  // recommendations
  const [recoResult, setRecoResult] = React.useState<RecommendationsResponse | null>(null);
  const [recoLoading, setRecoLoading] = React.useState(false);
  const [recoError, setRecoError] = React.useState<string | null>(null);
  const recoAbortRef = React.useRef<AbortController | null>(null);

  // plan
  const [plan, setPlan] = React.useState<Plan | null>(null);
  const [planLoading, setPlanLoading] = React.useState(false);
  const [planError, setPlanError] = React.useState<string | null>(null);
  const planAbortRef = React.useRef<AbortController | null>(null);
  const [completingStep, setCompletingStep] = React.useState<string | null>(null);
  const [stepMessages, setStepMessages] = React.useState<Record<string, string>>({});

  // hearts
  const [hearts, setHearts] = React.useState<HeartsResponse | null>(null);
  const [impact, setImpact] = React.useState<ImpactResponse | null>(null);
  const [heartsLoading, setHeartsLoading] = React.useState(false);

  function errorMessage(err: unknown): string {
    if (err instanceof ApiCallError) return err.message;
    if (err instanceof DOMException && err.name === 'AbortError') return '요청이 취소됐어요.';
    if (err instanceof Error) return err.message;
    return '알 수 없는 오류가 발생했어요.';
  }

  // ─── Recommendations ────────────────────────
  async function loadRecommendations(prof: Profile) {
    if (recoAbortRef.current) recoAbortRef.current.abort();
    const ac = new AbortController();
    recoAbortRef.current = ac;
    const timer = setTimeout(() => ac.abort(), 60_000);

    setRecoLoading(true);
    setRecoError(null);
    setRecoResult(null);
    setScreen('recommendations');

    try {
      const result = await fetchRecommendations(sessionId, prof, ac.signal);
      clearTimeout(timer);
      setSessionId(result.sessionId);
      const valid = result.recommendations.filter(r => r.sourceUrl && r.verifiedAt);
      setRecoResult({ ...result, recommendations: valid });
    } catch (err) {
      clearTimeout(timer);
      if (!(err instanceof DOMException && err.name === 'AbortError')) {
        setRecoError(errorMessage(err));
      }
    } finally {
      setRecoLoading(false);
    }
  }

  function handleProfileSubmit(prof: Profile) {
    setProfile(prof);
    loadRecommendations(prof);
  }

  function cancelReco() {
    recoAbortRef.current?.abort();
    setRecoLoading(false);
    setScreen('profile');
  }

  function retryReco() {
    if (profile) loadRecommendations(profile);
  }

  // ─── Plan ────────────────────────────────────
  async function loadPlan(benefitId: string) {
    if (!sessionId) return;
    if (planAbortRef.current) planAbortRef.current.abort();
    const ac = new AbortController();
    planAbortRef.current = ac;
    const timer = setTimeout(() => ac.abort(), 60_000);

    setPlanLoading(true);
    setPlanError(null);
    setPlan(null);
    setScreen('plan');

    try {
      const result = await fetchPlan(sessionId, benefitId, ac.signal);
      clearTimeout(timer);
      setPlan(result);
    } catch (err) {
      clearTimeout(timer);
      if (!(err instanceof DOMException && err.name === 'AbortError')) {
        setPlanError(errorMessage(err));
      }
    } finally {
      setPlanLoading(false);
    }
  }

  function cancelPlan() {
    planAbortRef.current?.abort();
    setPlanLoading(false);
    setScreen('recommendations');
  }

  function retryPlan() {
    if (plan) loadPlan(plan.benefitId);
    else if (recoResult?.recommendations[0]) loadPlan(recoResult.recommendations[0].benefitId);
  }

  // ─── Complete step ───────────────────────────
  async function handleCompleteStep(stepId: string) {
    if (!plan || !sessionId) return;
    setCompletingStep(stepId);
    try {
      const res = await completeStep(plan.planId, stepId, sessionId);
      if (res.alreadyCompleted) {
        setStepMessages(prev => ({ ...prev, [stepId]: '이미 완료한 단계예요' }));
      } else {
        setStepMessages(prev => ({ ...prev, [stepId]: `🩷 +${res.awarded} 하트 적립!` }));
      }
      setPlan(prev => prev ? {
        ...prev,
        steps: prev.steps.map(s => s.stepId === stepId ? { ...s, completed: true } : s),
      } : prev);
    } catch (err) {
      setStepMessages(prev => ({ ...prev, [stepId]: `❌ ${errorMessage(err)}` }));
    } finally {
      setCompletingStep(null);
    }
  }

  // ─── Hearts & Impact ─────────────────────────
  async function loadHeartsScreen() {
    if (!sessionId) return;
    setHeartsLoading(true);
    setScreen('hearts');
    try {
      const [h, i] = await Promise.all([fetchHearts(sessionId), fetchImpact(sessionId)]);
      setHearts(h);
      setImpact(i);
    } catch {
      // show whatever we have
    } finally {
      setHeartsLoading(false);
    }
  }

  function handleRestart() {
    setScreen('profile');
    setSessionId(null);
    setProfile(null);
    setRecoResult(null);
    setRecoError(null);
    setPlan(null);
    setPlanError(null);
    setHearts(null);
    setImpact(null);
    setStepMessages({});
  }

  const currentIdx = stepIndex(screen);

  return (
    <div className="app-wrapper">
      {/* Top navigation */}
      <nav className="top-nav" aria-label="단계 탐색">
        <span className="top-nav-brand">🩷 디딤하트</span>
        <ol className="step-indicator" role="list">
          {STEPS.map((s, i) => {
            const state = i < currentIdx ? 'done' : i === currentIdx ? 'active' : '';
            return (
              <li key={s.id} className={`step-dot ${state}`} aria-current={i === currentIdx ? 'step' : undefined}>
                <span className="step-dot-circle" aria-hidden="true">
                  {i < currentIdx ? '✓' : i + 1}
                </span>
                <span>{s.label}</span>
              </li>
            );
          })}
        </ol>
      </nav>

      <main className="main-content">
        {/* Disclaimer — always visible */}
        <div className="disclaimer-banner" role="note">
          ℹ️ AI 추천 결과는 <strong>신청 가능성</strong>을 안내하는 것으로, 공식 수급 자격 판정이 아닙니다. 정확한 자격은 담당 기관에 문의해 주세요.
        </div>

        {/* ── Screen: Profile ── */}
        {screen === 'profile' && (
          <section aria-labelledby="hero-title">
            <div className="hero">
              <div className="hero-icon" aria-hidden="true">🩷</div>
              <h1 id="hero-title">디딤하트</h1>
              <p>자립준비청년을 위한 AI 자립 실행 코파일럿 — 나에게 맞는 지원사업을 찾고 실행 가능한 체크리스트로 바꿔드려요.</p>
            </div>
            <ProfileForm onSubmit={handleProfileSubmit} />
          </section>
        )}

        {/* ── Screen: Recommendations ── */}
        {screen === 'recommendations' && (
          <section aria-labelledby="reco-title">
            <h2 id="reco-title" className="section-title">맞춤 지원사업 추천</h2>

            {recoLoading && (
              <LoadingState
                step="🤖 AI가 지원사업을 분석하고 있어요…"
                onCancel={cancelReco}
                onRetry={retryReco}
                canRetry={false}
              />
            )}

            {recoError && !recoLoading && (
              <>
                <ErrorState message={recoError} onRetry={retryReco} />
                <button className="btn-ghost" style={{ marginTop: 12 }} onClick={() => setScreen('profile')}>← 프로필로 돌아가기</button>
              </>
            )}

            {recoResult && !recoLoading && (
              <>
                {recoResult.degraded && (
                  <div className="degraded-banner" role="status">
                    ⚠️ AI 서비스에 일시적으로 접근하지 못해 규칙 기반 결과를 보여드리고 있어요. 결과가 다를 수 있습니다.
                  </div>
                )}
                <p className="reco-summary">{recoResult.summary}</p>
                {recoResult.recommendations.length === 0 ? (
                  <div className="error-state">
                    <div className="error-icon">🔍</div>
                    <div className="error-title">조건에 맞는 지원사업을 찾지 못했어요</div>
                    <div className="error-message">프로필을 조정하거나 나중에 다시 시도해 주세요.</div>
                    <button className="btn-secondary" onClick={() => setScreen('profile')}>← 프로필 수정</button>
                  </div>
                ) : (
                  <div className="cards-list">
                    {recoResult.recommendations.map(r => (
                      <RecoCard key={r.benefitId} reco={r} onSelectPlan={loadPlan} />
                    ))}
                  </div>
                )}
                <div style={{ marginTop: 24, display: 'flex', gap: 10 }}>
                  <button className="btn-ghost" onClick={() => setScreen('profile')}>← 프로필 수정</button>
                  <button className="btn-ghost" onClick={loadHeartsScreen}>🩷 하트 보기</button>
                </div>
              </>
            )}
          </section>
        )}

        {/* ── Screen: Plan ── */}
        {screen === 'plan' && (
          <section aria-labelledby="plan-title">
            <h2 id="plan-title" className="section-title">📋 실행 계획</h2>

            {planLoading && (
              <LoadingState
                step="📋 실행 계획을 만들고 있어요…"
                onCancel={cancelPlan}
                onRetry={retryPlan}
                canRetry={false}
              />
            )}

            {planError && !planLoading && (
              <>
                <ErrorState message={planError} onRetry={retryPlan} />
                <button className="btn-ghost" style={{ marginTop: 12 }} onClick={() => setScreen('recommendations')}>← 추천으로 돌아가기</button>
              </>
            )}

            {plan && !planLoading && (
              <>
                <div className="plan-header">
                  <div className="plan-title">{plan.title}</div>
                  <div className="plan-meta">
                    <a href={plan.sourceUrl} target="_blank" rel="noopener noreferrer">🔗 출처</a>
                    <span>🗓 마지막 확인일: {plan.verifiedAt}</span>
                    {plan.deadline && <span className="deadline-badge">⏰ 마감: {plan.deadline}</span>}
                  </div>
                </div>

                {plan.requiredDocuments.length > 0 && (
                  <div className="plan-docs">
                    <div className="plan-docs-title">📄 필요 서류</div>
                    <ul className="plan-docs-list">
                      {plan.requiredDocuments.map((doc, i) => <li key={i}>{doc}</li>)}
                    </ul>
                  </div>
                )}

                <div className="steps-list">
                  {[...plan.steps].sort((a, b) => a.order - b.order).map(step => (
                    <div key={step.stepId} className={`step-card${step.completed ? ' completed' : ''}`}>
                      <div className="step-number" aria-hidden="true">{step.completed ? '✓' : step.order}</div>
                      <div className="step-body">
                        <div className="step-title">{step.title}</div>
                        <div className="step-detail">{step.detail}</div>
                        <div className="step-footer">
                          <span className="step-hearts">🩷 {step.hearts} 하트</span>
                          {step.completed ? (
                            <span className="already-done">✅ 완료</span>
                          ) : (
                            <button
                              className="btn-complete"
                              disabled={completingStep === step.stepId}
                              onClick={() => handleCompleteStep(step.stepId)}
                              aria-label={`${step.title} 완료로 표시`}
                            >
                              {completingStep === step.stepId ? '처리 중…' : '완료하기'}
                            </button>
                          )}
                        </div>
                        {stepMessages[step.stepId] && (
                          <div className={stepMessages[step.stepId].startsWith('이미') ? 'already-done' : 'hearts-earned-notice'} style={{ marginTop: 6 }}>
                            {stepMessages[step.stepId]}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>

                <div style={{ marginTop: 24, display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                  <button className="btn-ghost" onClick={() => setScreen('recommendations')}>← 추천으로 돌아가기</button>
                  <button className="btn-ghost" onClick={loadHeartsScreen}>🩷 하트 확인하기</button>
                </div>
              </>
            )}
          </section>
        )}

        {/* ── Screen: Hearts ── */}
        {screen === 'hearts' && (
          <section aria-labelledby="hearts-title">
            <h2 id="hearts-title" className="section-title">🩷 내 하트 & 임팩트</h2>

            <div className="demo-notice" role="note">
              💡 하트는 <strong>데모 포인트</strong>이며 현금·전자화폐가 아닙니다. 실제 지급·환전은 불가합니다.
            </div>

            {heartsLoading && (
              <LoadingState
                step="하트 정보를 불러오고 있어요…"
                onCancel={() => setHeartsLoading(false)}
                onRetry={loadHeartsScreen}
                canRetry={false}
              />
            )}

            {hearts && (
              <>
                <div className="hearts-balance-card" aria-label={`현재 하트 잔액 ${hearts.balance}개`}>
                  <div className="hearts-balance-number">{hearts.balance}</div>
                  <div className="hearts-balance-label">🩷 하트 잔액</div>
                </div>

                <div className="ledger-section">
                  <div className="ledger-title">📒 하트 적립 내역</div>
                  {hearts.entries.length === 0 ? (
                    <p style={{ color: 'var(--color-text-muted)', fontSize: '0.88rem' }}>아직 적립된 하트가 없어요. 실행 계획의 단계를 완료해 보세요!</p>
                  ) : (
                    <table className="ledger-table">
                      <thead>
                        <tr>
                          <th scope="col">일시</th>
                          <th scope="col">이유</th>
                          <th scope="col">하트</th>
                        </tr>
                      </thead>
                      <tbody>
                        {hearts.entries.map(e => (
                          <tr key={e.entryId}>
                            <td>{new Date(e.createdAt).toLocaleDateString('ko-KR')}</td>
                            <td>{e.reason}</td>
                            <td className="ledger-hearts">+{e.hearts}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              </>
            )}

            {impact && (
              <>
                <div className="impact-grid">
                  <div className="impact-card">
                    <div className="impact-value">{impact.completedActions.toLocaleString()}</div>
                    <div className="impact-label">✅ 완료한 행동</div>
                  </div>
                  <div className="impact-card">
                    <div className="impact-value">{impact.heartsDistributed.toLocaleString()}</div>
                    <div className="impact-label">🩷 배분된 하트</div>
                  </div>
                  <div className="impact-card">
                    <div className="impact-value">{impact.heartsPledged.toLocaleString()}</div>
                    <div className="impact-label">💌 약정 하트</div>
                  </div>
                  <div className="impact-card">
                    <div className="impact-value">₩{(impact.totalDonationKrw / 10000).toFixed(0)}만</div>
                    <div className="impact-label">💰 데모 후원금 총액</div>
                  </div>
                </div>

                {impact.sponsors.length > 0 && (
                  <div className="sponsors-section">
                    <div className="ledger-title">🏛 후원 기관</div>
                    <ul className="sponsors-list">
                      {impact.sponsors.map((s, i) => (
                        <li key={i} className="sponsor-item">
                          <span>{s.name}</span>
                          <span>₩{s.amountKrw.toLocaleString()}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            )}

            <div style={{ marginTop: 24, display: 'flex', flexDirection: 'column', gap: 10 }}>
              {plan && <button className="btn-ghost" onClick={() => setScreen('plan')}>← 실행 계획으로</button>}
              {recoResult && <button className="btn-ghost" onClick={() => setScreen('recommendations')}>← 추천으로</button>}
              <button className="btn-restart" onClick={handleRestart}>🔄 처음부터 다시 시작</button>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
