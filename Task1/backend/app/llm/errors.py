"""Translate OpenAI SDK failures into messages a user can act on.

"Something went wrong" is never a useful thing to show someone. An expired key,
an exhausted quota and a model the account cannot access all need different
actions, and the API tells us which one it is -- so say so.
"""

from __future__ import annotations

import openai

from ..config import get_settings

BILLING_URL = "https://platform.openai.com/settings/organization/billing"


def describe_openai_error(exc: Exception) -> str | None:
    """Return a user-facing message, or None if this is not an OpenAI API error."""
    settings = get_settings()

    if isinstance(exc, openai.RateLimitError):
        if _is_quota_exhausted(exc):
            return (
                "The OpenAI account has no remaining quota, so the text could not be "
                f"embedded. Add credit at {BILLING_URL} and try again."
            )
        return "OpenAI is rate limiting requests right now. Wait a few seconds and try again."

    if isinstance(exc, openai.AuthenticationError):
        return (
            "OpenAI rejected the API key. Check OPENAI_API_KEY in backend/.env "
            "(or .env.local) and restart the server."
        )

    if isinstance(exc, openai.PermissionDeniedError):
        return (
            f"This OpenAI key does not have access to '{settings.openai_chat_model}' or "
            f"'{settings.openai_embed_model}'. Run scripts/check_models.py to see what it can use."
        )

    if isinstance(exc, openai.NotFoundError):
        return (
            "OpenAI does not recognise the configured model. Run scripts/check_models.py "
            "and set OPENAI_CHAT_MODEL / OPENAI_EMBED_MODEL to a model this key can use."
        )

    if isinstance(exc, openai.APIConnectionError):
        return "Could not reach OpenAI. Check your network connection and try again."

    if isinstance(exc, openai.APIStatusError):
        if exc.status_code >= 500:
            return "OpenAI had a server error. Try again in a moment."
        return f"OpenAI rejected the request (HTTP {exc.status_code})."

    return None


def _is_quota_exhausted(exc: openai.RateLimitError) -> bool:
    """Distinguish "out of credit" from "slow down" -- both arrive as HTTP 429."""
    if getattr(exc, "code", None) == "insufficient_quota":
        return True
    return "insufficient_quota" in str(exc) or "exceeded your current quota" in str(exc)
