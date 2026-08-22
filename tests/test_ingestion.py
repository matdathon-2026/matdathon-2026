from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from app.domain.benefit import RawRecord
from app.ingestion.allowlist import HostNotAllowedError, ensure_allowed, is_allowed
from app.ingestion.normalizer import (
    NormalizationError,
    build_curator_prompt,
    parse_curator_output,
)
from app.ingestion.pipeline import deduplicate
from app.ingestion.sources.base import find_record_list, pick_source_id
from app.ingestion.validator import RejectedCandidate, validate_candidate

TODAY = date(2026, 8, 22)


def make_record(**overrides) -> RawRecord:
    defaults = {
        "source_system": "youthcenter",
        "source_id": "PLC0001",
        "source_url": "https://www.youthcenter.go.kr/youthPolicy/ythPlcyDetail?plcyNo=PLC0001",
        "source_agency": "온통청년",
        "fetched_at": datetime(2026, 8, 22, tzinfo=timezone.utc),
        "payload": {"plcyNo": "PLC0001", "plcyNm": "청년 자립 지원"},
    }
    defaults.update(overrides)
    return RawRecord(**defaults)


def good_candidate(**overrides) -> dict:
    candidate = {
        "title": "자립수당",
        "provider": "보건복지부",
        "category": "living",
        "regions": ["ALL"],
        "age": {"min": 18, "max": None},
        "eligibilityText": "보호가 종료된 자립준비청년",
        "benefitText": "매월 자립수당 지급",
        "applicationSteps": ["행정복지센터 방문"],
        "requiredDocuments": ["신분증"],
        "deadline": None,
    }
    candidate.update(overrides)
    return candidate


class TestAllowlist:
    def test_government_hosts_are_allowed(self):
        assert is_allowed("https://www.youthcenter.go.kr/go/ythip/getPlcy")
        assert is_allowed("https://apis.data.go.kr/B554287/x")

    def test_arbitrary_host_is_rejected(self):
        assert not is_allowed("https://evil.example.com/steal")
        with pytest.raises(HostNotAllowedError):
            ensure_allowed("https://evil.example.com/steal")

    def test_lookalike_host_is_rejected(self):
        assert not is_allowed("https://www.youthcenter.go.kr.evil.com/x")


class TestRecordExtraction:
    def test_finds_records_in_nested_envelope(self):
        payload = {"result": {"pagging": {"totCount": 2}, "youthPolicyList": [{"a": 1}, {"a": 2}]}}
        assert find_record_list(payload) == [{"a": 1}, {"a": 2}]

    def test_finds_records_in_alternate_envelope(self):
        payload = {"response": {"body": {"items": {"item": [{"servId": "X"}]}}}}
        assert find_record_list(payload) == [{"servId": "X"}]

    def test_missing_id_falls_back(self):
        assert pick_source_id({"plcyNo": "P1"}, "fb") == "P1"
        assert pick_source_id({"nothing": 1}, "fb") == "fb"


class TestCuratorOutputParsing:
    def test_parses_code_fenced_json(self):
        assert parse_curator_output('```json\n{"title": "x"}\n```') == {"title": "x"}

    def test_parses_json_with_surrounding_prose(self):
        assert parse_curator_output('결과입니다:\n{"title": "x"}\n감사합니다') == {"title": "x"}

    def test_rejects_non_json(self):
        with pytest.raises(NormalizationError):
            parse_curator_output("죄송하지만 변환할 수 없습니다")

    def test_prompt_marks_record_as_untrusted_data(self):
        prompt = build_curator_prompt(make_record())
        assert "<record>" in prompt
        assert "신뢰할 수 없는 외부 데이터" in prompt


