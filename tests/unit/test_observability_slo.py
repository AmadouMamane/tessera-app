"""Unit tests for quality SLOs + error budgets (ADR 0010, #15)."""

from __future__ import annotations

from tessera.observability.slo import compute_slo


def test_empty_scores_no_breach() -> None:
    report = compute_slo([])
    assert report.n == 0
    assert report.budget_remaining == 1.0
    assert report.burn_rate == 0.0
    assert report.breaching is False


def test_all_good_full_budget_remaining() -> None:
    report = compute_slo([0.9, 0.85, 0.95, 0.8], threshold=0.8, target=0.95)
    assert report.n_good == 4
    assert report.n_bad == 0
    assert report.good_rate == 1.0
    assert report.budget_consumed == 0.0
    assert report.budget_remaining == 1.0
    assert report.burn_rate == 0.0
    assert report.breaching is False


def test_threshold_is_inclusive() -> None:
    # A score exactly at the threshold counts as good.
    report = compute_slo([0.8], threshold=0.8, target=0.95)
    assert report.n_good == 1
    assert report.n_bad == 0


def test_bad_rate_within_budget_does_not_breach() -> None:
    # 1 bad of 100 = 1 % bad rate, under the 5 % budget → burn rate 0.2.
    scores = [0.9] * 99 + [0.1]
    report = compute_slo(scores, threshold=0.8, target=0.95)
    assert report.n_bad == 1
    assert abs(report.burn_rate - 0.2) < 1e-9
    assert report.budget_remaining > 0.0
    assert report.breaching is False


def test_budget_exhausted_and_burning() -> None:
    # 50 % bad rate against a 5 % budget → burn rate 10, budget exhausted.
    scores = [0.9, 0.1] * 20
    report = compute_slo(scores, threshold=0.8, target=0.95)
    assert abs(report.burn_rate - 10.0) < 1e-9
    assert report.budget_consumed > 1.0
    assert report.budget_remaining == 0.0
    assert report.breaching is True


def test_fast_window_isolates_recent_burst() -> None:
    # A long-clean history followed by a recent burst of failures: the slow
    # window stays under budget so it should not breach, even though the fast
    # window is hot. Multi-window guards against single-window flapping.
    scores = [0.9] * 200 + [0.1] * 5
    report = compute_slo(scores, threshold=0.8, target=0.95)
    assert report.burn_rate_fast > 1.0
    assert report.burn_rate < 1.0
    assert report.breaching is False


def test_zero_error_budget_is_safe() -> None:
    # target=1.0 → no budget; must not divide by zero.
    report = compute_slo([0.9, 0.1], threshold=0.8, target=1.0)
    assert report.error_budget == 0.0
    assert report.budget_consumed == 0.0
    assert report.burn_rate == 0.0
