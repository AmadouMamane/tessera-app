"""The live open-incidents badge count is memoised; as-of / explicit-now compute fresh.

``open_incidents()`` (no args) hangs on the chrome bell of every cockpit page and is ~0.83 s of
incident-clustering compute. It is memoised single-flight on a 30 s TTL. These tests pin that the
live call is served from the cache, that an as-of-T or explicit-``now`` call always bypasses it
(its moment is exact), and that the reset hook forces a recompute (test isolation).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from tessera.observability import incidents

if TYPE_CHECKING:
    import pytest


def test_live_badge_call_is_memoised(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two live calls within the TTL yield ONE compute — the second reads the cached value."""
    incidents.reset_open_incidents_cache()
    calls: list[tuple[object, object]] = []
    monkeypatch.setattr(
        incidents,
        "_compute_open_incidents",
        lambda now, at: (calls.append((now, at)), (3, 1))[1],
    )
    assert incidents.open_incidents() == (3, 1)
    assert incidents.open_incidents() == (3, 1)
    assert len(calls) == 1


def test_asof_and_explicit_now_bypass_the_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """An as-of-T or explicit-``now`` caller (the incidents page) computes fresh every time."""
    incidents.reset_open_incidents_cache()
    calls: list[tuple[object, object]] = []
    monkeypatch.setattr(
        incidents,
        "_compute_open_incidents",
        lambda now, at: (calls.append((now, at)), (0, 0))[1],
    )
    incidents.open_incidents(at="2026-07-01T00:00:00+00:00")
    incidents.open_incidents(at="2026-07-01T00:00:00+00:00")
    incidents.open_incidents(now=datetime(2026, 7, 1, tzinfo=UTC))
    assert len(calls) == 3


def test_reset_forces_a_recompute(monkeypatch: pytest.MonkeyPatch) -> None:
    """The reset hook (conftest isolation) drops the memo so the next live call recomputes."""
    incidents.reset_open_incidents_cache()
    calls: list[tuple[object, object]] = []
    monkeypatch.setattr(
        incidents,
        "_compute_open_incidents",
        lambda now, at: (calls.append((now, at)), (1, 0))[1],
    )
    incidents.open_incidents()
    incidents.reset_open_incidents_cache()
    incidents.open_incidents()
    assert len(calls) == 2
