"""Corpus coverage gaps (ADR 0010, idea #28).

Retrieval always returns *something*; the question is whether what it returned is
actually about the query. When the best retrieved chunk is only weakly related to
the question, the corpus has a gap — "no docs on this" — and the agent is at high
risk of answering from parametric memory instead of grounded knowledge. This
module embeds the question and its retrieved chunks and reports the best and mean
similarity, flagging a coverage gap when even the best chunk is too far away.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from tessera.retrieval.embeddings import embed

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

__all__ = ["CoverageReport", "measure_coverage"]

_COVERAGE_THRESHOLD = 0.5  # best similarity below this is a coverage gap


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


@dataclass(frozen=True, slots=True)
class CoverageReport:
    """How well the retrieved chunks cover the question."""

    n_chunks: int
    max_similarity: float
    mean_similarity: float
    covered: bool  # best chunk clears the coverage threshold
    similarities: list[float] = field(default_factory=list)


async def measure_coverage(
    *,
    question: str,
    chunks: Sequence[str],
    threshold: float = _COVERAGE_THRESHOLD,
    embedder: Callable[[Sequence[str]], Awaitable[list[list[float]]]] | None = None,
) -> CoverageReport:
    """Measure how well ``chunks`` cover ``question``.

    Args:
        question: The user question.
        chunks: The retrieved context chunks.
        threshold: Minimum best-chunk cosine to count as covered.
        embedder: Async embedding function; defaults to the retrieval embedder.

    Returns:
        A :class:`CoverageReport`; ``covered`` is ``False`` on a coverage gap.
    """
    embed_fn = embedder or embed
    if not chunks:
        return CoverageReport(
            n_chunks=0, max_similarity=0.0, mean_similarity=0.0, covered=False
        )

    vectors = await embed_fn([question, *chunks])
    query_vec = vectors[0]
    sims = [_cosine(query_vec, chunk_vec) for chunk_vec in vectors[1:]]
    max_sim = max(sims)
    return CoverageReport(
        n_chunks=len(chunks),
        max_similarity=max_sim,
        mean_similarity=sum(sims) / len(sims),
        covered=max_sim >= threshold,
        similarities=sims,
    )
