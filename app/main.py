"""FastAPI application: API under /api/v1, static React under /, health probes.

Health/readiness never touch AI. AI runtime state is a separate non-blocking
diagnostic at /status/ai.
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.agents.runtime import AgentRuntime
from app.agents.tools import set_catalog
from app.config import get_settings
from app.domain.models import DemoSession, Profile
from app.repository.memory import MemoryRepository
from app.schemas import (
    AiStatusOut,
    BenefitDetailOut,
    CompareRequest,
    ErrorBody,
    ErrorResponse,
    HeartTxnOut,
    ImpactOut,
    LedgerOut,
    PlanDraftOut,
    PlanDraftRequest,
    PlanOut,
    ProfileIn,
    RecommendationRequest,
    RecommendationResponse,
    SavePlanRequest,
    SessionOut,
    StepActionRequest,
    StepOut,
)
from app.services import (
    AppError,
    HeartService,
    PlanService,
    RecommendationService,
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    repo = MemoryRepository(settings.seed_path, settings.state_path)
    await repo.startup()
    set_catalog(repo.list_benefits())
    runtime = AgentRuntime(timeout=settings.ai_timeout_seconds, model=settings.foundry_model)
    app.state.repo = repo
    app.state.runtime = runtime
    app.state.rec = RecommendationService(repo, runtime, settings.ai_enabled)
    app.state.plans = PlanService(repo)
    app.state.hearts = HeartService(repo, settings.demo_sponsor_total_krw)
    yield


app = FastAPI(title="DidimHeart API", version="1.0", lifespan=lifespan)

_cors_origins = [o.strip() for o in settings.cors_allow_origins.split(",") if o.strip()]
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
        "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'",
    )
    response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


def _error(code: str, message: str, status: int, retryable: bool = False) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorBody(code=code, message=message, retryable=retryable, requestId=uuid.uuid4().hex)
    )
    return JSONResponse(status_code=status, content=body.model_dump())


@app.exception_handler(AppError)
async def _app_error_handler(_request: Request, exc: AppError):
    return _error(exc.code, exc.message, exc.status, exc.retryable)


# ---------------- health / diagnostics ----------------
@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/readyz")
async def readyz(request: Request):
    ok = await request.app.state.repo.ping()
    if not ok:
        return _error("DATASTORE_UNAVAILABLE", "데이터 저장소를 사용할 수 없어요.", 503)
    return {"status": "ready"}


@app.get("/status/ai", response_model=AiStatusOut)
async def status_ai(request: Request):
    st = request.app.state.runtime.status()
    return AiStatusOut(
        runtime=st["runtime"],
        auth=st["auth"],
        model=st["model"],
        enabled=settings.ai_enabled,
    )


# ---------------- sessions / profile ----------------
def _now() -> datetime:
    return datetime.now(timezone.utc)


@app.post("/api/v1/demo-sessions", response_model=SessionOut)
async def create_session(request: Request):
    repo = request.app.state.repo
    session = DemoSession(id=f"sess-{uuid.uuid4().hex[:16]}", created_at=_now())
    await repo.create_session(session)
    return SessionOut(id=session.id, created_at=session.created_at, has_profile=False)


@app.put("/api/v1/demo-sessions/{session_id}/profile", response_model=SessionOut)
async def save_profile(session_id: str, body: ProfileIn, request: Request):
    repo = request.app.state.repo
    session = await repo.get_session(session_id)
    if session is None:
        raise AppError("SESSION_NOT_FOUND", "세션을 찾을 수 없어요. 새로 시작해 주세요.", 404)
    session.profile = Profile(**body.model_dump())
    await repo.save_session(session)
    return SessionOut(id=session.id, created_at=session.created_at, has_profile=True)


# ---------------- recommendations ----------------
@app.post("/api/v1/recommendations", response_model=RecommendationResponse)
async def recommendations(body: RecommendationRequest, request: Request):
    repo = request.app.state.repo
    session = await repo.get_session(body.session_id)
    if session is None:
        raise AppError("SESSION_NOT_FOUND", "세션을 찾을 수 없어요. 새로 시작해 주세요.", 404)
    if session.profile is None:
        raise AppError("VALIDATION_ERROR", "먼저 프로필을 입력해 주세요.", 422)
    summary, cards = await request.app.state.rec.recommend(session.profile)
    return RecommendationResponse(summary=summary, recommendations=cards, ai_generated=True)


# ---------------- benefits ----------------
@app.get("/api/v1/benefits/{benefit_id}", response_model=BenefitDetailOut)
async def benefit_detail(benefit_id: str, request: Request):
    b = request.app.state.repo.get_benefit(benefit_id)
    if b is None:
        raise AppError("BENEFIT_NOT_FOUND", "혜택을 찾을 수 없어요.", 404)
    return BenefitDetailOut(
        id=b.id,
        title=b.title,
        provider=b.provider,
        category=b.category.value,
        regions=b.regions,
        eligibility_text=b.eligibilityText,
        benefit_text=b.benefitText,
        application_steps=b.applicationSteps,
        required_documents=b.requiredDocuments,
        deadline=b.deadline,
        source_url=b.sourceUrl,
        source_agency=b.sourceAgency,
        verified_at=b.verifiedAt,
        status=b.status,
    )


@app.post("/api/v1/benefits/compare")
async def compare(body: CompareRequest, request: Request):
    from app.agents.tools import compare_benefits

    rows = compare_benefits(body.benefit_ids)
    return {"rows": rows}


# ---------------- plans ----------------
def _plan_out(plan) -> PlanOut:
    return PlanOut(
        id=plan.id,
        session_id=plan.session_id,
        benefit_id=plan.benefit_id,
        title=plan.title,
        deadline=plan.deadline,
        required_documents=plan.required_documents,
        steps=[
            StepOut(
                id=s.id,
                title=s.title,
                description=s.description,
                estimated_minutes=s.estimated_minutes,
                order=s.order,
                status=s.status,
            )
            for s in plan.steps
        ],
        uncertainties=plan.uncertainties,
        source_url=plan.source_url,
        apply_url=plan.apply_url,
        status=plan.status,
        created_at=plan.created_at,
    )


@app.post("/api/v1/plans/draft", response_model=PlanDraftOut)
async def plan_draft(body: PlanDraftRequest, request: Request):
    repo = request.app.state.repo
    session = await repo.get_session(body.session_id)
    if session is None:
        raise AppError("SESSION_NOT_FOUND", "세션을 찾을 수 없어요. 새로 시작해 주세요.", 404)
    draft = await request.app.state.rec.draft_plan(body.benefit_id)
    return PlanDraftOut(
        benefit_id=draft["benefit_id"],
        title=draft["title"],
        deadline=draft["deadline"],
        required_documents=draft["required_documents"],
        steps=[
            StepOut(
                id=s.id,
                title=s.title,
                description=s.description,
                estimated_minutes=s.estimated_minutes,
                order=s.order,
                status=s.status,
            )
            for s in draft["steps"]
        ],
        uncertainties=draft["uncertainties"],
        source_url=draft["source_url"],
        apply_url=draft["apply_url"],
        ai_generated=True,
    )


@app.post("/api/v1/plans", response_model=PlanOut)
async def save_plan(body: SavePlanRequest, request: Request):
    from app.domain.models import ActionStep

    steps = [
        ActionStep(
            id=s.id or f"step-{i}",
            title=s.title,
            description=s.description,
            estimated_minutes=s.estimated_minutes,
            order=s.order,
            status="todo",
        )
        for i, s in enumerate(body.steps)
    ]
    plan = await request.app.state.plans.save_plan(
        session_id=body.session_id,
        benefit_id=body.benefit_id,
        title=body.title,
        deadline=body.deadline,
        required_documents=body.required_documents,
        steps=steps,
        uncertainties=body.uncertainties,
        source_url=body.source_url,
        apply_url=body.apply_url,
    )
    return _plan_out(plan)


@app.get("/api/v1/plans", response_model=list[PlanOut])
async def list_plans(
    request: Request,
    session_id: str = Query(alias="sessionId"),
):
    plans = await request.app.state.plans.list_plans(session_id)
    return [_plan_out(p) for p in plans]


def _txn_out(txn) -> HeartTxnOut:
    return HeartTxnOut(
        id=txn.id,
        plan_id=txn.plan_id,
        step_id=txn.step_id,
        type=txn.type,
        amount=txn.amount,
        reason=txn.reason,
        created_at=txn.created_at,
    )


@app.post("/api/v1/plans/{plan_id}/steps/{step_id}/complete")
async def complete_step(plan_id: str, step_id: str, body: StepActionRequest, request: Request):
    plan, txn, duplicate = await request.app.state.plans.complete_step(
        plan_id, step_id, body.session_id
    )
    return {
        "plan": _plan_out(plan).model_dump(by_alias=True),
        "transaction": _txn_out(txn).model_dump(by_alias=True) if txn else None,
        "duplicate": duplicate,
    }


@app.post("/api/v1/plans/{plan_id}/steps/{step_id}/reopen")
async def reopen_step(plan_id: str, step_id: str, body: StepActionRequest, request: Request):
    plan, reversal = await request.app.state.plans.reopen_step(
        plan_id, step_id, body.session_id
    )
    return {
        "plan": _plan_out(plan).model_dump(by_alias=True),
        "reversal": _txn_out(reversal).model_dump(by_alias=True) if reversal else None,
    }


# ---------------- hearts / impact ----------------
@app.get("/api/v1/hearts/ledger", response_model=LedgerOut)
async def hearts_ledger(
    request: Request,
    session_id: str = Query(alias="sessionId"),
):
    balance, txns = await request.app.state.hearts.ledger(session_id)
    return LedgerOut(balance=balance, transactions=[_txn_out(t) for t in txns])


@app.get("/api/v1/impact", response_model=ImpactOut)
async def impact(request: Request):
    data = await request.app.state.hearts.impact()
    return ImpactOut(
        sponsor_total_krw=data["sponsor_total_krw"],
        allocated_hearts=data["allocated_hearts"],
        completed_actions=data["completed_actions"],
        active_plans=data["active_plans"],
    )


# ---------------- static React app ----------------
_web_dist = Path(settings.web_dist)
if _web_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(_web_dist / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def spa(full_path: str):
        candidate = _web_dist / full_path
        if full_path and candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(_web_dist / "index.html"))
