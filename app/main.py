"""FastAPI application entry point.

Grows as each build step wires in a new piece — the Groq+Gemini report
engine (Step 2), the /api/v1/generate-report endpoint (Step 3),
production hardening (Step 4). See README.md's build-status checklist
for what's done.

Note: the reference doc jumped straight to a /health/all endpoint that
makes real HTTP/LLM calls, with no cheap /health for the Docker
healthcheck to poll every 30s. That would burn through Groq/Gemini quota
fast on its own. This repo keeps the same split as fireguard-agent-
compliance: a free /health for container polling, and /health/all (added
in Step 3) as a manual, real-call aggregate check.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.logger import get_logger

logger = get_logger(__name__)

app = FastAPI(title=settings.api_title, version=settings.api_version)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    """Basic liveness check — confirms the API process itself is up.
    Does NOT check Groq, Gemini, or the compliance agent; those get
    /health/all in Step 3."""
    return {"status": "ok", "service": settings.api_title}


@app.on_event("startup")
async def on_startup() -> None:
    logger.info(f"{settings.api_title} v{settings.api_version} starting up")
