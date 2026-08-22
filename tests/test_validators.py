import pytest

from app.agents.validators import ValidationFailure, validate_recommendations
from app.domain.models import AgeRange, Benefit, BenefitCategory
from datetime import date


def _benefit(bid):
    return Benefit(
        id=bid,
        title=f"title-{bid}",
        provider="p",
        category=BenefitCategory.housing,
        regions=["ALL"],
        age=AgeRange(min=18, max=34),
        eligibilityText="e",
        benefitText="b",
        applicationSteps=["첫 단계"],
        requiredDocuments=["d"],
        deadline=None,
        sourceUrl="https://real.gov.kr",
        sourceAgency="agency",
        verifiedAt=date(2026, 8, 22),
        status="active",
    )


def _catalog():
    by_id = {b.id: b for b in [_benefit("real-1"), _benefit("real-2")]}
    return by_id, set(by_id.keys())


def test_hallucinated_benefit_id_is_rejected():
    by_id, allowed = _catalog()
    raw = {
        "summary": "s",
        "recommendations": [
            {"benefitId": "does-not-exist", "fit": "high", "reasons": ["x"], "nextAction": "a"}
        ],
    }
    with pytest.raises(ValidationFailure):
        validate_recommendations(raw, by_id, allowed)


def test_source_url_and_verified_at_overwritten_from_catalog():
    by_id, allowed = _catalog()
    raw = {
        "summary": "s",
        "recommendations": [
            {
                "benefitId": "real-1",
                "fit": "high",
                "reasons": ["맞아요"],
                "uncertainties": [],
                "nextAction": "신청하세요",
                "sourceUrl": "https://evil.example.com/phish",
                "verifiedAt": "1999-01-01",
            }
        ],
    }
    summary, cards = validate_recommendations(raw, by_id, allowed)
    assert len(cards) == 1
    # model-provided source is discarded; catalog value wins
    assert cards[0].source_url == "https://real.gov.kr"
    assert str(cards[0].verified_at) == "2026-08-22"


def test_invalid_fit_defaults_to_medium():
    by_id, allowed = _catalog()
    raw = {
        "summary": "s",
        "recommendations": [
            {"benefitId": "real-2", "fit": "amazing", "reasons": ["r"], "nextAction": "a"}
        ],
    }
    _, cards = validate_recommendations(raw, by_id, allowed)
    assert cards[0].fit == "medium"
