"""Chunking is where citation accuracy is won or lost, so it gets the most tests."""

from __future__ import annotations

from itertools import pairwise

from app.chunking import chunk_segments, format_locator_range, normalise
from app.schemas import Segment


def make_segments(count: int, chars: int, prefix: str = "page") -> list[Segment]:
    return [
        Segment(
            text=f"Sentence about topic {i}. " * (chars // 26 + 1),
            position=i,
            locator=f"{prefix} {i}",
        )
        for i in range(1, count + 1)
    ]


def test_normalise_collapses_spaces_but_keeps_paragraphs() -> None:
    """PDFs are full of non-breaking spaces; they must collapse like ordinary ones."""
    raw = "Hello \u00a0 world again\n\n\n\nNext paragraph"

    assert normalise(raw) == "Hello world again\n\nNext paragraph"


def test_locator_range_pluralises_numbered_locators() -> None:
    assert format_locator_range("page 3", "page 4") == "pages 3-4"
    assert format_locator_range("slide 2", "slide 5") == "slides 2-5"


def test_locator_range_joins_timestamps() -> None:
    assert format_locator_range("03:15", "04:02") == "03:15-04:02"


def test_locator_range_collapses_identical_locators() -> None:
    assert format_locator_range("page 7", "page 7") == "page 7"


def test_locator_range_falls_back_to_first_for_headings() -> None:
    assert format_locator_range("Installation", "Usage") == "Installation"


def test_every_chunk_keeps_a_locator_and_source() -> None:
    chunks = chunk_segments(make_segments(10, 400), "src1", target_chars=800, overlap_chars=100)

    assert chunks, "expected at least one chunk"
    assert all(chunk.locator for chunk in chunks)
    assert all(chunk.source_id == "src1" for chunk in chunks)
    assert all(chunk.start_position <= chunk.end_position for chunk in chunks)


def test_chunk_ids_are_unique_and_ordered() -> None:
    chunks = chunk_segments(make_segments(12, 300), "src1", target_chars=600, overlap_chars=80)
    ids = [chunk.id for chunk in chunks]

    assert len(ids) == len(set(ids))
    assert ids == [f"src1:{i}" for i in range(len(ids))]


def test_oversized_single_segment_is_split() -> None:
    huge = [Segment(text="A long sentence that repeats. " * 300, position=1, locator="page 1")]
    chunks = chunk_segments(huge, "src1", target_chars=1000, overlap_chars=100)

    assert len(chunks) > 1
    assert all(len(chunk.text) <= 2400 for chunk in chunks)
    # A split segment still reports the page it came from.
    assert {chunk.locator for chunk in chunks} == {"page 1"}


def test_consecutive_chunks_overlap_even_when_segments_are_large() -> None:
    """Large segments (a PDF page) must still overlap, or answers break at page seams."""
    chunks = chunk_segments(make_segments(8, 500), "src1", target_chars=900, overlap_chars=300)

    assert len(chunks) >= 2
    for previous, following in pairwise(chunks):
        tail = previous.text[-60:].strip()
        assert tail in following.text, "expected the previous chunk's tail to open the next one"


def test_final_chunk_is_not_pure_overlap() -> None:
    """The tail carried into an empty window must not be emitted as a near-duplicate chunk."""
    chunks = chunk_segments(make_segments(4, 500), "src1", target_chars=600, overlap_chars=200)
    texts = [chunk.text for chunk in chunks]

    assert len(texts) == len(set(texts))
    assert all(len(chunk.text) > 200 for chunk in chunks)


def test_short_source_produces_one_chunk() -> None:
    segments = [Segment(text="Just a little text.", position=1, locator="page 1")]
    chunks = chunk_segments(segments, "src1")

    assert len(chunks) == 1
    assert chunks[0].text == "Just a little text."


def test_empty_segments_are_dropped() -> None:
    segments = [
        Segment(text="   ", position=1, locator="page 1"),
        Segment(text="Real content here.", position=2, locator="page 2"),
    ]
    chunks = chunk_segments(segments, "src1")

    assert len(chunks) == 1
    assert chunks[0].locator == "page 2"
