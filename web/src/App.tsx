import { useEffect, useState } from "react";
import { api, ApiError } from "./api";
import {
  AGE_BANDS,
  CATEGORIES,
  CATEGORY_LABEL,
  FIT_LABEL,
  REGIONS,
  STAGES,
  WORK_STUDY,
} from "./labels";
import type {
  BenefitCard,
  Category,
  Impact,
  Ledger,
  Plan,
  PlanDraft,
  ProfileInput,
  RecommendationResponse,
} from "./types";

type Screen = "landing" | "onboarding" | "recs" | "plan" | "board" | "impact" | "sponsor";

function ErrorBanner({ err, onRetry }: { err: ApiError; onRetry?: () => void }) {
  return (
    <div className="alert alert-error" role="alert">
      <span aria-hidden>⚠️</span>
      <div style={{ flex: 1 }}>
        <strong>{err.code}</strong>
        <div>{err.message}</div>
        {onRetry && (
          <button className="btn btn-ghost btn-sm mt" onClick={onRetry}>
            다시 시도
          </button>
        )}
      </div>
    </div>
  );
}

function Loading({ label }: { label: string }) {
  return (
    <div className="loading" role="status" aria-live="polite">
      <div className="spinner" aria-hidden />
      <div>
        <strong>{label}</strong>
        <p className="muted">AI가 카탈로그를 조회하고 있어요. 최대 30초 정도 걸릴 수 있어요.</p>
      </div>
    </div>
  );
}

/* ---------------- Landing ---------------- */
function Landing({ onStart, onSponsor }: { onStart: () => void; onSponsor: () => void }) {
  return (
    <div className="content">
      <div className="card">
        <h1>내게 맞는 자립 지원을 3분 만에</h1>
        <p className="lead">
          디딤하트는 자립준비청년을 위한 지원제도를 프로필에 맞춰 찾아주고, 오늘 할 수 있는
          실행 계획으로 바꿔 드려요. 로그인 없이 바로 시작할 수 있어요.
        </p>
        <button className="btn btn-primary" onClick={onStart}>
          시작하기
        </button>
        <button className="btn btn-ghost mt" onClick={onSponsor}>
          🤝 후원자이신가요? 후원 임팩트 보기
        </button>
      </div>
      <div className="card">
        <h3>이렇게 도와드려요</h3>
        <ul className="reasons">
          <li>프로필 기반 맞춤 추천 3건 (출처·확인일 포함)</li>
          <li>선택한 혜택을 단계별 체크리스트로</li>
          <li>단계를 완료하면 디딤하트 적립</li>
        </ul>
        <p className="muted">
          ※ 추천은 참고용이며 공식 수급 자격을 보장하지 않아요. 신청 전 공식 페이지에서 꼭
          확인하세요.
        </p>
      </div>
    </div>
  );
}

/* ---------------- Onboarding ---------------- */
const EMPTY: ProfileInput = {
  ageBand: "18_24",
  region: "seoul",
  selfRelianceStage: "within_1_year",
  interests: [],
  workStudyStatus: "job_seeking",
  urgentNeed: "housing",
};

