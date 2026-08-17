"""Streaming chat endpoint.

Server-Sent Events over POST: the request carries a JSON body, which `EventSource`
cannot do, so the frontend reads the response with `fetch` + `ReadableStream`.
Frames are `status`, `token`, `citations`, `done` and `error`.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from ..llm.chat import stream_chat
from ..llm.client import MissingApiKey
from ..schemas import ChatRequest
from ..sessions import Session
from .deps import SessionDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions/{session_id}", tags=["chat"])


def sse_frame(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _event_source(session: Session, message: str) -> AsyncIterator[str]:
    try:
        async for event, payload in stream_chat(session, message):
            yield sse_frame(event, payload)
    except MissingApiKey as exc:
        yield sse_frame("error", {"detail": str(exc)})
    except Exception as exc:
        logger.exception("Chat stream failed: %s", exc)
        yield sse_frame(
            "error",
            {"detail": "The assistant could not complete that answer. Please try again."},
        )


@router.post("/chat")
async def chat(session: SessionDep, payload: ChatRequest) -> StreamingResponse:
    return StreamingResponse(
        _event_source(session, payload.message.strip()),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # Stops nginx and similar proxies from buffering the stream.
            "X-Accel-Buffering": "no",
        },
    )
