"""Unit tests for cross-tenant leakage detection (ADR 0010, #74)."""

from __future__ import annotations

from tessera.observability.cross_tenant import detect_cross_tenant

_A = "434b766f-9e5a-4c21-8d0e-111111111111"
_B = "76721fda-f230-4a55-9c1b-222222222222"


def test_empty() -> None:
    report = detect_cross_tenant([])
    assert report.n_turns == 0
    assert report.leak_rate == 0.0


def test_no_leak_when_only_own_id() -> None:
    report = detect_cross_tenant([(_A, f"context referencing {_A} only")])
    assert report.n_leaks == 0


def test_no_leak_without_ids() -> None:
    report = detect_cross_tenant([(_A, "Les frais de tenue de compte sont de 2 euros.")])
    assert report.n_leaks == 0


def test_foreign_id_is_a_leak() -> None:
    report = detect_cross_tenant([(_A, f"leaked memory from {_B}")])
    assert report.n_leaks == 1
    assert _B in report.leaks[0].foreign_ids
    assert report.leak_rate == 1.0


def test_mixed_own_and_foreign() -> None:
    report = detect_cross_tenant([(_A, f"own {_A} and foreign {_B}")])
    assert report.leaks[0].foreign_ids == [_B]
