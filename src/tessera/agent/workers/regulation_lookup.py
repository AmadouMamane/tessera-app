"""Regulation lookup worker — searches the EU regulatory corpus.

The regulatory corpus contains DORA, CNIL, BaFin, and GDPR/DSGVO chunks
indexed once at ingestion time. The worker fans out across the language's
default regulator set (defined in :mod:`tessera.settings`-aware ingestion)
and writes both the retrieved chunks and any high-confidence citations to
the state.
"""

from __future__ import annotations

from tessera.agent.state import AgentState, Citation, RetrievedDocument
from tessera.observability.metrics import CITATIONS_TOTAL
from tessera.retrieval import hybrid_search

NODE_NAME = "regulation_lookup"

_TOP_K = 6
_CITATION_THRESHOLD = 0.75
_CORPUS = "regulations"


def _to_citation(doc: RetrievedDocument) -> Citation | None:
    """Promote a high-scoring chunk into a citation."""
    if doc.score < _CITATION_THRESHOLD:
        return None
    locator = doc.metadata.get("locator") or doc.chunk_id
    return Citation(
        source=doc.source,
        locator=locator,
        language=doc.language,
        excerpt=doc.text[:280],
    )


async def run(state: AgentState) -> dict[str, object]:
    """Worker entry point."""
    try:
        documents = await hybrid_search.search(
            query=state["user_input"],
            language=None,  # regulations are stored in their source language; search cross-lingual
            corpus=_CORPUS,
            top_k=_TOP_K,
        )
    except Exception as exc:
        return {"errors": [f"regulation_lookup failed: {exc}"]}

    citations = [c for c in (_to_citation(doc) for doc in documents) if c is not None]
    update: dict[str, object] = {"retrieved_documents": documents}
    if citations:
        CITATIONS_TOTAL.labels(target=_CORPUS, language=state["language"].value).inc(
            len(citations)
        )
        update["citations"] = citations
    return update
