"""Unit tests for grounding-based citation selection.

Selection blends retrieval relevance (``doc.score``) with a lexical usage boost.
Both signals are deterministic and offline (no embeddings), so the tests pin
exact ordering by controlling scores and chunk wording.
"""

from __future__ import annotations

from tessera.agent.grounding import select_grounded_citations
from tessera.agent.state import RetrievedDocument


def _doc(
    source: str,
    text: str,
    *,
    score: float = 0.9,
    locator: str = "",
    chunk_id: str = "c",
) -> RetrievedDocument:
    return RetrievedDocument(
        source=source,
        chunk_id=chunk_id,
        language="fr",
        text=text,
        score=score,
        metadata={"locator": locator} if locator else {},
    )


def test_ranks_by_retrieval_relevance() -> None:
    docs = [
        _doc("LOW/a", "contenu a", score=0.30),
        _doc("HIGH/b", "contenu b", score=0.95),
        _doc("MID/c", "contenu c", score=0.60),
    ]
    cites = [c.source for c in select_grounded_citations("question neutre", docs)]
    assert cites == ["HIGH/b", "MID/c", "LOW/a"]


def test_cross_lingual_chunk_still_cited() -> None:
    """A highly-retrieved English chunk survives a French answer (no lexical drop)."""
    docs = [
        _doc("GDPR/art-20", "Article 20 grants the right to data portability.", score=0.92),
        _doc("CNIL/acces", "Droit d'accès aux données bancaires.", score=0.80),
    ]
    answer = "Vous disposez d'un droit de portabilité de vos données personnelles."
    assert "GDPR/art-20" in [c.source for c in select_grounded_citations(answer, docs)]


def test_lexical_usage_boosts_a_used_chunk() -> None:
    """A slightly-less-retrieved chunk the answer clearly uses climbs above."""
    docs = [
        _doc("A/unused", "horaires agences jours fériés guichets", score=0.70, chunk_id="a"),
        _doc(
            "B/used", "portabilité données personnelles format structuré", score=0.66, chunk_id="b"
        ),
    ]
    answer = "La portabilité des données personnelles fournit un format structuré."
    cites = [c.source for c in select_grounded_citations(answer, docs, max_citations=1)]
    assert cites == ["B/used"]


def test_dedup_by_source() -> None:
    docs = [
        _doc("GDPR/art-20", "Portabilité des données.", score=0.95, chunk_id="a"),
        _doc("GDPR/art-20", "Transmission directe.", score=0.90, chunk_id="b"),
        _doc("CNIL/acces", "Droit d'accès.", score=0.50),
    ]
    assert [c.source for c in select_grounded_citations("q", docs)] == ["GDPR/art-20", "CNIL/acces"]


def test_cap_and_excerpt_verbatim() -> None:
    docs = [
        _doc(f"S/{i}", f"contenu {i}", score=0.9 - i * 0.1, locator=f"loc{i}") for i in range(6)
    ]
    cites = select_grounded_citations("q", docs, max_citations=2)
    assert len(cites) == 2
    assert cites[0].excerpt == docs[0].text  # full chunk verbatim
    assert cites[0].locator == "loc0"


def test_empty_documents() -> None:
    assert select_grounded_citations("answer", []) == []
