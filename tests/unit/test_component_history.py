"""A gap in the record is not uptime — the property the whole history module exists for.

The probe runs when somebody asks. A cockpit left open overnight produces a dense record; a
cockpit nobody opened produces none. Any code that folds the second case into "it was fine" is
manufacturing availability out of nobody looking, and it is the easiest thing in this module to
write by accident: the natural implementation extends a phase to *now* and reports 100 %.

So the assertions below are mostly about silence — what the journal must REFUSE to say.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from tessera.observability.component_history import (
    CONTINUITY_WINDOW,
    ComponentPhase,
    availability,
    record_observation,
    transitions,
)

_T0 = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)


def _phases(*specs: tuple[str, str, datetime, datetime]) -> list[ComponentPhase]:
    return [
        ComponentPhase(
            component=component,
            verdict=verdict,
            since=since.isoformat(),
            until=until.isoformat(),
            n_observations=2,
        )
        for component, verdict, since, until in specs
    ]


def test_an_unobserved_window_yields_no_availability_at_all() -> None:
    """Nothing recorded ⇒ no component, no percentage. Not 0 %, not 100 %."""
    assert availability(since=_T0, until=_T0 + timedelta(hours=1), phases=[]) == {}


def test_time_nobody_watched_stays_out_of_the_numerator_and_the_denominator() -> None:
    """Six minutes watched inside a one-hour window is a statement about six minutes."""
    watched = _phases(("clickhouse", "ok", _T0, _T0 + timedelta(minutes=6)))
    stat = availability(since=_T0, until=_T0 + timedelta(hours=1), phases=watched)["clickhouse"]

    assert stat.observed_seconds == 360.0
    assert stat.window_seconds == 3600.0
    assert stat.observed_ratio == 0.1
    assert stat.ok_ratio == 1.0, "of what was observed, all of it was ok — and that is all"


def test_a_window_watched_entirely_through_a_blind_spot_has_no_availability() -> None:
    """Caught on the screen, not in a test: three blind minutes rendered as **0.0 % available**.

    Blind time IS observed — looking and failing to see is still looking — but it decides nothing
    about the component, so it may not sit in the denominator of a number called availability.
    Dividing by observed time printed "the database is down" over "nobody could ask the database",
    in the same column and the same ink as a real outage.
    """
    unseeable = _phases(("clickhouse", "blind", _T0, _T0 + timedelta(minutes=3)))
    stat = availability(since=_T0, until=_T0 + timedelta(hours=24), phases=unseeable)["clickhouse"]

    assert stat.observed_seconds == 180.0, "the probe did look — that is not in question"
    assert stat.decidable_seconds == 0.0, "…and it decided nothing about the component"
    assert stat.ok_ratio is None, "so there is no availability to state, not even 0 %"


def test_availability_is_a_share_of_decidable_time_not_of_watched_time() -> None:
    """Half up, then down, then a blind stretch that must dilute neither."""
    mixed = _phases(
        ("prometheus", "ok", _T0, _T0 + timedelta(minutes=6)),
        ("prometheus", "fail", _T0 + timedelta(minutes=6), _T0 + timedelta(minutes=8)),
        ("prometheus", "blind", _T0 + timedelta(minutes=8), _T0 + timedelta(minutes=28)),
    )
    stat = availability(since=_T0, until=_T0 + timedelta(hours=1), phases=mixed)["prometheus"]

    assert stat.observed_seconds == 1680.0
    assert stat.decidable_seconds == 480.0
    assert stat.ok_ratio == 0.75, "6 of the 8 minutes anybody could judge"


def test_a_phase_does_not_run_on_to_the_edge_of_the_window() -> None:
    """The one-line bug this module is shaped against: clipping to `until`, not to now."""
    stale = _phases(("prometheus", "ok", _T0, _T0 + timedelta(minutes=1)))
    stat = availability(since=_T0, until=_T0 + timedelta(hours=24), phases=stale)["prometheus"]
    assert stat.observed_seconds == 60.0
    assert stat.observed_ratio < 0.001


def test_availability_over_an_unobserved_window_is_none_rather_than_a_number() -> None:
    """`ok_ratio` has to be able to say nothing; 0.0 and 1.0 are both assertions."""
    outside = _phases(("redis", "ok", _T0 - timedelta(days=3), _T0 - timedelta(days=3)))
    stats = availability(since=_T0, until=_T0 + timedelta(hours=1), phases=outside)
    assert "redis" not in stats, "a phase entirely outside the window contributes nothing"


def test_two_observations_close_together_extend_one_phase() -> None:
    """Otherwise a 15-second poll writes 5 760 rows a day that all say 'no change'."""
    first = record_observation({"redis": "ok"}, at=_T0, phases=[])
    second = record_observation({"redis": "ok"}, at=_T0 + timedelta(seconds=15), phases=first)
    assert len(second) == 1
    assert second[0].n_observations == 2
    assert second[0].since == _T0.isoformat()
    assert second[0].until == (_T0 + timedelta(seconds=15)).isoformat()


def test_the_same_verdict_after_a_long_silence_starts_a_new_phase() -> None:
    """The heart of it. Extending here would claim the component was ok all night.

    Same verdict on both sides, and the record still splits: what happened in between is not
    known, and the hole has to survive into the arithmetic as a hole.
    """
    first = record_observation({"grafana": "ok"}, at=_T0, phases=[])
    later = record_observation(
        {"grafana": "ok"}, at=_T0 + CONTINUITY_WINDOW + timedelta(seconds=1), phases=first
    )
    assert len(later) == 2, "a hole must not be absorbed into a steady phase"

    stat = availability(since=_T0, until=_T0 + timedelta(hours=1), phases=later)["grafana"]
    assert stat.observed_seconds == 0.0, "two instants, no observed duration between them"


def test_a_restart_after_silence_is_not_reported_as_a_transition() -> None:
    """Same verdict either side of a hole: the record restarted, the component did not change.

    Reporting it would invent an incident out of a cockpit having been closed — and it would do
    so every single morning.
    """
    first = record_observation({"minio": "ok"}, at=_T0, phases=[])
    later = record_observation({"minio": "ok"}, at=_T0 + timedelta(hours=8), phases=first)
    assert transitions(since=_T0, until=_T0 + timedelta(days=1), phases=later) == []


def test_a_verdict_change_is_a_transition_and_names_both_sides() -> None:
    """The event a poll-and-render page throws away."""
    first = record_observation({"clickhouse": "ok"}, at=_T0, phases=[])
    broke = record_observation({"clickhouse": "fail"}, at=_T0 + timedelta(seconds=15), phases=first)
    found = transitions(since=_T0, until=_T0 + timedelta(hours=1), phases=broke)

    assert len(found) == 1
    assert (found[0].from_verdict, found[0].to_verdict) == ("ok", "fail")
    assert not found[0].after_gap, "witnessed within the continuity window, not discovered late"


def test_a_change_discovered_after_a_hole_is_flagged_as_discovered() -> None:
    """Its instant is when the probe FOUND it, not when it happened. The UI must say which."""
    first = record_observation({"phoenix": "ok"}, at=_T0, phases=[])
    broke = record_observation({"phoenix": "fail"}, at=_T0 + timedelta(hours=6), phases=first)
    found = transitions(since=_T0, until=_T0 + timedelta(days=1), phases=broke)

    assert len(found) == 1
    assert found[0].after_gap, "six hours of silence sit between the two verdicts"


def test_a_first_ever_observation_is_not_a_transition() -> None:
    """Nothing changed — the record began. The component may have been failing for a week.

    The alternative, emitting it with an assumed ``ok`` on the left, reports a recovery nobody
    witnessed; emitting it with ``None`` announces an incident every time a container restarts.
    Neither is a fact, so neither is published.
    """
    first = record_observation({"postgres": "fail"}, at=_T0, phases=[])
    assert (
        transitions(since=_T0 - timedelta(hours=1), until=_T0 + timedelta(hours=1), phases=first)
        == []
    )


def test_a_change_older_than_the_window_is_not_reported_as_recent() -> None:
    """Otherwise last week's incident is re-litigated at every morning stand-up."""
    old = _phases(
        ("langfuse-web", "ok", _T0 - timedelta(days=9), _T0 - timedelta(days=9)),
        ("langfuse-web", "fail", _T0 - timedelta(days=8), _T0 + timedelta(hours=1)),
    )
    assert transitions(since=_T0, until=_T0 + timedelta(hours=1), phases=old) == []


def test_a_flapping_component_cannot_evict_the_others_history() -> None:
    """The cap is per component; a shared cap makes one noisy node erase everyone else's record."""
    phases: list[ComponentPhase] = []
    for index in range(600):
        phases = record_observation(
            {"redis": "ok" if index % 2 else "fail", "postgres": "ok"},
            at=_T0 + timedelta(hours=index),
            phases=phases,
        )
    kept = {phase.component for phase in phases}
    assert "postgres" in kept, "the quiet component's history survived the noisy one"