function Onboarding({
  busy,
  err,
  onSubmit,
}: {
  busy: boolean;
  err: ApiError | null;
  onSubmit: (p: ProfileInput) => void;
}) {
  const [p, setP] = useState<ProfileInput>(EMPTY);

  const toggleInterest = (c: Category) => {
    setP((prev) => {
      const has = prev.interests.includes(c);
      let next = has
        ? prev.interests.filter((x) => x !== c)
        : [...prev.interests, c];
      if (next.length > 3) next = next.slice(0, 3);
      return { ...prev, interests: next };
    });
  };

  const valid = p.interests.length >= 1;

  return (
    <div className="content">
      <div className="card">
        <div className="stepper">1 / 2 · 기본 정보</div>
        <h2>나에 대해 알려주세요</h2>
        <p className="muted">6개 항목만 입력하면 맞춤 추천을 받을 수 있어요.</p>

        <div className="field">
          <label className="field-label" htmlFor="age">
            나이대
          </label>
          <select
            id="age"
            value={p.ageBand}
            onChange={(e) => setP({ ...p, ageBand: e.target.value as ProfileInput["ageBand"] })}
          >
            {AGE_BANDS.map((a) => (
              <option key={a.value} value={a.value}>
                {a.label}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label className="field-label" htmlFor="region">
            거주 지역
          </label>
          <select
            id="region"
            value={p.region}
            onChange={(e) => setP({ ...p, region: e.target.value })}
          >
            {REGIONS.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label className="field-label" htmlFor="stage">
            자립 단계
          </label>
          <select
            id="stage"
            value={p.selfRelianceStage}
            onChange={(e) =>
              setP({ ...p, selfRelianceStage: e.target.value as ProfileInput["selfRelianceStage"] })
            }
          >
            {STAGES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label className="field-label" htmlFor="work">
            현재 상태
          </label>
          <select
            id="work"
            value={p.workStudyStatus}
            onChange={(e) =>
              setP({ ...p, workStudyStatus: e.target.value as ProfileInput["workStudyStatus"] })
            }
          >
            {WORK_STUDY.map((w) => (
              <option key={w.value} value={w.value}>
                {w.label}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <span className="field-label" id="interests-label">
            관심 분야 (1~3개 선택)
          </span>
          <div className="chips" role="group" aria-labelledby="interests-label">
            {CATEGORIES.map((c) => (
              <button
                type="button"
                key={c.value}
                className="chip"
                aria-pressed={p.interests.includes(c.value)}
                onClick={() => toggleInterest(c.value)}
              >
                <span aria-hidden>{c.icon}</span> {c.label}
              </button>
            ))}
          </div>
          <div className="hint">
            {p.interests.length === 0
              ? "최소 한 개를 선택해 주세요."
              : `${p.interests.length}개 선택됨`}
          </div>
        </div>

        <div className="field">
          <label className="field-label" htmlFor="urgent">
            가장 급한 문제
          </label>
          <select
            id="urgent"
            value={p.urgentNeed}
            onChange={(e) => setP({ ...p, urgentNeed: e.target.value as Category })}
          >
            {CATEGORIES.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
        </div>

        {err && <ErrorBanner err={err} />}

        <button
          className="btn btn-primary mt"
          disabled={!valid || busy}
          onClick={() => onSubmit(p)}
        >
          {busy ? "추천을 준비하고 있어요…" : "맞춤 추천 받기"}
        </button>
        {!valid && <div className="hint">관심 분야를 하나 이상 선택하면 버튼이 활성화돼요.</div>}
      </div>
    </div>
  );
}

/* ---------------- Recommendation card ---------------- */
function RecCard({
  card,
  onChoose,
  busy,
}: {
  card: BenefitCard;
  onChoose: () => void;
  busy: boolean;
}) {
  // Guard: never render a card without source + verified date.
  if (!card.sourceUrl || !card.verifiedAt) return null;
  const fit = FIT_LABEL[card.fit] ?? FIT_LABEL.medium;
  return (
    <div className="card benefit">
      <div className="benefit-head">
        <h3 style={{ margin: 0 }}>{card.title}</h3>
        <span className={`badge ${fit.cls}`}>{fit.text}</span>
      </div>
      <div className="muted">
        {card.provider} · {CATEGORY_LABEL[card.category] ?? card.category}
      </div>
      {card.reasons.length > 0 && (
        <ul className="reasons">
          {card.reasons.map((r, i) => (
            <li key={i}>{r}</li>
          ))}
        </ul>
      )}
      {card.uncertainties.length > 0 && (
        <div className="alert alert-warn" style={{ fontSize: 13 }}>
          <span aria-hidden>❓</span>
          <div>
            추가 확인이 필요해요:
            <ul className="reasons" style={{ marginTop: 4 }}>
              {card.uncertainties.map((u, i) => (
                <li key={i}>{u}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
      <div className="next-action">
        <strong>오늘 할 일 </strong>
        {card.nextAction}
      </div>
      <div className="source">
        <a href={card.sourceUrl} target="_blank" rel="noreferrer noopener">
          🔗 공식 출처 ({card.sourceAgency})
        </a>
        <span>마지막 확인일: {card.verifiedAt}</span>
        {card.deadline && <span>마감: {card.deadline}</span>}
      </div>
      <button className="btn btn-primary" onClick={onChoose} disabled={busy}>
        {busy ? "계획을 만드는 중…" : "이 혜택으로 실행 계획 만들기"}
      </button>
    </div>
  );
}

/* ---------------- Recommendations screen ---------------- */
function Recs({
  data,
  loading,
  err,
  onRetry,
  onChoose,
  choosing,
}: {
  data: RecommendationResponse | null;
  loading: boolean;
  err: ApiError | null;
  onRetry: () => void;
  onChoose: (benefitId: string) => void;
  choosing: string | null;
}) {
  if (loading) return <div className="content"><Loading label="맞춤 추천을 찾고 있어요" /></div>;
  return (
    <div className="content">
      {err && <ErrorBanner err={err} onRetry={onRetry} />}
      {data && (
        <>
          <div className="card">
            <h2>맞춤 추천 {data.recommendations.length}건</h2>
            <p className="lead" style={{ margin: 0 }}>
              {data.summary}
            </p>
          </div>
          {data.recommendations.map((c) => (
            <RecCard
              key={c.benefitId}
              card={c}
              busy={choosing === c.benefitId}
              onChoose={() => onChoose(c.benefitId)}
            />
          ))}
          <p className="muted center">
            AI 추천은 참고용이에요. 신청 전 공식 페이지에서 자격을 확인하세요.
          </p>
        </>
      )}
    </div>
  );
}

/* ---------------- Plan screen ---------------- */
function PlanScreen({
  plan,
  draftLoading,
  err,
  onRetry,
  onSave,
  onToggle,
  saving,
  togglingStep,
}: {
  plan: PlanDraft | Plan | null;
  draftLoading: boolean;
  err: ApiError | null;
  onRetry: () => void;
  onSave: () => void;
  onToggle: (stepId: string, done: boolean) => void;
  saving: boolean;
  togglingStep: string | null;
}) {
  if (draftLoading)
    return <div className="content"><Loading label="실행 계획을 만드는 중이에요" /></div>;
  if (err)
    return (
      <div className="content">
        <ErrorBanner err={err} onRetry={onRetry} />
      </div>
    );
  if (!plan) return <div className="content" />;

  const saved = "id" in plan;
  const doneCount = plan.steps.filter((s) => s.status === "done").length;
  const pct = Math.round((doneCount / Math.max(plan.steps.length, 1)) * 100);

  return (
    <div className="content">
      <div className="card">
        <h2>{plan.title}</h2>
        {plan.deadline && <div className="muted">마감: {plan.deadline}</div>}
        <div className="progress mt" aria-hidden>
          <span style={{ width: `${pct}%` }} />
        </div>
        <div className="muted mt">
          {doneCount} / {plan.steps.length} 단계 완료
        </div>
      </div>

      {plan.requiredDocuments.length > 0 && (
        <div className="card">
          <h3>준비할 서류</h3>
          <ul className="doc-list">
            {plan.requiredDocuments.map((d, i) => (
              <li key={i}>{d}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="card">
        <h3>실행 단계</h3>
        {!saved && (
          <div className="alert alert-info" role="note" style={{ fontSize: 13 }}>
            <span aria-hidden>💾</span>
            <div>
              아래 <strong>‘이 계획 저장하고 시작하기’</strong>를 누르면 단계 완료 버튼이
              켜지고, 완료할 때마다 하트가 적립돼요.
            </div>
          </div>
        )}
        {plan.steps.map((s, i) => {
          const done = s.status === "done";
          const awards = i < 3;
          return (
            <div className={`step ${done ? "done" : ""}`} key={s.id}>
              <button
                className="step-check"
                aria-label={done ? "완료 취소" : "완료 표시"}
                aria-pressed={done}
                disabled={!saved || togglingStep === s.id}
                title={!saved ? "먼저 계획을 저장해 주세요" : undefined}
                onClick={() => onToggle(s.id, !done)}
              >
                {done ? "✓" : ""}
              </button>
              <div className="step-body">
                <div className="step-title">{s.title}</div>
                <div className="step-meta">약 {s.estimatedMinutes}분 소요</div>
                {s.description && <div className="muted">{s.description}</div>}
                {awards && <div className="step-award">완료 시 +10 하트</div>}
              </div>
            </div>
          );
        })}
      </div>

      {"uncertainties" in plan && plan.uncertainties.length > 0 && (
        <div className="card">
          <div className="alert alert-warn">
            <span aria-hidden>❓</span>
            <div>
              <strong>확인이 필요한 부분</strong>
              <ul className="reasons mt">
                {plan.uncertainties.map((u, i) => (
                  <li key={i}>{u}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {!saved && (
        <button className="btn btn-primary" onClick={onSave} disabled={saving}>
          {saving ? "저장 중…" : "이 계획 저장하고 시작하기"}
        </button>
      )}
      {saved && (
        <div className="alert alert-info">
          <span aria-hidden>✅</span>
          <div>계획이 저장됐어요. 단계를 완료하면 하트가 적립돼요.</div>
        </div>
      )}

      {(plan.applyUrl || plan.sourceUrl) && (
        <a
          className="btn btn-ghost"
          href={plan.applyUrl || plan.sourceUrl}
          target="_blank"
          rel="noreferrer noopener"
        >
          🔗 공식 신청 페이지 열기
        </a>
      )}
    </div>
  );
}

/* ---------------- Board (내 디딤판) ---------------- */
function Board({
  plans,
  ledger,
  loading,
  onOpenPlan,
}: {
  plans: Plan[];
  ledger: Ledger | null;
  loading: boolean;
  onOpenPlan: (p: Plan) => void;
}) {
  if (loading) return <div className="content"><Loading label="내 디딤판을 불러오는 중" /></div>;
  return (
    <div className="content">
      <div className="card center">
        <div className="muted">지금까지 모은 디딤하트</div>
        <div style={{ fontSize: 40, fontWeight: 800, color: "var(--heart)" }}>
          ❤️ {ledger?.balance ?? 0}
        </div>
      </div>

      <div className="card">
        <h3>내 실행 계획</h3>
        {plans.length === 0 && <p className="muted">아직 저장한 계획이 없어요.</p>}
        {plans.map((p) => {
          const done = p.steps.filter((s) => s.status === "done").length;
          return (
            <button
              key={p.id}
              className="ledger-row"
              style={{ width: "100%", background: "none", border: "none", textAlign: "left" }}
              onClick={() => onOpenPlan(p)}
            >
              <span>{p.title}</span>
              <span className="muted">
                {done}/{p.steps.length} 완료 →
              </span>
            </button>
          );
        })}
      </div>

      {ledger && ledger.transactions.length > 0 && (
        <div className="card">
          <h3>하트 적립 내역</h3>
          {ledger.transactions.map((t) => (
            <div className="ledger-row" key={t.id}>
              <span>{t.reason}</span>
              <span className={t.type === "reversal" ? "amt-rev" : "amt-earn"}>
                {t.type === "reversal" ? "-" : "+"}
                {t.amount}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ---------------- Sponsor impact (후원 임팩트) ---------------- */
function SponsorImpact({
  impact,
  loading,
  err,
  onRetry,
  publicView,
  onBackToApp,
}: {
  impact: Impact | null;
  loading: boolean;
  err: ApiError | null;
  onRetry: () => void;
  publicView?: boolean;
  onBackToApp?: () => void;
}) {
  if (loading)
    return <div className="content"><Loading label="후원 임팩트를 불러오는 중" /></div>;

  // A demo heart is funded by 1,000원 of sponsorship (demo-only allocation rule).
  const perHeartKrw = 1000;
  const allocated = impact?.allocatedHearts ?? 0;
  const fundedKrw = allocated * perHeartKrw;

  return (
    <div className="content">
      <div className="card">
        {publicView && <div className="stepper">후원자 화면 · 로그인 없이 열람</div>}
        <h2>후원 임팩트</h2>
        <p className="lead">
          후원자의 마음이 자립준비청년의 실제 실행으로 이어지는 과정을 보여줘요.
        </p>
        <div className="alert alert-warn" role="note" style={{ fontSize: 13 }}>
          <span aria-hidden>ℹ️</span>
          <div>
            <strong>시뮬레이션 안내</strong>
            <div>
              이 화면의 후원금·하트·배분은 데모 데이터예요. 실제 결제, 출금, 계좌이체는
              일어나지 않아요.
            </div>
          </div>
        </div>
      </div>

      {err && (
        <div className="content" style={{ padding: 0 }}>
          <ErrorBanner err={err} onRetry={onRetry} />
        </div>
      )}

      {impact && (
        <>
          <div className="card">
            <div className="stats">
              <div className="stat">
                <div className="num">{impact.sponsorTotalKrw.toLocaleString()}원</div>
                <div className="lbl">데모 후원금</div>
              </div>
              <div className="stat">
                <div className="num">❤️ {impact.allocatedHearts}</div>
                <div className="lbl">배분 예정 하트</div>
              </div>
              <div className="stat">
                <div className="num">{impact.completedActions}</div>
                <div className="lbl">완료된 실행</div>
              </div>
              <div className="stat">
                <div className="num">{impact.activePlans}</div>
                <div className="lbl">진행 중인 계획</div>
              </div>
            </div>
          </div>

          <div className="card">
            <h3>후원이 청년의 실행과 이렇게 연결돼요</h3>
            <ol className="reasons">
              <li>
                후원자가 <strong>{impact.sponsorTotalKrw.toLocaleString()}원</strong>을 데모로
                후원했어요.
              </li>
              <li>
                청년이 실행 계획의 단계를 완료할 때마다 서버 규칙에 따라 하트가 적립돼요.
                지금까지 <strong>{impact.completedActions}건</strong>의 실행이 완료됐어요.
              </li>
              <li>
                완료된 실행에 <strong>❤️ {impact.allocatedHearts}</strong>개의 하트가 배분될
                예정이고, 이는 약 <strong>{fundedKrw.toLocaleString()}원</strong>의 후원과
                연결돼요. (하트 1개 = {perHeartKrw.toLocaleString()}원 데모 환산)
              </li>
              <li>
                현재 <strong>{impact.activePlans}개</strong>의 계획이 진행 중이라, 앞으로도
                후원이 실제 실행으로 이어질 거예요.
              </li>
            </ol>
            <p className="muted">
              하트 수량과 배분은 사람이나 AI가 임의로 정하지 않고, 완료된 실행에 대한 서버의
              고정 규칙으로만 계산돼요.
            </p>
          </div>

          {publicView && onBackToApp && (
            <button className="btn btn-primary" onClick={onBackToApp}>
              나도 자립 지원 찾아보기
            </button>
          )}
        </>
      )}
    </div>
  );
}

/* ---------------- Root App ---------------- */
export default function App() {
  const [screen, setScreen] = useState<Screen>("landing");
  const [sessionId, setSessionId] = useState<string | null>(null);

  const [onbBusy, setOnbBusy] = useState(false);
  const [onbErr, setOnbErr] = useState<ApiError | null>(null);

  const [recs, setRecs] = useState<RecommendationResponse | null>(null);
  const [recsLoading, setRecsLoading] = useState(false);
  const [recsErr, setRecsErr] = useState<ApiError | null>(null);
  const [choosing, setChoosing] = useState<string | null>(null);

  const [plan, setPlan] = useState<PlanDraft | Plan | null>(null);
  const [draftLoading, setDraftLoading] = useState(false);
  const [planErr, setPlanErr] = useState<ApiError | null>(null);
  const [saving, setSaving] = useState(false);
  const [togglingStep, setTogglingStep] = useState<string | null>(null);

  const [plans, setPlans] = useState<Plan[]>([]);
  const [ledger, setLedger] = useState<Ledger | null>(null);
  const [boardLoading, setBoardLoading] = useState(false);

  const [impact, setImpact] = useState<Impact | null>(null);
  const [impactLoading, setImpactLoading] = useState(false);
  const [impactErr, setImpactErr] = useState<ApiError | null>(null);

  const [lastProfile, setLastProfile] = useState<ProfileInput | null>(null);

  async function ensureSession(): Promise<string> {
    if (sessionId) return sessionId;
    const s = await api.createSession();
    setSessionId(s.id);
    return s.id;
  }

  async function submitProfile(p: ProfileInput) {
    setOnbBusy(true);
    setOnbErr(null);
    setLastProfile(p);
    try {
      const sid = await ensureSession();
      await api.saveProfile(sid, p);
      setScreen("recs");
      await loadRecs(sid);
    } catch (e) {
      if (e instanceof ApiError) setOnbErr(e);
    } finally {
      setOnbBusy(false);
    }
  }

  async function loadRecs(sid: string) {
    setRecsLoading(true);
    setRecsErr(null);
    try {
      const r = await api.recommend(sid);
      setRecs(r);
    } catch (e) {
      if (e instanceof ApiError) setRecsErr(e);
    } finally {
      setRecsLoading(false);
    }
  }

  async function chooseBenefit(benefitId: string) {
    setChoosing(benefitId);
    setPlanErr(null);
    setPlan(null);
    try {
      const sid = await ensureSession();
      setScreen("plan");
      setDraftLoading(true);
      const draft = await api.draftPlan(sid, benefitId);
      setPlan(draft);
    } catch (e) {
      if (e instanceof ApiError) setPlanErr(e);
    } finally {
      setChoosing(null);
      setDraftLoading(false);
    }
  }

  async function savePlan() {
    if (!plan || "id" in plan) return;
    setSaving(true);
    setPlanErr(null);
    try {
      const sid = await ensureSession();
      const saved = await api.savePlan({
        sessionId: sid,
        benefitId: plan.benefitId,
        title: plan.title,
        deadline: plan.deadline ?? null,
        requiredDocuments: plan.requiredDocuments,
        steps: plan.steps,
        uncertainties: plan.uncertainties,
        sourceUrl: plan.sourceUrl,
        applyUrl: plan.applyUrl,
      });
      setPlan(saved);
    } catch (e) {
      if (e instanceof ApiError) setPlanErr(e);
    } finally {
      setSaving(false);
    }
  }

  async function toggleStep(stepId: string, done: boolean) {
    if (!plan || !("id" in plan) || !sessionId) return;
    setTogglingStep(stepId);
    try {
      const res = done
        ? await api.completeStep(plan.id, stepId, sessionId)
        : await api.reopenStep(plan.id, stepId, sessionId);
      setPlan(res.plan);
      await refreshLedger(sessionId);
    } catch (e) {
      if (e instanceof ApiError) setPlanErr(e);
    } finally {
      setTogglingStep(null);
    }
  }

  async function refreshLedger(sid: string) {
    try {
      setLedger(await api.ledger(sid));
    } catch {
      /* non-blocking */
    }
  }

  async function openBoard() {
    setScreen("board");
    if (!sessionId) return;
    setBoardLoading(true);
    try {
      const [pl, lg] = await Promise.all([api.listPlans(sessionId), api.ledger(sessionId)]);
      setPlans(pl);
      setLedger(lg);
    } catch {
      /* non-blocking */
    } finally {
      setBoardLoading(false);
    }
  }

  async function loadImpact() {
    setImpactLoading(true);
    setImpactErr(null);
    try {
      setImpact(await api.impact());
    } catch (e) {
      if (e instanceof ApiError) setImpactErr(e);
      else setImpactErr(new ApiError("NETWORK_ERROR", "임팩트를 불러오지 못했어요.", 0));
    } finally {
      setImpactLoading(false);
    }
  }

  async function openImpact() {
    setScreen("impact");
    await loadImpact();
  }

  function goSponsor() {
    if (window.location.pathname !== "/sponsor") {
      window.history.pushState({}, "", "/sponsor");
    }
    setScreen("sponsor");
    void loadImpact();
  }

  function leaveSponsor(target: Screen) {
    if (window.location.pathname !== "/") {
      window.history.pushState({}, "", "/");
    }
    setScreen(target);
  }

  // Deep-link support: /sponsor opens the public sponsor view on load & back/forward.
  useEffect(() => {
    if (window.location.pathname === "/sponsor") {
      setScreen("sponsor");
      void loadImpact();
    }
    const onPop = () => {
      if (window.location.pathname === "/sponsor") {
        setScreen("sponsor");
        void loadImpact();
      } else {
        setScreen("landing");
      }
    };
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const showTabs = screen !== "landing" && screen !== "onboarding" && screen !== "sponsor";

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo" aria-hidden>
            ❤️
          </span>
          디딤하트
        </div>
        {ledger && showTabs && (
          <span className="hearts-pill">❤️ {ledger.balance}</span>
        )}
      </header>

      {screen === "landing" && (
        <Landing onStart={() => setScreen("onboarding")} onSponsor={goSponsor} />
      )}
      {screen === "onboarding" && (
        <Onboarding busy={onbBusy} err={onbErr} onSubmit={submitProfile} />
      )}
      {screen === "recs" && (
        <Recs
          data={recs}
          loading={recsLoading}
          err={recsErr}
          onRetry={() => sessionId && loadRecs(sessionId)}
          onChoose={chooseBenefit}
          choosing={choosing}
        />
      )}
      {screen === "plan" && (
        <PlanScreen
          plan={plan}
          draftLoading={draftLoading}
          err={planErr}
          onRetry={() =>
            plan && "benefitId" in plan ? chooseBenefit(plan.benefitId) : undefined
          }
          onSave={savePlan}
          onToggle={toggleStep}
          saving={saving}
          togglingStep={togglingStep}
        />
      )}
      {screen === "board" && (
        <Board
          plans={plans}
          ledger={ledger}
          loading={boardLoading}
          onOpenPlan={(p) => {
            setPlan(p);
            setScreen("plan");
          }}
        />
      )}
      {screen === "impact" && (
        <SponsorImpact
          impact={impact}
          loading={impactLoading}
          err={impactErr}
          onRetry={loadImpact}
        />
      )}
      {screen === "sponsor" && (
        <SponsorImpact
          impact={impact}
          loading={impactLoading}
          err={impactErr}
          onRetry={loadImpact}
          publicView
          onBackToApp={() => leaveSponsor("onboarding")}
        />
      )}

      {showTabs && (
        <nav className="tabbar" aria-label="주요 화면">
          <button
            className="tab"
            aria-current={screen === "recs"}
            onClick={() => setScreen("recs")}
          >
            <span className="ic" aria-hidden>
              ✨
            </span>
            추천
          </button>
          <button
            className="tab"
            aria-current={screen === "plan"}
            onClick={() => setScreen("plan")}
            disabled={!plan}
          >
            <span className="ic" aria-hidden>
              📋
            </span>
            계획
          </button>
          <button className="tab" aria-current={screen === "board"} onClick={openBoard}>
            <span className="ic" aria-hidden>
              ❤️
            </span>
            디딤판
          </button>
          <button className="tab" aria-current={screen === "impact"} onClick={openImpact}>
            <span className="ic" aria-hidden>
              🤝
            </span>
            임팩트
          </button>
        </nav>
      )}
    </div>
  );
}
