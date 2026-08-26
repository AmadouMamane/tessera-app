"""The period selector must change the numbers — measured on the answers, not the code.

The cockpit has shown a 24 h / 7 d / 30 d selector for as long as the rail has existed, and
until 2026-08-01 it steered nothing. Three separate omissions lined up, each invisible on its
own: no fetch sent the period, no handler declared it, and FastAPI drops an undeclared query
param without a word. ``/observability/slo?days=1``, ``?days=7`` and ``?days=30`` all answered
``n=67``. The picture on the rail changed scale; every number under it stayed put.

That is why this file asserts on **answers**, never on signatures. A test that checked "every
handler has a ``days`` parameter" would have gone green the moment the parameter existed, while
the value was still being thrown away downstream — and a test that counted call sites would
have gone green on a tree where the front never sent one. So: seed a store whose rows sit at
known distances in the past, ask each route for two different windows, and require the two
answers to differ.

The teeth are the other half. ``test_a_handler_that_ignores_the_window_is_caught`` hands the
same assertion a deliberately deaf handler; if that passes, this file proves nothing about the
real ones.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from tessera.api.routes import observability as obs
from tessera.api.routes.observability.batch import observability_fleet_batch
from tessera.observability import replay as replay_mod
from tessera.observability.eval import scores as scores_mod
from tessera.observability.spine.adapters import set_reader
from tessera.observability.spine.capabilities import CAPABILITIES
from tessera.observability.spine.scope import (
    PERIOD_DAYS,
    Dimension,
    Scope,
    parse_period_days,
)
from tessera.observability.spine.snapshot import compute_snapshot, reset_snapshot_cache
from tests.unit._route_helpers import call_route

if TYPE_CHECKING:
    from collections.abc import Iterator

_FRONT_STORE = (
    Path(__file__).resolve().parents[2]
    / "webapp"
    / "frontend"
    / "lib"
    / "stores"
    / "window-store.ts"
)
_FRONT_RAIL = (
    Path(__file__).resolve().parents[2]
    / "webapp"
    / "frontend"
    / "components"
    / "overview"
    / "temporal-rail.tsx"
)

_NOW = datetime.now(UTC)


def _at(days_ago: float) -> str:
    """An instant ``days_ago`` days before now, as the stores write it."""
    return (_NOW - timedelta(days=days_ago)).isoformat()


def _score(days_ago: float, score: float, metric: str = "faithfulness") -> dict[str, object]:
    return {
        "scored_at": _at(days_ago),
        "metric": metric,
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
def _seed_spread_over_time(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """A store whose rows sit at 2 h, 3 days and 20 days back.

    The spacing is the whole point: each of the rail's three periods admits a DIFFERENT
    number of rows (1, then 2, then 3), so a window that is applied and a window that is
    ignored cannot produce the same answer. A fixture with every row at one instant would
    let a completely deaf handler pass.
    """
    # Pin the READER, or this file measures whichever source the previous test left behind.
    # Scores default to the ClickHouse-backed spine (`_FACT_DEFAULTS`), so without this the
    # assertions below pass or fail depending on test order and on whether a container is up —
    # and a verdict that cannot name the thing it judged is not a verdict (ADR 0027). The
    # spine reader's own lower bound is asserted separately, in SQL, further down.
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
        "\n".join(
            json.dumps(r)
            for r in (
                _score(20, 0.10),
                _score(3, 0.50),
                _score(0.08, 0.90),
                # A grounding score on each of the SAME conversations: the metric-pairs
                # scatter only makes a point when a conversation carries both metrics, so
                # without these rows its window test would compare 0 against 0 and prove
                # nothing. The SLO/trend rows above read faithfulness only — untouched.
                _score(20, 0.20, metric="grounding"),
                _score(3, 0.60, metric="grounding"),
                _score(0.08, 0.80, metric="grounding"),
            )
        )
        + "\n",
        encoding="utf-8",
    )
    bundles_path.write_text(
        "\n".join(
            json.dumps(_bundle(days, bid))
            for days, bid in ((20, "b-old"), (3, "b-mid"), (0.08, "b-new"))
        )
        + "\n",
        encoding="utf-8",
    )
    yield
    set_reader(None)
    reset_snapshot_cache()


# Routes whose sample carries a per-row timestamp, with the field that must move when the
# window narrows. Each is read TWICE and required to differ — the measurement, not a signature.
_WINDOWED_ROUTES: tuple[tuple[str, Any, str], ...] = (
    ("slo", obs.observability_slo, "n"),
    ("scores", obs.observability_scores, "scores"),
    ("trend", obs.observability_trend, "n"),
    ("toxicity", obs.observability_toxicity, "n_turns"),
    ("pii_leak", obs.observability_pii_leak, "n_turns"),
    ("cost", obs.observability_cost, "n_turns"),
    ("routing", obs.observability_routing, "n"),
    ("intent", obs.observability_intent, "n"),
    # The scatter was the page's ONE unwindowed read: it sat under the rail with a
    # hardcoded "(7 d)" title while reading all history (found on the served page,
    # 2026-08-25 — an empty week showed a gap on the evolution chart next to a scatter
    # full of last month's points).
    ("metric_pairs", obs.observability_metric_pairs, "n"),
)


def _size(value: object) -> int:
    """The row count a payload field stands for, whether it is a tally or the rows."""
    if isinstance(value, list):
        return len(value)
    if isinstance(value, int):
        return value
    msg = f"unsized field: {value!r}"
    raise AssertionError(msg)


@pytest.mark.asyncio
@pytest.mark.parametrize(("name", "route", "field"), _WINDOWED_ROUTES, ids=lambda v: str(v)[:24])
async def test_each_windowed_route_answers_differently_per_period(
    name: str, route: Any, field: str
) -> None:
    """24 h and 30 d must not be the same number. This is the defect, stated as a test."""
    day = await call_route(route, days="1")
    month = await call_route(route, days="30")
    assert _size(day[field]) < _size(month[field]), (
        f"{name}: 24h and 30d both report {_size(day[field])} over a store holding rows at "
        f"2h, 3d and 20d — the window is being dropped somewhere between the query param and "
        f"the sample"
    )


@pytest.mark.asyncio
async def test_the_window_admits_exactly_the_rows_inside_it() -> None:
    """Not merely "different" — the RIGHT rows. A wrong-but-varying filter would pass above."""
    assert _size((await call_route(obs.observability_slo, days="1"))["n"]) == 1
    assert _size((await call_route(obs.observability_slo, days="7"))["n"]) == 2
    assert _size((await call_route(obs.observability_slo, days="30"))["n"]) == 3
    # No period at all is all history — the behaviour every caller had before the rail
    # could reach the data, and the one a caller that sends nothing must keep.
    assert _size((await call_route(obs.observability_slo))["n"]) == 3


@pytest.mark.asyncio
async def test_metric_pairs_names_the_window_it_applied() -> None:
    """The scatter's payload states its own window — null only when nothing was applied.

    Reading ``window.period_days`` before believing a figure is this cockpit's rule
    (instrumentation trap no. 2); a payload that stays silent about its window is how the
    unwindowed scatter read as a 7-day one for a month.
    """
    week = await call_route(obs.observability_metric_pairs, days="7")
    assert week["window"] == {"period_days": 7}
    assert _size(week["n"]) == 2
    bare = await call_route(obs.observability_metric_pairs)
    assert bare["window"] == {"period_days": None}
    assert _size(bare["n"]) == 3


def _fanout_slo_n(bulk: Any, agent: str) -> int:
    """One agent's SLO sample size out of a fleet-snapshot payload (or a batch half)."""
    entries = {e["agent_id"]: e["snapshot"] for e in bulk["agents"]}
    return int(entries[agent]["signals"]["slo"]["data"]["n"])


