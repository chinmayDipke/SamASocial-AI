"""Turn extracted segments into overlapping, citable chunks.

Two properties matter here and are worth the extra code:

1. **Locators survive.** Every chunk records the span of segments it covers, so a
   retrieved chunk can say "slides 2-3" or "03:15-04:02" rather than just naming a file.
2. **Splits fall on natural boundaries.** Chunks are grown from paragraphs and
   sentences instead of a fixed character stride, which keeps sentences intact and
   makes retrieved context read like prose to the model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .schemas import Chunk, Segment

# Any horizontal whitespace, including the non-breaking spaces PDFs are full of.
_WHITESPACE_RE = re.compile(r"[^\S\n]+")
_BLANK_LINES_RE = re.compile(r"\n{3,}")
# Split after ., !, ? or a newline, keeping the delimiter with the preceding sentence.
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")
_NUMBERED_LOCATOR_RE = re.compile(r"^([A-Za-z]+) (\d+)$")
_TIMESTAMP_LOCATOR_RE = re.compile(r"^\d{1,2}:\d{2}(?::\d{2})?$")


@dataclass(slots=True)
class _Piece:
    """A segment, or part of an over-long segment, ready to be packed into a chunk."""

    text: str
    position: int
    locator: str
    # True for the tail carried over from the previous chunk, so a trailing window
    # made only of carried text is not emitted as a near-duplicate chunk.
    carried: bool = False


def normalise(text: str) -> str:
    """Collapse runs of spaces and blank lines without destroying paragraph breaks."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _WHITESPACE_RE.sub(" ", text)
    text = _BLANK_LINES_RE.sub("\n\n", text)
    return "\n".join(line.strip() for line in text.split("\n")).strip()


def format_locator_range(first: str, last: str) -> str:
    """Render a human-readable locator for a chunk spanning two segment locators."""
    if first == last:
        return first

    first_match = _NUMBERED_LOCATOR_RE.match(first)
    last_match = _NUMBERED_LOCATOR_RE.match(last)
    if first_match and last_match and first_match.group(1) == last_match.group(1):
        noun = first_match.group(1)
        plural = noun if noun.endswith("s") else f"{noun}s"
        return f"{plural} {first_match.group(2)}-{last_match.group(2)}"

    if _TIMESTAMP_LOCATOR_RE.match(first) and _TIMESTAMP_LOCATOR_RE.match(last):
        return f"{first}-{last}"

    # Headings and anything else: the opening locator is the useful anchor.
    return first


def _split_oversized(piece: _Piece, target: int) -> list[_Piece]:
    """Break a segment that is larger than one chunk into sentence-aligned pieces."""
    sentences = [s for s in _SENTENCE_RE.split(piece.text) if s.strip()]
    pieces: list[_Piece] = []
    buffer: list[str] = []
    length = 0

    for sentence in sentences:
        # A single sentence longer than the target is hard-split as a last resort.
        if len(sentence) > target:
            if buffer:
                pieces.append(_Piece(" ".join(buffer), piece.position, piece.locator))
                buffer, length = [], 0
            for start in range(0, len(sentence), target):
                pieces.append(_Piece(sentence[start : start + target], piece.position, piece.locator))
            continue

        if length + len(sentence) > target and buffer:
            pieces.append(_Piece(" ".join(buffer), piece.position, piece.locator))
            buffer, length = [], 0
        buffer.append(sentence)
        length += len(sentence) + 1

    if buffer:
        pieces.append(_Piece(" ".join(buffer), piece.position, piece.locator))
    return pieces


def chunk_segments(
    segments: list[Segment],
    source_id: str,
    *,
    target_chars: int = 1200,
    overlap_chars: int = 200,
) -> list[Chunk]:
    """Pack segments into overlapping chunks, never merging across sources."""
    pieces: list[_Piece] = []
    for segment in segments:
        text = normalise(segment.text)
        if not text:
            continue
        piece = _Piece(text, segment.position, segment.locator)
        pieces.extend(_split_oversized(piece, target_chars) if len(text) > target_chars else [piece])

    # Overlap must be smaller than a chunk, or a carried tail could fill a whole window.
    overlap_chars = max(0, min(overlap_chars, target_chars // 2))

    chunks: list[Chunk] = []
    window: list[_Piece] = []
    window_chars = 0

    def emit() -> None:
        """Turn the current window into a chunk and carry its tail into the next one."""
        nonlocal window, window_chars
        if not window:
            return

        text = "\n\n".join(p.text for p in window)
        chunks.append(
            Chunk(
                id=f"{source_id}:{len(chunks)}",
                source_id=source_id,
                text=text,
                locator=format_locator_range(window[0].locator, window[-1].locator),
                start_position=window[0].position,
                end_position=window[-1].position,
            )
        )

        last = window[-1]
        window, window_chars = [], 0
        if overlap_chars:
            tail = _tail_text(text, overlap_chars)
            if tail:
                window = [_Piece(tail, last.position, last.locator, carried=True)]
                window_chars = len(tail)

    for piece in pieces:
        window.append(piece)
        window_chars += len(piece.text)
        if window_chars >= target_chars:
            emit()

    # Emit the remainder only if it holds text that has not already been chunked.
    if any(not piece.carried for piece in window):
        emit()

    return chunks


def _tail_text(text: str, overlap_chars: int) -> str:
    """Take the last `overlap_chars` of a chunk, snapped forward to a word boundary."""
    if len(text) <= overlap_chars:
        return text
    tail = text[-overlap_chars:]
    boundary = tail.find(" ")
    return tail[boundary + 1 :].strip() if boundary != -1 else tail.strip()
