"""Benefit catalog domain model.

Field names mirror the catalog contract in TRD section 4.3 so the ingestion
job and the recommendation API agree on one shape.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

BenefitCategory = Literal["생활", "주거", "교육", "취업", "의료", "금융", "심리"]
BenefitStatus = Literal["active", "review_needed", "stale", "archived"]
FitLevel = Literal["high", "medium", "low"]


class AgeRange(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    min: int | None = Field(default=None, ge=0, le=120)
    max: int | None = Field(default=None, ge=0, le=120)


class Benefit(BaseModel):
    """A curated benefit as stored in Cosmos DB."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(min_length=3, max_length=120)
    title: str = Field(min_length=2, max_length=200)
    provider: str = Field(min_length=2, max_length=120)
    category: BenefitCategory
    regions: list[str] = Field(min_length=1, max_length=40)
    age: AgeRange = Field(default_factory=AgeRange)
    eligibility_text: str = Field(alias="eligibilityText", max_length=2000)
    benefit_text: str = Field(alias="benefitText", max_length=2000)
    application_steps: list[str] = Field(alias="applicationSteps", max_length=12)
    required_documents: list[str] = Field(
        alias="requiredDocuments", default_factory=list, max_length=12
    )
    deadline: date | None = None
    source_url: HttpUrl = Field(alias="sourceUrl")
    source_agency: str = Field(alias="sourceAgency", max_length=120)
    verified_at: date = Field(alias="verifiedAt")
    status: BenefitStatus = "active"

    # Ingestion provenance. Lets us prove where every row came from.
    source_system: str = Field(alias="sourceSystem", default="snapshot")
    source_id: str = Field(alias="sourceId", default="")
    content_hash: str = Field(alias="contentHash", default="")
    ingested_at: datetime | None = Field(alias="ingestedAt", default=None)

    def to_cosmos_item(self) -> dict[str, Any]:
        return self.model_dump(mode="json", by_alias=True)


class RawRecord(BaseModel):
    """One untouched record as returned by an upstream source."""

    source_system: str
    source_id: str
    source_url: str
    source_agency: str
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload: dict[str, Any]

    @property
    def content_hash(self) -> str:
        canonical = json.dumps(self.payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def archive_blob_name(self) -> str:
        day = self.fetched_at.strftime("%Y/%m/%d")
        safe_id = self.source_id.replace("/", "_")[:100]
        return f"{self.source_system}/{day}/{safe_id}.json"
