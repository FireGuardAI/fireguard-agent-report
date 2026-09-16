"""Custom exceptions — never let raw library errors (or raw provider
error text from Groq/Gemini) leak into API responses as str(exc).
"""


class ReportError(Exception):
    """Base exception for the report agent domain."""


class ReportEngineError(ReportError):
    """Raised when BOTH the primary (Groq) and fallback (Gemini) engines
    fail. Carries both underlying errors for logging, but main.py maps
    this to a single clean client-facing message — not the raw
    provider-specific exception text from either service."""

    def __init__(self, message: str, primary_error: str, fallback_error: str):
        super().__init__(message)
        self.primary_error = primary_error
        self.fallback_error = fallback_error
