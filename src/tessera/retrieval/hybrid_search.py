"""Hybrid (vector + lexical) search — the public entry point for retrieval.

Workers call :func:`search` to obtain a ranked list of
:class:`RetrievedDocument` instances. The implementation:

1. Embeds the query using the active backend.
2. Runs an HNSW nearest-neighbour query against pgvector.
3. Reranks the candidates with RRF fusion.
4. Materialises :class:`RetrievedDocument` records for the agent state.
"""

from __future__ import annotations

from tessera.agent.sdk import instrument
from tessera.agent.state import RetrievedDocument
from tessera.retrieval import citations, embeddings, reranking, store
from tessera.settings import LanguageCode  # noqa: TCH001 — used in signature at runtime

__all__ = ["search"]


_VECTOR_OVERFETCH: int = 3

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
) -> list[RetrievedDocument]:
    """Search ``corpus`` for ``query`` and return top-k hits.

    When ``language`` is ``None`` the search spans all languages — useful for
    regulatory corpora stored in their source language regardless of the active
    conversation locale. Over-fetches by :data:`_VECTOR_OVERFETCH` so the
    reranker has enough candidates to meaningfully reorder.
    """
    if not query.strip():
        return []

    with instrument.retrieval_span(corpus, language) as span:
        [query_vec] = await embeddings.embed([query])
        raw_hits = await store.knn_search(
            query_embedding=query_vec,
            corpus=corpus,
            language=language,
            top_k=top_k * _VECTOR_OVERFETCH,
        )
        categories, top_score = _cited_categories(raw_hits)
        cited_count = sum(1 for hit in raw_hits if hit.score >= _CITATION_THRESHOLD)
        instrument.annotate_retrieval(
            span, categories=categories, hit_count=cited_count, top_score=top_score
        )
        # Durable, live citation telemetry: record this query + its cited
        # categories in Postgres. Best-effort — never breaks the turn.
        await citations.record_retrieval_query(categories)
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
