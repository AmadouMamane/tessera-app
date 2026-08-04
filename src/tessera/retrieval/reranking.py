"""Fusion — one ordering out of the dense and sparse retrievers.

Two functions live here and they do different jobs; the difference is the whole
point of this module:

* :func:`fuse` is the production path. It takes **two independently retrieved
  candidate lists** — pgvector's nearest neighbours and PostgreSQL's full-text
  matches — and fuses them. Because the lists are independent, a chunk the dense
  arm never returned can still reach the answer. This is retrieval.
* :func:`rerank` takes **one** list and reorders it with a Python token-overlap
  score. It is the historical path and it survives as the declared fallback for
  a store whose lexical index is missing. Reordering is not retrieval: whatever
  the dense arm did not return, this cannot recover.

Both use normalised reciprocal-rank fusion, which is robust to the very
different score distributions of the two signals and is parameter-light (only
``k``). RRF sums over the lists that *contain* a document: a chunk present in
one list only gets one term, never an invented rank in the other.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from tessera.retrieval.store import LexicalHit, VectorHit
    from tessera.settings import LanguageCode

__all__ = ["FusedHit", "RerankedHit", "fuse", "lexical_score", "rerank"]


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


@dataclass(frozen=True, slots=True)
class FusedHit:
    """One document out of the union of the two retrievers.

    ``fused_score`` is on the same ``[0, 1]`` scale :class:`RerankedHit` has always used —
    1.0 means first in both lists, ~0.5 means first in one and absent from the other — so the
    thresholds downstream of retrieval keep their meaning across this change.

    ``found_by`` is the field that makes the lexical arm falsifiable at runtime: ``"lexical"``
    names a document the dense arm did not return, which under the previous implementation
    could not have been retrieved at all.
    """

    source: str
    chunk_id: str
    language: LanguageCode
    text: str
    metadata: dict[str, str]
    fused_score: float
    vector_score: float
    lexical_rank: float
    found_by: str  # "both" | "vector" | "lexical"


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


def fuse(
    vector_hits: Sequence[VectorHit],
    lexical_hits: Sequence[LexicalHit],
    *,
    top_k: int | None = None,
) -> list[FusedHit]:
    """Fuse two independently retrieved lists into one ranking.

    Reciprocal-rank fusion over the *retrieved* lists: a document contributes ``1/(k+rank)``
    for each list that returned it, and nothing for a list that did not. A document found only
    lexically therefore scores ~0.5 rather than being penalised with a fabricated dense rank —
    and a document found only densely is treated identically, symmetrically.

    Args:
        vector_hits: Nearest neighbours, in any order (re-sorted by cosine here).
        lexical_hits: Full-text matches, in any order (re-sorted by ``ts_rank_cd`` here).
        top_k: Cut the result at this many documents; ``None`` returns the whole union.

    Returns:
        The union of both lists, best first. Empty when both inputs are empty.
    """
    if not vector_hits and not lexical_hits:
        return []

    # Ties broken on identity, never on arrival order. Two chunks with the same cosine are a
    # normal occurrence in a corpus with near-duplicate boilerplate, and ranking them by
    # whichever order Postgres happened to return would make the whole search a coin flip
    # between runs — the kind of nondeterminism that makes a retrieval regression unprovable.
    vector_ranking: dict[tuple[str, str], int] = {
        (hit.source, hit.chunk_id): rank
        for rank, hit in enumerate(
            sorted(vector_hits, key=lambda h: (-h.score, h.source, h.chunk_id)), start=1
        )
    }
    lexical_ranking: dict[tuple[str, str], int] = {
        (hit.source, hit.chunk_id): rank
        for rank, hit in enumerate(
            sorted(lexical_hits, key=lambda h: (-h.lexical_rank, h.source, h.chunk_id)), start=1
        )
    }

    # The dense arm wins ties on identity fields because its rows are the ones already flowing
    # through the rest of the pipeline; the two arms read the same columns of the same row, so
    # the only field that can differ is which score each carries.
    by_key: dict[tuple[str, str], FusedHit] = {}
    for lex in lexical_hits:
        by_key[lex.source, lex.chunk_id] = FusedHit(
            source=lex.source,
            chunk_id=lex.chunk_id,
            language=lex.language,
            text=lex.text,
            metadata=lex.metadata,
            fused_score=0.0,
            vector_score=lex.score,
            lexical_rank=lex.lexical_rank,
            found_by="lexical",
        )
    for dense in vector_hits:
        previous = by_key.get((dense.source, dense.chunk_id))
        by_key[dense.source, dense.chunk_id] = FusedHit(
            source=dense.source,
            chunk_id=dense.chunk_id,
            language=dense.language,
            text=dense.text,
            metadata=dense.metadata,
            fused_score=0.0,
            vector_score=dense.score,
            # A document the lexical query did not return does not match the tsquery, so its
            # cover-density rank is 0.0 by definition. That is a measurement, not a default.
            lexical_rank=previous.lexical_rank if previous is not None else 0.0,
            found_by="both" if previous is not None else "vector",
        )

    fused = [
        FusedHit(
            source=item.source,
            chunk_id=item.chunk_id,
            language=item.language,
            text=item.text,
            metadata=item.metadata,
            fused_score=(
                (_rrf(vector_ranking[key]) if key in vector_ranking else 0.0)
                + (_rrf(lexical_ranking[key]) if key in lexical_ranking else 0.0)
            )
            / _MAX_FUSED,
            vector_score=item.vector_score,
            lexical_rank=item.lexical_rank,
            found_by=item.found_by,
        )
        for key, item in by_key.items()
    ]
    fused.sort(key=lambda item: (-item.fused_score, -item.vector_score, item.source, item.chunk_id))
    if top_k is not None:
        fused = fused[:top_k]
    return fused


def rerank(
    query: str,
    hits: Sequence[VectorHit],
    *,
    top_k: int | None = None,
) -> list[RerankedHit]:
    """Return ``hits`` reordered by a vector + lexical RRF fusion, within the given set.

    The historical path, kept as the declared fallback when the lexical index is absent
    (see :func:`tessera.retrieval.store.lexical_search`). It reorders; it cannot recover.
    :func:`fuse` is what production uses when both arms are available.
    """
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
