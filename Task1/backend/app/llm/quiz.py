"""Quiz mode: auto-generate multiple-choice questions from the loaded sources.

Asks for JSON against an explicit schema. Providers vary in how strictly they
support `response_format`, so this degrades in two steps -- json_schema, then
plain json_object -- and validates the result with Pydantic either way, so a
malformed quiz is rejected rather than shown.
"""

from __future__ import annotations

import json
import logging

import openai

from ..config import get_settings
from ..schemas import Citation, QuizQuestion, QuizResponse
from ..sessions import Session
from .client import get_openai_client
from .prompts import QUIZ_SYSTEM_PROMPT, build_context_block

logger = logging.getLogger(__name__)

_MAX_QUIZ_INPUT_CHARS = 12_000

# Written out rather than derived from the Pydantic model: providers reject
# keywords like minItems/maxItems, and this stays the portable subset.
QUIZ_SCHEMA = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "options": {"type": "array", "items": {"type": "string"}},
                    "correct_index": {"type": "integer"},
                    "explanation": {"type": "string"},
                    "source_ref": {"type": "string"},
                    "locator": {"type": "string"},
                },
                "required": [
                    "question",
                    "options",
                    "correct_index",
                    "explanation",
                    "source_ref",
                    "locator",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["questions"],
    "additionalProperties": False,
}


class QuizUnavailable(RuntimeError):
    """Raised when a quiz cannot be produced from the loaded material."""


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


def _extract_json(text: str) -> dict:
    """Parse a JSON object, tolerating markdown fences and surrounding prose."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        cleaned = cleaned.removeprefix("json").strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end <= start:
            raise
        return json.loads(cleaned[start : end + 1])


async def generate_quiz(session: Session, question_count: int = 5) -> list[QuizQuestion]:
    settings = get_settings()
    citations = _sample_context(session, question_count)
    context = build_context_block(citations)

    messages = [
        {"role": "system", "content": QUIZ_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Write exactly {question_count} questions.\n\n"
                f"Return JSON of the form "
                f'{{"questions": [{{"question": str, "options": [str, ...], '
                f'"correct_index": int, "explanation": str, "source_ref": str, "locator": str}}]}}\n\n'
                f"SOURCE MATERIAL\n\n{context}"
            ),
        },
    ]

    client = get_openai_client()
    formats: list[dict] = [
        {"type": "json_schema", "json_schema": {"name": "quiz", "schema": QUIZ_SCHEMA, "strict": True}},
        {"type": "json_object"},
    ]

    last_error: Exception | None = None
    for response_format in formats:
        try:
            response = await client.chat.completions.create(
                model=settings.llm_chat_model,
                messages=messages,
                response_format=response_format,
            )
            payload = _extract_json(response.choices[0].message.content or "")
            parsed = QuizResponse.model_validate(payload)
            break
        except (openai.BadRequestError, openai.UnprocessableEntityError) as exc:
            # This provider does not support that response_format -- try the simpler one.
            logger.info("Quiz response_format %s rejected: %s", response_format["type"], exc)
            last_error = exc
        except (json.JSONDecodeError, ValueError) as exc:
            logger.info("Quiz output was not valid against the schema: %s", exc)
            last_error = exc
    else:
        raise QuizUnavailable(
            "The quiz could not be generated from this material. Please try again."
        ) from last_error

    valid = [q for q in parsed.questions if 0 <= q.correct_index < len(q.options)]
    if not valid:
        raise QuizUnavailable("The quiz came back malformed. Please try again.")
    return valid[:question_count]
