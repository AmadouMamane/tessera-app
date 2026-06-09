"""Unit tests for tool least-privilege observability (ADR 0010, #101)."""

from __future__ import annotations

from tessera.observability.least_privilege import analyze_privilege

_GRANTED = {"account_balance", "card_block", "transaction_search", "loan_simulate"}


def test_empty_usage_all_over_provisioned() -> None:
    report = analyze_privilege(_GRANTED, {})
    assert report.n_granted == 4
    assert report.n_used == 0
    assert report.n_over_provisioned == 4
    assert report.utilization_rate == 0.0


def test_partial_usage() -> None:
    report = analyze_privilege(_GRANTED, {"account_balance": 5, "card_block": 1})
    assert report.n_used == 2
    assert report.utilization_rate == 0.5
    assert "transaction_search" in report.over_provisioned
    assert "loan_simulate" in report.over_provisioned


def test_violation_used_but_not_granted() -> None:
    report = analyze_privilege(_GRANTED, {"account_balance": 1, "wire_transfer": 3})
    assert "wire_transfer" in report.violations
    assert report.n_violations == 1


def test_zero_count_is_not_used() -> None:
    report = analyze_privilege(_GRANTED, {"account_balance": 0})
    assert report.n_used == 0
    assert "account_balance" in report.over_provisioned


def test_usage_sorted_by_count() -> None:
    report = analyze_privilege(_GRANTED, {"card_block": 10, "account_balance": 2})
    assert report.usage[0].tool == "card_block"
    assert report.usage[0].used == 10
