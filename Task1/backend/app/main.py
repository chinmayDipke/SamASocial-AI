"""FastAPI application entry point."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routers import chat, quiz, sessions, sources

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)

settings = get_settings()

app = FastAPI(
    title="Multi-Source AI Learning Assistant",
    description=(
        "Ingests PDFs, PowerPoint decks, YouTube videos and webpages, then answers "
        "questions grounded strictly in that material, with citations."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)

app.include_router(sessions.router)
app.include_router(sources.router)
app.include_router(chat.router)
app.include_router(quiz.router)


@app.get("/api/health", tags=["meta"])
async def health() -> dict[str, object]:
    """Liveness plus the configuration the frontend cares about."""
    return {
        "status": "ok",
        "chat_model": settings.openai_chat_model,
        "embed_model": settings.openai_embed_model,
        "openai_key_configured": bool(settings.openai_api_key),
        "max_upload_mb": settings.max_upload_mb,
        "max_sources_per_session": settings.max_sources_per_session,
    }
