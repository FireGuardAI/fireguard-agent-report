class ReportError(Exception):
    """Base exception for the report agent domain."""


class ReportEngineError(ReportError):

    def __init__(self, message: str, primary_error: str, fallback_error: str):
        super().__init__(message)
        self.primary_error = primary_error
        self.fallback_error = fallback_error
