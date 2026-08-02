"""A control's curve is its own derivation over narrower windows — never a second one.

The registry exists because "Calibration des refus" said different things on two pages, and
the cause was always the same: a derivation copied instead of shared. A sparkline is the same
trap on the time axis. Give each control a bespoke "trend" computation and, sooner or later,
a row shows a falling line above a rising number and both are defensible in isolation.

So the series is defined as: the SAME handler, called with the bucket as its scope. These
tests hold that definition to account — the last bucket of a one-bucket series must BE the
point value, byte for byte, because there is only one code path and one window.

They also hold the two refusals, which are the part most likely to be quietly "improved" away:
an empty bucket is a gap, not a zero, and a fixed-corpus probe gets no line at all rather than
a flat one.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest import mock

import pytest

from tessera.api.routes import observability as obs
from tessera.observability import control_series, replay as replay_mod
from tessera.observability.control_series import (
    _ROUND_HOURS,
    MAX_BUCKETS,
    REASON_FIXED_CORPUS,
    REASON_NO_TIMESTAMP,
    buckets_for_window,
    compute_control_series,
)
from tessera.observability.eval import scores as scores_mod
from tessera.observability.spine.adapters import set_reader
from tessera.observability.spine.scope import Scope
from tessera.observability.spine.snapshot import reset_snapshot_cache
from tests.unit._route_helpers import call_route

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

_NOW = datetime.now(UTC)


def _at(days_ago: float) -> str:
    return (_NOW - timedelta(days=days_ago)).isoformat()


def _score(days_ago: float, score: float) -> dict[str, object]:
    return {
        "scored_at": _at(days_ago),
        "metric": "faithfulness",
        "score": score,
        "language": "fr",
        "conversation_id": f"c-{days_ago}",
        "agent_id": "support-client",
    }


def _bundle(days_ago: float, bundle_id: str) -> dict[str, object]:
    return {
        "bundle_id": bundle_id,
        "captured_at": _at(days_ago),
        "conversation_id": f"c-{bundle_id}",
        "language": "fr",
        "question": "Quel est mon solde ?",
        "context": "Le solde est 100 EUR.",
        "original_answer": "Votre solde est de 100 EUR.",
        "original_model": "llama3.2:3b",
        "original_score": 0.9,
        "lineage": None,
        "latency_ms": None,
        "agent_id": "support-client",
    }


@pytest.fixture(autouse=True)
def _seed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Traffic on days 6, 5 and 1 — and deliberately NONE on days 4, 3 and 2.

    The hole in the middle is the fixture's real job: it is what tells an empty bucket
    (``null``) apart from a measured zero, and a series that quietly zero-fills passes every
    other assertion here while failing that one.
    """
    # Same reason as `test_period_reaches_the_data`: name the reader being judged.
    monkeypatch.setenv("TESSERA_SPINE_SOURCE", "local")
    set_reader(None)
    reset_snapshot_cache()
    scores_path = tmp_path / "scores.jsonl"
    bundles_path = tmp_path / "bundles.jsonl"
    monkeypatch.setattr(scores_mod, "_scores_path", lambda: scores_path)
    monkeypatch.setattr(replay_mod, "_bundles_path", lambda: bundles_path)
    # Both stores keep a MODULE-LEVEL live view with a "already warmed" flag. Repointing the
    # path is not enough: a test that ran earlier has already warmed the deque from ITS file,
    # and the flag makes every later read return those rows. Alone this file passed; in the
    # suite it read another test's bundles. Clear both, or the fixture is decorative.
    replay_mod._BUNDLES.clear()
    monkeypatch.setattr(replay_mod, "_WARMED", False)
    scores_mod._RECENT.clear()
    monkeypatch.setattr(scores_mod, "_WARMED", False)
    scores_path.write_text(
        "\n".join(json.dumps(_score(d, s)) for d, s in ((6, 0.4), (5, 0.6), (1, 0.95))) + "\n",
        encoding="utf-8",
    )
    bundles_path.write_text(
        "\n".join(json.dumps(_bundle(d, f"b{d}")) for d in (6, 5, 1)) + "\n",
        encoding="utf-8",
    )
    yield
    set_reader(None)
    reset_snapshot_cache()


#: Fields that echo the scope back rather than measure anything. A bucket names the instant
#: it ends at; a live read has none to name. They differ BY CONSTRUCTION, and comparing them
#: would make this test fail for the one reason that proves nothing.
_SCOPE_ECHO = frozenset({"as_of", "agent", "days"})


def _measured(payload: object) -> dict[str, object]:
    """A payload stripped of its scope echo — what the control actually measured."""
    assert isinstance(payload, dict)
    return {k: v for k, v in payload.items() if k not in _SCOPE_ECHO}


