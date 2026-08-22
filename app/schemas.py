"""API request/response models. Kept separate from domain models.

Responses use camelCase aliases for the frontend; requests accept snake_case.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models import (
    AgeBand,
    BenefitCategory,
    IncomeBand,
    SelfRelianceStage,
    WorkStudyStatus,
)


def _camel(s: str) -> str:
    head, *rest = s.split("_")
    return head + "".join(w.capitalize() for w in rest)


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=_camel, populate_by_name=True)


# --- requests ---
class ProfileIn(CamelModel):
    age_band: AgeBand
    region: str = Field(max_length=40)
    self_reliance_stage: SelfRelianceStage
    interests: list[BenefitCategory] = Field(min_length=1, max_length=3)
    work_study_status: WorkStudyStatus
    urgent_need: BenefitCategory
    income_band: Optional[IncomeBand] = None
    urgent_note: Optional[str] = Field(default=None, max_length=300)


class RecommendationRequest(CamelModel):
    session_id: str


class CompareRequest(CamelModel):
    benefit_ids: list[str] = Field(min_length=1, max_length=3)
    session_id: Optional[str] = None


class PlanDraftRequest(CamelModel):
    session_id: str
    benefit_id: str


class SaveStepIn(CamelModel):
    id: str
    title: str
    description: str
    estimated_minutes: int = Field(ge=1, le=240)
    order: int


class SavePlanRequest(CamelModel):
    session_id: str
    benefit_id: str
    title: str
    deadline: Optional[date] = None
    required_documents: list[str] = Field(default_factory=list)
    steps: list[SaveStepIn] = Field(min_length=1, max_length=10)
    uncertainties: list[str] = Field(default_factory=list)
    source_url: str = ""
    apply_url: str = ""


class StepActionRequest(CamelModel):
    session_id: str


# --- responses ---
class BenefitCard(CamelModel):
    benefit_id: str
    title: str
    provider: str
    category: str
    fit: str
    reasons: list[str]
    uncertainties: list[str]
    next_action: str
    source_url: str
    source_agency: str
    verified_at: date
    deadline: Optional[date] = None


class RecommendationResponse(CamelModel):
    summary: str
    recommendations: list[BenefitCard]
    ai_generated: bool = True


class BenefitDetailOut(CamelModel):
    id: str
    title: str
    provider: str
    category: str
    regions: list[str]
    eligibility_text: str
    benefit_text: str
    application_steps: list[str]
    required_documents: list[str]
    deadline: Optional[date] = None
    source_url: str
    source_agency: str
    verified_at: date
    status: str


class StepOut(CamelModel):
    id: str
    title: str
    description: str
    estimated_minutes: int
    order: int
    status: str


class PlanOut(CamelModel):
    id: str
    session_id: str
    benefit_id: str
    title: str
    deadline: Optional[date] = None
    required_documents: list[str]
    steps: list[StepOut]
    uncertainties: list[str]
    source_url: str
    apply_url: str
    status: str
    created_at: datetime


class PlanDraftOut(CamelModel):
    benefit_id: str
    title: str
    deadline: Optional[date] = None
    required_documents: list[str]
    steps: list[StepOut]
    uncertainties: list[str]
    source_url: str
    apply_url: str
    ai_generated: bool = True


class HeartTxnOut(CamelModel):
    id: str
    plan_id: str
    step_id: str
    type: str
    amount: int
    reason: str
    created_at: datetime


class LedgerOut(CamelModel):
    balance: int
    transactions: list[HeartTxnOut]


class ImpactOut(CamelModel):
    sponsor_total_krw: int
    allocated_hearts: int
    completed_actions: int
    active_plans: int


class SessionOut(CamelModel):
    id: str
    created_at: datetime
    has_profile: bool


class AiStatusOut(BaseModel):
    runtime: str
    auth: str
    model: str
    enabled: bool


class ErrorBody(BaseModel):
    code: str
    message: str
    retryable: bool = False
    requestId: Optional[str] = None


class ErrorResponse(BaseModel):
    error: ErrorBody
