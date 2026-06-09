"""Unit tests for corpus coverage gaps (ADR 0010, #28)."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from tessera.observability import coverage

if TYPE_CHECKING:
    from collections.abc import Sequence

_VECTORS: dict[str, list[float]] = {
    "loan rate?": [1.0, 0.0, 0.0],
    "the loan rate is 3.2%": [1.0, 0.0, 0.0],  # on-topic
    "office opening hours": [0.0, 1.0, 0.0],  # off-topic
}


async def _toy_embed(texts: Sequence[str]) -> list[list[float]]:
    return [_VECTORS.get(t, [0.0, 0.0, 0.0]) for t in texts]


def test_covered_when_chunk_matches() -> None:
    report = asyncio.run(
        coverage.measure_coverage(
            question="loan rate?", chunks=["the loan rate is 3.2%"], embedder=_toy_embed
        )
    )
    assert report.covered is True
    assert report.max_similarity >= 0.5


def test_coverage_gap_when_chunks_off_topic() -> None:
    report = asyncio.run(
        coverage.measure_coverage(
            question="loan rate?", chunks=["office opening hours"], embedder=_toy_embed
        )
    )
    assert report.covered is False
    assert report.max_similarity < 0.5


def test_empty_chunks_is_a_gap() -> None:
    report = asyncio.run(
        coverage.measure_coverage(question="loan rate?", chunks=[], embedder=_toy_embed)
    )
    assert report.n_chunks == 0
    assert report.covered is False
