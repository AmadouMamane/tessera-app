"""Unit tests for citation selection in the regulation_lookup worker.

Regression guard for the latent bug where an absolute 0.75 threshold was
applied to reciprocal-rank-fusion scores (max ≈ 0.033), silently suppressing
every citation.
"""

from __future__ import annotations

from tessera.agent.state import RetrievedDocument
from tessera.agent.workers.regulation_lookup import (
    _MAX_CITATIONS,
    _select_citations,
)


def _doc(source: str, score: float, *, locator: str = "", chunk_id: str = "c") -> RetrievedDocument:
    return RetrievedDocument(
        source=source,
        chunk_id=chunk_id,
        language="fr",
        text="Texte du chunk réglementaire.",
        score=score,
        metadata={"locator": locator} if locator else {},
    )


def test_rrf_scale_scores_still_produce_citations() -> None:
    """Realistic RRF scores (~0.03) must yield citations, not be suppressed."""
    docs = [
        _doc("GDPR/art-20", 0.0318, locator="GDPR Article 20"),
        _doc("CNIL/droit-acces", 0.0315, locator="CNIL droit d'accès"),
        _doc("CNIL/conservation", 0.0309, locator="CNIL conservation"),
    ]
    citations = _select_citations(docs)
    assert citations
    assert citations[0].source == "GDPR/art-20"
    assert citations[0].locator == "GDPR Article 20"


def test_dedup_by_source() -> None:
    """The same regulation retrieved twice is cited once."""
    docs = [
        _doc("GDPR/art-20", 0.0318, locator="GDPR Article 20", chunk_id="a"),
        _doc("GDPR/art-20", 0.0314, locator="GDPR Article 20", chunk_id="b"),
        _doc("CNIL/droit-acces", 0.0309, locator="CNIL droit d'accès"),
    ]
    sources = [c.source for c in _select_citations(docs)]
    assert sources == ["GDPR/art-20", "CNIL/droit-acces"]


def test_cap_at_max_citations() -> None:
    docs = [_doc(f"SRC/{i}", 0.032 - i * 0.0001, locator=f"loc-{i}") for i in range(10)]
    assert len(_select_citations(docs)) == _MAX_CITATIONS


def test_low_relative_score_excluded() -> None:
    """A hit far below the best fused score is dropped (ratio cut)."""
    docs = [
        _doc("GDPR/art-20", 0.0320, locator="GDPR Article 20"),
        _doc("OFFTOPIC/noise", 0.0050, locator="noise"),
    ]
    sources = [c.source for c in _select_citations(docs)]
    assert sources == ["GDPR/art-20"]


def test_empty_documents() -> None:
    assert _select_citations([]) == []


def test_locator_falls_back_to_chunk_id() -> None:
    docs = [_doc("DORA/art-5", 0.031, chunk_id="dora-5-0")]
    assert _select_citations(docs)[0].locator == "dora-5-0"