class TestValidator:
    def test_accepts_a_good_candidate(self):
        benefit = validate_candidate(good_candidate(), make_record(), today=TODAY)
        assert benefit.title == "자립수당"
        assert benefit.status == "active"
        assert benefit.source_system == "youthcenter"
        assert benefit.content_hash

    def test_snapshot_preserves_catalog_id_and_maps_korean_category(self):
        record = make_record(
            source_system="snapshot",
            source_id="self-reliance-allowance",
        )
        candidate = good_candidate(id="self-reliance-allowance", category="생활")
        benefit = validate_candidate(candidate, record, today=TODAY)
        assert benefit.id == "self-reliance-allowance"
        assert benefit.category == "living"

    def test_provenance_comes_from_the_record_not_the_model(self):
        # A curator that invents its own source must not be able to override it.
        candidate = good_candidate(
            sourceUrl="https://evil.example.com/fake",
            sourceAgency="가짜기관",
        )
        benefit = validate_candidate(candidate, make_record(), today=TODAY)
        assert str(benefit.source_url).startswith("https://www.youthcenter.go.kr/")
        assert benefit.source_agency == "온통청년"

    def test_rejects_record_whose_source_host_is_not_allowlisted(self):
        record = make_record(source_url="https://evil.example.com/fake")
        with pytest.raises(RejectedCandidate, match="not allowlisted"):
            validate_candidate(good_candidate(), record, today=TODAY)

    def test_rejects_missing_title(self):
        with pytest.raises(RejectedCandidate, match="missing title"):
            validate_candidate(good_candidate(title="  "), make_record(), today=TODAY)

    def test_rejects_invalid_category(self):
        with pytest.raises(RejectedCandidate, match="category"):
            validate_candidate(
                good_candidate(category="아무거나"), make_record(), today=TODAY
            )

    def test_rejects_future_verified_at(self):
        candidate = good_candidate(verifiedAt="2030-01-01")
        with pytest.raises(RejectedCandidate, match="future"):
            validate_candidate(candidate, make_record(), today=TODAY)

    def test_rejects_inverted_age_range(self):
        candidate = good_candidate(age={"min": 40, "max": 20})
        with pytest.raises(RejectedCandidate, match="age.min"):
            validate_candidate(candidate, make_record(), today=TODAY)

    def test_rejects_candidate_with_no_actionable_content(self):
        candidate = good_candidate(eligibilityText="", applicationSteps=[])
        with pytest.raises(RejectedCandidate, match="no eligibility text"):
            validate_candidate(candidate, make_record(), today=TODAY)

    def test_past_deadline_is_marked_stale_not_hidden(self):
        candidate = good_candidate(deadline=(TODAY - timedelta(days=1)).isoformat())
        benefit = validate_candidate(candidate, make_record(), today=TODAY)
        assert benefit.status == "stale"

    def test_accepts_alternate_date_formats(self):
        candidate = good_candidate(deadline="20261231")
        benefit = validate_candidate(candidate, make_record(), today=TODAY)
        assert benefit.deadline == date(2026, 12, 31)

    def test_oversized_text_is_truncated_not_rejected(self):
        candidate = good_candidate(benefitText="가" * 9000)
        benefit = validate_candidate(candidate, make_record(), today=TODAY)
        assert len(benefit.benefit_text) <= 2000


class TestIdempotency:
    def test_same_payload_produces_same_content_hash(self):
        a = make_record(payload={"b": 2, "a": 1})
        b = make_record(payload={"a": 1, "b": 2})
        assert a.content_hash == b.content_hash

    def test_changed_payload_changes_content_hash(self):
        a = make_record(payload={"a": 1})
        b = make_record(payload={"a": 2})
        assert a.content_hash != b.content_hash

    def test_repeated_validation_is_stable(self):
        record = make_record()
        first = validate_candidate(good_candidate(), record, today=TODAY)
        second = validate_candidate(good_candidate(), record, today=TODAY)
        assert first.id == second.id
        assert first.content_hash == second.content_hash

    def test_duplicate_ids_keep_the_first_source(self):
        record = make_record()
        first = validate_candidate(good_candidate(provider="기관A"), record, today=TODAY)
        second = validate_candidate(good_candidate(provider="기관B"), record, today=TODAY)
        deduped = deduplicate([first, second])
        assert len(deduped) == 1
        assert deduped[0].provider == "기관A"
