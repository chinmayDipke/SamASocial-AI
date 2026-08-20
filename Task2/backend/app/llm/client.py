"""Shared LLM plumbing: the client, the structured-output ladder, token streaming.

Any provider that speaks the OpenAI Chat Completions wire format works here --
OpenAI, Google Gemini, Groq, Together -- selected with `LLM_BASE_URL`.

Both JSON-producing steps of a turn (the intake read and the planner) need the
same defence, so it lives here once instead of twice. Providers disagree about
`response_format`: some honour a full `json_schema`, some only accept
`json_object`, some accept the schema and then wrap the answer in a markdown
fence anyway. `request_json` walks down that ladder and `extract_json` copes with
the fence, and the caller still validates with Pydantic -- so a malformed answer
is rejected rather than half-parsed.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from functools import lru_cache

import openai
from openai import AsyncOpenAI

from ..config import get_settings

logger = logging.getLogger(__name__)

# A chat message as the wire format wants it.
Message = dict[str, str]


class MissingApiKey(RuntimeError):
    """Raised when the server is started without an LLM API key."""


class StructuredOutputError(RuntimeError):
    """Raised when no response_format produced JSON that parsed."""


@lru_cache
def get_openai_client() -> AsyncOpenAI:
    settings = get_settings()
    if not settings.llm_api_key:
        raise MissingApiKey(
            "No LLM API key is set. Copy backend/.env.example to backend/.env and set "
            "LLM_API_KEY (GEMINI_API_KEY and OPENAI_API_KEY are also accepted)."
        )

    # The SDK retries connection errors, 429s and 5xx with backoff. A whole course
    # plan is a long generation, so the timeout is generous.
    return AsyncOpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.resolved_base_url,
        max_retries=3,
        timeout=120.0,
    )


def extract_json(text: str) -> dict:
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


async def request_json(
    model: str,
    messages: list[Message],
    schema: dict,
    name: str,
) -> dict:
    """Ask for one JSON object, degrading json_schema -> json_object if refused.

    Only format rejections and unparseable output are absorbed. Authentication,
    quota and connection failures propagate, because `llm/errors.py` turns those
    into something the mentor can actually act on.
    """
    client = get_openai_client()
    formats: list[dict] = [
        {"type": "json_schema", "json_schema": {"name": name, "schema": schema, "strict": True}},
        {"type": "json_object"},
    ]

    last_error: Exception | None = None
    for response_format in formats:
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                response_format=response_format,
            )
            return extract_json(response.choices[0].message.content or "")
        except (openai.BadRequestError, openai.UnprocessableEntityError) as exc:
            # This provider does not support that response_format -- try the simpler one.
            logger.info("%s response_format %s rejected: %s", name, response_format["type"], exc)
            last_error = exc
        except (json.JSONDecodeError, ValueError) as exc:
            logger.info("%s output was not parseable JSON: %s", name, exc)
            last_error = exc

    raise StructuredOutputError(f"{name}: no usable JSON came back") from last_error


async def stream_text(model: str, messages: list[Message]) -> AsyncIterator[str]:
    """Yield the assistant's reply token by token."""
    stream = await get_openai_client().chat.completions.create(
        model=model,
        messages=messages,
        stream=True,
    )
    async for chunk in stream:
        if not chunk.choices:
            continue  # Some providers emit usage-only chunks with no choices.
        text = getattr(chunk.choices[0].delta, "content", None)
        if text:
            yield text
