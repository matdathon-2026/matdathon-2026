"""Cosmos DB repository used by the Aspire deployment."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from contextlib import suppress
from pathlib import Path
from typing import Any, Optional

from azure.cosmos.aio import CosmosClient
from azure.cosmos.exceptions import (
    CosmosResourceExistsError,
    CosmosResourceNotFoundError,
)
from azure.identity.aio import DefaultAzureCredential
from pydantic import ValidationError

from app.domain.models import ActionPlan, Benefit, DemoSession, HeartTransaction
from app.repository.base import Repository

logger = logging.getLogger(__name__)


class CosmosRepository(Repository):
    """Persist the guest golden path and serve the collected benefit catalog."""

    def __init__(self, endpoint: str, database: str, seed_path: str) -> None:
        self._endpoint = endpoint
        self._database_name = database
        self._seed_path = Path(seed_path)
        self._credential: DefaultAzureCredential | None = None
        self._client: CosmosClient | None = None
        self._benefits_container: Any = None
        self._sessions_container: Any = None
        self._plans_container: Any = None
        self._ledger_container: Any = None
        self._benefits: dict[str, Benefit] = {}
        self._refresh_task: asyncio.Task[None] | None = None

    async def startup(self) -> None:
        self._credential = DefaultAzureCredential()
        self._client = CosmosClient(self._endpoint, credential=self._credential)
        database = self._client.get_database_client(self._database_name)
        self._benefits_container = database.get_container_client("benefits")
        self._sessions_container = database.get_container_client("sessions")
        self._plans_container = database.get_container_client("plans")
        self._ledger_container = database.get_container_client("heartLedger")
        await self._reload_benefits()
        if not self._benefits:
            await self._seed_benefits()
        self._refresh_task = asyncio.create_task(self._refresh_catalog())

    async def shutdown(self) -> None:
        if self._refresh_task is not None:
            self._refresh_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._refresh_task
        if self._client is not None:
            await self._client.close()
        if self._credential is not None:
            await self._credential.close()

    async def _refresh_catalog(self) -> None:
        while True:
            await asyncio.sleep(60)
            try:
                await self._reload_benefits()
            except Exception:
                logger.exception("failed to refresh the Cosmos benefit catalog")

    async def _reload_benefits(self) -> None:
        benefits: dict[str, Benefit] = {}
        async for item in self._benefits_container.query_items(
            query="SELECT * FROM c WHERE c.status = 'active'"
        ):
            try:
                benefit = Benefit.model_validate(item)
            except ValidationError:
                logger.warning(
                    "ignoring invalid Cosmos benefit", extra={"benefitId": item.get("id")}
                )
                continue
            benefits[benefit.id] = benefit
        self._benefits = benefits

    async def _seed_benefits(self) -> None:
        rows = json.loads(self._seed_path.read_text(encoding="utf-8"))
        for row in rows:
            benefit = Benefit.model_validate(row)
            canonical = json.dumps(row, ensure_ascii=False, sort_keys=True)
            item = benefit.model_dump(mode="json")
            item.update(
                {
                    "sourceSystem": "snapshot",
                    "sourceId": benefit.id,
                    "contentHash": hashlib.sha256(
                        canonical.encode("utf-8")
                    ).hexdigest(),
                }
            )
            await self._benefits_container.upsert_item(item)
            self._benefits[benefit.id] = benefit

    async def ping(self) -> bool:
        if not self._benefits:
            return False
        try:
            async for _ in self._benefits_container.query_items(
                query="SELECT TOP 1 VALUE c.id FROM c"
            ):
                return True
        except Exception:
            logger.exception("Cosmos readiness check failed")
        return False

    def list_benefits(self) -> list[Benefit]:
        return list(self._benefits.values())

    def get_benefit(self, benefit_id: str) -> Optional[Benefit]:
        return self._benefits.get(benefit_id)

    async def create_session(self, session: DemoSession) -> DemoSession:
        await self._sessions_container.create_item(
            session.model_dump(mode="json")
        )
        return session

    async def get_session(self, session_id: str) -> Optional[DemoSession]:
        try:
            item = await self._sessions_container.read_item(
                item=session_id, partition_key=session_id
            )
        except CosmosResourceNotFoundError:
            return None
        return DemoSession.model_validate(item)

    async def save_session(self, session: DemoSession) -> DemoSession:
        await self._sessions_container.upsert_item(
            session.model_dump(mode="json")
        )
        return session

    @staticmethod
    def _plan_item(plan: ActionPlan) -> dict[str, Any]:
        item = plan.model_dump(mode="json")
        item["sessionId"] = plan.session_id
        return item

    async def create_plan(self, plan: ActionPlan) -> ActionPlan:
        await self._plans_container.create_item(self._plan_item(plan))
        return plan

    async def get_plan(self, plan_id: str) -> Optional[ActionPlan]:
        item = await self._first(
            self._plans_container,
            "SELECT TOP 1 * FROM c WHERE c.id = @id",
            [{"name": "@id", "value": plan_id}],
        )
        return ActionPlan.model_validate(item) if item else None

    async def list_plans(self, session_id: str) -> list[ActionPlan]:
        rows = []
        async for item in self._plans_container.query_items(
            query="SELECT * FROM c WHERE c.sessionId = @sessionId",
            parameters=[{"name": "@sessionId", "value": session_id}],
        ):
            rows.append(ActionPlan.model_validate(item))
        return rows

    async def save_plan(self, plan: ActionPlan) -> ActionPlan:
        await self._plans_container.upsert_item(self._plan_item(plan))
        return plan

    @staticmethod
    def _ledger_item(txn: HeartTransaction) -> dict[str, Any]:
        item = txn.model_dump(mode="json")
        item["sessionId"] = txn.session_id
        return item

    async def get_txn_by_key(
        self, idempotency_key: str
    ) -> Optional[HeartTransaction]:
        item = await self._first(
            self._ledger_container,
            (
                "SELECT TOP 1 * FROM c "
                "WHERE c.idempotency_key = @key AND c.type = 'earn'"
            ),
            [{"name": "@key", "value": idempotency_key}],
        )
        return HeartTransaction.model_validate(item) if item else None

    async def add_txn(self, txn: HeartTransaction) -> HeartTransaction:
        # A deterministic item id makes concurrent retries idempotent at Cosmos,
        # not merely inside one API process.
        digest = hashlib.sha256(txn.idempotency_key.encode("utf-8")).hexdigest()[:20]
        txn.id = f"htx-{digest}"
        try:
            await self._ledger_container.create_item(self._ledger_item(txn))
            return txn
        except CosmosResourceExistsError:
            existing = await self.get_txn_by_key(txn.idempotency_key)
            return existing or txn

    async def list_ledger(self, session_id: str) -> list[HeartTransaction]:
        rows = []
        async for item in self._ledger_container.query_items(
            query="SELECT * FROM c WHERE c.sessionId = @sessionId",
            parameters=[{"name": "@sessionId", "value": session_id}],
        ):
            rows.append(HeartTransaction.model_validate(item))
        return rows

    async def list_txns_for_plan(self, plan_id: str) -> list[HeartTransaction]:
        rows = []
        async for item in self._ledger_container.query_items(
            query="SELECT * FROM c WHERE c.plan_id = @planId",
            parameters=[{"name": "@planId", "value": plan_id}],
        ):
            rows.append(HeartTransaction.model_validate(item))
        return rows

    async def all_txns(self) -> list[HeartTransaction]:
        return [
            HeartTransaction.model_validate(item)
            async for item in self._ledger_container.query_items(query="SELECT * FROM c")
        ]

    async def count_completed_steps(self) -> int:
        total = 0
        async for item in self._plans_container.query_items(
            query="SELECT VALUE c.steps FROM c"
        ):
            total += sum(1 for step in item if step.get("status") == "completed")
        return total

    async def count_active_plans(self) -> int:
        count = 0
        async for _ in self._plans_container.query_items(
            query="SELECT VALUE c.id FROM c"
        ):
            count += 1
        return count

    @staticmethod
    async def _first(
        container: Any, query: str, parameters: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        async for item in container.query_items(
            query=query, parameters=parameters
        ):
            return item
        return None
