"""The four read-only tools exposed to the agents.

Tool names here are the ONLY names the permission allowlist approves. They read
from an in-memory catalog snapshot set at startup; they never write anything.
"""
from __future__ import annotations

from typing import Any, Optional

from app.domain.filters import prefilter, rank_by_interest
from app.domain.models import Benefit

_BENEFITS: list[Benefit] = []
_BY_ID: dict[str, Benefit] = {}

# Exact tool names allowed to execute (used by the permission handler).
ALLOWED_TOOL_NAMES = {
    "search_benefits",
    "get_benefit_detail",
    "compare_benefits",
    "get_source_metadata",
}


def set_catalog(benefits: list[Benefit]) -> None:
    global _BENEFITS, _BY_ID
    _BENEFITS = list(benefits)
    _BY_ID = {b.id: b for b in _BENEFITS}


def _summary(b: Benefit) -> dict[str, Any]:
    return {
        "benefitId": b.id,
        "title": b.title,
        "provider": b.provider,
        "category": b.category.value,
        "benefitText": b.benefitText,
        "eligibilityText": b.eligibilityText,
        "deadline": b.deadline.isoformat() if b.deadline else None,
        "regions": b.regions,
    }


def search_benefits(
    region: str,
    age: Optional[int] = None,
    categories: Optional[list[str]] = None,
    self_reliance_stage: str = "general_youth",
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Search the internal benefit catalog for candidates matching a profile.

    Args:
        region: 시·도 코드 (예: 'seoul'). 전국 혜택도 함께 반환됩니다.
        age: 신청자의 나이(정수). 생략 가능.
        categories: 관심 분야 코드 목록 (housing/employment/education/finance/living/mental_health).
        self_reliance_stage: 자립 단계 코드.
        limit: 최대 반환 개수 (1~20).
    Returns a list of read-only benefit summaries. Never modifies data.
    """
    limit = max(1, min(int(limit or 20), 20))
    age_band = _age_to_band(age)
    candidates = prefilter(_BENEFITS, region=region, age_band=age_band)
    interests = [c for c in (categories or []) if c]
    urgent = interests[0] if interests else "living"
    ranked = rank_by_interest(candidates, interests=interests, urgent_need=urgent)
    return [_summary(b) for b in ranked[:limit]]


def get_benefit_detail(benefit_id: str) -> dict[str, Any]:
    """Return the full public detail for one benefit id from the catalog.

    Args:
        benefit_id: 카탈로그에 존재하는 혜택 ID.
    Only ids that exist in the catalog are allowed.
    """
    b = _BY_ID.get(benefit_id)
    if b is None:
        return {"error": "benefit_not_found", "benefitId": benefit_id}
    return {
        **_summary(b),
        "applicationSteps": b.applicationSteps,
        "requiredDocuments": b.requiredDocuments,
        "sourceUrl": b.sourceUrl,
        "sourceAgency": b.sourceAgency,
        "verifiedAt": b.verifiedAt.isoformat(),
        "status": b.status,
        "ageMin": b.age.min,
        "ageMax": b.age.max,
    }


def compare_benefits(
    benefit_ids: list[str],
    profile: Optional[dict[str, Any]] = None,
) -> list[dict[str, Any]]:
    """Compare up to 3 benefits on rule-computable fields.

    Args:
        benefit_ids: 비교할 혜택 ID 목록 (최대 3개).
        profile: 공개 가능한 프로필 일부 (선택).
    Differences that can be computed by rules are computed here, not by the model.
    """
    ids = list(benefit_ids)[:3]
    rows: list[dict[str, Any]] = []
    for bid in ids:
        b = _BY_ID.get(bid)
        if b is None:
            rows.append({"benefitId": bid, "error": "benefit_not_found"})
            continue
        rows.append(
            {
                "benefitId": b.id,
                "title": b.title,
                "provider": b.provider,
                "category": b.category.value,
                "benefitText": b.benefitText,
                "eligibilityText": b.eligibilityText,
                "deadline": b.deadline.isoformat() if b.deadline else "상시(확인 필요)",
                "requiredDocumentsCount": len(b.requiredDocuments),
                "requiredDocuments": b.requiredDocuments,
                "applicationStepsCount": len(b.applicationSteps),
                "firstAction": b.applicationSteps[0] if b.applicationSteps else "확인 필요",
                "sourceUrl": b.sourceUrl,
                "verifiedAt": b.verifiedAt.isoformat(),
            }
        )
    return rows


def get_source_metadata(benefit_id: str) -> dict[str, Any]:
    """Return the trusted source metadata (url, agency, verified date) for a benefit.

    Args:
        benefit_id: 카탈로그에 존재하는 혜택 ID.
    """
    b = _BY_ID.get(benefit_id)
    if b is None:
        return {"error": "benefit_not_found", "benefitId": benefit_id}
    return {
        "benefitId": b.id,
        "sourceUrl": b.sourceUrl,
        "sourceAgency": b.sourceAgency,
        "verifiedAt": b.verifiedAt.isoformat(),
    }


def _age_to_band(age: Optional[int]) -> str:
    if age is None:
        return "18_24"
    if age < 18:
        return "under_18"
    if age <= 24:
        return "18_24"
    if age <= 29:
        return "25_29"
    if age <= 34:
        return "30_34"
    return "35_plus"


ALL_TOOLS = [search_benefits, get_benefit_detail, compare_benefits, get_source_metadata]
