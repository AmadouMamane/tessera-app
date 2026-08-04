"""Hybrid (vector + lexical) search — the public entry point for retrieval.

Workers call :func:`search` to obtain a ranked list of
:class:`RetrievedDocument` instances. The implementation:

1. Embeds the query using the active backend.
2. Runs, **concurrently**, an HNSW nearest-neighbour query against pgvector and
   a full-text query against the GIN index, each over-fetched for fusion.
3. Fuses the two candidate lists with RRF.
4. Materialises :class:`RetrievedDocument` records for the agent state.

Step 2 is what "hybrid" means and it did not exist until 2026-08-04. Before
that, the only lexical signal was a Python token-overlap score applied to the
vector candidates *after* the fact — so the search reordered what the dense arm
returned and could never reach anything else. See ADR 0050.
"""

from __future__ import annotations

import asyncio
import sys

from tessera.agent.sdk import instrument
from tessera.agent.state import RetrievedDocument
from tessera.retrieval import citations, embeddings, reranking, store
from tessera.settings import LanguageCode  # noqa: TCH001 — used in signature at runtime

__all__ = ["search"]


_VECTOR_OVERFETCH: int = 3

#: One warning per process for a store with no lexical index. The search still answers, on
#: the dense arm alone — but "degraded silently" is the failure mode this repository keeps
#: finding, so it degrades out loud instead (ADR 0026: a witness that cannot see says so).
_lexical_arm_warned: bool = False


async def _lexical_arm(
    *, query: str, query_embedding: list[float], corpus: str, language: LanguageCode | None, k: int
) -> list[store.LexicalHit] | None:
    """The lexical candidates, or ``None`` when this store has no lexical index.

    ``None`` and ``[]`` are different answers and the caller treats them differently: an empty
    list is "the index was asked and matched nothing" (an ordinary outcome — a query of pure
    stop words), ``None`` is "there is no index to ask".
    """
    global _lexical_arm_warned
    try:
        return await store.lexical_search(
            query=query,
            query_embedding=query_embedding,
            corpus=corpus,
            language=language,
            top_k=k,
        )
    except store.LexicalIndexUnavailableError as exc:
        if not _lexical_arm_warned:
            _lexical_arm_warned = True
            print(  # the repo's fail-open-loudly idiom
                f"[hybrid_search] no lexical index: {exc} "
                "— serving the dense arm only, with the historical in-candidate reranker.",
                file=sys.stderr,
            )
        return None


async def _no_lexical_arm() -> list[store.LexicalHit] | None:
    """``rerank=False`` — ADR 0035's plain dense retriever, with no lexical query at all."""
    return None


# Cosine-similarity gate for "this query cited this source", kept identical to
# scripts/probe_retrieval.py so the live Phoenix-backed citation telemetry and
# the offline probe measure the same thing.
_CITATION_THRESHOLD: float = 0.55


def _cited_categories(hits: list[store.VectorHit]) -> tuple[list[str], float | None]:
    """Source categories among ``hits`` whose cosine score clears the threshold.

    Returns the sorted category ids and the best cosine score in the candidate
    set (``None`` when there are no candidates), for the retrieval span.
    """
    cats: set[str] = set()
    top: float | None = None
    for hit in hits:
        if top is None or hit.score > top:
            top = hit.score
        if hit.score < _CITATION_THRESHOLD:
            continue
        category = str(hit.metadata.get("category", "")).strip()
        if category:
            cats.add(category)
    return sorted(cats), top


async def search(
    *,
    query: str,
    language: LanguageCode | None,
    corpus: str,
    top_k: int = 4,
    rerank: bool = True,
) -> list[RetrievedDocument]:
    """Search ``corpus`` for ``query`` and return top-k hits.

    When ``language`` is ``None`` the search spans all languages — useful for
    regulatory corpora stored in their source language regardless of the active
    conversation locale. With ``rerank`` (the default, the historical truth)
    both arms over-fetch by :data:`_VECTOR_OVERFETCH` so fusion has enough
    candidates to be meaningful; ``rerank=False`` (ADR 0035, a declared per-agent
    decision) serves the raw vector order, skips the over-fetch, **and skips the
    lexical arm** — the knob's declared meaning is "the dense retriever, plain",
    and ADR 0050 widens what it turns off without changing what it means.
    """
    if not query.strip():
        return []

    with instrument.retrieval_span(corpus, language) as span:
        [query_vec] = await embeddings.embed([query])
        depth = top_k * _VECTOR_OVERFETCH if rerank else top_k
        # The two arms are independent queries and neither needs the other's answer, so they
        # run concurrently: the hybrid search costs one round trip, not two.
        raw_hits, lexical_hits = await asyncio.gather(
            store.knn_search(
                query_embedding=query_vec, corpus=corpus, language=language, top_k=depth
            ),
            _lexical_arm(
                query=query,
                query_embedding=query_vec,
                corpus=corpus,
                language=language,
                k=depth,
            )
            if rerank
            else _no_lexical_arm(),
        )
        # The citation gauge stays on the DENSE arm, deliberately. It is a cosine-similarity
        # measurement of what the embeddings retrieve, and `scripts/probe_retrieval.py` keeps
        # measuring exactly that offline. Folding the lexical recoveries in here would move
        # the number without moving the thing, which reads as an improvement and is a change
        # of definition. What the lexical arm recovers is measured by the recall probe.
        categories, top_score = _cited_categories(raw_hits)
        cited_count = sum(1 for hit in raw_hits if hit.score >= _CITATION_THRESHOLD)
        instrument.annotate_retrieval(
            span, categories=categories, hit_count=cited_count, top_score=top_score
        )
        # Durable, live citation telemetry: record this query + its cited
        # categories in Postgres. Best-effort — never breaks the turn.
        await citations.record_retrieval_query(categories)

        if not rerank:
            return [
                RetrievedDocument(
                    source=hit.source,
                    chunk_id=hit.chunk_id,
                    language=hit.language,
                    text=hit.text,
                    score=hit.score,
                    metadata=hit.metadata,
                )
                for hit in raw_hits[:top_k]
            ]

        if lexical_hits is None:
            # No lexical index in this store: the declared fallback, already warned about.
            if not raw_hits:
                return []
            reranked = reranking.rerank(query=query, hits=raw_hits, top_k=top_k)
            return [
                RetrievedDocument(
                    source=item.hit.source,
                    chunk_id=item.hit.chunk_id,
                    language=item.hit.language,
                    text=item.hit.text,
                    score=item.fused_score,
                    metadata=item.hit.metadata,
                )
                for item in reranked
            ]

        return [
            RetrievedDocument(
                source=item.source,
                chunk_id=item.chunk_id,
                language=item.language,
                text=item.text,
                score=item.fused_score,
                metadata=item.metadata,
            )
            for item in reranking.fuse(raw_hits, lexical_hits, top_k=top_k)
        ]
