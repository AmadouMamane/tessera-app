"""Unit tests for the reliability & cost posture (image 08)."""

from __future__ import annotations

from tessera.observability import reliability as rel


def test_provider_mapping() -> None:
    assert rel._provider("llama3.2:3b") == "Meta"
    assert rel._provider("gemma3:27b") == "Google"
    assert rel._provider("gpt-5.5") == "OpenAI"
    assert rel._provider("claude-opus") == "Anthropic"
    assert rel._provider("something-local") == "Local"


def test_latency_estimate_scales_with_tokens() -> None:
    # latency ≈ tokens / throughput, in milliseconds.
    assert rel._latency_ms(rel._THROUGHPUT_TOK_S) == 1000.0
    assert rel._latency_ms(0) == 0.0
    assert rel._latency_ms(2 * rel._THROUGHPUT_TOK_S) == 2000.0


def test_compute_reliability_is_internally_consistent() -> None:
    report = rel.compute_reliability()
    assert 0.0 <= report.availability <= 1.0
    assert report.error_rate == 1.0 - report.availability
    assert report.latency_p95_ms >= report.latency_p50_ms
    # Per-provider request counts roll up the per-model counts.
    model_total = sum(m.n_requests for m in report.models)
    provider_total = sum(p.n_requests for p in report.providers)
    assert provider_total == model_total
    # Cost is non-negative and the per-request figure is consistent.
    assert report.total_cost_eur >= 0.0
    assert report.budget_monthly_eur > 0.0


def test_trends_bucket_real_scores(monkeypatch) -> None:
    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)
    # Higher quality + more volume in the current window than the previous one.
    rows: list[dict[str, object]] = []
    for day in range(rel._TREND_DAYS):  # current window
        for _ in range(3):
            rows.append(
                {
                    "scored_at": (now - timedelta(days=day)).isoformat(),
                    "metric": "faithfulness",
                    "score": 0.9,
                }
            )
    for day in range(rel._TREND_DAYS, rel._TREND_DAYS * 2):  # previous window, sparser + lower
        rows.append(
            {
                "scored_at": (now - timedelta(days=day)).isoformat(),
                "metric": "faithfulness",
                "score": 0.5,
            }
        )
    monkeypatch.setattr(rel, "persisted_scores", lambda: rows)
    volume_series, volume_delta, quality_series, quality_delta = rel._trends()
    assert len(volume_series) == rel._TREND_BUCKETS
    assert volume_delta is not None and volume_delta > 0  # current window busier
    assert all(0.0 <= v <= 1.0 for v in quality_series)
    assert quality_delta is not None and quality_delta > 0  # quality improved


def test_trends_empty_log_yields_nothing(monkeypatch) -> None:
    monkeypatch.setattr(rel, "persisted_scores", list)
    assert rel._trends() == ([], None, [], None)
