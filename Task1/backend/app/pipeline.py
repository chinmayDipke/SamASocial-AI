"""Ingestion pipeline: extract -> chunk -> index -> summarise.

Runs as a background task so uploads return immediately and the UI can show real
per-source progress. A source only becomes `ready` once it is in *both* indexes,
so a question can never hit a half-indexed source. The summary is filled in
afterwards -- it is a nicety and should not delay the first question.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from .chunking import chunk_segments
from .config import get_settings
from .ingest.base import IngestError, IngestResult
from .ingest.pdf import ingest_pdf
from .ingest.pptx import ingest_pptx
from .ingest.web import ingest_web
from .ingest.youtube import ingest_youtube, is_youtube_url
from .llm.summarize import summarise_source
from .retrieval.embeddings import embed_texts
from .schemas import SourceKind, SourceStatus
from .sessions import Session, Source

logger = logging.getLogger(__name__)

_EXTENSION_HANDLERS = {".pdf": SourceKind.PDF, ".pptx": SourceKind.PPTX}


@dataclass(slots=True)
class Upload:
    filename: str
    data: bytes


def kind_for_filename(filename: str) -> SourceKind:
    lowered = filename.lower()
    for extension, kind in _EXTENSION_HANDLERS.items():
        if lowered.endswith(extension):
            return kind
    raise IngestError("Only PDF (.pdf) and PowerPoint (.pptx) files are supported.")


def kind_for_url(url: str) -> SourceKind:
    return SourceKind.YOUTUBE if is_youtube_url(url) else SourceKind.WEB


async def _extract(*, upload: Upload | None, url: str | None) -> IngestResult:
    if upload is not None:
        kind = kind_for_filename(upload.filename)
        if kind is SourceKind.PDF:
            return await ingest_pdf(upload.data, upload.filename)
        return await ingest_pptx(upload.data, upload.filename)

    if url is not None:
        return await ingest_youtube(url) if is_youtube_url(url) else await ingest_web(url)

    raise IngestError("No file or URL was provided.")


async def run_ingestion(
    session: Session,
    source: Source,
    *,
    upload: Upload | None = None,
    url: str | None = None,
) -> None:
    settings = get_settings()
    try:
        result = await _extract(upload=upload, url=url)
        source.kind = result.kind
        source.title = result.title
        source.url = result.url or source.url

        chunks = chunk_segments(
            result.segments,
            source.id,
            target_chars=settings.chunk_target_chars,
            overlap_chars=settings.chunk_overlap_chars,
        )
        if not chunks:
            raise IngestError("No usable text could be extracted from this source.")

        matrix = await embed_texts([chunk.text for chunk in chunks])

        async with session.index_lock:
            session.register_chunks(chunks)
            session.vectors.add([chunk.id for chunk in chunks], matrix)

        source.chunk_count = len(chunks)
        source.status = SourceStatus.READY
        logger.info("Indexed source %s (%s) with %d chunks", source.id, source.kind, len(chunks))

        source.summary = await summarise_source(source.title, chunks)

    except IngestError as exc:
        source.status = SourceStatus.FAILED
        source.error = str(exc)
        logger.info("Ingestion rejected for source %s: %s", source.id, exc)
    except Exception as exc:
        source.status = SourceStatus.FAILED
        source.error = "Something went wrong while processing this source. Please try again."
        logger.exception("Unexpected ingestion failure for source %s: %s", source.id, exc)
