"""Deterministic prefilter: pure functions over age / region / deadline / status.

The AI never decides eligibility gating; these rules narrow the candidate set
before the matcher agent ranks them.
"""
from __future__ import annotations

from datetime import date

from app.domain.models import AGE_BAND_RANGE, Benefit


def region_matches(benefit: Benefit, region: str) -> bool:
    regions = [r.lower() for r in benefit.regions]
    return "all" in regions or region.lower() in regions


def age_matches(benefit: Benefit, age_band: str) -> bool:
    band = AGE_BAND_RANGE.get(age_band)
    if band is None:
        return True
    band_min, band_max = band
    b_min = benefit.age.min if benefit.age.min is not None else 0
    b_max = benefit.age.max if benefit.age.max is not None else 200
    # Overlap between the band range and the benefit's accepted age range.
    return band_max >= b_min and band_min <= b_max


def deadline_open(benefit: Benefit, today: date | None = None) -> bool:
    today = today or date.today()
    if benefit.deadline is None:
        return True  # 상시 모집
    return benefit.deadline >= today


def is_active(benefit: Benefit) -> bool:
    return benefit.status == "active"


def prefilter(
    benefits: list[Benefit],
    *,
    region: str,
    age_band: str,
    today: date | None = None,
    include_closed: bool = False,
) -> list[Benefit]:
    """Return catalog entries that pass region, age, status and deadline gates."""
    out: list[Benefit] = []
    for b in benefits:
        if not is_active(b):
            continue
        if not region_matches(b, region):
            continue
        if not age_matches(b, age_band):
            continue
        if not include_closed and not deadline_open(b, today):
            continue
        out.append(b)
    return out


def rank_by_interest(
    benefits: list[Benefit],
    *,
    interests: list[str],
    urgent_need: str,
) -> list[Benefit]:
    """Stable relevance ordering used as a deterministic fallback and pre-sort.

    Urgent need weighs highest, then declared interests, then everything else.
    """
    interest_set = set(interests)

    def score(b: Benefit) -> tuple[int, int]:
        cat = b.category.value
        primary = 2 if cat == urgent_need else (1 if cat in interest_set else 0)
        # Sooner deadlines first within the same tier (None deadlines last).
        return (-primary, 0)

    return sorted(benefits, key=score)
