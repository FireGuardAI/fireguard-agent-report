"""Structured, leveled logging — no print() statements anywhere.

Fixes a reference-doc bug: the Groq-to-Gemini fallback path used
print(f"[WARN] ...") for the failover notice, which is invisible to any
real log aggregator and has no level/timestamp. That path now uses this
logger instead (see services/report_engine.py).

NOTE: never log settings.groq_api_key, settings.gemini_api_key, or any
part of them.
"""
import logging
import sys

from app.config import settings


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # avoid duplicate handlers on re-import

    logger.setLevel(settings.log_level)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger
