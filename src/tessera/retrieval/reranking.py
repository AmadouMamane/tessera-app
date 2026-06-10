"""Reranker — blends vector and lexical scores into a single ordering.

We compute a normalised reciprocal-rank fusion across the dense (cosine) and
sparse (BM25-lite token overlap) signals. Reciprocal-rank fusion is robust
to the very different score distributions of the two signals and has the
useful property of being parameter-light (only ``k``).
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from tessera.retrieval.store import VectorHit

__all__ = ["RerankedHit", "lexical_score", "rerank"]


_RRF_K: Final[int] = 60
# A document ranked first by *both* signals scores ``2 / (k + 1)``; we divide by
# this maximum so ``fused_score`` lands in ``[0, 1]`` (1.0 = top of both lists,
# 0.5 = top of one only). Normalising keeps the ordering identical but makes the
# score an interpretable confidence on a stable scale, so downstream thresholds
# do not silently break when the fusion method changes.
_MAX_FUSED: Final[float] = 2.0 / (_RRF_K + 1)
_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


@dataclass(frozen=True, slots=True)
class RerankedHit:
    """A vector hit with a fused score in ``[0, 1]`` (1.0 = ranked first by both signals)."""

    hit: VectorHit
    fused_score: float


def _tokenise(text: str) -> list[str]:
    return [match.group(0).lower() for match in _TOKEN_RE.finditer(text)]


def lexical_score(query: str, document: str) -> float:
    """Cheap BM25-like score; deterministic and dependency-free."""
    query_tokens = _tokenise(query)
    doc_tokens = _tokenise(document)
    if not query_tokens or not doc_tokens:
        return 0.0
    counts = Counter(doc_tokens)
    score = 0.0
    for token in set(query_tokens):
        if token not in counts:
            continue
        tf = counts[token]
        idf = math.log(1 + 1 / (1 + sum(1 for t in doc_tokens if t == token)))
        score += tf * idf
    return score / math.log(2 + len(doc_tokens))


def _rrf(rank: int) -> float:
    return 1.0 / (_RRF_K + rank)


def rerank(
    query: str,
    hits: Sequence[VectorHit],
    *,
    top_k: int | None = None,
) -> list[RerankedHit]:
    """Return ``hits`` reordered by a vector + lexical RRF fusion."""
    if not hits:
        return []

    vector_ranking: dict[tuple[str, str], int] = {
        (hit.source, hit.chunk_id): rank
        for rank, hit in enumerate(sorted(hits, key=lambda h: h.score, reverse=True), start=1)
    }
    lexical_ranked: Iterable[tuple[VectorHit, float]] = (
        (hit, lexical_score(query, hit.text)) for hit in hits
    )
    lexical_ranking: dict[tuple[str, str], int] = {
        (hit.source, hit.chunk_id): rank
        for rank, (hit, _) in enumerate(
            sorted(lexical_ranked, key=lambda pair: pair[1], reverse=True), start=1
        )
    }

    fused: list[RerankedHit] = []
    for hit in hits:
        key = (hit.source, hit.chunk_id)
        score = (_rrf(vector_ranking[key]) + _rrf(lexical_ranking[key])) / _MAX_FUSED
        fused.append(RerankedHit(hit=hit, fused_score=score))

    fused.sort(key=lambda item: item.fused_score, reverse=True)
    if top_k is not None:
        fused = fused[:top_k]
    return fused
