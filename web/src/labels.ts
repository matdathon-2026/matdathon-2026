import type {
  AgeBand,
  Category,
  SelfRelianceStage,
  WorkStudyStatus,
} from "./types";

export const AGE_BANDS: { value: AgeBand; label: string }[] = [
  { value: "under_18", label: "18세 미만" },
  { value: "18_24", label: "18~24세" },
  { value: "25_29", label: "25~29세" },
  { value: "30_34", label: "30~34세" },
  { value: "35_plus", label: "35세 이상" },
];

export const STAGES: { value: SelfRelianceStage; label: string }[] = [
  { value: "before_exit", label: "보호종료 예정" },
  { value: "within_1_year", label: "보호종료 후 1년 이내" },
  { value: "within_5_years", label: "보호종료 후 5년 이내" },
  { value: "general_youth", label: "일반 청년" },
];

export const WORK_STUDY: { value: WorkStudyStatus; label: string }[] = [
  { value: "employed", label: "재직 중" },
  { value: "job_seeking", label: "구직 중" },
  { value: "studying", label: "학업 중" },
  { value: "neither", label: "해당 없음" },
];

export const CATEGORIES: { value: Category; label: string; icon: string }[] = [
  { value: "housing", label: "주거", icon: "🏠" },
  { value: "employment", label: "취업", icon: "💼" },
  { value: "education", label: "교육", icon: "📚" },
  { value: "finance", label: "금융", icon: "💰" },
  { value: "living", label: "생활", icon: "🧺" },
  { value: "mental_health", label: "마음건강", icon: "💚" },
];

export const REGIONS: { value: string; label: string }[] = [
  { value: "seoul", label: "서울" },
  { value: "busan", label: "부산" },
  { value: "daegu", label: "대구" },
  { value: "incheon", label: "인천" },
  { value: "gwangju", label: "광주" },
  { value: "daejeon", label: "대전" },
  { value: "ulsan", label: "울산" },
  { value: "sejong", label: "세종" },
  { value: "gyeonggi", label: "경기" },
  { value: "gangwon", label: "강원" },
  { value: "chungbuk", label: "충북" },
  { value: "chungnam", label: "충남" },
  { value: "jeonbuk", label: "전북" },
  { value: "jeonnam", label: "전남" },
  { value: "gyeongbuk", label: "경북" },
  { value: "gyeongnam", label: "경남" },
  { value: "jeju", label: "제주" },
];

export const CATEGORY_LABEL: Record<string, string> = Object.fromEntries(
  CATEGORIES.map((c) => [c.value, `${c.icon} ${c.label}`]),
);

export const FIT_LABEL: Record<string, { text: string; cls: string }> = {
  high: { text: "적합도 높음", cls: "fit-high" },
  medium: { text: "적합도 보통", cls: "fit-medium" },
  low: { text: "적합도 낮음", cls: "fit-low" },
};
