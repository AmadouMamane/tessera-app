"""Unit tests for claim-level provenance (ADR 0010, #11)."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

from tessera.observability import provenance

if TYPE_CHECKING:
    from collections.abc import Sequence


async def _fake_embed(texts: Sequence[str]) -> list[list[float]]:
    """Deterministic 3-d embeddings keyed by a marker word."""
    out: list[list[float]] = []
    for text in texts:
        if "alpha" in text:
            out.append([1.0, 0.0, 0.0])
        elif "beta" in text:
            out.append([0.0, 1.0, 0.0])
        else:
            out.append([0.0, 0.0, 1.0])
    return out


def test_split_claims_drops_trivial_fragments() -> None:
    claims = provenance.split_claims("This is a real sentence here. Short. Another real one here.")
    assert claims == ["This is a real sentence here.", "Another real one here."]


def test_attribute_marks_supported_and_unsupported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(provenance, "embed", _fake_embed)
    answer = "The alpha alpha rule clearly holds. Totally unrelated gamma claim here."
    chunks = ["alpha grounds this fact well"]
    report = asyncio.run(provenance.attribute(answer, chunks))

    assert report.n_claims == 2
    assert report.grounded_fraction == pytest.approx(0.5)
    assert report.claims[0].supported is True
    assert report.claims[0].best_chunk == 0
    assert report.claims[1].supported is False


def test_attribute_no_chunks_is_unsupported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(provenance, "embed", _fake_embed)
    report = asyncio.run(provenance.attribute("A grounded alpha statement here.", []))
    assert report.grounded_fraction == 0.0
    assert report.claims[0].supported is False


def test_attribute_no_claims_is_trivially_grounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(provenance, "embed", _fake_embed)
    report = asyncio.run(provenance.attribute("ok.", ["some chunk"]))
    assert report.n_claims == 0
    assert report.grounded_fraction == 1.0
