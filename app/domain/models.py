"""Domain enums, models, and value objects.

These are the internal source of truth. API request/response models (schemas.py)
are kept separate and map to/from these.
"""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class BenefitCategory(str, Enum):
    housing = "housing"          # 주거
    employment = "employment"    # 취업
    education = "education"      # 교육
    finance = "finance"          # 금융
    living = "living"            # 생활
    mental_health = "mental_health"  # 마음건강


class AgeBand(str, Enum):
    under_18 = "under_18"
    b18_24 = "18_24"
    b25_29 = "25_29"
    b30_34 = "30_34"
    b35_plus = "35_plus"


class SelfRelianceStage(str, Enum):
    before_exit = "before_exit"        # 보호종료 예정
    within_1_year = "within_1_year"    # 보호종료 후 1년 이내
    within_5_years = "within_5_years"  # 보호종료 후 5년 이내
    general_youth = "general_youth"    # 일반 청년


class WorkStudyStatus(str, Enum):
    employed = "employed"
    job_seeking = "job_seeking"
    studying = "studying"
    neither = "neither"


class IncomeBand(str, Enum):
    below_50 = "below_50"      # 기준 중위소득 50% 이하
    b50_100 = "50_100"
    b100_150 = "100_150"
    above_150 = "above_150"
    unknown = "unknown"


# 17 시·도 + ALL sentinel for nationwide benefits.
REGION_CODES = [
    "seoul", "busan", "daegu", "incheon", "gwangju", "daejeon", "ulsan",
    "sejong", "gyeonggi", "gangwon", "chungbuk", "chungnam", "jeonbuk",
    "jeonnam", "gyeongbuk", "gyeongnam", "jeju",
]

# Representative numeric range for each age band, used by the deterministic prefilter.
AGE_BAND_RANGE: dict[str, tuple[int, int]] = {
    "under_18": (15, 17),
    "18_24": (18, 24),
    "25_29": (25, 29),
    "30_34": (30, 34),
    "35_plus": (35, 120),
}


class AgeRange(BaseModel):
    min: Optional[int] = None
    max: Optional[int] = None


class Benefit(BaseModel):
    """Catalog entry. Mirrors data/benefits.seed.json shape."""

    id: str
    title: str
    provider: str
    category: BenefitCategory
    regions: list[str]
    age: AgeRange = Field(default_factory=AgeRange)
    eligibilityText: str
    benefitText: str
    applicationSteps: list[str] = Field(default_factory=list)
    requiredDocuments: list[str] = Field(default_factory=list)
    deadline: Optional[date] = None
    sourceUrl: str
    sourceAgency: str
    verifiedAt: date
    status: str = "active"


class Profile(BaseModel):
    age_band: AgeBand
    region: str
    self_reliance_stage: SelfRelianceStage
    interests: list[BenefitCategory] = Field(min_length=1, max_length=3)
    work_study_status: WorkStudyStatus
    urgent_need: BenefitCategory
    income_band: Optional[IncomeBand] = None
    urgent_note: Optional[str] = None


class DemoSession(BaseModel):
    id: str
    created_at: datetime
    profile: Optional[Profile] = None


class ActionStep(BaseModel):
    id: str
    title: str
    description: str
    estimated_minutes: int = Field(ge=1, le=240)
    order: int
    status: str = "todo"  # todo | completed


class ActionPlan(BaseModel):
    id: str
    session_id: str
    benefit_id: str
    title: str
    deadline: Optional[date] = None
    required_documents: list[str] = Field(default_factory=list)
    steps: list[ActionStep] = Field(min_length=1, max_length=10)
    uncertainties: list[str] = Field(default_factory=list)
    source_url: str = ""
    apply_url: str = ""
    status: str = "todo"  # todo | in_progress | completed
    created_at: datetime


class HeartTransaction(BaseModel):
    id: str
    session_id: str
    plan_id: str
    step_id: str
    type: str  # earn | reversal | sponsor_allocation_demo
    amount: int
    reason: str
    idempotency_key: str
    created_at: datetime
