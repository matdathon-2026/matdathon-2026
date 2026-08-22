import type {
  BenefitDetail,
  CompleteResult,
  Impact,
  Ledger,
  Plan,
  PlanDraft,
  ProfileInput,
  RecommendationResponse,
  Session,
} from "./types";

const BASE = "/api/v1";

export class ApiError extends Error {
  code: string;
  status: number;
  retryable: boolean;
  constructor(code: string, message: string, status: number, retryable = false) {
    super(message);
    this.code = code;
    this.status = status;
    this.retryable = retryable;
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 120_000);
  try {
    res = await fetch(path, {
      ...init,
      signal: controller.signal,
      headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") {
      throw new ApiError(
        "TIMEOUT",
        "응답이 너무 오래 걸려요. 잠시 후 다시 시도해 주세요.",
        0,
        true,
      );
    }
    throw new ApiError("NETWORK", "네트워크 연결에 문제가 있어요. 잠시 후 다시 시도해 주세요.", 0, true);
  } finally {
    clearTimeout(timer);
  }
  if (!res.ok) {
    let code = "ERROR";
    let message = "요청을 처리하지 못했어요.";
    let retryable = false;
    try {
      const body = await res.json();
      if (body?.error) {
        code = body.error.code ?? code;
        message = body.error.message ?? message;
        retryable = !!body.error.retryable;
      }
    } catch {
      /* ignore parse failure */
    }
    throw new ApiError(code, message, res.status, retryable);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  createSession: () => req<Session>(`${BASE}/demo-sessions`, { method: "POST" }),
  saveProfile: (sessionId: string, profile: ProfileInput) =>
    req<Session>(`${BASE}/demo-sessions/${sessionId}/profile`, {
      method: "PUT",
      body: JSON.stringify(profile),
    }),
  recommend: (sessionId: string) =>
    req<RecommendationResponse>(`${BASE}/recommendations`, {
      method: "POST",
      body: JSON.stringify({ sessionId }),
    }),
  benefit: (id: string) => req<BenefitDetail>(`${BASE}/benefits/${id}`),
  compare: (benefitIds: string[], sessionId?: string) =>
    req<{ rows: Record<string, unknown>[] }>(`${BASE}/benefits/compare`, {
      method: "POST",
      body: JSON.stringify({ benefitIds, sessionId }),
    }),
  draftPlan: (sessionId: string, benefitId: string) =>
    req<PlanDraft>(`${BASE}/plans/draft`, {
      method: "POST",
      body: JSON.stringify({ sessionId, benefitId }),
    }),
  savePlan: (body: {
    sessionId: string;
    benefitId: string;
    title: string;
    deadline?: string | null;
    requiredDocuments: string[];
    steps: PlanDraft["steps"];
    uncertainties: string[];
    sourceUrl: string;
    applyUrl: string;
  }) => req<Plan>(`${BASE}/plans`, { method: "POST", body: JSON.stringify(body) }),
  listPlans: (sessionId: string) =>
    req<Plan[]>(`${BASE}/plans?sessionId=${encodeURIComponent(sessionId)}`),
  completeStep: (planId: string, stepId: string, sessionId: string) =>
    req<CompleteResult>(`${BASE}/plans/${planId}/steps/${stepId}/complete`, {
      method: "POST",
      body: JSON.stringify({ sessionId }),
    }),
  reopenStep: (planId: string, stepId: string, sessionId: string) =>
    req<{ plan: Plan; reversal: unknown }>(
      `${BASE}/plans/${planId}/steps/${stepId}/reopen`,
      { method: "POST", body: JSON.stringify({ sessionId }) },
    ),
  ledger: (sessionId: string) =>
    req<Ledger>(`${BASE}/hearts/ledger?sessionId=${encodeURIComponent(sessionId)}`),
  impact: () => req<Impact>(`${BASE}/impact`),
};
