"""Abstract repository interface. Implementations: memory (JSON file), cosmos."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from app.domain.models import ActionPlan, Benefit, DemoSession, HeartTransaction


class Repository(ABC):
    # --- lifecycle ---
    @abstractmethod
    async def startup(self) -> None: ...

    @abstractmethod
    async def ping(self) -> bool:
        """Datastore readiness check for /readyz."""

    # --- benefits (read-only catalog) ---
    @abstractmethod
    def list_benefits(self) -> list[Benefit]: ...

    @abstractmethod
    def get_benefit(self, benefit_id: str) -> Optional[Benefit]: ...

    # --- sessions ---
    @abstractmethod
    async def create_session(self, session: DemoSession) -> DemoSession: ...

    @abstractmethod
    async def get_session(self, session_id: str) -> Optional[DemoSession]: ...

    @abstractmethod
    async def save_session(self, session: DemoSession) -> DemoSession: ...

    # --- plans ---
    @abstractmethod
    async def create_plan(self, plan: ActionPlan) -> ActionPlan: ...

    @abstractmethod
    async def get_plan(self, plan_id: str) -> Optional[ActionPlan]: ...

    @abstractmethod
    async def list_plans(self, session_id: str) -> list[ActionPlan]: ...

    @abstractmethod
    async def save_plan(self, plan: ActionPlan) -> ActionPlan: ...

    # --- hearts ---
    @abstractmethod
    async def get_txn_by_key(self, idempotency_key: str) -> Optional[HeartTransaction]: ...

    @abstractmethod
    async def add_txn(self, txn: HeartTransaction) -> HeartTransaction: ...

    @abstractmethod
    async def list_ledger(self, session_id: str) -> list[HeartTransaction]: ...

    @abstractmethod
    async def list_txns_for_plan(self, plan_id: str) -> list[HeartTransaction]: ...

    @abstractmethod
    async def all_txns(self) -> list[HeartTransaction]: ...

    @abstractmethod
    async def count_completed_steps(self) -> int: ...

    @abstractmethod
    async def count_active_plans(self) -> int: ...
