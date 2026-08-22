from app.domain import hearts
from app.domain.models import HeartTransaction
from datetime import datetime, timezone


def _txn(type_, amount, key="k"):
    return HeartTransaction(
        id="x",
        session_id="s",
        plan_id="p",
        step_id="st",
        type=type_,
        amount=amount,
        reason="r",
        idempotency_key=key,
        created_at=datetime.now(timezone.utc),
    )


def test_idempotency_key_shape():
    assert hearts.idempotency_key("s", "p", "st") == "s:p:st:complete"


def test_award_first_three_steps():
    assert hearts.award_for_step(0, 0) == 10
    assert hearts.award_for_step(1, 10) == 10
    assert hearts.award_for_step(2, 20) == 10


def test_award_caps_at_30_and_fourth_step_zero():
    assert hearts.award_for_step(3, 30) == 0     # 4th step never rewards
    assert hearts.award_for_step(2, 30) == 0     # cap reached
    assert hearts.award_for_step(2, 25) == 5     # partial up to cap


def test_balance_counts_earn_and_sponsor_minus_reversal():
    txns = [
        _txn("earn", 10),
        _txn("earn", 10),
        _txn("sponsor_allocation_demo", 5),
        _txn("reversal", 10),
    ]
    assert hearts.balance(txns) == 15


def test_earned_for_plan_never_negative():
    txns = [_txn("earn", 10), _txn("reversal", 10), _txn("reversal", 10)]
    assert hearts.earned_for_plan(txns) == 0
