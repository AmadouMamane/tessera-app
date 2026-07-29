"""The live incident CORE is memoised and shared; as-of / explicit-now cluster fresh.

The ~2.9 s ledger clustering (``_RealIncidents``) hangs on the chrome bell of every cockpit page
AND on the incidents page body. It is memoised single-flight on a 30 s TTL, and the SAME core is
served to both the sidebar badge (``open_incidents()``) and the page. These tests pin that a live
page load clusters the ledger once — not twice for the page and a third for the badge — that both
surfaces read the same core (so their counts agree by construction), that an as-of-T or explicit
``now`` call always clusters fresh (its moment is exact), and that the reset hook forces a
recompute (test isolation).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from tessera.observability import incidents

if TYPE_CHECKING:
    import pytest

_NOW = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)


def _spy_on_core(monkeypatch: pytest.MonkeyPatch) -> list[tuple[object, object]]:
    """Count ``_RealIncidents`` constructions (the clustering), delegating to the real class.

    The ledger read is stubbed to empty and low-score to a constant, so each build is cheap and
    DB-free; what we assert is HOW MANY cores get built, not what they contain.
    """
    builds: list[tuple[object, object]] = []
    real = incidents._RealIncidents

    def _wrapper(now: datetime, asof: str | None = None) -> incidents._RealIncidents:
        builds.append((now, asof))
        return real(now, asof=asof)

    monkeypatch.setattr(incidents, "read_ledger_entries", lambda **_kw: [])
    monkeypatch.setattr(incidents, "_scan_low_score", lambda *_a, **_kw: (0, None))
    monkeypatch.setattr(incidents, "_RealIncidents", _wrapper)
    return builds


def test_live_core_is_memoised(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two live badge calls within the TTL cluster the ledger ONCE — the second reads the memo."""
    incidents.reset_open_incidents_cache()
    builds = _spy_on_core(monkeypatch)
    incidents.open_incidents()
    incidents.open_incidents()
    assert len(builds) == 1


def test_badge_and_page_share_one_core(monkeypatch: pytest.MonkeyPatch) -> None:
    """The sidebar badge and the incidents page derive from the SAME memoised core — one build.

    This is the whole point of the change: a live page load used to cluster the ledger twice (once
    for the body, once for the KPI count) and the bell a third time. All three now share one core.
    """
    incidents.reset_open_incidents_cache()
    builds = _spy_on_core(monkeypatch)
    badge = incidents.open_incidents()  # the chrome bell
    payload = incidents.compute_incidents_overview("fr")  # the page (live)
    assert len(builds) == 1
    # …and the two surfaces report the SAME open count, by construction (same core).
    assert int(payload["kpis"][0]["value"]) == badge[0]  # type: ignore[index]


def test_asof_and_explicit_now_cluster_fresh(monkeypatch: pytest.MonkeyPatch) -> None:
    """An as-of-T or explicit-``now`` caller clusters fresh every time — never the live memo."""
    incidents.reset_open_incidents_cache()
    builds = _spy_on_core(monkeypatch)
    incidents.open_incidents(at="2026-07-01T00:00:00+00:00")
    incidents.open_incidents(at="2026-07-01T00:00:00+00:00")
    incidents.open_incidents(now=_NOW)
    assert len(builds) == 3


def test_asof_page_does_not_poison_the_live_memo(monkeypatch: pytest.MonkeyPatch) -> None:
    """An as-of-T page load clusters its own core and leaves the live memo untouched."""
    incidents.reset_open_incidents_cache()
    builds = _spy_on_core(monkeypatch)
    incidents.compute_incidents_overview("fr", at="2026-06-01T00:00:00+00:00")  # as-of: fresh
    incidents.open_incidents()  # live: first miss → its own build
    incidents.open_incidents()  # live: hit
    assert len(builds) == 2


def test_reset_forces_a_recompute(monkeypatch: pytest.MonkeyPatch) -> None:
    """The reset hook (conftest isolation) drops the memo so the next live call re-clusters."""
    incidents.reset_open_incidents_cache()
    builds = _spy_on_core(monkeypatch)
    incidents.open_incidents()
    incidents.reset_open_incidents_cache()
    incidents.open_incidents()
    assert len(builds) == 2


def test_a_stale_core_past_the_ttl_is_rebuilt(monkeypatch: pytest.MonkeyPatch) -> None:
    """Past the TTL the live core is re-clustered — the memo bounds staleness, it does not pin."""
    incidents.reset_open_incidents_cache()
    builds = _spy_on_core(monkeypatch)
    clock = [1000.0]
    monkeypatch.setattr(incidents.time, "monotonic", lambda: clock[0])
    incidents.open_incidents()
    clock[0] += incidents._OPEN_INCIDENTS_TTL_S + 1.0
    incidents.open_incidents()
    assert len(builds) == 2
