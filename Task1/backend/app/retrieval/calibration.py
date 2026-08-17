"""Work out what "unrelated" scores like, for this provider and this corpus.

An absolute cosine threshold cannot be portable. Measured against the same corpus,
a deliberately off-topic question scores ~0.05 with OpenAI's `text-embedding-3-small`
and ~0.48 with Gemini's `gemini-embedding-001`; a fixed floor that works for one
silently accepts everything on the other. (That is not hypothetical -- a floor tuned
for OpenAI let "average rainfall in Mumbai" through as in-scope on Gemini.)

So the floor is derived instead of configured: embed a handful of deliberately
mundane, unrelated probe questions, see how well the *best* chunk matches them, and
require a real question to clear that baseline by a margin of the remaining headroom.
The probes are constant, so their embeddings are computed once per process, and the
comparison against a session's chunks is a matmul -- no extra API calls per question.
"""

from __future__ import annotations

import statistics

import numpy as np

from .embeddings import VectorIndex, embed_texts

# Deliberately ordinary questions from unrelated domains. The median is used rather
# than the maximum so that one probe coincidentally matching a corpus (a meteorology
# deck, say) cannot inflate the baseline and cause false refusals.
PROBE_QUERIES = (
    "What was the average rainfall in Mumbai during July 1998?",
    "Who won the 1994 football world cup final?",
    "How do I bake sourdough bread at home?",
    "What is the tax treatment of capital gains in Germany?",
    "Which vaccinations does a kitten need in its first year?",
)

_probe_matrix: np.ndarray | None = None


async def probe_vectors() -> np.ndarray:
    """Embed the probe questions once per process."""
    global _probe_matrix
    if _probe_matrix is None:
        _probe_matrix = await embed_texts(list(PROBE_QUERIES))
    return _probe_matrix


async def unrelated_baseline(vectors: VectorIndex) -> float:
    """Median best-match score an unrelated question gets against these chunks."""
    if len(vectors) == 0:
        return 0.0

    probes = await probe_vectors()
    bests = [max(score for _id, score in vectors.search(probe, limit=1)) for probe in probes]
    return float(statistics.median(bests)) if bests else 0.0


def scope_threshold(baseline: float, margin: float) -> float:
    """Require a question to clear the unrelated baseline by a share of the headroom.

    `margin` is a fraction of the distance from the baseline to a perfect match, so
    the same setting behaves sensibly whichever embedding model is configured.
    """
    baseline = min(max(baseline, 0.0), 0.99)
    return baseline + (1.0 - baseline) * margin
