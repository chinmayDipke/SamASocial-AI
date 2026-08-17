"""Dense retrieval over an in-memory NumPy matrix.

No FAISS: a session holds at most a few thousand chunks, so a normalised
`float32` matrix and one `matmul` is both faster end-to-end (no index build) and
avoids native dependencies that have no Python 3.14 wheels.
"""

from __future__ import annotations

import numpy as np

from ..config import get_settings
from ..llm.client import get_openai_client


async def embed_texts(texts: list[str]) -> np.ndarray:
    """Embed texts in batches, returning an L2-normalised `(n, dim)` float32 matrix."""
    if not texts:
        return np.zeros((0, 0), dtype=np.float32)

    settings = get_settings()
    client = get_openai_client()
    vectors: list[list[float]] = []

    for start in range(0, len(texts), settings.embed_batch_size):
        batch = texts[start : start + settings.embed_batch_size]
        response = await client.embeddings.create(model=settings.openai_embed_model, input=batch)
        # The API preserves input order, but `index` is authoritative -- sort by it.
        for item in sorted(response.data, key=lambda d: d.index):
            vectors.append(item.embedding)

    matrix = np.asarray(vectors, dtype=np.float32)
    return _normalise_rows(matrix)


def _normalise_rows(matrix: np.ndarray) -> np.ndarray:
    if matrix.size == 0:
        return matrix
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    np.maximum(norms, 1e-12, out=norms)
    return matrix / norms


class VectorIndex:
    """Append-only store of normalised chunk embeddings, keyed by chunk id."""

    def __init__(self) -> None:
        self._ids: list[str] = []
        self._matrix: np.ndarray | None = None

    def __len__(self) -> int:
        return len(self._ids)

    def add(self, chunk_ids: list[str], matrix: np.ndarray) -> None:
        if not chunk_ids or matrix.size == 0:
            return
        if len(chunk_ids) != matrix.shape[0]:
            raise ValueError("chunk id count does not match embedding row count")

        self._ids.extend(chunk_ids)
        self._matrix = matrix if self._matrix is None else np.vstack((self._matrix, matrix))

    def search(self, query_vector: np.ndarray, limit: int = 10) -> list[tuple[str, float]]:
        """Cosine similarity search. Both sides are normalised, so this is a dot product."""
        if self._matrix is None or not self._ids:
            return []

        scores = self._matrix @ query_vector.astype(np.float32)
        top = np.argsort(-scores)[:limit]
        return [(self._ids[int(i)], float(scores[int(i)])) for i in top]