@pytest.mark.asyncio
async def test_the_per_agent_fanout_answers_differently_per_period() -> None:
    """The « Vue par agent » rows were the cockpit's LAST unwindowed read (found 2026-08-26).

    The card's fleet total obeyed the rail while the per-agent rows above it read all
    history — two clocks in one table, invisible because neither number errs. Same
    assertion as every route above: two windows must be two answers, measured on the
    payload; and the payload names the window it applied, ``None`` only when none was.
    """
    day = await call_route(obs.observability_fleet_snapshot, signals="slo", days="1")
    month = await call_route(obs.observability_fleet_snapshot, signals="slo", days="30")
    assert _fanout_slo_n(day, "support-client") == 1
    assert _fanout_slo_n(month, "support-client") == 3
    assert day["window"] == {"period_days": 1}
    # The rail's own vocabulary reaches the data too — the front forwards its period KEY.
    week = await call_route(obs.observability_fleet_snapshot, signals="slo", days="d7")
    assert _fanout_slo_n(week, "support-client") == 2
    bare = await call_route(obs.observability_fleet_snapshot, signals="slo")
    assert bare["window"] == {"period_days": None}
    assert _fanout_slo_n(bare, "support-client") == 3


@pytest.mark.asyncio
async def test_the_batch_forwards_the_window_to_both_snapshot_halves() -> None:
    """The coalesced read the breakdown actually makes — the defect measured on its own route.

    ``/observability/fleet-batch`` forwarded ``period`` to its fleet half only; both snapshot
    halves were computed live over all history, so the operator's period selector changed the
    total under the table and nothing in it. Two windows, two answers, on BOTH halves.
    """
    day: Any = await observability_fleet_batch(
        lang="fr", period="h24", signals="slo", org_signals="slo"
    )
    month: Any = await observability_fleet_batch(
        lang="fr", period="d30", signals="slo", org_signals="slo"
    )
    assert _fanout_slo_n(day["fleet_snapshot"], "support-client") == 1
    assert _fanout_slo_n(month["fleet_snapshot"], "support-client") == 3
    assert day["snapshot"]["signals"]["slo"]["data"]["n"] == 1
    assert month["snapshot"]["signals"]["slo"]["data"]["n"] == 3


