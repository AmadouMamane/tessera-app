"""Reranker & hybrid-search contribution (ADR 0010, idea #27).

Hybrid retrieval fuses two signals — dense (vector cosine) and sparse (lexical
overlap) — with reciprocal-rank fusion (``retrieval/reranking.py``). But which
signal is actually doing the work? If the fused order is identical to the
vector-only order, the lexical leg and the reranker are dead weight; if the
reranker keeps promoting lexically-strong chunks the vector missed, it is
earning its keep.

This module reconstructs both signals for a captured turn — re-embedding the
question and its chunks with the same embedder, and scoring the same lexical
overlap the reranker uses — then reports the **reranker lift** (chunks the fusion
pulled into the top-k that pure vector search would have dropped) and the
**lexical-vs-vector share** of the fused top results. It reuses
:func:`tessera.retrieval.reranking.lexical_score` and the same RRF constant.

**What it can and cannot see, since ADR 0050.** It analyses a *captured* chunk
set, so it measures how the two signals shaped an **ordering** — and that part
still mirrors production's arithmetic. It cannot measure what the lexical arm
**recovered**, because a recovered chunk is by definition one the dense arm did
not return, and therefore one that is not in the captured set. It also scores
the Python token-overlap approximation, where production's sparse arm is now
PostgreSQL's ``ts_rank_cd`` over a GIN index. So: a real reading of the fused
ordering, not a reading of hybrid recall. `scripts/probe_hybrid_recall.py`
measures the latter.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from tessera.retrieval.embeddings import embed
from tessera.retrieval.reranking import lexical_score

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

__all__ = ["RerankContribution", "measure_contribution"]

# Must match retrieval/reranking._RRF_K so the ordering analysis mirrors production's fusion
# arithmetic (see the module docstring for what that mirror does and does not cover).
_RRF_K = 60


@dataclass(frozen=True, slots=True)
class RerankContribution:
    """How vector vs lexical signals shaped the fused ordering of a turn."""

    n_chunks: int
    top_k: int
    reranker_lift: int  # chunks in the fused top-k that vector-only would drop
    top1_changed: bool  # the fusion changed which chunk ranks first
    mean_vector_share: float  # mean RRF share of the vector signal over fused top-k
    mean_lexical_share: float  # mean RRF share of the lexical signal over fused top-k
    vector_order: list[int] = field(default_factory=list)  # chunk indices, best first
    fused_order: list[int] = field(default_factory=list)


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _ranking(scores: Sequence[float]) -> dict[int, int]:
    """Map chunk index → 1-based rank (best score = rank 1)."""
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    return {idx: rank for rank, idx in enumerate(order, start=1)}


async def measure_contribution(
    *,
    question: str,
    chunks: Sequence[str],
    top_k: int = 4,
    embedder: Callable[[Sequence[str]], Awaitable[list[list[float]]]] | None = None,
) -> RerankContribution:
    """Decompose the fused ordering of ``chunks`` into vector vs lexical shares.

    Args:
        question: The user question.
        chunks: The retrieved context chunks, in any order.
        top_k: The cut-off the agent actually uses.
        embedder: Async embedding function; defaults to the retrieval embedder.

    Returns:
        A :class:`RerankContribution`. With no chunks, every field is zero/empty.
    """
    n = len(chunks)
    if n == 0:
        return RerankContribution(
            n_chunks=0,
            top_k=top_k,
            reranker_lift=0,
            top1_changed=False,
            mean_vector_share=0.0,
            mean_lexical_share=0.0,
        )

    embed_fn = embedder or embed
    vectors = await embed_fn([question, *chunks])
    query_vec = vectors[0]
    vector_scores = [_cosine(query_vec, cv) for cv in vectors[1:]]
    lexical_scores = [lexical_score(question, chunk) for chunk in chunks]

    vector_rank = _ranking(vector_scores)
    lexical_rank = _ranking(lexical_scores)

    fused_scores = {
        idx: 1.0 / (_RRF_K + vector_rank[idx]) + 1.0 / (_RRF_K + lexical_rank[idx])
        for idx in range(n)
    }
    fused_order = sorted(range(n), key=lambda i: fused_scores[i], reverse=True)
    vector_order = sorted(range(n), key=lambda i: vector_scores[i], reverse=True)

    k = min(top_k, n)
    fused_top = fused_order[:k]
    vector_top = set(vector_order[:k])
    reranker_lift = sum(1 for idx in fused_top if idx not in vector_top)
    top1_changed = fused_order[0] != vector_order[0]

    vector_shares: list[float] = []
    lexical_shares: list[float] = []
    for idx in fused_top:
        v = 1.0 / (_RRF_K + vector_rank[idx])
        lex = 1.0 / (_RRF_K + lexical_rank[idx])
        total = v + lex
        if total > 0:
            vector_shares.append(v / total)
            lexical_shares.append(lex / total)

    return RerankContribution(
        n_chunks=n,
        top_k=k,
        reranker_lift=reranker_lift,
        top1_changed=top1_changed,
        mean_vector_share=sum(vector_shares) / len(vector_shares) if vector_shares else 0.0,
        mean_lexical_share=sum(lexical_shares) / len(lexical_shares) if lexical_shares else 0.0,
        vector_order=vector_order[:k],
        fused_order=fused_top,
    )
