"""Unit tests for tail-based sampling (ADR 0010, #32)."""

from __future__ import annotations

from tessera.observability.replay import ReplayBundle
from tessera.observability.tail_sampling import analyze_sampling, decide


def _bundle(bundle_id: str, *, score: float, latency: float) -> ReplayBundle:
    return ReplayBundle(
        bundle_id=bundle_id,
        captured_at="2026-06-09T00:00:00+00:00",
        conversation_id="c1",
        language="fr",
        question="q",
        context="ctx",
        original_answer="a",
        original_model="llama3.2:3b",
        original_score=score,
        latency_ms={"total": latency},
    )


def test_slow_trace_is_tail_kept() -> None:
    d = decide(trace_id="x", latency_ms=5000, score=0.95, slow_threshold_ms=2500)
    assert d.keep is True
    assert d.tail is True
    assert "slow" in d.reasons


def test_low_score_is_tail_kept() -> None:
    d = decide(trace_id="x", latency_ms=10, score=0.4, score_threshold=0.8)
    assert d.keep is True
    assert d.tail is True
    assert "low_score" in d.reasons


def test_head_drop_with_zero_base_rate() -> None:
    d = decide(trace_id="x", latency_ms=10, score=0.95, base_rate=0.0)
    assert d.keep is False
    assert d.tail is False


def test_head_keep_with_full_base_rate() -> None:
    d = decide(trace_id="x", latency_ms=10, score=0.95, base_rate=1.0)
    assert d.keep is True
    assert d.tail is False
    assert d.reasons == ["sampled"]


def test_head_decision_is_deterministic() -> None:
    a = decide(trace_id="trace-42", latency_ms=10, score=0.95, base_rate=0.5)
    b = decide(trace_id="trace-42", latency_ms=10, score=0.95, base_rate=0.5)
    assert a.keep == b.keep


def test_empty_keeps_everything() -> None:
    report = analyze_sampling([])
    assert report.n_traces == 0
    assert report.retention_rate == 1.0
    assert report.tail_retention_rate == 1.0


def test_tail_fully_retained_head_thinned() -> None:
    # 5 tail (low score) + 100 clean fast head, base rate 0.1.
    tail = [_bundle(f"bad{i}", score=0.2, latency=10) for i in range(5)]
    head = [_bundle(f"ok{i}", score=0.95, latency=10) for i in range(100)]
    report = analyze_sampling(tail + head, base_rate=0.1)

    assert report.n_traces == 105
    assert report.n_tail == 5
    assert report.n_low_score == 5
    # The guarantee: every tail trace is kept.
    assert report.tail_retention_rate == 1.0
    # The head is thinned roughly to the base rate (deterministic hash, so not
    # exact), and far below full retention.
    assert report.n_kept >= 5
    assert report.n_kept < 105
    assert report.retention_rate < 0.5
