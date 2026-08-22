"""Cosmos DB catalog writer.

Only this module writes benefits. The curator agent has no database access, per
AGENTS.md section 8.2.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from azure.cosmos.aio import CosmosClient
from azure.cosmos.exceptions import CosmosResourceNotFoundError
from azure.identity.aio import DefaultAzureCredential

from app.domain.benefit import Benefit

logger = logging.getLogger(__name__)


@dataclass
class ExistingBenefit:
    id: str
    category: str
    content_hash: str


@dataclass
class UpsertReport:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    repartitioned: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def written(self) -> int:
        return self.created + self.updated + self.repartitioned


def _key(source_system: str, source_id: str) -> tuple[str, str]:
    return (source_system, source_id)


class BenefitRepository:
    def __init__(self, endpoint: str, database: str, container: str) -> None:
        self._endpoint = endpoint
        self._database = database
        self._container_name = container
        self._credential: DefaultAzureCredential | None = None
        self._client: CosmosClient | None = None
        self._container = None

    @property
    def configured(self) -> bool:
        return bool(self._endpoint)

    async def __aenter__(self) -> "BenefitRepository":
        if not self.configured:
            return self
        self._credential = DefaultAzureCredential()
        self._client = CosmosClient(self._endpoint, credential=self._credential)
        database = self._client.get_database_client(self._database)
        self._container = database.get_container_client(self._container_name)
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        if self._client is not None:
            await self._client.close()
        if self._credential is not None:
            await self._credential.close()

    async def load_existing(self) -> dict[tuple[str, str], ExistingBenefit]:
        """Index the catalog by upstream identity so reruns stay idempotent."""
        if self._container is None:
            return {}
        query = (
            "SELECT c.id, c.category, c.contentHash, c.sourceSystem, c.sourceId FROM c"
        )
        existing: dict[tuple[str, str], ExistingBenefit] = {}
        async for item in self._container.query_items(query=query):
            source_system = item.get("sourceSystem") or ""
            source_id = item.get("sourceId") or ""
            if not source_id:
                continue
            existing[_key(source_system, source_id)] = ExistingBenefit(
                id=item["id"],
                category=item.get("category") or "",
                content_hash=item.get("contentHash") or "",
            )
        return existing

    async def sync(self, benefits: list[Benefit], dry_run: bool = False) -> UpsertReport:
        report = UpsertReport()
        if self._container is None:
            report.errors.append("cosmos endpoint not configured; skipped write")
            return report

        existing = await self.load_existing()

        for benefit in benefits:
            key = _key(benefit.source_system, benefit.source_id)
            previous = existing.get(key)

            if previous is not None and previous.content_hash == benefit.content_hash:
                report.unchanged += 1
                continue

            if dry_run:
                report.updated += 1 if previous else 0
                report.created += 0 if previous else 1
                continue

            try:
                # A changed category moves the item to a new partition, so the
                # stale copy has to be removed explicitly.
                if previous is not None and previous.category != benefit.category:
                    await self._delete(previous)
                    report.repartitioned += 1
                elif previous is not None:
                    report.updated += 1
                else:
                    report.created += 1

                await self._container.upsert_item(benefit.to_cosmos_item())
            except Exception as exc:  # noqa: BLE001 - recorded, never silently dropped
                logger.exception("upsert failed", extra={"benefitId": benefit.id})
                report.errors.append(f"{benefit.id}: {exc.__class__.__name__}")

        return report

    async def _delete(self, previous: ExistingBenefit) -> None:
        try:
            await self._container.delete_item(
                item=previous.id, partition_key=previous.category
            )
        except CosmosResourceNotFoundError:
            logger.info("stale item already gone", extra={"benefitId": previous.id})
