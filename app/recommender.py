"""Recommendation service.

The agent explains; this module decides. Anything the model returns is checked
against the shortlist the pre-filter produced, and provenance is always written
by the server so a source URL or verification date can never be invented.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.agents import (
    MAX_RECOMMENDATIONS,
    ActionPlannerAgent,
    AgentTimeout,
    AgentUnavailable,
    BenefitMatcherAgent,
)
from app.domain.benefit import Benefit
from app.domain.plan import Plan, fallback_step_texts, plan_from_steps
from app.domain.profile import Profile, prefilter, rank, rule_based_fit, rule_based_reasons
from app.settings import Settings

logger = logging.getLogger(__name__)

VALID_FITS = {"high", "medium", "low"}


class Recommendation(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    benefit_id: str = Field(alias="benefitId")
    title: str
    provider: str
    category: str
    fit: str
    reason: list[str]
    uncertainties: list[str] = Field(default_factory=list)
    next_action: str = Field(alias="nextAction")
    source_url: str = Field(alias="sourceUrl")
    verified_at: str = Field(alias="verifiedAt")
    deadline: str | None = None


class RecommendationResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    summary: str
    recommendations: list[Recommendation]
    degraded: bool = False
    degraded_reason: str | None = Field(alias="degradedReason", default=None)


def _clean_text_list(value: Any, limit: int, max_len: int = 300) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            out.append(text[:max_len])
        if len(out) >= limit:
            break
    return out


def build_recommendation(benefit: Benefit, raw: dict[str, Any]) -> Recommendation:
    """Assemble one card, taking provenance from the catalog rather than the model."""
    fit = str(raw.get("fit", "")).strip().lower()
    if fit not in VALID_FITS:
        fit = "medium"

    reasons = _clean_text_list(raw.get("reason"), limit=4)
    if not reasons:
        reasons = ["프로필에서 확인한 기본 조건을 충족해요."]

    next_action = str(raw.get("nextAction", "")).strip()[:300]
    if not next_action:
        next_action = (
            benefit.application_steps[0]
            if benefit.application_steps
            else "공식 안내 페이지에서 신청 방법을 확인하세요."
        )

    return Recommendation(
        benefitId=benefit.id,
        title=benefit.title,
        provider=benefit.provider,
        category=benefit.category,
        fit=fit,
        reason=reasons,
        uncertainties=_clean_text_list(raw.get("uncertainties"), limit=3),
        nextAction=next_action,
        # Provenance is server-owned. AGENTS.md section 8.3.
        sourceUrl=str(benefit.source_url),
        verifiedAt=benefit.verified_at.isoformat(),
        deadline=benefit.deadline.isoformat() if benefit.deadline else None,
    )


def validate_agent_output(
    payload: dict[str, Any], candidates: list[Benefit]
) -> list[Recommendation]:
    """Keep only recommendations that point at a real shortlisted benefit."""
    by_id = {benefit.id: benefit for benefit in candidates}
    raw_items = payload.get("recommendations")
    if not isinstance(raw_items, list):
        return []

    seen: set[str] = set()
    result: list[Recommendation] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        benefit_id = str(item.get("benefitId", "")).strip()
        benefit = by_id.get(benefit_id)
        if benefit is None:
            logger.warning("agent returned unknown benefit id, dropping it")
            continue
        if benefit_id in seen:
            continue
        seen.add(benefit_id)
        result.append(build_recommendation(benefit, item))
        if len(result) >= MAX_RECOMMENDATIONS:
            break
    return result


def rule_based_result(
    candidates: list[Benefit], profile: Profile, today: date, reason: str
) -> RecommendationResult:
    """Deterministic recommendations for when the AI is unavailable."""
    top = rank(candidates, profile, today)[:MAX_RECOMMENDATIONS]
    recommendations = [
        build_recommendation(
            benefit,
            {
                "fit": rule_based_fit(benefit, profile),
                "reason": rule_based_reasons(benefit, profile, today),
                "uncertainties": ["세부 자격 조건은 공식 페이지에서 꼭 확인하세요."],
                "nextAction": (
                    benefit.application_steps[0]
                    if benefit.application_steps
                    else "공식 안내 페이지에서 신청 방법을 확인하세요."
                ),
            },
        )
        for benefit in top
    ]
    return RecommendationResult(
        summary=f"프로필 조건에 맞는 지원사업 {len(recommendations)}건을 찾았어요.",
        recommendations=recommendations,
        degraded=True,
        degradedReason=reason,
    )


class RecommendationService:
    def __init__(self, settings: Settings, provider: Any | None, model: str) -> None:
        self._settings = settings
        self._provider = provider
        self._model = model

    @property
    def ai_enabled(self) -> bool:
        return self._provider is not None and bool(self._model)

    def shortlist(self, benefits: list[Benefit], profile: Profile, today: date) -> list[Benefit]:
        return rank(prefilter(benefits, profile, today), profile, today)[:8]

    async def recommend(
        self, benefits: list[Benefit], profile: Profile, today: date
    ) -> RecommendationResult:
        candidates = self.shortlist(benefits, profile, today)
        if not candidates:
            return RecommendationResult(summary="", recommendations=[], degraded=False)

        if not self.ai_enabled:
            return rule_based_result(candidates, profile, today, "AI 연결이 설정되지 않았어요.")

        matcher = BenefitMatcherAgent(
            self._provider, self._model, self._settings.ai_timeout_seconds
        )
        try:
            payload = await matcher.recommend(profile, candidates, today)
        except (AgentTimeout, AgentUnavailable) as exc:
            logger.warning("matcher unavailable: %s", type(exc).__name__)
            return rule_based_result(
                candidates, profile, today, "AI 응답이 늦어서 규칙 기반으로 추천했어요."
            )
        except Exception:
            logger.exception("matcher failed")
            return rule_based_result(
                candidates, profile, today, "AI 추천에 문제가 있어 규칙 기반으로 추천했어요."
            )

        recommendations = validate_agent_output(payload, candidates)
        if not recommendations:
            return rule_based_result(
                candidates, profile, today, "AI 결과를 검증하지 못해 규칙 기반으로 추천했어요."
            )

        summary = str(payload.get("summary", "")).strip()[:300]
        return RecommendationResult(
            summary=summary or f"프로필에 맞는 지원사업 {len(recommendations)}건이에요.",
            recommendations=recommendations,
            degraded=False,
        )

    async def build_plan(self, benefit: Benefit, session_id: str, today: date) -> tuple[Plan, bool]:
        """Return the plan and whether it had to fall back to catalog text."""
        if self.ai_enabled:
            planner = ActionPlannerAgent(
                self._provider, self._model, self._settings.ai_timeout_seconds
            )
            try:
                steps = await planner.plan(benefit, today)
                return plan_from_steps(
                    session_id=session_id, benefit=benefit, step_texts=steps
                ), False
            except (AgentTimeout, AgentUnavailable) as exc:
                logger.warning("planner unavailable: %s", type(exc).__name__)
            except Exception:
                logger.exception("planner failed")

        return plan_from_steps(
            session_id=session_id, benefit=benefit, step_texts=fallback_step_texts(benefit)
        ), True
