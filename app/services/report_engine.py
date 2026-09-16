import asyncio
import json

from google import genai
from groq import AsyncGroq
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.exceptions import ReportEngineError
from app.logger import get_logger
from app.prompts import REPORT_GENERATION_PROMPT, REPORT_SYSTEM_PROMPT
from app.schemas import AuditDataInput

logger = get_logger(__name__)


class ReportEngine:
    def __init__(self):
        self._groq_client = AsyncGroq(api_key=settings.groq_api_key)
        self._gemini_client = genai.Client(api_key=settings.gemini_api_key)
        logger.info(
            f"ReportEngine ready (primary=Groq/{settings.groq_model_name}, "
            f"fallback=Gemini/{settings.gemini_model_name})"
        )

    @retry(
        stop=stop_after_attempt(settings.groq_max_retries),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    async def _generate_groq(self, prompt: str) -> str:
        response = await asyncio.wait_for(
            self._groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": REPORT_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                model=settings.groq_model_name,
                temperature=0.3,
                max_tokens=settings.groq_max_tokens,
            ),
            timeout=settings.groq_timeout_seconds,
        )
        content = response.choices[0].message.content
        if not content or not content.strip():
            raise ReportEngineError(
                "Groq returned an empty completion", primary_error="empty response",
                fallback_error="",
            )
        return content

    async def _generate_gemini(self, prompt: str) -> str:
        response = await asyncio.wait_for(
            self._gemini_client.aio.models.generate_content(
                model=settings.gemini_model_name,
                contents=prompt,
            ),
            timeout=settings.gemini_timeout_seconds,
        )
        if not response.text or not response.text.strip():
            raise RuntimeError("Gemini returned an empty response")
        return response.text

    async def self_check_groq(self) -> None:
        try:
            await asyncio.wait_for(
                self._groq_client.chat.completions.create(
                    messages=[{"role": "user", "content": "Respond with exactly: OK"}],
                    model=settings.groq_model_name,
                    max_tokens=5,
                ),
                timeout=settings.groq_timeout_seconds,
            )
        except Exception as exc:
            raise ReportEngineError(
                "Groq self-check failed", primary_error=str(exc), fallback_error=""
            ) from exc

    async def self_check_gemini(self) -> None:
        try:
            await asyncio.wait_for(
                self._gemini_client.aio.models.generate_content(
                    model=settings.gemini_model_name,
                    contents="Respond with exactly: OK",
                ),
                timeout=settings.gemini_timeout_seconds,
            )
        except Exception as exc:
            raise ReportEngineError(
                "Gemini self-check failed", primary_error="", fallback_error=str(exc)
            ) from exc

    async def generate_report(self, audit_data: AuditDataInput) -> tuple[str, str]:
        audit_json_str = json.dumps(audit_data.model_dump(), indent=2)
        prompt = REPORT_GENERATION_PROMPT.format(audit_json_str=audit_json_str)

        try:
            report_md = await self._generate_groq(prompt)
            return report_md, f"Groq ({settings.groq_model_name})"
        except Exception as groq_exc:
            logger.warning(
                f"Groq primary engine failed after {settings.groq_max_retries} "
                f"attempts, falling back to Gemini: {groq_exc}"
            )
            try:
                report_md = await self._generate_gemini(prompt)
                return report_md, f"Gemini ({settings.gemini_model_name}, fallback)"
            except Exception as gemini_exc:
                raise ReportEngineError(
                    "Both LLM engines failed to generate the report",
                    primary_error=str(groq_exc),
                    fallback_error=str(gemini_exc),
                ) from gemini_exc
