"""Post-validation of agent output. Enforces the trust boundary:

- reject unknown benefit ids,
- overwrite source_url / verified_at from the catalog (model cannot fabricate them),
- clamp fit to the allowed set,
- ensure at least one recommendation with a source survives.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any

from app.domain.models import ActionStep, Benefit
from app.schemas import BenefitCard

_FIT_ALLOWED = {"high", "medium", "low"}
_GUARANTEE_PATTERNS = [
    re.compile(r"반드시\s*받"),
    re.compile(r"100%\s*지급"),
    re.compile(r"무조건"),
]


class ValidationFailure(Exception):
    pass


def _soften(text: str) -> str:
    for pat in _GUARANTEE_PATTERNS:
        if pat.search(text):
            return text  # keep, but caller may flag; we simply don't guarantee
    return text


def validate_recommendations(
    raw: dict[str, Any],
    by_id: dict[str, Benefit],
    allowed_ids: set[str],
) -> tuple[str, list[BenefitCard]]:
    """Return (summary, cards). Raises ValidationFailure when nothing valid remains."""
    recs = raw.get("recommendations")
    if not isinstance(recs, list) or not recs:
        raise ValidationFailure("no recommendations array")

    summary = str(raw.get("summary") or "프로필에 맞는 지원제도를 정리했어요.")
    cards: list[BenefitCard] = []
    for item in recs:
        if not isinstance(item, dict):
            continue
        bid = item.get("benefitId") or item.get("benefit_id")
        if not bid or bid not in by_id:
            continue  # reject hallucinated / unknown ids
        if allowed_ids and bid not in allowed_ids:
            continue  # only ids that passed the deterministic prefilter
        b = by_id[bid]
        fit = str(item.get("fit", "medium")).lower()
        if fit not in _FIT_ALLOWED:
            fit = "medium"
        reasons = _as_str_list(item.get("reasons") or item.get("reason"))
        if not reasons:
            reasons = ["프로필의 지역·연령·관심 분야 조건에 맞는 제도입니다."]
        uncertainties = _as_str_list(item.get("uncertainties"))
        next_action = str(
            item.get("nextAction")
            or item.get("next_action")
            or (b.applicationSteps[0] if b.applicationSteps else "공식 출처에서 신청 방법을 확인하세요.")
        )
        cards.append(
            BenefitCard(
                benefit_id=b.id,
                title=b.title,
                provider=b.provider,
                category=b.category.value,
                fit=fit,
                reasons=[_soften(r) for r in reasons][:4],
                uncertainties=uncertainties[:4],
                next_action=_soften(next_action),
                # trust boundary: always from the catalog, never the model
                source_url=b.sourceUrl,
                source_agency=b.sourceAgency,
                verified_at=b.verifiedAt,
                deadline=b.deadline,
            )
        )
        if len(cards) >= 3:
            break

    if not cards:
        raise ValidationFailure("no valid recommendation survived validation")
    return summary, cards


def validate_plan_draft(
    raw: dict[str, Any],
    benefit: Benefit,
) -> dict[str, Any]:
    """Validate a plan draft, overwriting source fields and clamping values."""
    steps_raw = raw.get("steps")
    if not isinstance(steps_raw, list) or not steps_raw:
        raise ValidationFailure("no steps in plan draft")

    steps: list[ActionStep] = []
    for idx, s in enumerate(steps_raw[:10]):
        if not isinstance(s, dict):
            continue
        minutes = s.get("estimatedMinutes") or s.get("estimated_minutes") or 30
        try:
            minutes = int(minutes)
        except (TypeError, ValueError):
            minutes = 30
        minutes = max(1, min(minutes, 240))
        title = str(s.get("title") or f"단계 {idx + 1}")
        steps.append(
            ActionStep(
                id=f"step-{idx}",
                title=title[:120],
                description=str(s.get("description") or title)[:600],
                estimated_minutes=minutes,
                order=idx,
                status="todo",
            )
        )
    if not steps:
        raise ValidationFailure("no valid steps after validation")

    deadline = _parse_date(raw.get("deadline"))
    # Never invent a deadline the catalog doesn't have.
    if benefit.deadline is None:
        deadline = None
    else:
        deadline = benefit.deadline

    required = _as_str_list(raw.get("requiredDocuments") or raw.get("required_documents"))
    if not required:
        required = list(benefit.requiredDocuments)

    return {
        "benefit_id": benefit.id,
        "title": str(raw.get("title") or f"{benefit.title} 신청 계획")[:120],
        "deadline": deadline,
        "required_documents": required,
        "steps": steps,
        "uncertainties": _as_str_list(raw.get("uncertainties")),
        "source_url": benefit.sourceUrl,
        "apply_url": benefit.sourceUrl,
    }


def _as_str_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(v) for v in value if str(v).strip()]
    return []


def _parse_date(value: Any) -> date | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None
