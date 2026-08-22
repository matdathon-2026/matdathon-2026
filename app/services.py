"""Service layer: orchestrates prefilter -> agent -> validation, and the
deterministic plan/heart operations. AI failures are isolated here so the rest
of the app (health, catalog) keeps working.
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone

from app.agents import matcher as matcher_mod
from app.agents import planner as planner_mod
from app.agents.runtime import AgentRuntime, extract_json_object, token_present
from app.agents.validators import (
    ValidationFailure,
    validate_plan_draft,
    validate_recommendations,
)
from app.domain import hearts
from app.domain.filters import prefilter, rank_by_interest
from app.domain.models import ActionPlan, ActionStep, HeartTransaction, Profile
from app.repository.base import Repository

logger = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(self, code: str, message: str, status: int, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.retryable = retryable


def _now() -> datetime:
    return datetime.now(timezone.utc)


class RecommendationService:
    def __init__(self, repo: Repository, runtime: AgentRuntime, ai_enabled: bool) -> None:
        self.repo = repo
        self.runtime = runtime
        self.ai_enabled = ai_enabled

    def _candidates(self, profile: Profile):
        benefits = self.repo.list_benefits()
        candidates = prefilter(
            benefits, region=profile.region, age_band=profile.age_band.value
        )
        candidates = rank_by_interest(
            candidates,
            interests=[c.value for c in profile.interests],
            urgent_need=profile.urgent_need.value,
        )
        return candidates[:6]

    async def recommend(self, profile: Profile):
        if not self.ai_enabled or not token_present():
            raise AppError(
                "AI_UNAVAILABLE",
                "AI 추천 기능을 사용할 수 없어요. 잠시 후 다시 시도해 주세요.",
                503,
                retryable=True,
            )

        candidates = self._candidates(profile)
        by_id = {b.id: b for b in self.repo.list_benefits()}
        allowed_ids = {b.id for b in candidates}
        if not candidates:
            return "조건에 맞는 지원제도를 찾지 못했어요. 관심 분야나 지역을 넓혀 보세요.", []

        prompt = matcher_mod.build_matcher_prompt(profile, candidates)
        last_err = ""
        for attempt in range(2):
            try:
                text = await self.runtime.run_matcher(prompt)
                raw = extract_json_object(text)
                summary, cards = validate_recommendations(raw, by_id, allowed_ids)
                return summary, cards
            except (ValidationFailure, ValueError) as exc:
                last_err = str(exc)
                continue
            except Exception as exc:  # runtime / auth / timeout
                raise AppError(
                    "AI_UNAVAILABLE",
                    "AI 추천 생성 중 문제가 발생했어요. 입력은 저장되어 있어요.",
                    503,
                    retryable=True,
                ) from exc
        logger.warning("recommendation output rejected after retries: %s", last_err)
        raise AppError(
            "AI_INVALID_OUTPUT",
            "추천 결과를 확인하지 못했어요. 다시 시도해 주세요.",
            502,
            retryable=True,
        )

    async def draft_plan(self, benefit_id: str):
        benefit = self.repo.get_benefit(benefit_id)
        if benefit is None:
            raise AppError("BENEFIT_NOT_FOUND", "혜택을 찾을 수 없어요.", 404)
        if not self.ai_enabled or not token_present():
            raise AppError(
                "AI_UNAVAILABLE",
                "AI 계획 생성 기능을 사용할 수 없어요.",
                503,
                retryable=True,
            )
        prompt = planner_mod.build_planner_prompt(benefit)
        for attempt in range(2):
            try:
                text = await self.runtime.run_planner(prompt)
                raw = extract_json_object(text)
                return validate_plan_draft(raw, benefit)
            except (ValidationFailure, ValueError):
                continue
            except Exception as exc:
                raise AppError(
                    "AI_UNAVAILABLE",
                    "AI 계획 생성 중 문제가 발생했어요.",
                    503,
                    retryable=True,
                ) from exc
        raise AppError(
            "AI_INVALID_OUTPUT",
            "계획 초안을 확인하지 못했어요. 다시 시도해 주세요.",
            502,
            retryable=True,
        )


class PlanService:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    async def save_plan(
        self,
        *,
        session_id: str,
        benefit_id: str,
        title: str,
        deadline: date | None,
        required_documents: list[str],
        steps: list[ActionStep],
        uncertainties: list[str],
        source_url: str,
        apply_url: str,
    ) -> ActionPlan:
        session = await self.repo.get_session(session_id)
        if session is None:
            raise AppError("SESSION_NOT_FOUND", "세션을 찾을 수 없어요. 새로 시작해 주세요.", 404)
        if self.repo.get_benefit(benefit_id) is None:
            raise AppError("BENEFIT_NOT_FOUND", "혜택을 찾을 수 없어요.", 404)
        plan = ActionPlan(
            id=f"plan-{uuid.uuid4().hex[:12]}",
            session_id=session_id,
            benefit_id=benefit_id,
            title=title,
            deadline=deadline,
            required_documents=required_documents,
            steps=steps,
            uncertainties=uncertainties,
            source_url=source_url,
            apply_url=apply_url,
            status="todo",
            created_at=_now(),
        )
        return await self.repo.create_plan(plan)

    async def list_plans(self, session_id: str) -> list[ActionPlan]:
        return await self.repo.list_plans(session_id)

    def _refresh_status(self, plan: ActionPlan) -> None:
        completed = sum(1 for s in plan.steps if s.status == "completed")
        if completed == 0:
            plan.status = "todo"
        elif completed == len(plan.steps):
            plan.status = "completed"
        else:
            plan.status = "in_progress"

    async def complete_step(self, plan_id: str, step_id: str, session_id: str):
        plan = await self.repo.get_plan(plan_id)
        if plan is None or plan.session_id != session_id:
            raise AppError("SESSION_NOT_FOUND", "계획을 찾을 수 없어요.", 404)
        step = next((s for s in plan.steps if s.id == step_id), None)
        if step is None:
            raise AppError("BENEFIT_NOT_FOUND", "단계를 찾을 수 없어요.", 404)

        key = hearts.idempotency_key(session_id, plan_id, step_id)
        existing = await self.repo.get_txn_by_key(key)
        if existing is not None:
            # DUPLICATE_COMPLETION -> return existing, do not double-award.
            return plan, existing, True

        step.status = "completed"
        self._refresh_status(plan)

        plan_txns = await self.repo.list_txns_for_plan(plan_id)
        already = hearts.earned_for_plan(plan_txns)
        amount = hearts.award_for_step(step.order, already)

        txn = None
        if amount > 0:
            txn = HeartTransaction(
                id=f"htx-{uuid.uuid4().hex[:12]}",
                session_id=session_id,
                plan_id=plan_id,
                step_id=step_id,
                type="earn",
                amount=amount,
                reason=f"'{step.title}' 단계 완료",
                idempotency_key=key,
                created_at=_now(),
            )
            await self.repo.add_txn(txn)
        await self.repo.save_plan(plan)
        return plan, txn, False

    async def reopen_step(self, plan_id: str, step_id: str, session_id: str):
        plan = await self.repo.get_plan(plan_id)
        if plan is None or plan.session_id != session_id:
            raise AppError("SESSION_NOT_FOUND", "계획을 찾을 수 없어요.", 404)
        step = next((s for s in plan.steps if s.id == step_id), None)
        if step is None:
            raise AppError("BENEFIT_NOT_FOUND", "단계를 찾을 수 없어요.", 404)

        if step.status != "completed":
            return plan, None

        step.status = "todo"
        self._refresh_status(plan)

        key = hearts.idempotency_key(session_id, plan_id, step_id)
        earn = await self.repo.get_txn_by_key(key)
        reversal = None
        if earn is not None and earn.amount > 0:
            reversal = HeartTransaction(
                id=f"htx-{uuid.uuid4().hex[:12]}",
                session_id=session_id,
                plan_id=plan_id,
                step_id=step_id,
                type="reversal",
                amount=earn.amount,
                reason=f"'{step.title}' 단계 완료 취소",
                idempotency_key=f"{key}:reversal:{uuid.uuid4().hex[:6]}",
                created_at=_now(),
            )
            await self.repo.add_txn(reversal)
        await self.repo.save_plan(plan)
        return plan, reversal


class HeartService:
    def __init__(self, repo: Repository, sponsor_total_krw: int) -> None:
        self.repo = repo
        self.sponsor_total_krw = sponsor_total_krw

    async def ledger(self, session_id: str):
        txns = await self.repo.list_ledger(session_id)
        txns_sorted = sorted(txns, key=lambda t: t.created_at)
        return hearts.balance(txns_sorted), txns_sorted

    async def impact(self):
        all_txns = await self.repo.all_txns()
        allocated = hearts.balance(all_txns)
        completed = await self.repo.count_completed_steps()
        active = await self.repo.count_active_plans()
        return {
            "sponsor_total_krw": self.sponsor_total_krw,
            "allocated_hearts": max(allocated, 0),
            "completed_actions": completed,
            "active_plans": active,
        }
