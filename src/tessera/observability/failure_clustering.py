"""Embedding-based failure clustering (ADR 0010, idea #123).

A flat list of sixty-odd documented failures is hard to reason about; the
question an operator actually asks is "what *kinds* of things go wrong?". This
module answers it without hand-labelling: it embeds each failure's prompt and
runs k-means over the vectors, so semantically similar failures fall into the
same cluster. Each discovered cluster is then described by its dominant catalogue
category and its members, turning the corpus into a handful of themes.

Because the failures already carry a curated ``category``, the clusters double as
a *sanity check* on the taxonomy: a cluster's **purity** (the share of its
members sharing the dominant category) shows whether the embedding space agrees
with the human labels. The clustering is deterministic (fixed seed, farthest-
first initialisation) so the same corpus always yields the same themes, and the
embedder is injectable for testing.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

__all__ = ["ClusterReport", "FailureCluster", "FailureItem", "cluster_failures"]

_MAX_ITERATIONS = 25
_LABEL_PREVIEW = 60


@dataclass(frozen=True, slots=True)
class FailureItem:
    """One failure to cluster: an id, its curated category, and its text."""

    case_id: str
    category: str
    text: str


@dataclass(frozen=True, slots=True)
class FailureCluster:
    """A discovered cluster of semantically similar failures."""

    cluster_id: int
    size: int
    dominant_category: str
    purity: float  # share of members sharing the dominant category
    categories: dict[str, int]
    members: list[str] = field(default_factory=list)  # case ids


@dataclass(frozen=True, slots=True)
class ClusterReport:
    """The themes discovered across the failure corpus."""

    n_failures: int
    k: int
    mean_purity: float
    clusters: list[FailureCluster] = field(default_factory=list)


def _cosine_distance(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 1.0
    return 1.0 - dot / (na * nb)


def _farthest_first(vectors: list[list[float]], k: int) -> list[int]:
    """Deterministic seed selection: start at 0, then the farthest each step."""
    chosen = [0]
    while len(chosen) < k:
        best_idx, best_dist = 0, -1.0
        for i in range(len(vectors)):
            if i in chosen:
                continue
            nearest = min(_cosine_distance(vectors[i], vectors[c]) for c in chosen)
            if nearest > best_dist:
                best_dist, best_idx = nearest, i
        chosen.append(best_idx)
    return chosen


def _assign(vectors: list[list[float]], centroids: list[list[float]]) -> list[int]:
    labels: list[int] = []
    for vec in vectors:
        best_c, best_d = 0, math.inf
        for c, centroid in enumerate(centroids):
            d = _cosine_distance(vec, centroid)
            if d < best_d:
                best_d, best_c = d, c
        labels.append(best_c)
    return labels


def _recompute(vectors: list[list[float]], labels: list[int], k: int) -> list[list[float]]:
    dim = len(vectors[0])
    centroids: list[list[float]] = []
    for c in range(k):
        members = [vectors[i] for i in range(len(vectors)) if labels[i] == c]
        if not members:
            centroids.append([0.0] * dim)
            continue
        centroids.append([sum(vals) / len(members) for vals in zip(*members, strict=True)])
    return centroids


async def cluster_failures(
    items: Sequence[FailureItem],
    *,
    k: int,
    embedder: Callable[[Sequence[str]], Awaitable[list[list[float]]]],
) -> ClusterReport:
    """Cluster failures into ``k`` themes by embedding similarity.

    Args:
        items: The failures to cluster.
        k: Number of clusters (capped at the item count).
        embedder: Async embedding function.

    Returns:
        A :class:`ClusterReport`, clusters ordered by size (largest first).
    """
    rows = list(items)
    n = len(rows)
    if n == 0:
        return ClusterReport(n_failures=0, k=0, mean_purity=0.0)
    k = max(1, min(k, n))

    vectors = await embedder([item.text for item in rows])
    centroids = [vectors[i] for i in _farthest_first(vectors, k)]
    labels = [0] * n
    for _ in range(_MAX_ITERATIONS):
        new_labels = _assign(vectors, centroids)
        if new_labels == labels:
            break
        labels = new_labels
        centroids = _recompute(vectors, labels, k)

    clusters: list[FailureCluster] = []
    purities: list[float] = []
    for c in range(k):
        member_idx = [i for i in range(n) if labels[i] == c]
        if not member_idx:
            continue
        cats: dict[str, int] = {}
        for i in member_idx:
            cats[rows[i].category] = cats.get(rows[i].category, 0) + 1
        dominant = max(cats, key=lambda key: cats[key])
        purity = cats[dominant] / len(member_idx)
        purities.append(purity)
        clusters.append(
            FailureCluster(
                cluster_id=c,
                size=len(member_idx),
                dominant_category=dominant,
                purity=purity,
                categories=cats,
                members=[rows[i].case_id[:_LABEL_PREVIEW] for i in member_idx],
            )
        )

    clusters.sort(key=lambda cl: cl.size, reverse=True)
    return ClusterReport(
        n_failures=n,
        k=len(clusters),
        mean_purity=sum(purities) / len(purities) if purities else 0.0,
        clusters=clusters,
    )
