"""In-memory repository backed by a JSON file for durability across restarts.

Ships first so the golden path works with zero external dependencies. Cosmos DB
is a drop-in alternative behind the same interface.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Optional

from app.domain.models import ActionPlan, Benefit, DemoSession, HeartTransaction


class MemoryRepository:
    def __init__(self, seed_path: str, state_path: str) -> None:
        self._seed_path = Path(seed_path)
        self._state_path = Path(state_path)
        self._benefits: dict[str, Benefit] = {}
        self._sessions: dict[str, DemoSession] = {}
        self._plans: dict[str, ActionPlan] = {}
        self._ledger: list[HeartTransaction] = []
        self._keys: set[str] = set()
        self._lock = asyncio.Lock()

    async def startup(self) -> None:
        self._load_seed()
        self._load_state()

    async def ping(self) -> bool:
        return len(self._benefits) > 0

    # --- persistence helpers ---
    def _load_seed(self) -> None:
        data = json.loads(self._seed_path.read_text(encoding="utf-8"))
        self._benefits = {b["id"]: Benefit.model_validate(b) for b in data}

    def _load_state(self) -> None:
        if not self._state_path.exists():
            return
        try:
            data = json.loads(self._state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        self._sessions = {
            s["id"]: DemoSession.model_validate(s) for s in data.get("sessions", [])
        }
        self._plans = {
            p["id"]: ActionPlan.model_validate(p) for p in data.get("plans", [])
        }
        self._ledger = [
            HeartTransaction.model_validate(t) for t in data.get("ledger", [])
        ]
        self._keys = {t.idempotency_key for t in self._ledger}

    def _flush(self) -> None:
        payload = {
            "sessions": [json.loads(s.model_dump_json()) for s in self._sessions.values()],
            "plans": [json.loads(p.model_dump_json()) for p in self._plans.values()],
            "ledger": [json.loads(t.model_dump_json()) for t in self._ledger],
        }
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self._state_path)

    # --- benefits ---
    def list_benefits(self) -> list[Benefit]:
        return list(self._benefits.values())

    def get_benefit(self, benefit_id: str) -> Optional[Benefit]:
        return self._benefits.get(benefit_id)

    # --- sessions ---
    async def create_session(self, session: DemoSession) -> DemoSession:
        async with self._lock:
            self._sessions[session.id] = session
            self._flush()
        return session

    async def get_session(self, session_id: str) -> Optional[DemoSession]:
        return self._sessions.get(session_id)

    async def save_session(self, session: DemoSession) -> DemoSession:
        async with self._lock:
            self._sessions[session.id] = session
            self._flush()
        return session

    # --- plans ---
    async def create_plan(self, plan: ActionPlan) -> ActionPlan:
        async with self._lock:
            self._plans[plan.id] = plan
            self._flush()
        return plan

    async def get_plan(self, plan_id: str) -> Optional[ActionPlan]:
        return self._plans.get(plan_id)

    async def list_plans(self, session_id: str) -> list[ActionPlan]:
        return [p for p in self._plans.values() if p.session_id == session_id]

    async def save_plan(self, plan: ActionPlan) -> ActionPlan:
        async with self._lock:
            self._plans[plan.id] = plan
            self._flush()
        return plan

    # --- hearts ---
    async def get_txn_by_key(self, idempotency_key: str) -> Optional[HeartTransaction]:
        for t in self._ledger:
            if t.idempotency_key == idempotency_key and t.type == "earn":
                return t
        return None

    async def add_txn(self, txn: HeartTransaction) -> HeartTransaction:
        async with self._lock:
            self._ledger.append(txn)
            self._keys.add(txn.idempotency_key)
            self._flush()
        return txn

    async def list_ledger(self, session_id: str) -> list[HeartTransaction]:
        return [t for t in self._ledger if t.session_id == session_id]

    async def list_txns_for_plan(self, plan_id: str) -> list[HeartTransaction]:
        return [t for t in self._ledger if t.plan_id == plan_id]

    async def all_txns(self) -> list[HeartTransaction]:
        return list(self._ledger)

    async def count_completed_steps(self) -> int:
        total = 0
        for p in self._plans.values():
            total += sum(1 for s in p.steps if s.status == "completed")
        return total

    async def count_active_plans(self) -> int:
        return len(self._plans)
