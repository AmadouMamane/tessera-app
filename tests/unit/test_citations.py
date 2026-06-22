"""Unit tests for the durable citation telemetry shaping (pure pieces).

The Postgres read/write paths need a database and live in the integration
suite; here we cover the pure transform that turns the durable counters into the
probe payload the dashboards consume (``knowledge.citation_probe_from_counts``).
"""

from __future__ import annotations

from tessera.observability.knowledge import _SOURCE_META, citation_probe_from_counts
from tessera.retrieval.citations import CitationCounts


def test_citation_probe_from_counts_shapes_probe_format() -> None:
    counts = CitationCounts(queries=10, queries_with_hit=7, hits={"cartes": 5, "dora": 2})
    payload = citation_probe_from_counts(counts)

    assert payload["source"] == "postgres"
    assert payload["queries"] == 10

    cats = payload["categories"]
    assert isinstance(cats, dict)
    assert cats["cartes"] == {"citation": 50.0, "hits": 5}
    assert cats["dora"] == {"citation": 20.0, "hits": 2}
    # A never-cited category is still present with zeroes (parity with the probe).
    assert cats["comptes"] == {"citation": 0.0, "hits": 0}

    overall = payload["_overall"]
    assert isinstance(overall, dict)
    assert overall["hitrate"] == 70.0  # 7 of 10 queries cited at least one source
    assert overall["coverage"] == round(100 * 2 / len(_SOURCE_META), 1)  # 2 cited categories


def test_citation_probe_from_counts_handles_zero_queries() -> None:
    payload = citation_probe_from_counts(CitationCounts(queries=0, queries_with_hit=0, hits={}))
    cats = payload["categories"]
    assert isinstance(cats, dict)
    assert all(entry == {"citation": 0.0, "hits": 0} for entry in cats.values())
    assert payload["queries"] == 0
    overall = payload["_overall"]
    assert isinstance(overall, dict)
    assert overall["hitrate"] == 0.0
    assert overall["coverage"] == 0.0
