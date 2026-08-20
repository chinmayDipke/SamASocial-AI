"""FastAPI application entry point."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routers import chat, plan, sessions, syllabus

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)

settings = get_settings()

app = FastAPI(
    title="AI Course Planning Assistant",
    description=(
        "Plans a complete course through guided conversation: guided intake, a "
        "structured module-by-module plan with verified public resources, and "
        "refinement in place."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)

app.include_router(sessions.router)
app.include_router(chat.router)
app.include_router(plan.router)
app.include_router(syllabus.router)


@app.get("/api/health", tags=["meta"])
async def health() -> dict[str, object]:
    """Liveness plus the configuration the frontend cares about."""
    return {
        "status": "ok",
        "provider": settings.provider_label,
        "chat_model": settings.llm_chat_model,
        "llm_key_configured": bool(settings.llm_api_key),
        "max_upload_mb": settings.max_upload_mb,
        "verify_links": settings.verify_resource_links,
    }
