"""Deterministic gate between model output and the catalog.

Nothing reaches Cosmos DB unless it passes here. The rules exist to catch
hallucinated sources, invented dates and oversized text, per AGENTS.md
sections 8.3 and 10.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timezone
from typing import Any

from pydantic import ValidationError

from app.domain.benefit import Benefit, RawRecord
from app.ingestion.allowlist import host_of, is_allowed

SLUG_RE = re.compile(r"[^a-z0-9]+")
MAX_TEXT = 2000
MAX_LIST_ITEMS = 12


class RejectedCandidate(Exception):
    """A candidate failed validation and must not be stored."""

    def __init__(self, source_id: str, reason: str) -> None:
        super().__init__(f"{source_id}: {reason}")
        self.source_id = source_id
        self.reason = reason


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii").lower()
    return SLUG_RE.sub("-", ascii_only).strip("-")


def build_benefit_id(record: RawRecord, title: str) -> str:
    tail = slugify(title) or slugify(record.source_id) or "benefit"
    return f"{record.source_system}-{record.source_id}-{tail}"[:120].strip("-")


def _clean_text(value: Any, limit: int = MAX_TEXT) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())[:limit]


def _clean_list(value: Any) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    cleaned = [_clean_text(item, 300) for item in value]
    return [item for item in cleaned if item][:MAX_LIST_ITEMS]


def _parse_date(value: Any) -> date | None:
    if value in (None, "", "null"):
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y.%m.%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def validate_candidate(
    candidate: dict[str, Any],
    record: RawRecord,
    today: date | None = None,
) -> Benefit:
    """Turn raw curator output into a storable Benefit or raise RejectedCandidate."""
    today = today or datetime.now(timezone.utc).date()

    title = _clean_text(candidate.get("title"), 200)
    if not title:
        raise RejectedCandidate(record.source_id, "missing title")

    # Provenance is owned by the pipeline, never by the model. A curator that
    # tries to supply its own sourceUrl is ignored outright.
    source_url = record.source_url.strip()
    if not source_url:
        raise RejectedCandidate(record.source_id, "record has no source url")
    if not is_allowed(source_url):
        raise RejectedCandidate(
            record.source_id, f"source host not allowlisted: {host_of(source_url)}"
        )

    verified_at = _parse_date(candidate.get("verifiedAt")) or record.fetched_at.date()
    if verified_at > today:
        raise RejectedCandidate(record.source_id, "verifiedAt is in the future")

    deadline = _parse_date(candidate.get("deadline"))
    status = "active"
    if deadline is not None and deadline < today:
        status = "stale"

    age_raw = candidate.get("age")
    age = age_raw if isinstance(age_raw, dict) else {}
    age_min, age_max = age.get("min"), age.get("max")
    if isinstance(age_min, int) and isinstance(age_max, int) and age_min > age_max:
        raise RejectedCandidate(record.source_id, "age.min greater than age.max")

    regions = _clean_list(candidate.get("regions")) or ["ALL"]

    payload = {
        "id": build_benefit_id(record, title),
        "title": title,
        "provider": _clean_text(candidate.get("provider"), 120)
        or record.source_agency
        or "미확인",
        "category": candidate.get("category"),
        "regions": regions,
        "age": {"min": age_min, "max": age_max},
        "eligibilityText": _clean_text(candidate.get("eligibilityText")),
        "benefitText": _clean_text(candidate.get("benefitText")),
        "applicationSteps": _clean_list(candidate.get("applicationSteps")),
        "requiredDocuments": _clean_list(candidate.get("requiredDocuments")),
        "deadline": deadline.isoformat() if deadline else None,
        "sourceUrl": source_url,
        "sourceAgency": _clean_text(record.source_agency, 120) or "미확인",
        "verifiedAt": verified_at.isoformat(),
        "status": status,
        "sourceSystem": record.source_system,
        "sourceId": record.source_id,
        "contentHash": record.content_hash,
        "ingestedAt": datetime.now(timezone.utc).isoformat(),
    }

    try:
        benefit = Benefit.model_validate(payload)
    except ValidationError as exc:
        first = exc.errors()[0]
        location = ".".join(str(part) for part in first["loc"])
        raise RejectedCandidate(
            record.source_id, f"schema error at {location}: {first['msg']}"
        ) from exc

    # A card with no eligibility text and no next action is not actionable, and
    # PRD FR-03 forbids showing it.
    if not benefit.eligibility_text and not benefit.application_steps:
        raise RejectedCandidate(
            record.source_id, "no eligibility text and no application steps"
        )

    return benefit
