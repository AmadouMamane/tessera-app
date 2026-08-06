"""The scheduler's report is derived from what the loop WROTE, never from configuration.

ADR 0052 §Amendment 1. The failure this guards against is specific: the loop runs in the ADR
0044 leader process, the endpoint answering the page runs in any worker, and a report read off
the settings would say "scheduled" about a leader that died an hour ago. So the loop stamps
every beat to a file, and everything the page may claim is derived from that stamp — `never`,
`active` or `stale`, three words with three different repairs.

The stamp lands in the per-test state dir (`TESSERA_GUARD__AUDIT_FILE`'s parent, pinned to
`tmp_path` by conftest), so nothing here touches shared state.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from tessera.api.routes.observability import components as components_route
from tessera.observability import component_history, probe_scheduler
from tessera.observability.component_history import ComponentPhase, clipped_phases
from tessera.observability.stack_components import StackObservation
from tessera.preflight import Check, Verdict
from tessera.settings import get_settings

if TYPE_CHECKING:
    import pytest

_T0 = datetime(2026, 8, 7, 9, 0, tzinfo=UTC)


def test_no_stamp_reads_as_never_with_the_configured_intent() -> None:
    """Before the first beat the report may announce the cadence, but not a heartbeat."""
    report = probe_scheduler.scheduler_report(now=_T0)
    assert report["state"] == "never"
    assert report["last_run_at"] is None
    # The default posture ships the scheduler ON, so the intent is announced.
    assert report["interval_s"] == 60.0


def test_a_fresh_stamp_reads_as_active_and_carries_its_beat() -> None:
    probe_scheduler.write_stamp(at=_T0)
    report = probe_scheduler.scheduler_report(now=_T0 + timedelta(seconds=90))
    assert report["state"] == "active"
    assert report["interval_s"] == 60.0
    assert report["last_run_at"] is not None


def test_a_stopped_loop_reads_as_stale_never_as_active() -> None:
    """Two missed beats plus slack: the loop is dead, and the page must say so."""
    probe_scheduler.write_stamp(at=_T0)
    report = probe_scheduler.scheduler_report(now=_T0 + timedelta(seconds=60 * 2 + 31))
    assert report["state"] == "stale"
    # The beat itself stays visible: "stopped, last seen at T" is the actionable sentence.
    assert report["last_run_at"] is not None


def test_a_stamp_from_the_future_is_not_active() -> None:
    """A skewed clock must not manufacture liveness out of a beat that has not happened."""
    probe_scheduler.write_stamp(at=_T0 + timedelta(hours=1))
    report = probe_scheduler.scheduler_report(now=_T0)
    assert report["state"] == "stale"


def test_an_unreadable_stamp_is_indistinguishable_from_none() -> None:
    """Corrupt on disk ⇒ the report may not claim the scheduler is alive."""
    path = probe_scheduler._stamp_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")
    assert probe_scheduler.read_stamp() is None
    assert probe_scheduler.scheduler_report(now=_T0)["state"] == "never"


def test_posture_reads_the_setting_and_zero_disables(monkeypatch: pytest.MonkeyPatch) -> None:
    assert probe_scheduler.probe_posture() == {"scheduling": True, "interval_s": 60}
    monkeypatch.setenv("TESSERA_OBSERVABILITY__PROBE_INTERVAL_S", "0")
    get_settings.cache_clear()
    try:
        assert probe_scheduler.probe_posture() == {"scheduling": False, "interval_s": None}
    finally:
        get_settings.cache_clear()


def test_probe_for_scheduler_records_an_observation_and_a_beat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One beat = one journal write + one stamp — the two facts the page will lean on."""
    check = Check("clickhouse", Verdict.OK, "http 200")
    monkeypatch.setattr(components_route, "_stack_cache", None)
    monkeypatch.setattr(
        components_route,
        "probe_stack_observations",
        lambda *_, **__: (
            StackObservation(check=check, outcome="http_ok", address="clickhouse:8123", raw="200"),
        ),
    )
    observed_at = components_route.probe_for_scheduler()
    assert observed_at > 0
    journal = component_history.load_phases()
    assert [phase.component for phase in journal] == ["clickhouse"]
    assert probe_scheduler.read_stamp() is not None


# ---------------------------------------------------------------------------------------------
# clipped_phases — what a timeline may draw


def _phase(component: str, verdict: str, since: datetime, until: datetime) -> ComponentPhase:
    return ComponentPhase(
        component=component,
        verdict=verdict,
        since=since.isoformat(),
        until=until.isoformat(),
        n_observations=3,
    )


def test_clipping_bounds_a_phase_to_the_window() -> None:
    """A phase overhanging both edges is drawn as the slice the window can vouch for."""
    phases = [_phase("redis", "ok", _T0 - timedelta(hours=2), _T0 + timedelta(hours=2))]
    only = clipped_phases(since=_T0, until=_T0 + timedelta(hours=1), phases=phases)
    assert len(only) == 1
    assert only[0].since == _T0.isoformat()
    assert only[0].until == (_T0 + timedelta(hours=1)).isoformat()


def test_a_phase_wholly_outside_the_window_is_not_drawn() -> None:
    phases = [_phase("redis", "ok", _T0 - timedelta(hours=3), _T0 - timedelta(hours=2))]
    assert clipped_phases(since=_T0, until=_T0 + timedelta(hours=1), phases=phases) == []


def test_a_point_phase_survives_clipping() -> None:
    """One observation is a real look; dropping it would render « jamais observé »."""
    instant = _T0 + timedelta(minutes=30)
    phases = [_phase("minio", "fail", instant, instant)]
    only = clipped_phases(since=_T0, until=_T0 + timedelta(hours=1), phases=phases)
    assert len(only) == 1
    assert only[0].since == only[0].until == instant.isoformat()
    assert only[0].verdict == "fail"


def test_clipped_phases_are_ordered_for_a_renderer() -> None:
    """By component then by start — rows draw without re-sorting, holes stay visible as gaps."""
    phases = [
        _phase("redis", "ok", _T0 + timedelta(minutes=40), _T0 + timedelta(minutes=50)),
        _phase("minio", "ok", _T0 + timedelta(minutes=10), _T0 + timedelta(minutes=20)),
        _phase("redis", "fail", _T0 + timedelta(minutes=5), _T0 + timedelta(minutes=8)),
    ]
    ordered = clipped_phases(since=_T0, until=_T0 + timedelta(hours=1), phases=phases)
    assert [(p.component, p.verdict) for p in ordered] == [
        ("minio", "ok"),
        ("redis", "fail"),
        ("redis", "ok"),
    ]
