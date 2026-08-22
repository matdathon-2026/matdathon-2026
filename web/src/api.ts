import type {
  Profile,
  RecommendationsResponse,
  Plan,
  CompleteStepResponse,
  HeartsResponse,
  ImpactResponse,
  BenefitsResponse,
  ApiError,
} from './types';

class ApiCallError extends Error {
  code: string;
  constructor(message: string, code: string) {
    super(message);
    this.code = code;
    this.name = 'ApiCallError';
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let code = 'UNKNOWN_ERROR';
    let message = `서버 오류가 발생했어요 (${res.status})`;
    try {
      const body = await res.json() as { error: ApiError };
      if (body?.error) {
        code = body.error.code;
        message = body.error.message;
      }
    } catch {
      // use defaults
    }
    throw new ApiCallError(message, code);
  }
  return res.json() as Promise<T>;
}

export async function fetchRecommendations(
  sessionId: string | null,
  profile: Profile,
  signal: AbortSignal,
): Promise<RecommendationsResponse> {
  const res = await fetch('/api/recommendations', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sessionId, profile }),
    signal,
  });
  return handleResponse<RecommendationsResponse>(res);
}

export async function fetchPlan(
  sessionId: string,
  benefitId: string,
  signal: AbortSignal,
): Promise<Plan> {
  const res = await fetch('/api/plans', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sessionId, benefitId }),
    signal,
  });
  return handleResponse<Plan>(res);
}

export async function completeStep(
  planId: string,
  stepId: string,
  sessionId: string,
): Promise<CompleteStepResponse> {
  const res = await fetch(`/api/plans/${planId}/steps/${stepId}/complete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sessionId }),
  });
  return handleResponse<CompleteStepResponse>(res);
}

export async function fetchHearts(sessionId: string): Promise<HeartsResponse> {
  const res = await fetch(`/api/hearts?sessionId=${encodeURIComponent(sessionId)}`);
  return handleResponse<HeartsResponse>(res);
}

export async function fetchImpact(sessionId: string): Promise<ImpactResponse> {
  const res = await fetch(`/api/impact?sessionId=${encodeURIComponent(sessionId)}`);
  return handleResponse<ImpactResponse>(res);
}

export async function fetchBenefits(): Promise<BenefitsResponse> {
  const res = await fetch('/api/benefits');
  return handleResponse<BenefitsResponse>(res);
}

export { ApiCallError };
