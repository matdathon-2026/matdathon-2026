from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.config import REPO_ROOT
from app.domain.models import ActionStep, DemoSession
from app.repository.memory import MemoryRepository
from app.services import PlanService, HeartService


def _mk_repo(tmp_path):
    seed = str(REPO_ROOT / "data" / "benefits.seed.json")
    state = str(Path(tmp_path) / "state.local.json")
    return MemoryRepository(seed, state)


def _steps(n=4):
    return [
        ActionStep(id=f"step-{i}", title=f"단계 {i}", description="d", estimated_minutes=30, order=i)
        for i in range(n)
    ]


@pytest.mark.asyncio
async def test_double_complete_awards_once_and_reversal_math(tmp_path):
    repo = _mk_repo(tmp_path)
    await repo.startup()
    plans = PlanService(repo)
    hearts_svc = HeartService(repo, 5_000_000)

    session = DemoSession(id="sess-1", created_at=datetime.now(timezone.utc))
    await repo.create_session(session)
    plan = await plans.save_plan(
        session_id="sess-1",
        benefit_id="self-reliance-allowance",
        title="계획",
        deadline=None,
        required_documents=[],
        steps=_steps(4),
        uncertainties=[],
        source_url="https://www.bokjiro.go.kr",
        apply_url="https://www.bokjiro.go.kr",
    )

    # First complete -> awards 10
    _, txn, dup = await plans.complete_step(plan.id, "step-0", "sess-1")
    assert dup is False and txn is not None and txn.amount == 10
    balance, _ = await hearts_svc.ledger("sess-1")
    assert balance == 10

    # Duplicate complete -> returns existing, no new award
    _, txn2, dup2 = await plans.complete_step(plan.id, "step-0", "sess-1")
    assert dup2 is True and txn2.id == txn.id
    balance, _ = await hearts_svc.ledger("sess-1")
    assert balance == 10

    # Complete steps 1,2,3 -> +10 +10 +0 (4th not rewardable, cap 30)
    await plans.complete_step(plan.id, "step-1", "sess-1")
    await plans.complete_step(plan.id, "step-2", "sess-1")
    _, txn4, _ = await plans.complete_step(plan.id, "step-3", "sess-1")
    balance, _ = await hearts_svc.ledger("sess-1")
    assert balance == 30
    assert txn4 is None  # fourth step earns nothing

    # Reopen step-0 -> reversal of 10
    _, reversal = await plans.reopen_step(plan.id, "step-0", "sess-1")
    assert reversal is not None and reversal.amount == 10
    balance, _ = await hearts_svc.ledger("sess-1")
    assert balance == 20


@pytest.mark.asyncio
async def test_impact_aggregates(tmp_path):
    repo = _mk_repo(tmp_path)
    await repo.startup()
    hearts_svc = HeartService(repo, 5_000_000)
    data = await hearts_svc.impact()
    assert data["sponsor_total_krw"] == 5_000_000
    assert data["completed_actions"] == 0
    assert data["active_plans"] == 0