@pytest.mark.asyncio
async def test_a_handler_that_ignores_the_window_is_caught() -> None:
    """The teeth: show the assertion a deaf handler and require it to fail.

    Without this, every assertion above could be passing for a reason that has nothing to do
    with windowing — and this file has already been the place where that mattered, because
    the defect it exists for was three independent silent drops in a row.
    """

    async def deaf(days: str | None = None, **_: object) -> dict[str, object]:
        _ = days  # accepted, declared, and thrown away — exactly the shape being hunted
        return {"n": 3}

    with pytest.raises(AssertionError):
        day = await call_route(deaf, days="1")
        month = await call_route(deaf, days="30")
        assert _size(day["n"]) < _size(month["n"])


@pytest.mark.asyncio
async def test_the_batched_snapshot_windows_exactly_as_the_routes_do() -> None:
    """A snapshot slice and its route must agree about the week they are showing.

    They are separate code paths over the same stores, and the snapshot is what the overview
    actually renders — a window that reached only the standalone routes would fix nothing on
    the page the operator is looking at.
    """
    for days, expected in ((1, 1), (7, 2), (30, 3)):
        reset_snapshot_cache()
        snap = await compute_snapshot(Scope(period_days=days), ("slo",))
        assert snap["signals"]["slo"]["data"]["n"] == expected, f"snapshot slo at {days}d"


