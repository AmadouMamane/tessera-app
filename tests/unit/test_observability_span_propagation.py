"""Unit tests for span propagation under async/parallel (ADR 0010, #85)."""

from __future__ import annotations

import asyncio

from tessera.observability import span_propagation
from tessera.observability.span_propagation import SpanRef


def test_clean_tree_propagates() -> None:
    spans = [
        SpanRef(name="request", span_id="root", parent_id=None),
        SpanRef(name="invoke_agent a", span_id="a", parent_id="root"),
        SpanRef(name="invoke_agent b", span_id="b", parent_id="root"),
    ]
    report = span_propagation.analyze_propagation(spans)
    assert report.propagated_ok is True
    assert report.n_orphans == 0
    assert report.n_roots == 1
    assert report.max_fanout == 2


def test_orphan_is_detected() -> None:
    spans = [
        SpanRef(name="request", span_id="root", parent_id=None),
        SpanRef(name="invoke_agent lost", span_id="x", parent_id="missing"),
    ]
    report = span_propagation.analyze_propagation(spans)
    assert report.propagated_ok is False
    assert report.n_orphans == 1
    assert report.orphan_names == ["invoke_agent lost"]


def test_multiple_roots_flagged() -> None:
    spans = [
        SpanRef(name="r1", span_id="r1", parent_id=None),
        SpanRef(name="r2", span_id="r2", parent_id=None),
    ]
    report = span_propagation.analyze_propagation(spans)
    assert report.n_roots == 2
    assert report.propagated_ok is False


def test_empty_is_not_ok() -> None:
    report = span_propagation.analyze_propagation([])
    assert report.propagated_ok is False
    assert report.n_spans == 0


def test_live_probe_has_no_orphans() -> None:
    report = asyncio.run(span_propagation.probe_propagation(fanout=4))
    # The parallel fan-out must nest under one root with no orphaned worker spans.
    assert report.propagated_ok is True
    assert report.n_spans == 5  # 1 request + 4 workers
    assert report.max_fanout == 4
    assert report.n_orphans == 0
