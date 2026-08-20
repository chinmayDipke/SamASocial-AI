"""Reading an existing syllabus PDF into plain text.

The bonus path starts here: a mentor who already has a syllabus should be able to
drop it in rather than answer four questions about it. Extraction is the fragile
part, so every way it can fail gets its own message -- an encrypted file, a scan with
no text layer, a Word document renamed to .pdf and a 40-page course handbook all need
different things from the person holding them, and "upload failed" tells them none of
it.

Only the text comes out of here. Turning it into a brief and a plan is the model's
job, in `llm/planner.plan_from_syllabus`.
"""

from __future__ import annotations

import asyncio
import logging
from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from ..config import get_settings

logger = logging.getLogger(__name__)

# Every PDF starts with this, whatever the filename claims.
_MAGIC = b"%PDF"


class SyllabusError(Exception):
    """A failure whose message is safe and useful to show to the mentor."""


def _read(data: bytes, filename: str) -> str:
    settings = get_settings()

    if not data:
        raise SyllabusError("That file is empty, so there is nothing to read from it.")

    if not data.lstrip()[:4].startswith(_MAGIC):
        raise SyllabusError(
            f"'{filename}' is not a PDF. Export the syllabus as a PDF and upload that, "
            "or paste its text into the chat instead."
        )

    try:
        reader = PdfReader(BytesIO(data))
    except (PdfReadError, OSError, ValueError) as exc:
        raise SyllabusError(
            f"This PDF could not be opened ({exc}). It may be damaged -- try re-exporting it."
        ) from exc

    if reader.is_encrypted:
        # An empty user password is common for "protected" PDFs and decrypts silently.
        try:
            unlocked = reader.decrypt("") != 0
        except (NotImplementedError, PdfReadError):
            unlocked = False
        if not unlocked:
            raise SyllabusError(
                "This PDF is password protected, so its text cannot be read. Remove the "
                "password, or paste the syllabus text into the chat."
            )

    pages: list[str] = []
    for number, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:
            logger.info("Skipped page %d of %s: %s", number, filename, exc)
            continue
        if text.strip():
            pages.append(text.strip())

    if not pages:
        raise SyllabusError(
            "No selectable text was found in this PDF. It is most likely a scan or "
            "images of text, which needs OCR that this app does not perform. Paste the "
            "syllabus text into the chat and I will work from that."
        )

    document = "\n\n".join(pages)
    if len(document) > settings.max_syllabus_chars:
        # Cut on a paragraph break so the model is not handed half a sentence.
        cut = document.rfind("\n\n", 0, settings.max_syllabus_chars)
        document = document[: cut if cut > 0 else settings.max_syllabus_chars]
        logger.info(
            "Syllabus %s truncated to %d chars (limit %s)",
            filename,
            len(document),
            settings.max_syllabus_chars,
        )

    return document


async def extract_syllabus_text(data: bytes, filename: str) -> str:
    """Extract the syllabus text off the event loop -- pypdf is synchronous and CPU-bound."""
    return await asyncio.to_thread(_read, data, filename)
