from datetime import date, timedelta

from app.domain.filters import age_matches, deadline_open, prefilter, region_matches
from app.domain.models import AgeRange, Benefit, BenefitCategory


def _benefit(**kw) -> Benefit:
    base = dict(
        id="b1",
        title="t",
        provider="p",
        category=BenefitCategory.housing,
        regions=["ALL"],
        age=AgeRange(min=18, max=34),
        eligibilityText="e",
        benefitText="b",
        applicationSteps=["s"],
        requiredDocuments=["d"],
        deadline=None,
        sourceUrl="https://example.gov",
        sourceAgency="agency",
        verifiedAt=date(2026, 8, 22),
        status="active",
    )
    base.update(kw)
    return Benefit(**base)


def test_region_all_matches_any():
    b = _benefit(regions=["ALL"])
    assert region_matches(b, "seoul")
    assert region_matches(b, "jeju")


def test_region_specific_matches_only_that_region():
    b = _benefit(regions=["seoul"])
    assert region_matches(b, "seoul")
    assert not region_matches(b, "busan")


def test_age_overlap():
    b = _benefit(age=AgeRange(min=19, max=34))
    assert age_matches(b, "18_24")   # 18-24 overlaps 19-34
    assert age_matches(b, "30_34")
    assert not age_matches(b, "under_18")  # 15-17 vs 19-34
    assert not age_matches(b, "35_plus")   # 35-120 vs 19-34


def test_age_open_max():
    b = _benefit(age=AgeRange(min=18, max=None))
    assert age_matches(b, "35_plus")
    assert age_matches(b, "18_24")


def test_deadline_open_and_closed():
    today = date(2026, 8, 22)
    assert deadline_open(_benefit(deadline=None), today)
    assert deadline_open(_benefit(deadline=today), today)
    assert deadline_open(_benefit(deadline=today + timedelta(days=1)), today)
    assert not deadline_open(_benefit(deadline=today - timedelta(days=1)), today)


def test_prefilter_excludes_wrong_region_age_and_closed():
    today = date(2026, 8, 22)
    catalog = [
        _benefit(id="ok", regions=["ALL"], age=AgeRange(min=18, max=34)),
        _benefit(id="wrong_region", regions=["busan"]),
        _benefit(id="too_old_only", age=AgeRange(min=40, max=50)),
        _benefit(id="closed", deadline=today - timedelta(days=1)),
        _benefit(id="inactive", status="inactive"),
    ]
    got = {b.id for b in prefilter(catalog, region="seoul", age_band="18_24", today=today)}
    assert got == {"ok"}
