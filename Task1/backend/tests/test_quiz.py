"""Attribution tidying for quiz questions.

Models reliably return the whole citation label in `source_ref` and repeat it in
`locator`; these cases are all taken from real Gemini output.
"""

from __future__ import annotations

import pytest

from app.llm.quiz import _tidy_attribution
from app.schemas import QuizQuestion


def question(source_ref: str, locator: str) -> QuizQuestion:
    return QuizQuestion(
        question="Why?",
        options=["a", "b"],
        correct_index=0,
        explanation="because",
        source_ref=source_ref,
        locator=locator,
    )


@pytest.mark.parametrize(
    ("source_ref", "locator", "expected_ref", "expected_locator"),
    [
        # Already correct.
        ("S1", "page 4", "S1", "page 4"),
        # The whole label in both fields (the common failure).
        ("S1 | Introduction", "[S1 | Introduction]", "S1", "Introduction"),
        # Brackets kept around a plain ref.
        ("[S2]", "slide 3", "S2", "slide 3"),
        # Label in the locator only.
        ("S3", "[S3 | 03:15]", "S3", "03:15"),
        # Ranges survive intact.
        ("S2 | pages 1-2", "[S2 | pages 1-2]", "S2", "pages 1-2"),
    ],
)
def test_attribution_is_split_into_ref_and_locator(
    source_ref: str, locator: str, expected_ref: str, expected_locator: str
) -> None:
    tidied = _tidy_attribution(question(source_ref, locator))

    assert tidied.source_ref == expected_ref
    assert tidied.locator == expected_locator


def test_a_genuine_locator_is_not_overwritten_by_the_ref_tail() -> None:
    """When the locator is real and different, keep it rather than the ref's tail."""
    tidied = _tidy_attribution(question("S1 | Introduction", "page 7"))

    assert tidied.source_ref == "S1"
    assert tidied.locator == "page 7"
