"""Grounding-based citation selection.

Cite the retrieved chunks that best back the answer, drawn from *every* worker's
context (so a product answer gets product sources, not only regulatory ones).

Two cheap, dependency-free signals are blended — no embeddings on the hot path,
which is what made an earlier attribution pass add ~900 ms per turn:

* **retrieval relevance** — the normalised RRF score already on each chunk. It
  is semantic, hence cross-lingual: a French answer can still surface an English
  GDPR chunk that retrieval ranked highly.
* **lexical usage** — a BM25-lite overlap between the answer's claims and the
  chunk. It nudges chunks the answer visibly draws on above incidentally
  retrieved ones, but cannot by itself drop a strongly-retrieved chunk just
  because it is in another language.

The richer embedding-based provenance (idea #11) stays on the offline
observability dashboard, where latency does not matter.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tessera.agent.state import Citation
from tessera.observability.provenance import split_claims
from tessera.retrieval.reranking import lexical_score

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tessera.agent.state import RetrievedDocument

__all__ = ["select_grounded_citations"]

_MAX_CITATIONS = 3
# How much a fully answer-used chunk can climb past a more-retrieved one. Kept
# below 1.0 so retrieval relevance (also in [0, 1]) stays the dominant signal.
_LEXICAL_BOOST = 0.5


def _locator(doc: RetrievedDocument) -> str:
    return doc.metadata.get("locator") or doc.chunk_id


def _lexical_usage(answer: str, texts: Sequence[str]) -> dict[int, float]:
    """Accumulate, per chunk, the lexical overlap of the claims it best matches."""
    usage: dict[int, float] = {}
    if not answer.strip():
        return usage
    for claim in split_claims(answer):
        scores = [lexical_score(claim, text) for text in texts]
        best = max(range(len(scores)), key=scores.__getitem__)
        if scores[best] > 0.0:
            usage[best] = usage.get(best, 0.0) + scores[best]
    return usage


def select_grounded_citations(
    answer: str,
    documents: Sequence[RetrievedDocument],
    *,
    max_citations: int = _MAX_CITATIONS,
) -> list[Citation]:
    """Cite the chunks that best back the answer, deduplicated by source.

    Chunks are ranked by ``retrieval_score + boost * normalised_lexical_usage``,
    deduplicated by source and capped at ``max_citations``. The excerpt is the
    full chunk verbatim.

    Args:
        answer: The agent's final answer (without any citations footer).
        documents: All retrieved chunks for the turn, across every worker.
        max_citations: Upper bound on the number of citations returned.

    Returns:
        The citations, or an empty list when there are no retrieved chunks.
    """
    if not documents:
        return []

    texts = [doc.text for doc in documents]
    usage = _lexical_usage(answer, texts)
    max_usage = max(usage.values()) if usage else 0.0

    def rank(idx: int) -> float:
        norm_usage = usage.get(idx, 0.0) / max_usage if max_usage > 0.0 else 0.0
        return documents[idx].score + _LEXICAL_BOOST * norm_usage

    ordered = sorted(range(len(documents)), key=rank, reverse=True)
    citations: list[Citation] = []
    seen: set[str] = set()
    for idx in ordered:
        doc = documents[idx]
        if doc.source in seen:
            continue
        seen.add(doc.source)
        citations.append(
            Citation(
                source=doc.source,
                locator=_locator(doc),
                language=doc.language,
                excerpt=doc.text,
            )
        )
        if len(citations) >= max_citations:
            break
    return citations
