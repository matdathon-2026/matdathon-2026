// Shared types matching the API contract

export type FitLevel = 'high' | 'medium' | 'low';

export interface Profile {
  age: number;
  region: string;
  situation: string;
  interests: string[];
  housingStatus: string;
  employmentStatus: string;
}

export interface Recommendation {
  benefitId: string;
  title: string;
  provider: string;
  category: string;
  fit: FitLevel;
  reason: string[];
  uncertainties: string[];
  nextAction: string;
  sourceUrl: string;
  verifiedAt: string;
  deadline: string | null;
}

export interface RecommendationsResponse {
  sessionId: string;
  summary: string;
  degraded: boolean;
  recommendations: Recommendation[];
}

export interface PlanStep {
  stepId: string;
  order: number;
  title: string;
  detail: string;
  hearts: number;
  completed: boolean;
}

export interface Plan {
  planId: string;
  sessionId: string;
  benefitId: string;
  title: string;
  sourceUrl: string;
  verifiedAt: string;
  deadline: string | null;
  requiredDocuments: string[];
  steps: PlanStep[];
}

export interface CompleteStepResponse {
  planId: string;
  stepId: string;
  awarded: number;
  alreadyCompleted: boolean;
  heartBalance: number;
}

export interface HeartEntry {
  entryId: string;
  reason: string;
  hearts: number;
  createdAt: string;
  planId: string;
  stepId: string;
}

export interface HeartsResponse {
  sessionId: string;
  balance: number;
  entries: HeartEntry[];
}

export interface Sponsor {
  name: string;
  amountKrw: number;
}

export interface ImpactResponse {
  totalDonationKrw: number;
  heartsPledged: number;
  heartsDistributed: number;
  completedActions: number;
  sponsors: Sponsor[];
}

export interface Benefit {
  id: string;
  title: string;
  provider: string;
  category: string;
  regions: string[];
  eligibilityText: string;
  benefitText: string;
  applicationSteps: string[];
  requiredDocuments: string[];
  deadline: string | null;
  sourceUrl: string;
  sourceAgency: string;
  verifiedAt: string;
}

export interface BenefitsResponse {
  items: Benefit[];
  count: number;
}

export interface ApiError {
  code: string;
  message: string;
}
