"""Single shared OpenAI client."""

from __future__ import annotations

from functools import lru_cache

from openai import AsyncOpenAI

from ..config import get_settings


class MissingApiKey(RuntimeError):
    """Raised when the server is started without an OpenAI key."""


@lru_cache
def get_openai_client() -> AsyncOpenAI:
    settings = get_settings()
    if not settings.openai_api_key:
        raise MissingApiKey(
            "OPENAI_API_KEY is not set. Copy backend/.env.example to backend/.env and add your key."
        )
    # The SDK retries connection errors, 429s and 5xx with backoff.
    return AsyncOpenAI(api_key=settings.openai_api_key, max_retries=3, timeout=90.0)
