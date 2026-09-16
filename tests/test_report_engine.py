"""Tests for ReportEngine's fallback orchestration — verifies Groq is
used when it succeeds, Gemini is used only when Groq fails, and both
failing raises ReportEngineError. No real API keys/clients needed:
ReportEngine.__new__() skips __init__ entirely, and the two provider
methods are mocked directly, testing generate_report()'s own logic in
isolation."""
import os

os.environ.setdefault("GROQ_API_KEY", "test-key-for-unit-tests")
os.environ.setdefault("GEMINI_API_KEY", "test-key-for-unit-tests")

from unittest.mock import AsyncMock

import pytest

from app.exceptions import ReportEngineError
from app.schemas import AuditDataInput
from app.services.report_engine import ReportEngine


def _sample_audit_data() -> AuditDataInput:
    return AuditDataInput(
        overall_status="COMPLIANT",
        compliance_score=100.0,
        detailed_checks=[],
        summary="test summary",
    )


def _bare_engine() -> ReportEngine:
    # skips __init__ — no real Groq/Gemini clients constructed, so no
    # API keys are actually used despite the env vars set above
    return ReportEngine.__new__(ReportEngine)


@pytest.mark.asyncio
async def test_uses_groq_when_it_succeeds():
    engine = _bare_engine()
    engine._generate_groq = AsyncMock(return_value="# Groq Report")
    engine._generate_gemini = AsyncMock(return_value="# Gemini Report")

    report_md, generated_by = await engine.generate_report(_sample_audit_data())

    assert report_md == "# Groq Report"
    assert "Groq" in generated_by
    engine._generate_gemini.assert_not_called()


@pytest.mark.asyncio
async def test_falls_back_to_gemini_when_groq_fails():
    engine = _bare_engine()
    engine._generate_groq = AsyncMock(side_effect=RuntimeError("groq down"))
    engine._generate_gemini = AsyncMock(return_value="# Gemini Report")

    report_md, generated_by = await engine.generate_report(_sample_audit_data())

    assert report_md == "# Gemini Report"
    assert "Gemini" in generated_by
    assert "fallback" in generated_by


@pytest.mark.asyncio
async def test_raises_when_both_engines_fail():
    engine = _bare_engine()
    engine._generate_groq = AsyncMock(side_effect=RuntimeError("groq down"))
    engine._generate_gemini = AsyncMock(side_effect=RuntimeError("gemini down"))

    with pytest.raises(ReportEngineError):
        await engine.generate_report(_sample_audit_data())
