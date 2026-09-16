"""Centralized, type-safe application configuration.

Same pattern as the other repos. groq_api_key and gemini_api_key have NO
defaults — Pydantic raises a validation error at startup if either is
missing, which is the desired fail-fast behavior.

Note: the reference doc had a `PORT: int = 8003` field that was never
actually read anywhere (uvicorn's --port was hardcoded separately) —
dropped here rather than wired, matching how the other 3 repos handle
ports: fixed in the Dockerfile CMD, not a runtime setting.
"""
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # API metadata
    api_title: str = Field(default="FireGuard Report Generation Agent")
    api_version: str = Field(default="0.1.0")
    cors_allow_origins: list[str] = Field(default_factory=lambda: ["*"])

    # Compliance agent connection (for /health/all only — this service
    # doesn't call compliance for data, it's called BY whatever already
    # has compliance's output) — service name on the shared fireguard-net
    # network, not localhost
    compliance_service_url: str = Field(default="http://agent-compliance:8002")
    compliance_health_timeout_seconds: float = Field(default=3.0, gt=0)

    # Groq LLM (primary) — required, no default
    groq_api_key: str
    groq_model_name: str = Field(default="llama-3.1-70b-versatile")
    groq_timeout_seconds: float = Field(default=30.0, gt=0)
    groq_max_retries: int = Field(default=2, ge=0)
    groq_max_tokens: int = Field(default=2048, gt=0)

    # Gemini LLM (fallback) — required, no default
    gemini_api_key: str
    gemini_model_name: str = Field(default="gemini-1.5-flash")
    gemini_timeout_seconds: float = Field(default=30.0, gt=0)

    # Production hardening (Step 4)
    report_rate_limit: str = Field(default="10/minute")

    # Observability
    log_level: str = Field(default="INFO")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
