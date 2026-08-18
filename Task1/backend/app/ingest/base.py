"""Shared contract for source ingestors.

Every ingestor turns raw input into a title plus a list of `Segment`s, each
carrying the location its text came from. Failures raise `IngestError` with a
message written for the end user -- the UI shows it verbatim on the source card,
so "Ingestion failed" is never an acceptable message.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..schemas import Segment, SourceKind


class IngestError(Exception):
    """A failure whose message is safe and useful to show to the user."""


@dataclass(slots=True)
class IngestResult:
    kind: SourceKind
    title: str
    segments: list[Segment] = field(default_factory=list)
    url: str | None = None


def ensure_not_empty(result: IngestResult, empty_message: str) -> IngestResult:
    """Guard against sources that parse successfully but yield no usable text."""
    if not any(segment.text.strip() for segment in result.segments):
        raise IngestError(empty_message)
    return result
