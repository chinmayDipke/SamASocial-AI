"""Which models the UI may offer, and what they have cost so far."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter

from ..config import get_settings
from ..llm import catalog
from ..schemas import ModelOptionOut, ModelsResponse

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("", response_model=ModelsResponse)
async def list_models() -> ModelsResponse:
    settings = get_settings()
    options = await catalog.list_models()
    return ModelsResponse(
        provider=settings.provider_label,
        default=catalog.short_id(settings.llm_chat_model),
        # `ModelOption` uses slots, so it has no __dict__ for vars() to read.
        models=[ModelOptionOut(**asdict(option)) for option in options],
    )
