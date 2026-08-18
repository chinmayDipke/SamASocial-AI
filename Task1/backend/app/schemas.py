"""Wire and domain models.

`Segment` and `Chunk` are the backbone of citation accuracy: an ingestor emits
segments that each know *where* they came from, and chunking preserves that
locator information so every retrieved chunk can point back at a page, slide,
timestamp or section heading.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class SourceKind(StrEnum):
    PDF = "pdf"
    PPTX = "pptx"
    YOUTUBE = "youtube"
    WEB = "web"


class SourceStatus(StrEnum):
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class Segment(BaseModel):
    """A unit of extracted text with the location it came from."""

    text: str
    # Ordinal position within the source: page no., slide no., seconds offset, block index.
    position: int
    # Human-readable location, e.g. "page 4", "slide 2", "03:15", "Installation".
    locator: str


class Chunk(BaseModel):
    """A retrievable window of text, traceable back to its source location."""

    id: str
    source_id: str
    text: str
    locator: str
    start_position: int
    end_position: int


class Citation(BaseModel):
    """Resolved provenance for a chunk that was shown to the model."""

    ref: str  # the label the model is told to cite, e.g. "S1"
    source_id: str
    source_title: str
    source_kind: SourceKind
    locator: str
    quote: str
    # Deep link back into the original material where one exists.
    url: str | None = None


class SourceSummary(BaseModel):
    """Public view of an ingested source."""

    id: str
    ref: str
    kind: SourceKind
    title: str
    status: SourceStatus
    url: str | None = None
    chunk_count: int = 0
    summary: str | None = None
    error: str | None = None
    created_at: datetime


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class SessionInfo(BaseModel):
    session_id: str
    created_at: datetime
    sources: list[SourceSummary]
    message_count: int


class AddUrlSourceRequest(BaseModel):
    url: str = Field(min_length=4, max_length=2048)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class QuizQuestion(BaseModel):
    question: str
    options: list[str] = Field(min_length=2, max_length=6)
    correct_index: int
    explanation: str
    source_ref: str
    locator: str


class QuizResponse(BaseModel):
    questions: list[QuizQuestion]


class ErrorResponse(BaseModel):
    detail: str
