"""Translate LLM API failures into messages a user can act on.

"Something went wrong" is never a useful thing to show someone. An expired key,
an exhausted quota and a model the account cannot access all need different
actions, and the API tells us which one it is -- so say so. Wording adapts to the
configured provider, since the fix lives in a different console for each.
"""

from __future__ import annotations

import re

import openai

from ..config import get_settings

BILLING_URLS = {
    "openai": "https://platform.openai.com/settings/organization/billing",
    "gemini": "https://aistudio.google.com/apikey",
    "groq": "https://console.groq.com/settings/billing",
}

PROVIDER_NAMES = {"openai": "OpenAI", "gemini": "Gemini", "groq": "Groq", "together": "Together"}


def describe_llm_error(exc: Exception) -> str | None:
    """Return a user-facing message, or None if this is not an LLM API error."""
    settings = get_settings()
    provider = settings.provider_label
    name = PROVIDER_NAMES.get(provider, "The LLM provider")

    if isinstance(exc, openai.RateLimitError):
        wait = _retry_after(exc)
        soon = f" Try again in about {wait} seconds." if wait else ""
        if _is_quota_exhausted(exc):
            console = BILLING_URLS.get(provider)
            where = f" Check your quota at {console}." if console else ""
            # Providers use the same error for "out of credit" and "hit today's free
            # allowance", so mention the wait when they tell us there is one.
            return (
                f"The {name} quota is used up, so this could not be processed.{soon}{where}"
            )
        return f"{name} is rate limiting requests right now.{soon or ' Wait a few seconds and try again.'}"

    if isinstance(exc, openai.AuthenticationError):
        return (
            f"{name} rejected the API key. Check LLM_API_KEY in backend/.env "
            "(or .env.local) and restart the server."
        )

    if isinstance(exc, openai.PermissionDeniedError):
        return (
            f"This key does not have access to '{settings.llm_chat_model}' or "
            f"'{settings.llm_embed_model}'. Run scripts/check_models.py to see what it can use."
        )

    if isinstance(exc, openai.NotFoundError):
        return (
            f"{name} does not recognise the configured model. Run scripts/check_models.py and set "
            "LLM_CHAT_MODEL / LLM_EMBED_MODEL to a model this key can use."
        )

    if isinstance(exc, openai.APIConnectionError):
        return f"Could not reach {name}. Check your network connection and try again."

    if isinstance(exc, openai.APIStatusError):
        if exc.status_code >= 500:
            return f"{name} had a server error. Try again in a moment."
        return f"{name} rejected the request (HTTP {exc.status_code})."

    return None


# Kept under the previous name so existing call sites stay valid.
describe_openai_error = describe_llm_error


def _retry_after(exc: openai.RateLimitError) -> int | None:
    """Pull a retry delay out of the response, whichever way the provider states it."""
    header = getattr(getattr(exc, "response", None), "headers", None)
    if header:
        raw = header.get("retry-after")
        if raw and str(raw).strip().isdigit():
            return int(str(raw).strip())

    # Gemini puts it in the message body: "Please retry in 23.169578455s."
    match = re.search(r"retry in (\d+(?:\.\d+)?)s", str(exc))
    return round(float(match.group(1))) if match else None


def _is_quota_exhausted(exc: openai.RateLimitError) -> bool:
    """Distinguish "out of credit" from "slow down" -- both arrive as HTTP 429."""
    if getattr(exc, "code", None) == "insufficient_quota":
        return True
    text = str(exc)
    return "insufficient_quota" in text or "exceeded your current quota" in text
