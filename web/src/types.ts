// API response/request types mirroring the FastAPI camelCase schemas.

export type AgeBand = "under_18" | "18_24" | "25_29" | "30_34" | "35_plus";
export type SelfRelianceStage =
  | "before_exit"
  | "within_1_year"
  | "within_5_years"
  | "general_youth";
export type WorkStudyStatus = "employed" | "job_seeking" | "studying" | "neither";
export type Category =
  | "housing"
  | "employment"
  | "education"
  | "finance"
  | "living"
  | "mental_health";

export interface ProfileInput {
  ageBand: AgeBand;
  region: string;
  selfRelianceStage: SelfRelianceStage;
  interests: Category[];
  workStudyStatus: WorkStudyStatus;
  urgentNeed: Category;
  urgentNote?: string;
}

export interface Session {
  id: string;
  createdAt: string;
  hasProfile: boolean;
}

export interface BenefitCard {
  benefitId: string;
  title: string;
  provider: string;
  category: string;
  fit: "high" | "medium" | "low";
  reasons: string[];
  uncertainties: string[];
  nextAction: string;
  sourceUrl: string;
  sourceAgency: string;
  verifiedAt: string;
  deadline?: string | null;
}

export interface RecommendationResponse {
  summary: string;
  recommendations: BenefitCard[];
  aiGenerated: boolean;
}

export interface BenefitDetail {
  id: string;
  title: string;
  provider: string;
  category: string;
  regions: string[];
  eligibilityText: string;
  benefitText: string;
  applicationSteps: string[];
  requiredDocuments: string[];
  deadline?: string | null;
  sourceUrl: string;
  sourceAgency: string;
  verifiedAt: string;
  status: string;
}

export interface Step {
  id: string;
  title: string;
  description: string;
  estimatedMinutes: number;
  order: number;
  status: string;
}

export interface PlanDraft {
  benefitId: string;
  title: string;
  deadline?: string | null;
  requiredDocuments: string[];
  steps: Step[];
  uncertainties: string[];
  sourceUrl: string;
  applyUrl: string;
  aiGenerated: boolean;
}

export interface Plan {
  id: string;
  sessionId: string;
  benefitId: string;
  title: string;
  deadline?: string | null;
  requiredDocuments: string[];
  steps: Step[];
  uncertainties: string[];
  sourceUrl: string;
  applyUrl: string;
  status: string;
  createdAt: string;
}

export interface HeartTxn {
  id: string;
  planId: string;
  stepId: string;
  type: string;
  amount: number;
  reason: string;
  createdAt: string;
}

export interface Ledger {
  balance: number;
  transactions: HeartTxn[];
}

export interface Impact {
  sponsorTotalKrw: number;
  allocatedHearts: number;
  completedActions: number;
  activePlans: number;
}

export interface CompleteResult {
  plan: Plan;
  transaction: HeartTxn | null;
  duplicate: boolean;
}
