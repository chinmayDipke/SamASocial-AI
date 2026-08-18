"""Per-source summaries, shown on the source card once processing finishes."""

from __future__ import annotations

from ..config import get_settings
from ..schemas import Chunk
from .client import get_openai_client
from .prompts import SUMMARY_SYSTEM_PROMPT

_MAX_SUMMARY_INPUT_CHARS = 8000


def _sample_chunks(chunks: list[Chunk], budget: int = _MAX_SUMMARY_INPUT_CHARS) -> str:
    """Take an evenly spread sample so the summary reflects the whole source, not just page 1."""
    if not chunks:
        return ""

    step = max(1, len(chunks) // 8)
    sampled = chunks[::step][:8]
    parts: list[str] = []
    used = 0
    for chunk in sampled:
        text = chunk.text[: budget // len(sampled)]
        if used + len(text) > budget:
            break
        parts.append(f"[{chunk.locator}] {text}")
        used += len(text)
    return "\n\n".join(parts)


async def summarise_source(title: str, chunks: list[Chunk]) -> str | None:
    """Return a short bullet summary, or None if it could not be produced.

    A failure here must never fail ingestion -- the source is still usable for
    retrieval without its summary.
    """
    excerpt = _sample_chunks(chunks)
    if not excerpt:
        return None

    try:
        response = await get_openai_client().chat.completions.create(
            model=get_settings().llm_chat_model,
            messages=[
                {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": f"SOURCE TITLE: {title}\n\nEXCERPT\n\n{excerpt}"},
            ],
        )
        return (response.choices[0].message.content or "").strip() or None
    except Exception:
        return None
