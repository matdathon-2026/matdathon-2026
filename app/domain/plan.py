"""Action plans and the heart ledger.

AGENTS.md section 9: hearts are demo points, the amount per step is fixed by the
server, the same step can only ever be credited once, and the balance is the sum
of the ledger rather than a stored number the AI could touch.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.domain.benefit import Benefit

# Fixed reward table. Never derived from model output.
HEARTS_FIRST_STEP = 10
HEARTS_PER_STEP = 10
HEARTS_FINAL_STEP = 20

MAX_STEPS = 6


class PlanStep(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    step_id: str = Field(alias="stepId")
    order: int
    title: str
    detail: str = ""
    hearts: int
    completed: bool = False
    completed_at: datetime | None = Field(alias="completedAt", default=None)


class Plan(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    plan_id: str = Field(alias="planId")
    session_id: str = Field(alias="sessionId")
    benefit_id: str = Field(alias="benefitId")
    title: str
    source_url: str = Field(alias="sourceUrl")
    verified_at: str = Field(alias="verifiedAt")
    deadline: str | None = None
    required_documents: list[str] = Field(alias="requiredDocuments", default_factory=list)
    steps: list[PlanStep]
    created_at: datetime = Field(
        alias="createdAt", default_factory=lambda: datetime.now(timezone.utc)
    )

    def find_step(self, step_id: str) -> PlanStep | None:
        return next((step for step in self.steps if step.step_id == step_id), None)

    def to_cosmos_item(self) -> dict[str, Any]:
        return self.model_dump(mode="json", by_alias=True)


class HeartEntry(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    entry_id: str = Field(alias="entryId")
    session_id: str = Field(alias="sessionId")
    reason: str
    hearts: int
    plan_id: str | None = Field(alias="planId", default=None)
    step_id: str | None = Field(alias="stepId", default=None)
    created_at: datetime = Field(
        alias="createdAt", default_factory=lambda: datetime.now(timezone.utc)
    )

    def to_cosmos_item(self) -> dict[str, Any]:
        return self.model_dump(mode="json", by_alias=True)


def hearts_for_step(order: int, total: int) -> int:
    """Fixed server-side reward for completing one step."""
    if order == 1:
        return HEARTS_FIRST_STEP
    if order == total:
        return HEARTS_FINAL_STEP
    return HEARTS_PER_STEP


def balance_of(entries: list[HeartEntry]) -> int:
    """The balance is always recomputed from the ledger, never stored."""
    return sum(entry.hearts for entry in entries)


def build_step_id(plan_id: str, order: int) -> str:
    return f"{plan_id}-{order}"


def new_plan_id() -> str:
    return f"p_{uuid.uuid4().hex[:12]}"


def plan_from_steps(
    *,
    session_id: str,
    benefit: Benefit,
    step_texts: list[tuple[str, str]],
    plan_id: str | None = None,
) -> Plan:
    """Turn ordered (title, detail) pairs into a plan with fixed heart values."""
    identifier = plan_id or new_plan_id()
    trimmed = step_texts[:MAX_STEPS]
    total = len(trimmed)

    steps = [
        PlanStep(
            stepId=build_step_id(identifier, order),
            order=order,
            title=title,
            detail=detail,
            hearts=hearts_for_step(order, total),
        )
        for order, (title, detail) in enumerate(trimmed, start=1)
    ]

    return Plan(
        planId=identifier,
        sessionId=session_id,
        benefitId=benefit.id,
        title=benefit.title,
        sourceUrl=str(benefit.source_url),
        verifiedAt=benefit.verified_at.isoformat(),
        deadline=benefit.deadline.isoformat() if benefit.deadline else None,
        requiredDocuments=list(benefit.required_documents),
        steps=steps,
    )


def fallback_step_texts(benefit: Benefit) -> list[tuple[str, str]]:
    """Plan steps taken straight from the catalog when the planner agent is down.

    Only text already present in the benefit row is used, so a degraded plan
    still cannot contain invented instructions.
    """
    steps: list[tuple[str, str]] = []
    if benefit.required_documents:
        steps.append(
            ("필요한 서류 준비하기", "필요 서류: " + ", ".join(benefit.required_documents))
        )
    for text in benefit.application_steps:
        steps.append((text, ""))
    if not steps:
        steps.append(("공식 안내 페이지 확인하기", str(benefit.source_url)))
    steps.append(("신청 결과 확인하고 기록하기", "접수 번호와 담당 부서 연락처를 메모해 두세요."))
    return steps
