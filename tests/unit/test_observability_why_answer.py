"""Unit tests for "Why this answer?" (ADR 0010, #133)."""

from __future__ import annotations

import asyncio

import pytest

from tessera.observability import why_answer
from tessera.observability.provenance import ProvenanceClaim, ProvenanceReport


@pytest.fixture
def _stub_attribute(monkeypatch: pytest.MonkeyPatch):
    def _install(report: ProvenanceReport) -> None:
        async def fake_attribute(answer: str, chunks, threshold: float = 0.5):
            return report

        monkeypatch.setattr(why_answer, "attribute", fake_attribute)

    return _install


def test_grounded_explanation(_stub_attribute) -> None:
    _stub_attribute(
        ProvenanceReport(
            n_claims=2,
            grounded_fraction=1.0,
            claims=[
                ProvenanceClaim(text="fee is 2 EUR", support=0.9, supported=True, best_chunk=0),
                ProvenanceClaim(text="no SEPA fee", support=0.8, supported=True, best_chunk=1),
            ],
        )
    )
    exp = asyncio.run(
        why_answer.build_explanation(answer="a", chunks=["chunk about fees", "chunk about SEPA"])
    )
    assert exp.n_claims == 2
    assert exp.fully_grounded is True
    assert abs(exp.confidence - 0.85) < 1e-9
    assert exp.claims[0].source == "chunk about fees"


def test_unsupported_claim_has_no_source(_stub_attribute) -> None:
    _stub_attribute(
        ProvenanceReport(
            n_claims=1,
            grounded_fraction=0.0,
            claims=[ProvenanceClaim(text="invented", support=0.2, supported=False, best_chunk=-1)],
        )
    )
    exp = asyncio.run(why_answer.build_explanation(answer="a", chunks=["c"]))
    assert exp.fully_grounded is False
    assert exp.claims[0].supported is False
    assert exp.claims[0].source == ""


def test_no_claims_is_confident(_stub_attribute) -> None:
    _stub_attribute(ProvenanceReport(n_claims=0, grounded_fraction=1.0, claims=[]))
    exp = asyncio.run(why_answer.build_explanation(answer="", chunks=[]))
    assert exp.n_claims == 0
    assert exp.confidence == 1.0
