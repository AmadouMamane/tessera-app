"""Hybrid (vector + lexical) search — the public entry point for retrieval.

Workers call :func:`search` to obtain a ranked list of
:class:`RetrievedDocument` instances. The implementation:

1. Embeds the query using the active backend.
2. Runs an HNSW nearest-neighbour query against pgvector.
3. Reranks the candidates with RRF fusion.
4. Materialises :class:`RetrievedDocument` records for the agent state.
"""

from __future__ import annotations

from tessera.agent.state import RetrievedDocument
from tessera.observability.instrumentation import start_span
from tessera.observability.metrics import RETRIEVAL_DOCUMENTS_TOTAL
from tessera.observability.schema import TelemetrySpan
from tessera.retrieval import embeddings, reranking, store
from tessera.settings import LanguageCode  # noqa: TCH001 — used in signature at runtime

__all__ = ["search"]


_VECTOR_OVERFETCH: int = 3


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

    language_label = language.value if language is not None else "all"
    with start_span(
        TelemetrySpan.RETRIEVAL_QUERY,
        {
            "target": corpus,
            "language": language_label,
        },
    ):
        [query_vec] = await embeddings.embed([query])
        raw_hits = await store.knn_search(
            query_embedding=query_vec,
            corpus=corpus,
            language=language,
            top_k=top_k * _VECTOR_OVERFETCH,
        )
        if not raw_hits:
            RETRIEVAL_DOCUMENTS_TOTAL.labels(target=corpus, language=language_label).inc(0)
            return []

        reranked = reranking.rerank(query=query, hits=raw_hits, top_k=top_k)
        documents = [
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
        RETRIEVAL_DOCUMENTS_TOTAL.labels(target=corpus, language=language_label).inc(len(documents))
        return documents
