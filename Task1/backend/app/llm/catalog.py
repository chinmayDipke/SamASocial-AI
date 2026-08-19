"""Which chat models this key can use, and what they cost you in quota.

Providers do not expose rate limits over the API, so limits come from three
places, in decreasing order of trust:

1. **Measured** — when a model returns a quota error, the response usually states
   the cap and the retry delay. That is recorded and shown verbatim.
2. **Counted** — every request this process makes is tallied per model, so the
   picker can show what has actually been spent this run.
3. **Documented** — a published figure, clearly labelled as such, and only where
   it is known. Unknown limits say "unknown" rather than inventing a number.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from ..config import get_settings
from .client import get_openai_client

# Cache the provider's model list; it changes rarely and the call is not free.
_LIST_TTL_SECONDS = 600


@dataclass(slots=True)
class CatalogEntry:
    """A model we are willing to offer, with what is known about it."""

    id: str
    label: str
    note: str
    # Published free-tier requests per day. None means "not documented here".
    documented_daily: int | None = None
    recommended: bool = False


# Ordered best-default-first. Only models present on the key are ever shown.
CATALOG: dict[str, list[CatalogEntry]] = {
    "gemini": [
        CatalogEntry(
            id="gemini-3.6-flash",
            label="Gemini 3.6 Flash",
            note="Balanced. The default for grounded answers.",
            recommended=True,
        ),
        CatalogEntry(
            id="gemini-3.5-flash",
            label="Gemini 3.5 Flash",
            note="Slightly older, similar quality.",
        ),
        CatalogEntry(
            id="gemini-3.5-flash-lite",
            label="Gemini 3.5 Flash Lite",
            note="Fastest and cheapest. Best for short lookups.",
        ),
        CatalogEntry(
            id="gemini-3.1-flash-lite",
            label="Gemini 3.1 Flash Lite",
            note="Lite tier, higher free allowance.",
        ),
        CatalogEntry(
            id="gemini-3.7-flash",
            label="Gemini 3.7 Flash",
            note="Newest, but a very small free allowance.",
            documented_daily=20,
        ),
        CatalogEntry(
            id="gemini-flash-lite-latest",
            label="Gemini Flash Lite (latest)",
            note="Always points at the current lite model.",
        ),
    ],
    "openai": [
        CatalogEntry(
            id="gpt-5.5",
            label="GPT-5.5",
            note="Highest quality.",
            recommended=True,
        ),
        CatalogEntry(id="gpt-5-mini", label="GPT-5 mini", note="Faster and cheaper."),
        CatalogEntry(id="gpt-4.1", label="GPT-4.1", note="Previous generation."),
        CatalogEntry(id="gpt-4.1-mini", label="GPT-4.1 mini", note="Cheapest option."),
    ],
}


@dataclass(slots=True)
class Usage:
    """What this process has spent on a model, and any limit it has run into."""

    requests: int = 0
    quota_message: str | None = None
    quota_hit_at: float | None = None


_usage: dict[str, Usage] = {}
_listed: tuple[float, set[str]] | None = None


def record_request(model: str) -> None:
    _usage.setdefault(model, Usage()).requests += 1


def record_quota_hit(model: str, message: str) -> None:
    entry = _usage.setdefault(model, Usage())
    entry.quota_message = message
    entry.quota_hit_at = time.time()


def usage_for(model: str) -> Usage:
    return _usage.get(model, Usage())


def clear_usage() -> None:
    """Test hook."""
    _usage.clear()


def short_id(model_id: str) -> str:
    """Gemini returns `models/gemini-3.6-flash`; the API accepts either form."""
    return model_id.split("/")[-1]


async def _installed_models() -> set[str]:
    """The set of model ids this key can use, cached briefly."""
    global _listed
    now = time.time()
    if _listed and now - _listed[0] < _LIST_TTL_SECONDS:
        return _listed[1]

    client = get_openai_client()
    ids = {short_id(model.id) async for model in client.models.list()}
    _listed = (now, ids)
    return ids


@dataclass(slots=True)
class ModelOption:
    """One row in the picker."""

    id: str
    label: str
    note: str
    recommended: bool
    is_default: bool
    documented_daily: int | None
    requests_used: int
    # Set once the provider has told us this model is out of quota.
    limit_reached: bool = False
    limit_message: str | None = None
    tags: list[str] = field(default_factory=list)


async def list_models() -> list[ModelOption]:
    """Catalog entries the key actually has, annotated with live usage."""
    settings = get_settings()
    entries = CATALOG.get(settings.provider_label, [])
    configured = short_id(settings.llm_chat_model)

    try:
        installed = await _installed_models()
    except Exception:
        installed = set()

    options: list[ModelOption] = []
    for entry in entries:
        # An empty `installed` means the listing failed; show the catalog anyway.
        if installed and entry.id not in installed:
            continue
        usage = usage_for(entry.id)
        options.append(
            ModelOption(
                id=entry.id,
                label=entry.label,
                note=entry.note,
                recommended=entry.recommended,
                is_default=entry.id == configured,
                documented_daily=entry.documented_daily,
                requests_used=usage.requests,
                limit_reached=usage.quota_hit_at is not None,
                limit_message=usage.quota_message,
            )
        )

    # The configured model always appears, even if it is not in the catalog.
    if configured and not any(option.id == configured for option in options):
        usage = usage_for(configured)
        options.insert(
            0,
            ModelOption(
                id=configured,
                label=configured,
                note="Configured in the backend environment.",
                recommended=True,
                is_default=True,
                documented_daily=None,
                requests_used=usage.requests,
                limit_reached=usage.quota_hit_at is not None,
                limit_message=usage.quota_message,
            ),
        )
    return options


async def resolve(requested: str | None) -> str:
    """Pick the model to answer with, ignoring anything not on the allowlist."""
    settings = get_settings()
    if not requested:
        return settings.llm_chat_model

    allowed = {entry.id for entry in CATALOG.get(settings.provider_label, [])}
    allowed.add(short_id(settings.llm_chat_model))
    return requested if short_id(requested) in allowed else settings.llm_chat_model
