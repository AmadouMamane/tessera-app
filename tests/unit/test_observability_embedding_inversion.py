"""Unit tests for embedding-inversion privacy risk (ADR 0010, #73)."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from tessera.observability.embedding_inversion import assess_inversion_risk

if TYPE_CHECKING:
    from collections.abc import Sequence


def _embedder(table: dict[str, list[float]]):
    async def embed(texts: Sequence[str]) -> list[list[float]]:
        return [table[t] for t in texts]

    return embed


def test_empty_inputs() -> None:
    report = asyncio.run(assess_inversion_risk([], ["probe"], embedder=_embedder({"probe": [1.0]})))
    assert report.n_memories == 0
    assert report.recovery_rate == 0.0


def test_recoverable_memory() -> None:
    # memory and matching probe share a direction → cosine 1.0 → recoverable.
    table = {
        "secret": [1.0, 0.0],
        "matching guess": [1.0, 0.0],
        "unrelated": [0.0, 1.0],
    }
    report = asyncio.run(
        assess_inversion_risk(
            ["secret"],
            ["unrelated", "matching guess"],
            embedder=_embedder(table),
            threshold=0.6,
        )
    )
    assert report.n_recoverable == 1
    assert report.recovery_rate == 1.0
    assert report.matches[0].probe == "matching guess"
    assert report.matches[0].recoverable is True


def test_not_recoverable_below_threshold() -> None:
    table = {
        "secret": [1.0, 0.0],
        "weak guess": [0.3, 0.95],  # cosine ~0.3 < 0.6
    }
    report = asyncio.run(
        assess_inversion_risk(["secret"], ["weak guess"], embedder=_embedder(table), threshold=0.6)
    )
    assert report.n_recoverable == 0
    assert report.matches[0].recoverable is False


def test_picks_nearest_probe() -> None:
    table = {
        "secret": [1.0, 0.0],
        "far": [0.0, 1.0],
        "near": [0.9, 0.1],
    }
    report = asyncio.run(
        assess_inversion_risk(["secret"], ["far", "near"], embedder=_embedder(table))
    )
    assert report.matches[0].probe == "near"
