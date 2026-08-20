"""The syllabus upload path: an existing PDF instead of an intake conversation.

This is one turn compressed into one request. The PDF is read to text, and a single
model call fills the intake slots *and* returns a first plan, because the document is
the expensive part of that prompt and sending it twice would buy nothing. The mentor
lands in the same place they would have reached by answering four questions -- a plan
on the right, a chat that knows what it is looking at -- and refines from there.
"""

from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from ..config import get_settings
from ..ingest.syllabus_pdf import SyllabusError, extract_syllabus_text
from ..llm.client import MissingApiKey
from ..llm.errors import describe_llm_error
from ..llm.planner import PlanUnavailable, plan_from_syllabus
from ..llm.prompts import SYLLABUS_IMPORTED_REPLY
from ..resources.links import verify_links
from ..schemas import ChatMessage, SessionInfo
from .deps import SessionDep

router = APIRouter(prefix="/api/sessions/{session_id}/syllabus", tags=["syllabus"])

_READ_CHUNK = 1024 * 1024


async def _read_upload(file: UploadFile) -> bytes:
    """Read the upload with a hard size cap, without buffering an oversized file."""
    settings = get_settings()
    buffer = bytearray()
    while chunk := await file.read(_READ_CHUNK):
        buffer.extend(chunk)
        if len(buffer) > settings.max_upload_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=(
                    f"That file is larger than the {settings.max_upload_mb} MB limit. "
                    "Upload the syllabus on its own rather than a whole course pack."
                ),
            )
    if not buffer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="That file is empty, so there is nothing to read from it.",
        )
    return bytes(buffer)


@router.post("", response_model=SessionInfo)
async def import_syllabus(session: SessionDep, file: UploadFile = File(...)) -> SessionInfo:
    filename = file.filename or "syllabus.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"'{filename}' is not a PDF. Export the syllabus as a PDF, or paste its "
                "text into the chat instead."
            ),
        )

    data = await _read_upload(file)
    try:
        text = await extract_syllabus_text(data, filename)
    except SyllabusError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    try:
        async with session.plan_lock:
            intake, plan = await plan_from_syllabus(text)
            # Checked here rather than in the browser so the badges are already
            # honest when the plan first appears.
            await verify_links(plan.resources)
            session.intake = intake
            session.plan = plan
    except MissingApiKey as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except PlanUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    except Exception as exc:
        detail = describe_llm_error(exc)
        if not detail:
            raise
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=detail
        ) from exc

    session.messages.append(
        ChatMessage(
            role="assistant",
            content=SYLLABUS_IMPORTED_REPLY.format(
                modules=len(plan.modules), title=plan.title
            ),
        )
    )
    return session.to_info()
