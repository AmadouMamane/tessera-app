"""Product lookup worker — searches the Crédit Aurore product corpus.

The product corpus is the fictional retail-banking catalogue under
``src/tessera/corpus/data/credit_aurore_{fr,de,en}.json``. The worker queries
the retrieval layer with the user's input, scoped to the detected language,
and writes the top-k chunks plus their citations back into the graph state.
"""

from __future__ import annotations

from tessera.agent.state import (
    AgentState,
    Citation,
    RetrievedDocument,
)
from tessera.observability.metrics import CITATIONS_TOTAL
from tessera.retrieval import hybrid_search

NODE_NAME = "product_lookup"

_TOP_K = 4
_CORPUS = "credit_aurore"


def _to_citation(doc: RetrievedDocument) -> Citation:
    """Promote a product-corpus chunk into a citation."""
    locator = doc.metadata.get("locator") or doc.chunk_id
    return Citation(
        source=doc.source,
        locator=locator,
        language=doc.language,
        excerpt=doc.text[:280],
    )


async def _search(state: AgentState) -> list[RetrievedDocument]:
    """Wrap :func:`tessera.retrieval.hybrid_search.search` with worker defaults."""
    return await hybrid_search.search(
        query=state["user_input"],
        language=state["language"],
        corpus=_CORPUS,
        top_k=_TOP_K,
    )


async def run(state: AgentState) -> dict[str, object]:
    """Worker entry point.

    Returns a partial state update. Any retrieval failure is captured into
    ``error`` rather than raised so the reviewer can still emit a graceful
    fallback rather than crashing the graph.
    """
    try:
        documents = await _search(state)
    except Exception as exc:
        return {
            "errors": [f"product_lookup failed: {exc}"],
        }
    update: dict[str, object] = {"retrieved_documents": documents}
    if documents:
        citations = [_to_citation(doc) for doc in documents]
        CITATIONS_TOTAL.labels(target=_CORPUS, language=state["language"].value).inc(len(citations))
        update["citations"] = citations
    return update
