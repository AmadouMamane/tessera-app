"""Unit tests for grounding-based citation selection.

The answer's claims are attributed to retrieved chunks; only chunks that
actually support a claim become citations. The provenance attributor is stubbed
so the test is deterministic and offline (no embeddings).
"""

from __future__ import annotations

import pytest

from tessera.agent import grounding
from tessera.agent.state import RetrievedDocument
from tessera.observability.provenance import ProvenanceClaim, ProvenanceReport


def _doc(source: str, *, locator: str = "", chunk_id: str = "c") -> RetrievedDocument:
    return RetrievedDocument(
        source=source,
        chunk_id=chunk_id,
        language="fr",
        text=f"Contenu du chunk {source}.",
        score=0.9,
        metadata={"locator": locator} if locator else {},
    )


def _stub_attribute(claims: list[ProvenanceClaim]):
    grounded = sum(1 for c in claims if c.supported) / len(claims) if claims else 1.0

    async def _fake(answer, chunks, *, threshold=0.55):
        return ProvenanceReport(n_claims=len(claims), grounded_fraction=grounded, claims=claims)

    return _fake


@pytest.mark.asyncio
async def test_cites_only_supported_chunks(monkeypatch: pytest.MonkeyPatch) -> None:
    docs = [_doc("GDPR/art-20"), _doc("CNIL/droit-acces"), _doc("PRODUCT/credit-aurore")]
    claims = [
        ProvenanceClaim(text="a", support=0.8, supported=True, best_chunk=0),
        ProvenanceClaim(text="b", support=0.7, supported=True, best_chunk=2),
        ProvenanceClaim(text="c", support=0.3, supported=False, best_chunk=1),
    ]
    monkeypatch.setattr(grounding, "attribute", _stub_attribute(claims))
    cites = await grounding.select_grounded_citations("answer", docs)
    sources = [c.source for c in cites]
    # chunk 1 (unsupported) excluded; ordered by support: 0 (0.8) then 2 (0.7)
    assert sources == ["GDPR/art-20", "PRODUCT/credit-aurore"]


@pytest.mark.asyncio
async def test_covers_product_chunks(monkeypatch: pytest.MonkeyPatch) -> None:
    docs = [_doc("PRODUCT/credit-aurore", locator="Crédit Aurore — taux")]
    claims = [ProvenanceClaim(text="a", support=0.9, supported=True, best_chunk=0)]
    monkeypatch.setattr(grounding, "attribute", _stub_attribute(claims))
    cites = await grounding.select_grounded_citations("answer", docs)
    assert len(cites) == 1
    assert cites[0].source == "PRODUCT/credit-aurore"
    assert cites[0].locator == "Crédit Aurore — taux"
    assert cites[0].excerpt == docs[0].text  # full chunk verbatim


@pytest.mark.asyncio
async def test_dedup_by_source(monkeypatch: pytest.MonkeyPatch) -> None:
    docs = [_doc("GDPR/art-20", chunk_id="a"), _doc("GDPR/art-20", chunk_id="b")]
    claims = [
        ProvenanceClaim(text="a", support=0.8, supported=True, best_chunk=0),
        ProvenanceClaim(text="b", support=0.9, supported=True, best_chunk=1),
    ]
    monkeypatch.setattr(grounding, "attribute", _stub_attribute(claims))
    cites = await grounding.select_grounded_citations("answer", docs)
    assert [c.source for c in cites] == ["GDPR/art-20"]


@pytest.mark.asyncio
async def test_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    docs = [_doc(f"S/{i}") for i in range(6)]
    claims = [
        ProvenanceClaim(text=str(i), support=0.9 - i * 0.01, supported=True, best_chunk=i)
        for i in range(6)
    ]
    monkeypatch.setattr(grounding, "attribute", _stub_attribute(claims))
    cites = await grounding.select_grounded_citations("answer", docs, max_citations=2)
    assert len(cites) == 2


@pytest.mark.asyncio
async def test_no_supported_claims_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    docs = [_doc("GDPR/art-20")]
    claims = [ProvenanceClaim(text="a", support=0.1, supported=False, best_chunk=0)]
    monkeypatch.setattr(grounding, "attribute", _stub_attribute(claims))
    assert await grounding.select_grounded_citations("answer", docs) == []


@pytest.mark.asyncio
async def test_empty_inputs() -> None:
    assert await grounding.select_grounded_citations("", [_doc("X")]) == []
    assert await grounding.select_grounded_citations("answer", []) == []
