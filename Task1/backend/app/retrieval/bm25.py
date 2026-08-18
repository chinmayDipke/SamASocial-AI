"""A small BM25-Okapi index.

Written by hand rather than pulled from a library so the tokeniser is ours: light
stemming and stop-word removal matter more for short questions than raw ranking
sophistication does, and `query_term_coverage` gives the chat layer a cheap,
absolute signal for "these words appear nowhere in the loaded sources".
"""

from __future__ import annotations

import math
import re
from collections import Counter

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Deliberately short: aggressive stop-word lists hurt recall on technical questions.
_STOPWORDS = frozenset(
    [
        "a", "an", "and", "are", "as", "at", "be", "been", "but", "by", "can",
        "did", "do", "does", "for", "from", "had", "has", "have", "how", "i",
        "if", "in", "into", "is", "it", "its", "me", "my", "no", "not", "of",
        "on", "or", "our", "so", "than", "that", "the", "their", "them", "then",
        "there", "these", "they", "this", "to", "too", "was", "we", "were",
        "what", "when", "where", "which", "who", "why", "will", "with",
        "would", "you", "your",
    ]
)


def tokenize(text: str) -> list[str]:
    """Lowercase, split on non-alphanumerics, drop stop-words, trim simple plurals."""
    tokens: list[str] = []
    for raw in _TOKEN_RE.findall(text.lower()):
        if raw in _STOPWORDS or len(raw) == 1:
            continue
        # Cheap singularisation so "embeddings" matches "embedding".
        if len(raw) > 3 and raw.endswith("s") and not raw.endswith("ss"):
            raw = raw[:-1]
        tokens.append(raw)
    return tokens


class BM25Index:
    """Incremental BM25 index over chunk texts, keyed by chunk id."""

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self._ids: list[str] = []
        self._term_freqs: list[Counter[str]] = []
        self._lengths: list[int] = []
        self._doc_freq: Counter[str] = Counter()

    def __len__(self) -> int:
        return len(self._ids)

    @property
    def vocabulary(self) -> set[str]:
        return set(self._doc_freq)

    def add(self, chunk_id: str, text: str) -> None:
        tokens = tokenize(text)
        freqs = Counter(tokens)
        self._ids.append(chunk_id)
        self._term_freqs.append(freqs)
        self._lengths.append(len(tokens))
        self._doc_freq.update(freqs.keys())

    def _idf(self, term: str) -> float:
        n_docs = len(self._ids)
        doc_freq = self._doc_freq.get(term, 0)
        if not doc_freq:
            return 0.0
        # BM25 idf with the +1 guard that keeps common terms non-negative.
        return math.log(1 + (n_docs - doc_freq + 0.5) / (doc_freq + 0.5))

    def search(self, query: str, limit: int = 10) -> list[tuple[str, float]]:
        """Return `(chunk_id, score)` for the best matches, highest score first."""
        if not self._ids:
            return []

        query_terms = [t for t in tokenize(query) if t in self._doc_freq]
        if not query_terms:
            return []

        avg_len = sum(self._lengths) / len(self._lengths) or 1.0
        idf_cache = {term: self._idf(term) for term in set(query_terms)}

        scored: list[tuple[str, float]] = []
        for index, chunk_id in enumerate(self._ids):
            freqs = self._term_freqs[index]
            length = self._lengths[index]
            score = 0.0
            for term in query_terms:
                freq = freqs.get(term, 0)
                if not freq:
                    continue
                denominator = freq + self.k1 * (1 - self.b + self.b * length / avg_len)
                score += idf_cache[term] * freq * (self.k1 + 1) / denominator
            if score > 0:
                scored.append((chunk_id, score))

        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:limit]

    def query_term_coverage(self, query: str) -> float:
        """Fraction of the query's content words that appear anywhere in the corpus.

        A coverage of 0 means the question is about vocabulary the sources never use --
        a strong, model-free hint that the question is out of scope.
        """
        terms = set(tokenize(query))
        if not terms:
            return 0.0
        return sum(1 for term in terms if term in self._doc_freq) / len(terms)
