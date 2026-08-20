"""The streaming conversation endpoint.

Server-Sent Events over POST: the request carries a JSON body, which `EventSource`
cannot do, so the frontend reads the response with `fetch` + `ReadableStream`. Frames
are `status`, `token`, `intake`, `plan`, `done` and `error`.

Nothing in a turn is allowed to surface as an HTTP 500 once the stream has started --
the response headers are long gone by then. Failures become a final `error` frame
carrying a message written for the mentor.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from ..llm.client import MissingApiKey
from ..llm.errors import describe_llm_error
from ..llm.turn import run_turn
from ..schemas import ChatRequest
from ..sessions import Session
from .deps import SessionDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions/{session_id}", tags=["chat"])


def sse_frame(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _event_source(session: Session, message: str) -> AsyncIterator[str]:
    try:
        async for event, payload in run_turn(session, message):
            yield sse_frame(event, payload)
    except MissingApiKey as exc:
        yield sse_frame("error", {"detail": str(exc)})
    except Exception as exc:
        api_message = describe_llm_error(exc)
        if api_message:
            logger.error("Turn failed: %s", api_message)
        else:
            logger.exception("Turn failed: %s", exc)
        yield sse_frame(
            "error",
            {"detail": api_message or "That turn could not be completed. Please try again."},
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
