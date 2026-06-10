"""Grounding-based citation selection.

Instead of citing the top *retrieved* chunks, this attributes the answer's
claims to the chunks that actually support them — reusing the provenance
attributor (idea #11) — and cites only those. Two consequences follow:

* citations reflect what the answer *used*, not merely what retrieval surfaced;
* every worker's retrieved context is eligible, so a product-grounded answer
  gets product sources, not only regulatory ones.

The caller falls back to the worker-selected citations when attribution yields
nothing, so this never regresses a turn that previously had sources.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tessera.agent.state import Citation
from tessera.observability.provenance import attribute

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tessera.agent.state import RetrievedDocument

__all__ = ["select_grounded_citations"]

_MAX_CITATIONS = 3
_SUPPORT_THRESHOLD = 0.55


def _locator(doc: RetrievedDocument) -> str:
    return doc.metadata.get("locator") or doc.chunk_id


async def select_grounded_citations(
    answer: str,
    documents: Sequence[RetrievedDocument],
    *,
    max_citations: int = _MAX_CITATIONS,
    threshold: float = _SUPPORT_THRESHOLD,
) -> list[Citation]:
    """Cite the retrieved chunks that actually ground the answer's claims.

    Each claim is attributed to its best-supporting chunk; a chunk that supports
    at least one claim above ``threshold`` becomes a citation. Citations are
    ranked by their strongest supporting claim, deduplicated by source, and
    capped at ``max_citations``. The excerpt is the full chunk verbatim.

    Args:
        answer: The agent's final answer (without the citations footer).
        documents: All retrieved chunks for the turn, across every worker.
        max_citations: Upper bound on the number of citations returned.
        threshold: Minimum claim→chunk cosine support to count as grounding.

    Returns:
        The grounding citations, or an empty list when nothing is supported.
    """
    if not answer.strip() or not documents:
        return []

    report = await attribute(answer, [d.text for d in documents], threshold=threshold)

    best_support: dict[int, float] = {}
    for claim in report.claims:
        if claim.supported and 0 <= claim.best_chunk < len(documents):
            idx = claim.best_chunk
            if claim.support > best_support.get(idx, 0.0):
                best_support[idx] = claim.support

    if not best_support:
        return []

    ordered = sorted(best_support, key=lambda i: best_support[i], reverse=True)
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
