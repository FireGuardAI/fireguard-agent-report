from typing import Optional

from pydantic import BaseModel, Field


class RuleCheckItem(BaseModel):
    rule_clause: str
    status: str
    finding: str
    recommendation: Optional[str] = None


class AuditDataInput(BaseModel):
    overall_status: str
    compliance_score: float = Field(..., ge=0.0, le=100.0)
    detailed_checks: list[RuleCheckItem]
    summary: str


class ReportRequest(BaseModel):
    building_name: str = Field(default="Target Commercial Building")
    auditor_notes: Optional[str] = None
    audit_data: AuditDataInput


class ReportResponse(BaseModel):
    building_name: str
    overall_status: str
    compliance_score: float
    executive_summary_markdown: str
    generated_by: str = Field(
        description="Which LLM actually produced this report, e.g. "
        "'Groq (llama-3.1-70b-versatile)' or 'Gemini (gemini-1.5-flash, fallback)'"
    )
