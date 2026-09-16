"""FastAPI application entry point.

Grows as each build step wires in a new piece — the Groq+Gemini report
engine (Step 2), the /api/v1/generate-report endpoint (Step 3),
production hardening (Step 4). See README.md's build-status checklist
for what's done.

Note: the reference doc jumped straight to a /health/all endpoint that
makes real HTTP/LLM calls, with no cheap /health for the Docker
healthcheck to poll every 30s. That would burn through Groq/Gemini quota
fast on its own. This repo keeps the same split as fireguard-agent-
compliance: a free /health for container polling, and /health/all as a
manual, real-call aggregate check.
"""
import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import settings
from app.exceptions import ReportEngineError
from app.logger import get_logger
from app.middleware import RequestLoggingMiddleware
from app.schemas import ReportRequest, ReportResponse
from app.services.report_engine import ReportEngine

logger = get_logger(__name__)

app = FastAPI(title=settings.api_title, version=settings.api_version)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)

# Rate limiting (Step 4) — protects both Groq and Gemini quota from
# being exhausted by /api/v1/generate-report traffic.
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Defense-in-depth: catches anything NOT already caught by a
    specific handler, so a bug can never leak a raw traceback to a
    client — same philosophy as fireguard-agent-compliance's Step 5."""
    logger.error(f"Unhandled exception on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# Loaded once at startup (see on_startup below), never per-request.
report_engine: ReportEngine | None = None


@app.get("/health")
async def health() -> dict:
    """Basic liveness check — confirms the API process itself is up.
    Does NOT check Groq, Gemini, or the compliance agent; those get
    /health/groq, /health/gemini, and /health/all."""
    return {"status": "ok", "service": settings.api_title}


@app.get("/health/groq")
async def health_groq() -> dict:
    """Makes one real (minimal) Groq API call. Not polled automatically —
    call it manually."""
    if report_engine is None:
        raise HTTPException(status_code=503, detail="Report engine not initialized")
    try:
        await report_engine.self_check_groq()
    except ReportEngineError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"status": "ok", "model": settings.groq_model_name}


@app.get("/health/gemini")
async def health_gemini() -> dict:
    """Makes one real (minimal) Gemini API call. Not polled automatically —
    call it manually."""
    if report_engine is None:
        raise HTTPException(status_code=503, detail="Report engine not initialized")
    try:
        await report_engine.self_check_gemini()
    except ReportEngineError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"status": "ok", "model": settings.gemini_model_name}


@app.get("/health/all")
async def health_all() -> dict:
    """Aggregate check — compliance service liveness + both LLM
    providers. Deliberately hits the compliance agent's cheap /health
    (not its own /health/all), so one call here doesn't cascade into
    triggering real LLM calls across multiple services."""
    dependencies: dict = {}
    overall_ok = True

    try:
        async with httpx.AsyncClient(
            timeout=settings.compliance_health_timeout_seconds
        ) as client:
            response = await client.get(f"{settings.compliance_service_url}/health")
            response.raise_for_status()
            dependencies["compliance_service"] = {
                "status": "ok",
                "detail": response.json(),
            }
    except Exception as exc:
        dependencies["compliance_service"] = {"status": "error", "detail": str(exc)}
        overall_ok = False

    if report_engine is None:
        dependencies["groq"] = {"status": "error", "detail": "not initialized"}
        dependencies["gemini"] = {"status": "error", "detail": "not initialized"}
        overall_ok = False
    else:
        try:
            await report_engine.self_check_groq()
            dependencies["groq"] = {"status": "ok"}
        except ReportEngineError as exc:
            dependencies["groq"] = {"status": "error", "detail": str(exc)}
            overall_ok = False
        try:
            await report_engine.self_check_gemini()
            dependencies["gemini"] = {"status": "ok"}
        except ReportEngineError as exc:
            dependencies["gemini"] = {"status": "error", "detail": str(exc)}
            overall_ok = False

    return {"status": "ok" if overall_ok else "degraded", "dependencies": dependencies}


@app.post("/api/v1/generate-report", response_model=ReportResponse)
@limiter.limit(settings.report_rate_limit)
async def generate_executive_report(
    request: Request, report_request: ReportRequest
) -> ReportResponse:
    """Generates the executive report. Fixes the reference doc's blanket
    `except Exception: raise HTTPException(500, str(e))` — that leaked
    raw provider-internal error text straight into the client-facing
    response. Now the specific failure details are logged server-side
    only; the client gets one clean, actionable message.

    NOTE: the Starlette request param MUST be named exactly `request` —
    slowapi's @limiter.limit() looks it up by that name. The reference
    doc's endpoint used `request: ReportRequest` for the body, which
    would have collided with this; the body param is named
    `report_request` instead (same fix as fireguard-agent-compliance's
    Step 5)."""
    if report_engine is None:
        raise HTTPException(status_code=503, detail="Report engine not initialized")

    try:
        report_md, generated_by = await report_engine.generate_report(
            report_request.audit_data
        )
    except ReportEngineError as exc:
        logger.error(
            f"Report generation failed — primary(Groq): {exc.primary_error} | "
            f"fallback(Gemini): {exc.fallback_error}"
        )
        raise HTTPException(
            status_code=503,
            detail="Report generation failed: both the primary and fallback "
            "LLM engines were unavailable. Please try again shortly.",
        ) from exc

    return ReportResponse(
        building_name=report_request.building_name,
        overall_status=report_request.audit_data.overall_status,
        compliance_score=report_request.audit_data.compliance_score,
        executive_summary_markdown=report_md,
        generated_by=generated_by,
    )


@app.on_event("startup")
async def on_startup() -> None:
    global report_engine
    logger.info(f"{settings.api_title} v{settings.api_version} starting up")
    report_engine = ReportEngine()
