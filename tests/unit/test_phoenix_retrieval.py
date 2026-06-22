"""Unit tests for the Phoenix-backed citation backfill (ADR 0010, idea #4).

Covers the pure pieces: the in-process category extraction that annotates a
retrieval span (``hybrid_search._cited_categories``) and the per-day
reconstruction that turns real Phoenix spans into durable counters
(``scripts.phoenix_retrieval._aggregate_by_day`` / ``_span_day``).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from scripts import phoenix_retrieval

from tessera.retrieval import hybrid_search, store
from tessera.settings import LanguageCode


def _hit(category: str, score: float) -> store.VectorHit:
    return store.VectorHit(
        source=f"src-{category}",
        chunk_id=f"{category}-1",
        language=LanguageCode.FR,
        text="...",
        metadata={"category": category},
        score=score,
    )


def test_cited_categories_keeps_only_above_threshold() -> None:
    hits = [
        _hit("cartes", 0.80),
        _hit("comptes", 0.60),
        _hit("epargne", 0.40),  # below 0.55 threshold -> dropped
    ]
    cats, top = hybrid_search._cited_categories(hits)
    assert cats == ["cartes", "comptes"]
    assert top == 0.80  # best cosine across the candidate set, even below-threshold


def test_cited_categories_empty_when_nothing_clears() -> None:
    cats, top = hybrid_search._cited_categories([_hit("dora", 0.10)])
    assert cats == []
    assert top == 0.10


def test_cited_categories_handles_no_hits() -> None:
    cats, top = hybrid_search._cited_categories([])
    assert cats == []
    assert top is None


def test_aggregate_by_day_groups_and_counts() -> None:
    d1, d2 = date(2026, 6, 20), date(2026, 6, 21)
    # Day 1: three queries (two cite cartes, one cites nothing). Day 2: one query.
    spans = [
        (d1, ["cartes", "comptes"]),
        (d1, ["cartes"]),
        (d1, []),
        (d2, ["dora"]),
    ]
    per_day = phoenix_retrieval._aggregate_by_day(spans)

    queries, with_hit, hits = per_day[d1]
    assert queries == 3
    assert with_hit == 2  # one query cited nothing
    assert hits == {"cartes": 2, "comptes": 1}

    assert per_day[d2] == (1, 1, {"dora": 1})


def test_aggregate_by_day_dedupes_repeated_category_in_one_query() -> None:
    d = date(2026, 6, 20)
    per_day = phoenix_retrieval._aggregate_by_day([(d, ["cartes", "cartes"])])
    _, _, hits = per_day[d]
    assert hits["cartes"] == 1


def test_span_day_extracts_utc_date_and_respects_cutoff() -> None:
    now = datetime.now(UTC)
    cutoff = now - timedelta(hours=1)
    recent = {"start_time": now.isoformat()}
    old = {"start_time": (now - timedelta(hours=2)).isoformat()}

    assert phoenix_retrieval._span_day(recent, cutoff) == now.date()
    # Older than the cutoff -> excluded.
    assert phoenix_retrieval._span_day(old, cutoff) is None
    # No cutoff -> included, returns its own day.
    assert phoenix_retrieval._span_day(old, None) == (now - timedelta(hours=2)).date()
    # Malformed / missing timestamp -> excluded.
    assert phoenix_retrieval._span_day({"start_time": "nope"}, cutoff) is None
    assert phoenix_retrieval._span_day({}, cutoff) is None
