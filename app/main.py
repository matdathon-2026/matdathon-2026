"""FastAPI application: API plus the built React app on one origin.

Keeping both in one container is deliberate (TRD section 2): the judged URL has
no CORS hop, no second deployment and no login.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from app.ai.provider import build_foundry_provider
from app.domain.plan import HeartEntry
from app.domain.profile import Profile
from app.recommender import RecommendationService
from app.settings import get_settings
from app.store import BenefitCatalog, CatalogUnavailable, SessionStore

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger("didimheart")

WEB_DIST = Path(__file__).resolve().parents[1] / "web" / "dist"

# Demo sponsorship figures. AGENTS.md section 9: nothing here moves real money.
DEMO_DONATION_KRW = 1_500_000
DEMO_HEARTS_PLEDGED = 30_000
DEMO_SPONSORS = [
    {"name": "디딤 파트너스", "amountKrw": 900_000},
    {"name": "함께재단", "amountKrw": 600_000},
]

settings = get_settings()
catalog = BenefitCatalog(settings)
sessions = SessionStore(settings)


def _build_service() -> RecommendationService:
    """Wire the Copilot SDK provider, degrading to rule-based mode if it fails."""
    provider: Any | None = None
    try:
        if settings.foundry_resource_url:
            provider = build_foundry_provider(settings)
    except Exception:
        logger.warning("foundry provider unavailable, rule-based mode", exc_info=True)
    return RecommendationService(settings, provider, settings.foundry_model)


service = _build_service()


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


class RecommendRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    session_id: str | None = Field(alias="sessionId", default=None, max_length=64)
    profile: Profile


class PlanRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    session_id: str = Field(alias="sessionId", min_length=1, max_length=64)
    benefit_id: str = Field(alias="benefitId", min_length=1, max_length=120)


class CompleteRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    session_id: str = Field(alias="sessionId", min_length=1, max_length=64)


def new_session_id() -> str:
    return f"s_{uuid.uuid4().hex[:12]}"


def today() -> date:
    return datetime.now(timezone.utc).date()


api = APIRouter(prefix="/api")


@api.get("/benefits")
def list_benefits() -> dict[str, Any]:
    try:
        items = catalog.all()
    except CatalogUnavailable as exc:
        raise ApiError(503, "NO_RESULTS", "지원사업 데이터를 불러오지 못했어요.") from exc
    return {
        "items": [b.model_dump(mode="json", by_alias=True) for b in items],
        "count": len(items),
        "source": catalog.source,
    }


@api.post("/recommendations")
async def recommend(payload: RecommendRequest) -> dict[str, Any]:
    try:
        benefits = catalog.all()
    except CatalogUnavailable as exc:
        raise ApiError(503, "NO_RESULTS", "지원사업 데이터를 불러오지 못했어요.") from exc

    session_id = payload.session_id or new_session_id()
    result = await service.recommend(benefits, payload.profile, today())

    if not result.recommendations:
        raise ApiError(
            404,
            "NO_RESULTS",
            "입력하신 조건에 맞는 지원사업을 찾지 못했어요. 관심 분야나 지역을 바꿔서 다시 시도해 보세요.",
        )

    body = result.model_dump(mode="json", by_alias=True)
    body["sessionId"] = session_id
    return body


@api.post("/plans")
async def create_plan(payload: PlanRequest) -> dict[str, Any]:
    benefit = catalog.get(payload.benefit_id)
    if benefit is None:
        raise ApiError(404, "NO_RESULTS", "선택한 지원사업을 찾지 못했어요.")

    plan, degraded = await service.build_plan(benefit, payload.session_id, today())
    sessions.save_plan(plan)

    body = plan.model_dump(mode="json", by_alias=True)
    body["degraded"] = degraded
    return body


@api.post("/plans/{plan_id}/steps/{step_id}/complete")
def complete_step(plan_id: str, step_id: str, payload: CompleteRequest) -> dict[str, Any]:
    plan = sessions.get_plan(plan_id)
    if plan is None or plan.session_id != payload.session_id:
        raise ApiError(404, "NO_RESULTS", "계획을 찾지 못했어요. 추천부터 다시 시작해 주세요.")

    step = plan.find_step(step_id)
    if step is None:
        raise ApiError(404, "NO_RESULTS", "해당 단계를 찾지 못했어요.")

    # The step itself is the idempotency key, so a repeated click never pays twice.
    if step.completed:
        return {
            "planId": plan.plan_id,
            "stepId": step.step_id,
            "awarded": 0,
            "alreadyCompleted": True,
            "heartBalance": sessions.balance(payload.session_id),
        }

    step.completed = True
    step.completed_at = datetime.now(timezone.utc)
    sessions.save_plan(plan)

    entry = HeartEntry(
        entryId=f"e_{uuid.uuid4().hex[:12]}",
        sessionId=payload.session_id,
        reason=f"단계 완료: {step.title}",
        hearts=step.hearts,
        planId=plan.plan_id,
        stepId=step.step_id,
    )
    sessions.add_heart_entry(entry)

    return {
        "planId": plan.plan_id,
        "stepId": step.step_id,
        "awarded": step.hearts,
        "alreadyCompleted": False,
        "heartBalance": sessions.balance(payload.session_id),
    }


@api.get("/hearts")
def hearts(sessionId: str) -> dict[str, Any]:
    entries = sessions.ledger(sessionId)
    return {
        "sessionId": sessionId,
        "balance": sum(entry.hearts for entry in entries),
        "entries": [e.model_dump(mode="json", by_alias=True) for e in entries],
    }


@api.get("/impact")
def impact(sessionId: str | None = None) -> dict[str, Any]:
    return {
        "totalDonationKrw": DEMO_DONATION_KRW,
        "heartsPledged": DEMO_HEARTS_PLEDGED,
        "heartsDistributed": sessions.total_hearts_distributed(),
        "completedActions": sessions.completed_action_count(),
        "sponsors": DEMO_SPONSORS,
        "note": "하트는 데모 포인트이며 현금이나 전자화폐가 아닙니다.",
    }


def create_app() -> FastAPI:
    app = FastAPI(title="디딤하트 API", version="0.1.0", docs_url="/api/docs")

    @app.exception_handler(ApiError)
    async def _api_error(_request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status, content={"error": {"code": exc.code, "message": exc.message}}
        )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
            "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
        )
        return response

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    def readyz() -> JSONResponse:
        try:
            count = len(catalog.all())
        except CatalogUnavailable:
            return JSONResponse(status_code=503, content={"status": "no-catalog"})
        return JSONResponse(
            content={"status": "ok", "benefits": count, "catalogSource": catalog.source}
        )

    @app.get("/status/ai")
    def status_ai() -> dict[str, Any]:
        return {
            "aiEnabled": service.ai_enabled,
            "model": settings.foundry_model or None,
            "foundryConfigured": bool(settings.foundry_resource_url),
            "agents": ["BenefitMatcherAgent", "ActionPlannerAgent"],
            "runtime": "microsoft-agent-framework + github-copilot-sdk",
        }

    app.include_router(api)

    if WEB_DIST.exists():
        assets = WEB_DIST / "assets"
        if assets.exists():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/{full_path:path}")
        def spa(full_path: str) -> FileResponse:
            candidate = WEB_DIST / full_path
            if full_path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(WEB_DIST / "index.html")

    return app


app = create_app()
