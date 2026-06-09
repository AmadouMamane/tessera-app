"""Unit tests for multi-turn contradiction detection (ADR 0010, #30)."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from tessera.observability import contradiction

if TYPE_CHECKING:
    from collections.abc import Sequence

# A toy embedder: maps known strings to fixed vectors so similarity is exact.
_VECTORS: dict[str, list[float]] = {
    "card status?": [1.0, 0.0, 0.0],
    "is my card ok?": [1.0, 0.0, 0.0],  # same topic as above
    "blocked": [0.0, 1.0, 0.0],
    "active": [0.0, 0.0, 1.0],  # orthogonal to "blocked" → disagree
    "weather?": [0.0, 0.0, 1.0],
    "sunny": [0.5, 0.5, 0.0],
}


async def _toy_embed(texts: Sequence[str]) -> list[list[float]]:
    return [_VECTORS.get(t, [0.0, 0.0, 0.0]) for t in texts]


def test_single_turn_has_no_contradiction() -> None:
    report = asyncio.run(
        contradiction.detect_contradictions([("card status?", "blocked")], embedder=_toy_embed)
    )
    assert report.n_turns == 1
    assert report.n_contradictions == 0


def test_same_topic_divergent_answers_flagged() -> None:
    turns = [("card status?", "blocked"), ("is my card ok?", "active")]
    report = asyncio.run(contradiction.detect_contradictions(turns, embedder=_toy_embed))
    assert report.n_pairs_checked == 1
    assert report.n_contradictions == 1
    pair = report.contradictions[0]
    assert pair.topic_similarity >= 0.6
    assert pair.answer_similarity <= 0.4


def test_different_topics_not_flagged() -> None:
    turns = [("card status?", "blocked"), ("weather?", "sunny")]
    report = asyncio.run(contradiction.detect_contradictions(turns, embedder=_toy_embed))
    assert report.n_contradictions == 0
