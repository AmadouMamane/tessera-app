"""Unit tests for the reliability & cost posture (image 08)."""

from __future__ import annotations

from tessera.observability import funnel as funnel_mod, reliability as rel


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


def test_trends_bucket_real_scores() -> None:
    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)
    days = 14
    # Higher quality + more volume in the current window than the previous one.
    rows: list[dict[str, object]] = []
    for day in range(days):  # current window
        for _ in range(3):
            rows.append(
                {
                    "scored_at": (now - timedelta(days=day)).isoformat(),
                    "metric": "faithfulness",
                    "score": 0.9,
                }
            )
    for day in range(days, days * 2):  # previous window, sparser + lower
        rows.append(
            {
                "scored_at": (now - timedelta(days=day)).isoformat(),
                "metric": "faithfulness",
                "score": 0.5,
            }
        )
    volume_series, volume_delta, quality_series, quality_delta = rel._trends(
        rows, end=now, days=days
    )
    assert len(volume_series) == rel._TREND_BUCKETS
    assert volume_delta is not None and volume_delta > 0  # current window busier
    assert all(0.0 <= v <= 1.0 for v in quality_series)
    assert quality_delta is not None and quality_delta > 0  # quality improved


def test_trends_empty_log_yields_nothing() -> None:
    from datetime import UTC, datetime

    assert rel._trends([], end=datetime.now(UTC), days=30) == ([], None, [], None)


def test_services_cost_shares_sum_to_one() -> None:
    funnel = funnel_mod.FunnelReport(
        n_turns=180,
        languages=[
            funnel_mod.LanguageFunnel("fr", 70, 50, 0.8, 0.5, 0.1),
            funnel_mod.LanguageFunnel("de", 60, 40, 0.7, 0.4, 0.2),
            funnel_mod.LanguageFunnel("en", 50, 30, 0.9, 0.6, 0.05),
        ],
    )
    rows = rel._services_cost(funnel, cost_per_request=0.001)
    assert [r.name for r in rows] == ["FR", "DE", "EN"]  # sorted by cost desc
    assert abs(sum(r.share for r in rows) - 1.0) < 1e-9


def test_daily_holds_snapshot_availability(monkeypatch) -> None:
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    rows = [{"scored_at": now.isoformat(), "metric": "faithfulness", "score": 0.2}]
    daily = rel._daily(
        rows, cost_per_request=0.01, availability=0.997, error_rate=0.003, end=now, days=30
    )
    assert len(daily) == 30
    # Availability is the headline rate held flat — never reinterpreted as quality.
    assert all(p.availability == 0.997 and p.error_rate == 0.003 for p in daily)
    assert any(p.volume > 0 for p in daily)  # the real turn was bucketed
