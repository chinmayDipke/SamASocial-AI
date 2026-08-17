"""Fuse keyword and dense rankings, then assemble a context window.

Reciprocal rank fusion is used instead of score blending because BM25 scores and
cosine similarities are not on comparable scales; RRF only needs the *order* from
each retriever, so neither has to be calibrated against the other.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..schemas import Chunk


@dataclass(slots=True)
class RetrievedChunk:
    chunk: Chunk
    fused_score: float
    bm25_score: float
    vector_score: float


def reciprocal_rank_fusion(
    rankings: list[list[tuple[str, float]]],
    *,
    k: int = 60,
) -> dict[str, float]:
    """Combine ranked id lists into one score per id: sum of 1 / (k + rank)."""
    fused: dict[str, float] = {}
    for ranking in rankings:
        for rank, (chunk_id, _score) in enumerate(ranking, start=1):
            fused[chunk_id] = fused.get(chunk_id, 0.0) + 1.0 / (k + rank)
    return fused


def fuse(
    chunks_by_id: dict[str, Chunk],
    bm25_hits: list[tuple[str, float]],
    vector_hits: list[tuple[str, float]],
    *,
    rrf_k: int = 60,
) -> list[RetrievedChunk]:
    """Rank chunks by fused relevance, keeping each retriever's raw score for diagnostics."""
    fused_scores = reciprocal_rank_fusion([bm25_hits, vector_hits], k=rrf_k)
    bm25_scores = dict(bm25_hits)
    vector_scores = dict(vector_hits)

    results = [
        RetrievedChunk(
            chunk=chunks_by_id[chunk_id],
            fused_score=score,
            bm25_score=bm25_scores.get(chunk_id, 0.0),
            vector_score=vector_scores.get(chunk_id, 0.0),
        )
        for chunk_id, score in fused_scores.items()
        if chunk_id in chunks_by_id
    ]
    results.sort(key=lambda item: item.fused_score, reverse=True)
    return results


def select_context(
    ranked: list[RetrievedChunk],
    *,
    top_k: int,
    char_budget: int,
    max_per_source: int,
) -> list[RetrievedChunk]:
    """Take the best chunks, but stop any one source from crowding out the others.

    With several sources loaded, a single long PDF will usually dominate a pure
    top-k cut. Capping per-source share is what makes cross-source answers -- and
    the "which source did this come from" bonus requirement -- actually work.
    """
    selected: list[RetrievedChunk] = []
    per_source: dict[str, int] = {}
    used_chars = 0

    for item in ranked:
        if len(selected) >= top_k:
            break
        source_id = item.chunk.source_id
        if per_source.get(source_id, 0) >= max_per_source:
            continue
        if used_chars + len(item.chunk.text) > char_budget and selected:
            continue
        selected.append(item)
        per_source[source_id] = per_source.get(source_id, 0) + 1
        used_chars += len(item.chunk.text)

    return selected
