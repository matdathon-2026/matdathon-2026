"""Heart policy: pure, deterministic functions. The AI never touches this.

Rules (server-owned):
- First 3 steps of a plan award 10 hearts each.
- Maximum 30 hearts per plan.
- Reopening a completed step writes a `reversal` of the same amount (rows are never deleted).
- Balance is always SUM(earn + sponsor_allocation_demo) - SUM(reversal).
"""
from __future__ import annotations

from typing import Iterable, Protocol

HEART_PER_STEP = 10
MAX_HEARTS_PER_PLAN = 30
REWARDED_STEP_COUNT = 3


class _Txn(Protocol):
    type: str
    amount: int


def idempotency_key(session_id: str, plan_id: str, step_id: str) -> str:
    return f"{session_id}:{plan_id}:{step_id}:complete"


def is_rewardable_order(step_order: int) -> bool:
    """Steps with order 0,1,2 (first three) are rewardable."""
    return 0 <= step_order < REWARDED_STEP_COUNT


def award_for_step(step_order: int, already_earned_for_plan: int) -> int:
    """How many hearts a step completion earns, honoring the per-plan cap.

    `already_earned_for_plan` is the sum of prior `earn` amounts for the plan.
    Returns 0 for steps beyond the first three or once the cap is reached.
    """
    if not is_rewardable_order(step_order):
        return 0
    if already_earned_for_plan >= MAX_HEARTS_PER_PLAN:
        return 0
    return min(HEART_PER_STEP, MAX_HEARTS_PER_PLAN - already_earned_for_plan)


def balance(transactions: Iterable[_Txn]) -> int:
    total = 0
    for t in transactions:
        if t.type in ("earn", "sponsor_allocation_demo"):
            total += t.amount
        elif t.type == "reversal":
            total -= t.amount
    return total


def earned_for_plan(transactions: Iterable[_Txn]) -> int:
    """Net earned hearts for a plan (earn minus reversal), never below zero."""
    total = 0
    for t in transactions:
        if t.type == "earn":
            total += t.amount
        elif t.type == "reversal":
            total -= t.amount
    return max(total, 0)
