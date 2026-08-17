"""BM25 ranking, out-of-scope coverage signal, and rank fusion."""

from __future__ import annotations

from app.retrieval.bm25 import BM25Index, tokenize
from app.retrieval.hybrid import fuse, reciprocal_rank_fusion, select_context
from app.schemas import Chunk


def build_index() -> BM25Index:
    index = BM25Index()
    index.add("c1", "Vector embeddings map text into a high dimensional space for similarity search.")
    index.add("c2", "Reciprocal rank fusion merges two ranked lists without score calibration.")
    index.add("c3", "The mitochondria is the powerhouse of the cell in biology lessons.")
    return index


def test_tokenize_drops_stopwords_and_singularises() -> None:
    assert tokenize("What are the embeddings?") == ["embedding"]


def test_bm25_ranks_the_matching_document_first() -> None:
    index = build_index()
    hits = index.search("how do embeddings work", limit=3)

    assert hits, "expected at least one hit"
    assert hits[0][0] == "c1"


def test_bm25_returns_nothing_for_unknown_vocabulary() -> None:
    assert build_index().search("quarterly dividend payout") == []


def test_query_term_coverage_signals_out_of_scope() -> None:
    index = build_index()

    assert index.query_term_coverage("embeddings similarity") == 1.0
    assert index.query_term_coverage("dividend payout schedule") == 0.0


def test_rrf_rewards_agreement_between_retrievers() -> None:
    keyword = [("a", 9.0), ("b", 4.0)]
    vector = [("b", 0.9), ("a", 0.4)]

    scores = reciprocal_rank_fusion([keyword, vector], k=60)

    # "a" and "b" each rank 1st once and 2nd once, so fusion ties them.
    assert scores["a"] == scores["b"]
    # A chunk found by only one retriever scores lower than one found by both.
    solo = reciprocal_rank_fusion([[("c", 9.0)]], k=60)
    assert solo["c"] < scores["a"]


def chunk(chunk_id: str, source_id: str, text: str = "text") -> Chunk:
    return Chunk(
        id=chunk_id,
        source_id=source_id,
        text=text,
        locator="page 1",
        start_position=1,
        end_position=1,
    )


def test_fusion_is_deterministic_and_keeps_raw_scores() -> None:
    chunks = {"c1": chunk("c1", "s1"), "c2": chunk("c2", "s1")}
    bm25 = [("c1", 5.0)]
    vector = [("c2", 0.8), ("c1", 0.4)]

    first = [item.chunk.id for item in fuse(chunks, bm25, vector)]
    second = [item.chunk.id for item in fuse(chunks, bm25, vector)]

    assert first == second
    assert fuse(chunks, bm25, vector)[0].bm25_score or fuse(chunks, bm25, vector)[0].vector_score


def test_select_context_caps_chunks_per_source() -> None:
    chunks = {f"c{i}": chunk(f"c{i}", "dominant") for i in range(6)}
    chunks["other"] = chunk("other", "second")
    bm25 = [(f"c{i}", 10.0 - i) for i in range(6)] + [("other", 0.1)]
    ranked = fuse(chunks, bm25, [])

    selected = select_context(ranked, top_k=5, char_budget=10_000, max_per_source=2)
    per_source = [item.chunk.source_id for item in selected]

    assert per_source.count("dominant") == 2
    assert "second" in per_source


def test_select_context_respects_the_char_budget() -> None:
    chunks = {f"c{i}": chunk(f"c{i}", f"s{i}", text="x" * 900) for i in range(5)}
    ranked = fuse(chunks, [(f"c{i}", 5.0 - i) for i in range(5)], [])

    selected = select_context(ranked, top_k=5, char_budget=2000, max_per_source=4)

    assert 0 < len(selected) <= 2
