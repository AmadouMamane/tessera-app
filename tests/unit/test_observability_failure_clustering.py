"""Unit tests for embedding-based failure clustering (ADR 0010, #123)."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from tessera.observability.failure_clustering import FailureItem, cluster_failures

if TYPE_CHECKING:
    from collections.abc import Sequence


def _embedder(table: dict[str, list[float]]):
    async def embed(texts: Sequence[str]) -> list[list[float]]:
        return [table[t] for t in texts]

    return embed


def test_empty() -> None:
    report = asyncio.run(cluster_failures([], k=3, embedder=_embedder({})))
    assert report.n_failures == 0
    assert report.clusters == []


def test_two_clean_clusters() -> None:
    table = {
        "inj a": [1.0, 0.0],
        "inj b": [0.99, 0.01],
        "pii a": [0.0, 1.0],
        "pii b": [0.01, 0.99],
    }
    items = [
        FailureItem("01", "prompt_injection", "inj a"),
        FailureItem("02", "prompt_injection", "inj b"),
        FailureItem("03", "pii_leak", "pii a"),
        FailureItem("04", "pii_leak", "pii b"),
    ]
    report = asyncio.run(cluster_failures(items, k=2, embedder=_embedder(table)))
    assert report.n_failures == 4
    assert report.k == 2
    # Each cluster is pure: members share one category.
    assert report.mean_purity == 1.0
    dominants = {c.dominant_category for c in report.clusters}
    assert dominants == {"prompt_injection", "pii_leak"}


def test_k_capped_at_item_count() -> None:
    table = {"x": [1.0, 0.0]}
    items = [FailureItem("01", "c", "x")]
    report = asyncio.run(cluster_failures(items, k=5, embedder=_embedder(table)))
    assert report.k == 1
    assert report.clusters[0].size == 1


def test_clusters_sorted_by_size() -> None:
    table = {
        "a": [1.0, 0.0],
        "b": [0.98, 0.02],
        "c": [0.97, 0.03],
        "d": [0.0, 1.0],
    }
    items = [
        FailureItem("1", "x", "a"),
        FailureItem("2", "x", "b"),
        FailureItem("3", "x", "c"),
        FailureItem("4", "y", "d"),
    ]
    report = asyncio.run(cluster_failures(items, k=2, embedder=_embedder(table)))
    assert report.clusters[0].size >= report.clusters[-1].size