@pytest.mark.asyncio
async def test_a_one_bucket_series_is_the_point_value_itself() -> None:
    """The identity that makes a curve incapable of contradicting its number.

    One bucket over the whole window IS the window. If these ever differ, a second derivation
    has appeared somewhere — which is the defect this module was written to make impossible,
    not merely unlikely.

    Every measured field must match: the sample size, the rate, the burn, the budget. Only the
    scope echo is allowed to differ, and only because a bucket has an end instant to report and
    a live read does not.
    """
    report = await compute_control_series(Scope(period_days=7), n_buckets=1)
    assert report.n_buckets == 1
    only = report.buckets[0]
    point = await call_route(obs.observability_slo, days="7")
    assert _measured(only.payload["slo"]) == _measured(point), (
        "the single bucket of a 7-day series is not the 7-day value — the series and the "
        "number are being computed by different paths"
    )
    # …and the echo is not vacuous: the bucket really does name where it ends.
    assert only.payload["slo"]["as_of"] == only.until  # type: ignore[index,call-overload]


@pytest.mark.asyncio
async def test_the_buckets_partition_the_window_with_no_gap_and_no_overlap() -> None:
    """Each bucket ends where the next begins, and the last ends at the window's end."""
    report = await compute_control_series(Scope(period_days=7), n_buckets=8)
    assert [b.index for b in report.buckets] == list(range(8))
    for earlier, later in zip(report.buckets, report.buckets[1:], strict=False):
        assert earlier.until == later.since, "buckets leave a hole or overlap"
    assert report.buckets[0].since == report.since
    assert report.buckets[-1].until == report.until


@pytest.mark.asyncio
async def test_a_bucket_with_no_traffic_reports_an_empty_sample_not_a_zero() -> None:
    """The distinction a chart cannot draw twice: nothing measured vs measured nothing.

    On a leak rate those two render the same colour and mean opposite things — one is a quiet
    week, the other is a week of clean answers.
    """
    report = await compute_control_series(Scope(period_days=7), n_buckets=7)
    sizes = [int(b.payload["slo"]["n"]) for b in report.buckets]  # type: ignore[index,call-overload]
    assert sum(sizes) == 3, f"the buckets hold {sum(sizes)} scores, the window holds 3"
    assert 0 in sizes, "the fixture's quiet days produced no empty bucket — the hole was filled"
    # An empty bucket answers n=0 with no scores; the FRONT turns that into a gap because
    # `readControls` reports `noData` on an empty sample. What must never happen here is a
    # bucket inheriting its neighbour's rows to avoid looking empty.
    assert sizes.count(0) >= 3, f"expected the three quiet days to stay empty, got {sizes}"


@pytest.mark.asyncio
async def test_the_curve_and_the_number_agree_on_how_many_rows_they_saw() -> None:
    """Summing the buckets must recover the window: a partition, not a sample of it."""
    for days, expected in ((7, 3), (2, 1)):
        report = await compute_control_series(Scope(period_days=days), n_buckets=4)
        total = sum(int(b.payload["slo"]["n"]) for b in report.buckets)  # type: ignore[index,call-overload]
        point = await call_route(obs.observability_slo, days=str(days))
        assert (
            total == point["n"] == expected
        ), f"{days}d: buckets see {total} rows, the point value sees {point['n']}"


@pytest.mark.asyncio
async def test_a_fixed_corpus_probe_gets_no_line_and_says_which_reason() -> None:
    """No curve is a statement. A flat one is a claim, and it would be false.

    Re-running the same adversarial corpus against the same policy in a narrower window
    returns the same number — eight identical points that draw as a reassuringly stable
    metric while being one measurement, repeated.
    """
    report = await compute_control_series(Scope(period_days=7), n_buckets=8)
    for key in ("refusal", "firewall", "crossTenant", "privilege", "inversion"):
        assert report.unwindowed[key] == REASON_FIXED_CORPUS
        for bucket in report.buckets:
            assert key not in bucket.payload, f"{key} was bucketed despite being fixed-corpus"
    for key in ("clusters", "calibration", "predictor"):
        assert report.unwindowed[key] == REASON_NO_TIMESTAMP


@pytest.mark.asyncio
async def test_no_source_is_both_bucketed_and_declared_unwindowed() -> None:
    """The two lists must not intersect — a key in both would draw a line AND excuse itself."""
    report = await compute_control_series(Scope(period_days=7), n_buckets=4)
    bucketed = {key for bucket in report.buckets for key in bucket.payload}
    overlap = bucketed & set(report.unwindowed)
    assert not overlap, f"{sorted(overlap)} are bucketed and declared unwindowed at once"


@pytest.mark.asyncio
async def test_all_history_yields_no_buckets_rather_than_an_invented_axis() -> None:
    """A window with no width cannot be sliced, and guessing one moves the axis with the demo.

    Deriving the span from the oldest row present would make "30 days" mean something
    different every morning — and the operator would have no way to tell.
    """
    report = await compute_control_series(Scope(), n_buckets=8)
    assert report.buckets == []
    assert report.n_buckets == 0
    assert report.days is None
    # The refusals still travel: the UI must be able to say WHY a control has no curve even
    # when nothing has a curve.
    assert report.unwindowed["refusal"] == REASON_FIXED_CORPUS