@pytest.mark.asyncio
async def test_the_scope_cache_does_not_serve_one_period_for_another() -> None:
    """Two periods, one cache key, one wrong answer — the failure this nearly shipped as.

    ``Scope.key()`` feeds both the snapshot read-through cache and the per-snapshot shared-read
    memo. Omitting the period there produces a page where the selector *is* wired end to end
    and still shows one number, which is indistinguishable on screen from the original defect.
    """
    assert Scope(period_days=1).key() != Scope(period_days=30).key()
    assert Scope(period_days=None).key() != Scope(period_days=7).key()


def test_an_unreadable_period_is_all_history_and_never_a_guess() -> None:
    """Refusing to guess: a window nobody can read must not become one nobody chose."""
    assert parse_period_days(None) is None
    assert parse_period_days("") is None
    assert parse_period_days("nonsense") is None
    assert parse_period_days("0") is None
    assert parse_period_days("-5") is None
    assert parse_period_days("7") == 7
    # The rail's own vocabulary is accepted directly, so a caller holding a period key does
    # not have to convert it and risk a second, divergent mapping.
    assert parse_period_days("d7") == 7
    assert parse_period_days("d14") == 14
    assert parse_period_days("h24") == 1


def test_the_front_and_the_backend_agree_on_what_a_period_means() -> None:
    """One vocabulary. A period added to the selector must mean something to the backend.

    Read off the front's own sources rather than restated here: a constant copied into this
    test would agree with itself forever while the two real lists drifted apart.
    """
    declared = set(re.findall(r'key:\s*"([a-z0-9]+)"', _FRONT_RAIL.read_text(encoding="utf-8")))
    assert declared, "no period keys found in temporal-rail.tsx — the scan went blind"
    assert declared == set(PERIOD_DAYS), (
        f"the rail offers {sorted(declared)} but the backend knows {sorted(PERIOD_DAYS)}; "
        "a period the backend cannot read is dropped to all-history in silence"
    )
    default = re.search(r'period:\s*"([a-z0-9]+)"', _FRONT_STORE.read_text(encoding="utf-8"))
    assert default is not None, "no default period in window-store.ts"
    assert default.group(1) in PERIOD_DAYS


def test_every_time_capable_signal_can_be_windowed_and_the_rest_say_so() -> None:
    """The period rides TIME, so "windowable" is not a second list somebody must maintain.

    Both temporal bounds are read off the same field of the same rows. A signal that declares
    TIME can answer either; one that does not gets the period dropped by ``narrow_to`` and
    reports it ignored, which is what lets the UI say "not windowed" without anyone keeping a
    register of which numbers those are.
    """
    time_capable = {c.id for c in CAPABILITIES.values() if Dimension.TIME in c.dimensions}
    assert time_capable, "no signal declares TIME — the capability scan went blind"
    for cap in CAPABILITIES.values():
        narrowed = Scope(at="2026-01-01T00:00:00Z", period_days=7).narrow_to(cap.dimensions)
        if Dimension.TIME in cap.dimensions:
            assert narrowed.period_days == 7, f"{cap.id} declares TIME but drops the period"
            assert narrowed.at is not None
        else:
            assert narrowed.period_days is None, (
                f"{cap.id} does not declare TIME, so a period reaching its read would be "
                "applied to a sample that cannot carry one"
            )
            assert narrowed.at is None


def test_a_windowed_read_reports_time_as_a_filter_it_honoured() -> None:
    """The badge the UI draws comes from here; a period alone must light it, not just an instant."""
    assert Dimension.TIME in Scope(period_days=7).filters
    assert Dimension.TIME in Scope(at="2026-01-01T00:00:00Z").filters
    assert Dimension.TIME not in Scope().filters


def test_a_row_with_no_readable_timestamp_is_kept_not_deleted() -> None:
    """Fail-open, same posture as the as-of bound — a bad stamp must not shrink a count."""
    scope = Scope(period_days=1)
    assert scope.within(None) is True
    assert scope.within("not-a-date") is True
    assert scope.within(_at(0.01)) is True
    assert scope.within(_at(9)) is False
