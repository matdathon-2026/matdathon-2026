"""Guest profile and the deterministic eligibility pre-filter.

The pre-filter is pure so it can be unit tested and so the agent never gets to
decide who is eligible. AGENTS.md section 5.3: the AI explains, the code decides.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.benefit import Benefit

Region = Literal[
    "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종",
    "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주", "전국",
]

Situation = Literal["자립준비청년", "보호연장아동", "가정위탁 종료", "잘 모르겠어요"]
HousingStatus = Literal["월세", "전세", "자가", "기숙사/시설", "주거 불안정", "잘 모르겠어요"]
EmploymentStatus = Literal["재학중", "구직중", "재직중", "쉬고 있어요", "잘 모르겠어요"]

NATIONWIDE = "전국"
# The ingestion curator emits "ALL" for a nationwide programme; a hand-written
# snapshot may use the Korean word. Both mean the same thing.
NATIONWIDE_TOKENS = frozenset({"ALL", "전국"})
UNKNOWN = "잘 모르겠어요"


def is_nationwide(benefit: Benefit) -> bool:
    return any(region in NATIONWIDE_TOKENS for region in benefit.regions)


class Profile(BaseModel):
    """Everything we ask a guest for. AGENTS.md section 11 caps this at 6 fields."""

    model_config = ConfigDict(populate_by_name=True)

    age: int = Field(ge=15, le=45)
    region: Region
    situation: Situation = UNKNOWN
    interests: list[str] = Field(default_factory=list, max_length=7)
    housing_status: HousingStatus = Field(alias="housingStatus", default=UNKNOWN)
    employment_status: EmploymentStatus = Field(alias="employmentStatus", default=UNKNOWN)


def matches_age(benefit: Benefit, age: int) -> bool:
    if benefit.age.min is not None and age < benefit.age.min:
        return False
    if benefit.age.max is not None and age > benefit.age.max:
        return False
    return True


def matches_region(benefit: Benefit, region: str) -> bool:
    """A nationwide benefit fits everyone; a local one only fits its own region."""
    if is_nationwide(benefit):
        return True
    if region in NATIONWIDE_TOKENS:
        return True
    return region in benefit.regions


def is_open(benefit: Benefit, today: date) -> bool:
    """A benefit whose deadline has passed is never recommended."""
    return benefit.deadline is None or benefit.deadline >= today


def prefilter(benefits: list[Benefit], profile: Profile, today: date) -> list[Benefit]:
    """Narrow the catalog before the agent ever sees it.

    Anything this function drops can never be recommended, so eligibility can
    not be hallucinated into existence by the model.
    """
    return [
        benefit
        for benefit in benefits
        if benefit.status in {"active", "review_needed"}
        and matches_age(benefit, profile.age)
        and matches_region(benefit, profile.region)
        and is_open(benefit, today)
    ]


def rank(benefits: list[Benefit], profile: Profile, today: date) -> list[Benefit]:
    """Order candidates by how well they line up with the stated profile.

    This is the rule-based ordering the API falls back to when the AI is
    unavailable, and the shortlist the agent is asked to explain otherwise.
    """
    interests = set(profile.interests)

    def score(benefit: Benefit) -> tuple[int, int, int, str]:
        points = 0
        if benefit.category in interests:
            points += 40
        if not is_nationwide(benefit):
            points += 15  # a local programme is a tighter match than a national one
        if profile.housing_status == "주거 불안정" and benefit.category == "주거":
            points += 20
        if profile.employment_status == "구직중" and benefit.category == "취업":
            points += 20
        if profile.employment_status == "재학중" and benefit.category == "교육":
            points += 15
        if profile.situation in {"자립준비청년", "보호연장아동", "가정위탁 종료"}:
            points += 10

        # Prefer things that close soon and, all else equal, recently verified data.
        days_left = (benefit.deadline - today).days if benefit.deadline else 9999
        urgency = 1 if days_left <= 30 else 0
        freshness = benefit.verified_at.toordinal()
        return (points, urgency, freshness, benefit.id)

    return sorted(benefits, key=score, reverse=True)


def rule_based_fit(benefit: Benefit, profile: Profile) -> str:
    """Fit level used when the AI is unavailable."""
    if benefit.category in set(profile.interests):
        return "high"
    if not is_nationwide(benefit):
        return "medium"
    return "medium"


def rule_based_reasons(benefit: Benefit, profile: Profile, today: date) -> list[str]:
    """Explain a rule-based match using only facts taken from the catalog row."""
    reasons: list[str] = []
    if benefit.category in set(profile.interests):
        reasons.append(f"관심 분야로 고른 '{benefit.category}' 지원사업이에요.")
    if is_nationwide(benefit):
        reasons.append("전국에서 신청할 수 있어요.")
    elif profile.region in benefit.regions:
        reasons.append(f"{profile.region} 지역에서 신청할 수 있어요.")
    if benefit.age.min is not None or benefit.age.max is not None:
        low = benefit.age.min if benefit.age.min is not None else "제한 없음"
        high = benefit.age.max if benefit.age.max is not None else "제한 없음"
        reasons.append(f"나이 조건(만 {low}~{high}세)에 해당해요.")
    if benefit.deadline is not None:
        reasons.append(f"신청 마감이 {benefit.deadline.isoformat()}까지 남아 있어요.")
    return reasons or ["프로필에서 확인한 기본 조건을 충족해요."]
