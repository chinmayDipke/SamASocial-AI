"""Answering a question: condense -> retrieve -> stream.

The condense step is what makes follow-ups work. "Explain that more simply" has no
retrievable content of its own; rewriting it against the conversation into a
standalone query is the difference between finding the right chunks and finding none.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

import openai

from ..config import get_settings
from ..retrieval import hybrid
from ..retrieval.calibration import scope_threshold, unrelated_baseline
from ..retrieval.embeddings import embed_texts
from ..schemas import ChatMessage, Chunk, Citation, SourceKind
from ..sessions import Session, Source
from .client import get_openai_client
from .errors import describe_llm_error
from .prompts import (
    ANSWER_SYSTEM_PROMPT,
    CONDENSE_SYSTEM_PROMPT,
    NO_SOURCES_REPLY,
    OUT_OF_SCOPE_REPLY,
    build_answer_input,
    build_context_block,
)

logger = logging.getLogger(__name__)

# A stream event: (event name, JSON-serialisable payload).
StreamEvent = tuple[str, dict]


@dataclass(slots=True)
class Retrieval:
    query: str
    citations: list[Citation] = field(default_factory=list)
    context: str = ""
    in_scope: bool = False
    best_vector_score: float = 0.0
    term_coverage: float = 0.0
    # The derived floor this question was judged against, kept for logging.
    threshold: float = 0.0


def citation_url(source: Source, chunk: Chunk) -> str | None:
    """Deep link back into the original material where the format allows one."""
    if source.kind is SourceKind.YOUTUBE and source.url:
        return f"{source.url}&t={max(chunk.start_position - 2, 0)}s"
    if source.kind is SourceKind.WEB:
        return source.url
    return None


async def condense_query(session: Session, message: str) -> str:
    """Rewrite a follow-up into a standalone query. Falls back to the raw message."""
    history = session.recent_messages(get_settings().max_history_messages)
    if not history:
        return message

    transcript = "\n".join(
        f"{'Learner' if m.role == 'user' else 'Assistant'}: {m.content}" for m in history
    )
    try:
        response = await get_openai_client().chat.completions.create(
            model=get_settings().condense_model,
            messages=[
                {"role": "system", "content": CONDENSE_SYSTEM_PROMPT},
                {"role": "user", "content": f"CONVERSATION\n{transcript}\n\nLATEST MESSAGE\n{message}"},
            ],
        )
        rewritten = (response.choices[0].message.content or "").strip()
    except Exception:
        return message

    # Guard against a model that returns an explanation instead of a query.
    if not rewritten or len(rewritten) > 400:
        return message
    return rewritten


async def retrieve(session: Session, query: str) -> Retrieval:
    """Hybrid search across every ready source in the session."""
    settings = get_settings()
    outcome = Retrieval(query=query)
    if not session.chunks:
        return outcome

    query_matrix = await embed_texts([query])
    vector_hits = session.vectors.search(query_matrix[0], limit=settings.retrieval_top_k * 3)
    bm25_hits = session.bm25.search(query, limit=settings.retrieval_top_k * 3)

    # What does an unrelated question score against this corpus? Cached until the
    # corpus changes, because it depends on both the embedding model and the sources.
    if session.scope_baseline is None or session.scope_baseline_chunks != len(session.chunks):
        session.scope_baseline = await unrelated_baseline(session.vectors)
        session.scope_baseline_chunks = len(session.chunks)

    outcome.threshold = scope_threshold(session.scope_baseline, settings.scope_margin)
    outcome.best_vector_score = max((score for _id, score in vector_hits), default=0.0)
    outcome.term_coverage = session.bm25.query_term_coverage(query)
    outcome.in_scope = (
        outcome.best_vector_score >= outcome.threshold
        or outcome.term_coverage >= settings.scope_term_coverage
    )

    logger.info(
        "scope check: best=%.3f threshold=%.3f (baseline=%.3f) coverage=%.2f -> %s",
        outcome.best_vector_score,
        outcome.threshold,
        session.scope_baseline,
        outcome.term_coverage,
        "in scope" if outcome.in_scope else "out of scope",
    )
    if not outcome.in_scope:
        return outcome

    ranked = hybrid.fuse(session.chunks, bm25_hits, vector_hits, rrf_k=settings.rrf_k)
    selected = hybrid.select_context(
        ranked,
        top_k=settings.retrieval_top_k,
        char_budget=settings.context_char_budget,
        max_per_source=settings.max_chunks_per_source,
    )
    if not selected:
        outcome.in_scope = False
        return outcome

    for item in selected:
        source = session.sources.get(item.chunk.source_id)
        if source is None:
            continue
        outcome.citations.append(
            Citation(
                ref=source.ref,
                source_id=source.id,
                source_title=source.title,
                source_kind=source.kind,
                locator=item.chunk.locator,
                quote=item.chunk.text,
                url=citation_url(source, item.chunk),
            )
        )

    outcome.context = build_context_block(outcome.citations)
    return outcome


def _loaded_topics(session: Session) -> str:
    titles = [source.title for source in session.ready_sources]
    if not titles:
        return "nothing yet"
    if len(titles) == 1:
        return titles[0]
    return f"{', '.join(titles[:-1])} and {titles[-1]}"


async def stream_chat(session: Session, message: str) -> AsyncIterator[StreamEvent]:
    """Yield SSE-shaped events for one turn, recording it in the session history."""
    settings = get_settings()

    if not session.ready_sources:
        yield ("token", {"text": NO_SOURCES_REPLY})
        yield ("citations", {"citations": []})
        yield ("done", {})
        return

    yield ("status", {"stage": "retrieving"})
    search_query = await condense_query(session, message)
    retrieval = await retrieve(session, search_query)

    if not retrieval.in_scope:
        reply = OUT_OF_SCOPE_REPLY.format(topics=_loaded_topics(session))
        session.messages.append(ChatMessage(role="user", content=message))
        session.messages.append(ChatMessage(role="assistant", content=reply))
        yield ("token", {"text": reply})
        yield ("citations", {"citations": []})
        yield ("done", {"out_of_scope": True})
        return

    yield (
        "status",
        {
            "stage": "generating",
            "chunks": len(retrieval.citations),
            "query": retrieval.query,
        },
    )

    history = [
        {"role": m.role, "content": m.content}
        for m in session.recent_messages(settings.max_history_messages)
    ]
    answer_input = build_answer_input(message, retrieval.context, history)

    messages = [
        {"role": "system", "content": ANSWER_SYSTEM_PROMPT},
        {"role": "user", "content": answer_input},
    ]

    collected: list[str] = []
    failure: str | None = None

    # A 5xx before any token is worth one retry -- providers do drop streams. Once
    # text has been sent we keep the partial answer instead, since re-running would
    # repeat what the reader has already seen.
    for attempt in range(2):
        try:
            stream = await get_openai_client().chat.completions.create(
                model=settings.llm_chat_model,
                messages=messages,
                stream=True,
            )
            async for chunk in stream:
                if not chunk.choices:
                    continue  # Some providers emit usage-only chunks with no choices.
                text = getattr(chunk.choices[0].delta, "content", None)
                if text:
                    collected.append(text)
                    yield ("token", {"text": text})
            failure = None
            break
        # Any failure is reported to the caller as an error frame, never raised.
        except Exception as exc:
            failure = describe_llm_error(exc) or "The answer could not be completed."
            retryable = isinstance(exc, openai.APIStatusError) and exc.status_code >= 500
            if collected or not retryable or attempt == 1:
                logger.warning("Answer stream failed: %s", exc)
                break
            logger.info("Answer stream failed before any output; retrying once: %s", exc)

    answer = "".join(collected).strip()

    # Record the turn even when generation was cut short, so the conversation stays
    # coherent and the next follow-up still has something to resolve against.
    if answer or failure is None:
        session.messages.append(ChatMessage(role="user", content=message))
        session.messages.append(ChatMessage(role="assistant", content=answer))

    if failure:
        yield ("error", {"detail": failure})
        if not answer:
            yield ("done", {})
            return

    # Only report citations the model actually referenced, so the chips match the text.
    cited = [c for c in retrieval.citations if f"[{c.ref} | {c.locator}]" in answer]
    yield ("citations", {"citations": [c.model_dump() for c in (cited or retrieval.citations)]})
    yield ("done", {})
