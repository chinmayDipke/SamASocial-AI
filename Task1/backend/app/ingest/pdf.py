"""PDF ingestion. Locator granularity is the page, which is what people cite."""

from __future__ import annotations

import asyncio
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from ..config import get_settings
from ..schemas import Segment, SourceKind
from .base import IngestError, IngestResult, ensure_not_empty


def _extract(data: bytes, filename: str) -> IngestResult:
    settings = get_settings()
    try:
        reader = PdfReader(BytesIO(data))
    except (PdfReadError, OSError, ValueError) as exc:
        raise IngestError(f"This file could not be read as a PDF ({exc}).") from exc

    if reader.is_encrypted:
        # An empty user password is common for "protected" PDFs and decrypts silently.
        try:
            if reader.decrypt("") == 0:
                raise IngestError("This PDF is password protected, so its text cannot be read.")
        except (NotImplementedError, PdfReadError) as exc:
            raise IngestError("This PDF is password protected, so its text cannot be read.") from exc

    page_count = len(reader.pages)
    if page_count > settings.max_pdf_pages:
        raise IngestError(
            f"This PDF has {page_count} pages; the limit is {settings.max_pdf_pages}. "
            "Please upload a shorter extract."
        )

    segments: list[Segment] = []
    for number, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            continue
        if text.strip():
            segments.append(Segment(text=text, position=number, locator=f"page {number}"))

    title = (reader.metadata.title if reader.metadata else None) or Path(filename).stem
    result = IngestResult(kind=SourceKind.PDF, title=title.strip() or filename, segments=segments)
    return ensure_not_empty(
        result,
        "No selectable text was found in this PDF. It is most likely a scan or images "
        "of text, which needs OCR that this app does not perform.",
    )


async def ingest_pdf(data: bytes, filename: str) -> IngestResult:
    """Parse a PDF off the event loop -- pypdf is synchronous and CPU-bound."""
    return await asyncio.to_thread(_extract, data, filename)
