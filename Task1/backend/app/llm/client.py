"""Single shared LLM client.

Any provider that speaks the OpenAI Chat Completions wire format works here --
OpenAI, Google Gemini, Groq, Together -- selected with `LLM_BASE_URL`.
"""

from __future__ import annotations

from functools import lru_cache

from openai import AsyncOpenAI

from ..config import get_settings


class MissingApiKey(RuntimeError):
    """Raised when the server is started without an LLM API key."""


@lru_cache
def get_openai_client() -> AsyncOpenAI:
    settings = get_settings()
    if not settings.llm_api_key:
        raise MissingApiKey(
            "No LLM API key is set. Copy backend/.env.example to backend/.env and set "
            "LLM_API_KEY (GEMINI_API_KEY and OPENAI_API_KEY are also accepted)."
        )

    # The SDK retries connection errors, 429s and 5xx with backoff.
    return AsyncOpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.resolved_base_url,
        max_retries=3,
        timeout=90.0,
    )
