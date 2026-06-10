"""Regulation lookup worker — searches the EU regulatory corpus.

The regulatory corpus contains DORA, CNIL, BaFin, and GDPR/DSGVO chunks
indexed once at ingestion time. The worker fans out across the language's
default regulator set (defined in :mod:`tessera.settings`-aware ingestion)
and writes both the retrieved chunks and any high-confidence citations to
the state.
"""

from __future__ import annotations

from tessera.agent.state import AgentState, Citation, RetrievedDocument
from tessera.retrieval import hybrid_search

NODE_NAME = "regulation_lookup"

_TOP_K = 6
# ``hybrid_search`` exposes a reciprocal-rank-fusion (RRF) score, not a cosine
# similarity: the theoretical maximum is ``2 / (RRF_K + 1) ≈ 0.033`` (see
# :mod:`tessera.retrieval.reranking`). An absolute 0.75 cut — calibrated for a
# [0, 1] cosine scale — was therefore unreachable and silently suppressed every
# citation. We instead keep the hits that rank close to the best fused result,
# which is robust to corpus size. See ADR 0010 / insights.
_CITATION_SCORE_RATIO = 0.6
_MAX_CITATIONS = 3
_CORPUS = "regulations"


def _to_citation(doc: RetrievedDocument) -> Citation:
    """Render a retrieved chunk as a citation.

    The excerpt is the full retrieved chunk verbatim — never truncated here.
    The retrieval-time chunk size already bounds its length, and the UI shows
    it in a scrollable panel, so the citation reproduces exactly the grounding
    text rather than an arbitrary slice.
    """
    locator = doc.metadata.get("locator") or doc.chunk_id
    return Citation(
        source=doc.source,
        locator=locator,
        language=doc.language,
        excerpt=doc.text,
    )


def _select_citations(documents: list[RetrievedDocument]) -> list[Citation]:
    """Pick the strongest hits relative to the best fused score.

    Hits are kept while they score within :data:`_CITATION_SCORE_RATIO` of the
    top result, deduplicated by source so the same regulation is not cited
    twice, and capped at :data:`_MAX_CITATIONS` to keep the answer footer and
    the chat UI legible.
    """
    if not documents:
        return []
    cutoff = documents[0].score * _CITATION_SCORE_RATIO
    citations: list[Citation] = []
    seen: set[str] = set()
    for doc in documents:
        if doc.score < cutoff:
            break
        if doc.source in seen:
            continue
        seen.add(doc.source)
        citations.append(_to_citation(doc))
        if len(citations) >= _MAX_CITATIONS:
            break
    return citations


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

    citations = _select_citations(documents)
    update: dict[str, object] = {"retrieved_documents": documents}
    if citations:
        update["citations"] = citations
    return update