@pytest.mark.asyncio
async def test_the_bucket_count_is_bounded_because_each_bucket_is_a_read() -> None:
    """`?buckets=` is a read multiplier; an unbounded one is an unbounded read."""
    report = await compute_control_series(Scope(period_days=7), n_buckets=10_000)
    assert report.n_buckets == MAX_BUCKETS
    assert (await compute_control_series(Scope(period_days=7), n_buckets=0)).n_buckets == 1
    assert (await compute_control_series(Scope(period_days=7), n_buckets=-4)).n_buckets == 1


@pytest.mark.parametrize(
    ("period_days", "expected_count", "expected_width_hours"),
    [(1, 12, 2), (7, 14, 12), (30, 30, 24)],
)
def test_each_cockpit_period_is_cut_into_round_clock_units(
    period_days: int, expected_count: int, expected_width_hours: float
) -> None:
    """The three periods the rail offers, and the width each slice ends up being.

    Pinned as values rather than derived, because they were CHOSEN by measuring the curves
    they draw (see ``_LADDER``). A formula would be prettier and would have to disagree with
    one of the three: the finest slicing is right at 30 j and buys nothing at 24 h and 7 j,
    where a slice narrower than the gaps between requests puts a hole between every pair of
    points.
    """
    count = buckets_for_window(period_days)
    assert count == expected_count
    assert period_days * 24 / count == pytest.approx(expected_width_hours)


@pytest.mark.parametrize("period_days", [1, 7, 30, 14, 90, 0.5, 3])
def test_no_window_is_sliced_into_a_duration_nobody_reads_an_axis_in(period_days: float) -> None:
    """Every slice is a round clock unit, and there are between 12 and MAX_BUCKETS of them.

    This is the bar the flat count of 8 failed, and failed worst exactly where it was reported:
    7 days over 8 buckets is **21 h** a slice — not a unit anyone reads, and wide enough to
    swallow a whole day's traffic into one point.

    Twelve is the floor because that configuration was measured, not because it reads well:
    replayed at 8 window ends over 3 controls, 8 slices of 21 h drew a 7-day curve in **0 of
    24** cases and 14 slices of 12 h drew one in 3. A bar this file cannot show failing
    somewhere would be decoration — this one fails on the count that shipped until today.
    """
    count = buckets_for_window(period_days)
    assert 12 <= count <= MAX_BUCKETS, f"{period_days} d → {count} buckets"
    assert period_days * 24 / count in _ROUND_HOURS


def test_a_window_no_round_unit_divides_still_answers_within_bounds() -> None:
    """53 days is divided evenly by no unit on the ladder, and must not raise or run away.

    The round-unit promise is dropped there and nowhere else; the bound is not, because a
    bucket is a full re-read of the stores.
    """
    count = buckets_for_window(53)
    assert 1 <= count <= MAX_BUCKETS


def test_only_the_month_overrides_the_general_rule() -> None:
    """Two of the three measured choices are what the general rule already picks.

    Worth pinning: it says the ladder is not three arbitrary numbers, and it localises the one
    place where a measurement beat the rule — 30 j, where slicing by DAY (30 points) beat the
    rule's 48 h (15 points) on real traffic. If a change to `_TARGET_BUCKETS` ever moved the
    other two, this is what would say so.
    """
    assert {days: control_series._LADDER[days] for days in (1.0, 7.0)} == {1.0: 2.0, 7.0: 12.0}
    without_ladder = dict(control_series._LADDER)
    del without_ladder[1.0], without_ladder[7.0]
    with mock.patch.object(control_series, "_LADDER", without_ladder):
        assert buckets_for_window(1) == 12
        assert buckets_for_window(7) == 14
        assert buckets_for_window(30) == 30  # the surviving override
    with mock.patch.object(control_series, "_LADDER", {}):
        assert buckets_for_window(30) == 15  # what the rule alone would have drawn


@pytest.mark.asyncio
async def test_the_window_picks_the_resolution_when_the_caller_does_not() -> None:
    """The default is derived from the window; an explicit count still wins, still clamped.

    The count has to be decided in ONE place: the same control's curve is drawn on Vue
    d'ensemble and on Qualité IA, and a resolution chosen per surface is a resolution that
    diverges — the shape of a line is part of what it says.
    """
    derived = await compute_control_series(Scope(period_days=7))
    assert derived.n_buckets == buckets_for_window(7) == 14
    explicit = await compute_control_series(Scope(period_days=7), n_buckets=3)
    assert explicit.n_buckets == 3
    assert (await compute_control_series(Scope(period_days=7), n_buckets=0)).n_buckets == 1


@pytest.mark.asyncio
async def test_the_agent_scope_rides_along_so_a_curve_is_scoped_like_its_number() -> None:
    """A curve drawn org-wide under a per-agent number is a different, unlabelled measurement."""
    mine = await compute_control_series(
        Scope(agent_id="support-client", period_days=7), n_buckets=2
    )
    other = await compute_control_series(Scope(agent_id="recouvrement", period_days=7), n_buckets=2)
    assert sum(int(b.payload["slo"]["n"]) for b in mine.buckets) == 3  # type: ignore[index,call-overload]
    assert sum(int(b.payload["slo"]["n"]) for b in other.buckets) == 0  # type: ignore[index,call-overload]
