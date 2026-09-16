from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    api_title: str = Field(default="FireGuard Report Generation Agent")
    api_version: str = Field(default="0.1.0")
    cors_allow_origins: list[str] = Field(default_factory=lambda: ["*"])

  
    compliance_service_url: str = Field(default="http://agent-compliance:8002")
    compliance_health_timeout_seconds: float = Field(default=3.0, gt=0)

    groq_api_key: str
    groq_model_name: str = Field(default="llama-3.1-70b-versatile")
    groq_timeout_seconds: float = Field(default=30.0, gt=0)
    groq_max_retries: int = Field(default=2, ge=0)
    groq_max_tokens: int = Field(default=2048, gt=0)

    gemini_api_key: str
    gemini_model_name: str = Field(default="gemini-1.5-flash")
    gemini_timeout_seconds: float = Field(default=30.0, gt=0)

    report_rate_limit: str = Field(default="10/minute")

    log_level: str = Field(default="INFO")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
