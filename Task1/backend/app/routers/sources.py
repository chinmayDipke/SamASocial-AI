"""Adding and listing knowledge sources."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile, status

from ..config import get_settings
from ..ingest.base import IngestError
from ..pipeline import Upload, kind_for_filename, kind_for_url, run_ingestion
from ..schemas import AddUrlSourceRequest, SourceSummary
from ..sessions import Session, Source
from .deps import SessionDep

router = APIRouter(prefix="/api/sessions/{session_id}/sources", tags=["sources"])

_READ_CHUNK = 1024 * 1024


def _assert_capacity(session: Session) -> None:
    limit = get_settings().max_sources_per_session
    if len(session.sources) >= limit:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This session already has {limit} sources, which is the limit.",
        )


def _register(session: Session, kind, title: str, url: str | None) -> Source:  # noqa: ANN001
    source = Source(
        id=uuid.uuid4().hex[:12],
        ref=session.next_ref(),
        kind=kind,
        title=title,
        url=url,
    )
    session.sources[source.id] = source
    return source


async def _read_upload(file: UploadFile) -> bytes:
    """Read the upload with a hard size cap, without buffering an oversized file."""
    limit = get_settings().max_upload_bytes
    buffer = bytearray()
    while chunk := await file.read(_READ_CHUNK):
        buffer.extend(chunk)
        if len(buffer) > limit:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"That file is larger than the {get_settings().max_upload_mb} MB limit.",
            )
    if not buffer:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="That file is empty.")
    return bytes(buffer)


@router.get("", response_model=list[SourceSummary])
async def list_sources(session: SessionDep) -> list[SourceSummary]:
    return [source.to_summary() for source in session.sources.values()]


@router.post("/file", response_model=SourceSummary, status_code=status.HTTP_202_ACCEPTED)
async def add_file_source(
    session: SessionDep,
    background: BackgroundTasks,
    file: UploadFile = File(...),
) -> SourceSummary:
    _assert_capacity(session)
    filename = file.filename or "upload"
    try:
        kind = kind_for_filename(filename)
    except IngestError as exc:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)) from exc

    data = await _read_upload(file)
    source = _register(session, kind, filename, None)
    background.add_task(run_ingestion, session, source, upload=Upload(filename=filename, data=data))
    return source.to_summary()


@router.post("/url", response_model=SourceSummary, status_code=status.HTTP_202_ACCEPTED)
async def add_url_source(
    session: SessionDep,
    background: BackgroundTasks,
    payload: AddUrlSourceRequest,
) -> SourceSummary:
    _assert_capacity(session)
    url = payload.url.strip()
    kind = kind_for_url(url)
    source = _register(session, kind, url, url)
    background.add_task(run_ingestion, session, source, url=url)
    return source.to_summary()
