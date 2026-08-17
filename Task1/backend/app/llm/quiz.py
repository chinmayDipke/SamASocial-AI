"""Quiz mode: auto-generate multiple-choice questions from the loaded sources.

Uses the Responses API's structured-output helper so questions come back as
validated objects rather than JSON-in-prose that has to be salvaged with a regex.
"""

from __future__ import annotations

from ..config import get_settings
from ..schemas import Citation, QuizQuestion, QuizResponse
from ..sessions import Session
from .client import get_openai_client
from .prompts import QUIZ_SYSTEM_PROMPT, build_context_block

_MAX_QUIZ_INPUT_CHARS = 12_000


class QuizUnavailable(RuntimeError):
    """Raised when there is not enough loaded material to build a quiz."""


def _sample_context(session: Session, question_count: int) -> list[Citation]:
    """Spread the sample across sources so a quiz covers everything that is loaded."""
    ready = session.ready_sources
    if not ready:
        raise QuizUnavailable("Add at least one source before starting a quiz.")

    per_source = max(2, (question_count * 2) // len(ready))
    citations: list[Citation] = []
    used = 0

    for source in ready:
        chunks = [c for c in session.chunks.values() if c.source_id == source.id]
        if not chunks:
            continue
        step = max(1, len(chunks) // per_source)
        for chunk in chunks[::step][:per_source]:
            if used + len(chunk.text) > _MAX_QUIZ_INPUT_CHARS:
                break
            citations.append(
                Citation(
                    ref=source.ref,
                    source_id=source.id,
                    source_title=source.title,
                    source_kind=source.kind,
                    locator=chunk.locator,
                    quote=chunk.text,
                )
            )
            used += len(chunk.text)

    if not citations:
        raise QuizUnavailable("The loaded sources do not contain enough text for a quiz.")
    return citations


async def generate_quiz(session: Session, question_count: int = 5) -> list[QuizQuestion]:
    citations = _sample_context(session, question_count)
    context = build_context_block(citations)

    response = await get_openai_client().responses.parse(
        model=get_settings().openai_chat_model,
        instructions=QUIZ_SYSTEM_PROMPT,
        input=f"Write exactly {question_count} questions.\n\nSOURCE MATERIAL\n\n{context}",
        text_format=QuizResponse,
    )

    parsed = response.output_parsed
    if parsed is None or not parsed.questions:
        raise QuizUnavailable("The quiz could not be generated from this material. Please try again.")

    valid = [q for q in parsed.questions if 0 <= q.correct_index < len(q.options)]
    if not valid:
        raise QuizUnavailable("The quiz came back malformed. Please try again.")
    return valid[:question_count]
