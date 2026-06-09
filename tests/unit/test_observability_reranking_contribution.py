"""Unit tests for reranker/hybrid contribution (ADR 0010, #27)."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from tessera.observability.reranking_contribution import measure_contribution

if TYPE_CHECKING:
    from collections.abc import Sequence


def _fake_embedder(vectors: dict[str, list[float]]):
    async def embedder(texts: Sequence[str]) -> list[list[float]]:
        return [vectors[t] for t in texts]

    return embedder


def test_empty_chunks() -> None:
    report = asyncio.run(measure_contribution(question="q", chunks=[], embedder=_fake_embedder({})))
    assert report.n_chunks == 0
    assert report.reranker_lift == 0
    assert report.fused_order == []


def test_pure_vector_no_lift() -> None:
    # Vector ranks chunk0 best and it is also lexically strongest → no reranker
    # change, no lift, top1 stable.
    vecs = {
        "what are the account fees": [1.0, 0.0],
        "account fees are five euros monthly": [1.0, 0.0],
        "unrelated text about weather": [0.0, 1.0],
    }
    report = asyncio.run(
        measure_contribution(
            question="what are the account fees",
            chunks=["account fees are five euros monthly", "unrelated text about weather"],
            top_k=1,
            embedder=_fake_embedder(vecs),
        )
    )
    assert report.n_chunks == 2
    assert report.top1_changed is False
    assert report.reranker_lift == 0
    assert report.vector_order[0] == 0


def test_lexical_promotes_a_chunk() -> None:
    # Vector puts the lexically-relevant chunk second; the lexical signal should
    # raise its fused share above 0.5.
    vecs = {
        "iban transfer limit": [0.0, 1.0],
        "the daily iban transfer limit is 10000 euros": [0.2, 0.9],
        "generic banking introduction paragraph": [0.1, 0.99],
    }
    report = asyncio.run(
        measure_contribution(
            question="iban transfer limit",
            chunks=[
                "generic banking introduction paragraph",
                "the daily iban transfer limit is 10000 euros",
            ],
            top_k=2,
            embedder=_fake_embedder(vecs),
        )
    )
    assert report.n_chunks == 2
    # Shares are complementary and sum to ~1.
    assert abs(report.mean_vector_share + report.mean_lexical_share - 1.0) < 1e-9
    assert report.mean_lexical_share > 0.0
