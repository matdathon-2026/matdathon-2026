"""Ingestion pipeline orchestration.

    fetch (allowlisted, deterministic)
      -> archive raw payload
      -> normalise (curator agent, or passthrough for snapshots)
      -> validate (deterministic gate)
      -> upsert into Cosmos DB (idempotent)

Each stage reports counts so a scheduled run is auditable in Azure Monitor.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.domain.benefit import Benefit, RawRecord
from app.ingestion.archive import RawArchive
from app.ingestion.http_client import build_client
from app.ingestion.normalizer import (
    CatalogCuratorAgent,
    NormalizationError,
    passthrough_normalize,
)
from app.ingestion.repository import BenefitRepository, UpsertReport
from app.ingestion.sources import (
    DataGoKrSource,
    SnapshotSource,
    SourceAdapter,
    SourceError,
    YouthCenterSource,
)
from app.ingestion.sources.snapshot import NAME as SNAPSHOT_NAME
from app.ingestion.validator import RejectedCandidate, validate_candidate
from app.settings import Settings

logger = logging.getLogger(__name__)


@dataclass
class RunReport:
    fetched: int = 0
    archived: int = 0
    normalized: int = 0
    rejected: int = 0
    source_errors: list[str] = field(default_factory=list)
    rejections: list[str] = field(default_factory=list)
    upserts: UpsertReport = field(default_factory=UpsertReport)

    def as_dict(self) -> dict[str, Any]:
        return {
            "fetched": self.fetched,
            "archived": self.archived,
            "normalized": self.normalized,
            "rejected": self.rejected,
            "created": self.upserts.created,
            "updated": self.upserts.updated,
            "unchanged": self.upserts.unchanged,
            "repartitioned": self.upserts.repartitioned,
            "sourceErrors": self.source_errors,
            "rejections": self.rejections[:20],
            "writeErrors": self.upserts.errors,
        }


def build_sources(settings: Settings) -> list[SourceAdapter]:
    return [
        YouthCenterSource(
            api_key=settings.youthcenter_api_key,
            enabled=settings.youthcenter_enabled,
            max_records=settings.ingest_max_records_per_source,
        ),
        DataGoKrSource(
            service_key=settings.data_go_kr_service_key,
            enabled=settings.data_go_kr_enabled,
            max_records=settings.ingest_max_records_per_source,
        ),
        SnapshotSource(
            path=settings.snapshot_path,
            enabled=settings.snapshot_enabled,
        ),
    ]


def build_curator(settings: Settings) -> CatalogCuratorAgent | None:
    """Create the curator agent, or None when the model is not configured.

    A missing model degrades the run to snapshot-only ingestion instead of
    failing, so a demo never depends on model availability.
    """
    if not (settings.foundry_resource_url and settings.foundry_model):
        logger.warning("foundry model not configured; curator disabled")
        return None
    try:
        from app.ai.provider import build_foundry_provider

        return CatalogCuratorAgent.create(
            foundry_provider=build_foundry_provider(settings),
            model=settings.foundry_model,
            timeout_seconds=settings.ai_timeout_seconds,
        )
    except ImportError:
        logger.warning("agent framework packages unavailable; curator disabled")
        return None


async def collect_raw(
    sources: list[SourceAdapter], settings: Settings, report: RunReport
) -> list[RawRecord]:
    records: list[RawRecord] = []
    async with build_client(settings.http_timeout_seconds) as client:
        for source in sources:
            if not source.enabled():
                logger.info("source skipped", extra={"source": source.name})
                continue
            try:
                fetched = await source.fetch(client)
            except SourceError as exc:
                report.source_errors.append(str(exc))
                logger.warning("source failed", extra={"source": source.name})
                continue
            logger.info(
                "source fetched", extra={"source": source.name, "count": len(fetched)}
            )
            records.extend(fetched)
    report.fetched = len(records)
    return records


async def normalize_all(
    records: list[RawRecord],
    curator: CatalogCuratorAgent | None,
    report: RunReport,
) -> list[Benefit]:
    benefits: list[Benefit] = []
    for record in records:
        try:
            if record.source_system == SNAPSHOT_NAME:
                candidate = passthrough_normalize(record)
            elif curator is not None:
                candidate = await curator.normalize(record)
            else:
                report.rejected += 1
                report.rejections.append(f"{record.source_id}: curator unavailable")
                continue
        except NormalizationError as exc:
            report.rejected += 1
            report.rejections.append(str(exc))
            continue

        try:
            benefits.append(validate_candidate(candidate, record))
        except RejectedCandidate as exc:
            report.rejected += 1
            report.rejections.append(str(exc))
            continue

    report.normalized = len(benefits)
    return benefits


def deduplicate(benefits: list[Benefit]) -> list[Benefit]:
    """Later sources must not overwrite an earlier record with the same id."""
    seen: dict[str, Benefit] = {}
    for benefit in benefits:
        seen.setdefault(benefit.id, benefit)
    return list(seen.values())


async def run_ingestion(settings: Settings) -> RunReport:
    report = RunReport()

    records = await collect_raw(build_sources(settings), settings, report)

    async with RawArchive(
        settings.ingest_archive_account_url, settings.ingest_archive_container
    ) as archive:
        for record in records:
            if await archive.store(record):
                report.archived += 1

    benefits = deduplicate(await normalize_all(records, build_curator(settings), report))

    async with BenefitRepository(
        settings.cosmos_endpoint,
        settings.cosmos_database,
        settings.cosmos_benefits_container,
    ) as repository:
        report.upserts = await repository.sync(benefits, dry_run=settings.ingest_dry_run)

    return report
