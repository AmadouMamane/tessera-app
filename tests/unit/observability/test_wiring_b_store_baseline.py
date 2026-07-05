"""Phase 2 — Table B: real-store baseline wiring proof (8 signals).

Trivial aggregates over the durable score store (``eval/scores._RECENT`` /
ClickHouse) or the ledger. Their job here is dual: prove each signal WIRED
*and* validate the harness itself — if a store-row perturbation does not move
one of these aggregates, the harness (not the signal) is suspect.

Every ``compute`` mirrors the actual route assembly in
``src/tessera/api/routes/observability.py``: ``_scores_for``/``read_scores``
resolve to ``CurrentStoresReader.scores()``, which calls
``eval.scores.recent_scores(agent_id)`` for the live (``at=None``) case — a
thin, unfiltered read over the durable row list. Each probe below constructs
that row list directly (the seam) and applies the same filter/extraction the
route performs before calling the pure aggregator, per
``docs/design/signal-wiring-map.md`` Table B.

**Duplication invariant** (map, "applies to all rate/mean rows in A & B"):
duplicating the whole input series leaves a rate/mean observable unchanged.
Applied here to the four genuine rate/mean rows (#15 good_rate, #66
low_score_rate, #21 single_turn_rate, score-series mean, #29 validity_rate).
Excluded, with reasons: ``#150`` slope (a least-squares coefficient over
*index* — duplication reshapes the series into a sawtooth and does NOT
preserve slope, so asserting invariance would be asserting something false)
and regression-risk's ``risk_score`` (a weighted composite of three
components, not a plain ratio/mean — no clean duplication invariant exists).
``online-scores`` observes the *last* row's score (a point read, not a
rate/mean), so duplication invariance does not apply either.

#21 needs a structural note: duplicating *session-grouped* rows verbatim
(same ``conversation_id``) would corrupt single-turn sessions into
two-turn ones and falsely appear to break the invariant. The valid
duplication is a second cohort with **fresh** conversation ids (same
per-session shape) — that's what ``_sessions_dup_perturb`` does.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from tessera.observability.eval import scores as scores_mod
from tessera.observability.eval.judge import JudgeVerdict
from tessera.observability.eval.releases import ReleaseStatus
from tessera.observability.eval.risk import RegressionRisk, compute_regression_risk
from tessera.observability.eval.series import ScoreSeries, compute_score_series
from tessera.observability.funnel import FunnelReport, aggregate_funnel
from tessera.observability.sessions import SessionReport, aggregate_sessions
from tessera.observability.slo import SLOReport, compute_slo
from tessera.observability.tool_validity import ToolValidityReport, compute_tool_validity
from tessera.observability.trends import TrendReport, analyze_trend
from tests.support.wiring import Probe, assert_invariant_ok, assert_wired

Row = dict[str, object]

_BASELINE_STATUS = ReleaseStatus(current=None, n_regressions=0, models_compared=0)

# --------------------------------------------------------------------------- #
# online-scores — eval/scores.py:recent_scores. No `rows` argument exists: the
# route chain (_scores_for -> read_scores -> CurrentStoresReader.scores ->
# recent_scores(agent_id)) reads the module-global `_RECENT` deque directly,
# and the map's own stated store perturbation is calling the REAL write API —
# `emit_score(faithfulness=0.42)` — not a hand-rolled dict splice. So `compute`
# resets the store to empty, then REPLAYS `emit_score` for each ``(metric,
# score)`` spec in ``source`` (the production write leg: logging + the
# EVAL_SCORE histogram + the hermetic ClickHouse insert + `_RECENT.append`),
# before reading back through the production read leg, `recent_scores()`. This
# proves the write leg and the read leg together, not the read leg in
# isolation. Determinism holds because replaying the same specs always yields
# the same `.score` values; only `scored_at` (wall-clock, never observed here)
# differs between the two baseline calls.
# --------------------------------------------------------------------------- #

_Spec = tuple[str, float]  # (metric, score)


def _online_compute(specs: list[_Spec]) -> object:
    scores_mod._WARMED = True
    scores_mod._RECENT.clear()
    for metric, score in specs:
        scores_mod.emit_score(
            JudgeVerdict(
                metric=metric, score=score, rationale="wiring-probe", judge_model="probe-judge"
            ),
            language="fr",
        )
    return scores_mod.recent_scores()


def _obs_last_score(payload: object) -> float:
    rows = cast("list[Row]", payload)
    return float(cast("float", rows[-1]["score"])) if rows else 0.0


_ONLINE_BASE: list[_Spec] = [("faithfulness", 0.10)]


def _online_perturb(specs: list[_Spec]) -> list[_Spec]:
    return [*specs, ("faithfulness", 0.42)]  # the map's literal perturbation


_online_probe: Probe[list[_Spec]] = Probe(
    key="online-scores",
    compute=_online_compute,
    observe=_obs_last_score,
    base_source=_ONLINE_BASE,
    perturb=_online_perturb,
    relation="up",
    seam="store",
    declared_class="real-store",
)

# --------------------------------------------------------------------------- #
# #15 quality-slo-error-budget — slo.py:compute_slo. Route: _scores_for(at=None,
# agent) -> [float(s["score"]) for s in rows if metric==faithfulness] ->
# compute_slo(). Already proven WIRED in Phase 1 (test_signal_wiring.py); the
# duplication invariant on good_rate is new here.
# --------------------------------------------------------------------------- #


def _slo_extract(rows: list[Row]) -> list[float]:
    return [float(cast("float", r["score"])) for r in rows if r.get("metric") == "faithfulness"]


def _slo_compute(rows: list[Row]) -> object:
    return compute_slo(_slo_extract(rows))


def _obs_good_rate(payload: object) -> float:
    return cast("SLOReport", payload).good_rate


_SLO_BASE: list[Row] = [{"metric": "faithfulness", "score": 0.95} for _ in range(8)]


def _slo_perturb(rows: list[Row]) -> list[Row]:
    return [*rows, *({"metric": "faithfulness", "score": 0.50} for _ in range(4))]


def _slo_duplicate(rows: list[Row]) -> list[Row]:
    return [*rows, *rows]


_slo_probe: Probe[list[Row]] = Probe(
    key="quality-slo-error-budget#15",
    compute=_slo_compute,
    observe=_obs_good_rate,
    base_source=_SLO_BASE,
    perturb=_slo_perturb,
    relation="down",
    seam="store",
    declared_class="real-store",
)

_slo_dup_probe: Probe[list[Row]] = Probe(
    key="quality-slo-error-budget#15-duplication",
    compute=_slo_compute,
    observe=_obs_good_rate,
    base_source=_SLO_BASE,
    perturb=_slo_duplicate,
    relation="invariant",
    seam="store",
    declared_class="real-store",
)

# --------------------------------------------------------------------------- #
# #150 long-horizon-trend — trends.py:analyze_trend. Route: _scores_for ->
# [(scored_at, score) for s in rows if metric==faithfulness] -> analyze_trend().
# No duplication invariant: slope is a least-squares coefficient over series
# *index*, not a rate/mean; duplicating the series reshapes it into a sawtooth
# and does not preserve slope (excluded per the map's own "rate/mean" scoping).
# --------------------------------------------------------------------------- #


def _trend_extract(rows: list[Row]) -> list[tuple[str, float]]:
    return [
        (cast("str", r["scored_at"]), float(cast("float", r["score"])))
        for r in rows
        if r.get("metric") == "faithfulness"
    ]


def _trend_compute(rows: list[Row]) -> object:
    return analyze_trend(_trend_extract(rows))


def _obs_slope(payload: object) -> float:
    return cast("TrendReport", payload).slope


_TREND_BASE: list[Row] = [
    {"metric": "faithfulness", "score": 0.90, "scored_at": f"2026-01-0{i + 1}T00:00:00+00:00"}
    for i in range(5)
]


def _trend_perturb(rows: list[Row]) -> list[Row]:
    tail = [
        {"metric": "faithfulness", "score": 0.30, "scored_at": f"2026-01-1{i}T00:00:00+00:00"}
        for i in range(3)
    ]
    return [*rows, *tail]


_trend_probe: Probe[list[Row]] = Probe(
    key="long-horizon-trend#150",
    compute=_trend_compute,
    observe=_obs_slope,
    base_source=_TREND_BASE,
    perturb=_trend_perturb,
    relation="down",
    seam="store",
    declared_class="real-store",
)

# --------------------------------------------------------------------------- #
# #66 funnel-per-language — funnel.py:aggregate_funnel. Route: _scores_for ->
# (language, conversation_id, score) triples -> aggregate_funnel(). Duplication
# invariant targets low_score_rate specifically (the row's declared
# observable) — a flat ratio over one language's turns, unaffected by
# conversation-id collisions, so verbatim duplication is valid here (unlike
# #21's single_turn_rate).
# --------------------------------------------------------------------------- #


def _funnel_extract(rows: list[Row]) -> list[tuple[str, str | None, float]]:
    out: list[tuple[str, str | None, float]] = []
    for r in rows:
        lang = cast("str", r["language"])
        conv = cast("str | None", r.get("conversation_id"))
        score = float(cast("float", r["score"]))
        out.append((lang, conv, score))
    return out


def _funnel_compute(rows: list[Row]) -> object:
    return aggregate_funnel(_funnel_extract(rows))


def _obs_fr_low_score_rate(payload: object) -> float:
    report = cast("FunnelReport", payload)
    fr = next(lang for lang in report.languages if lang.language == "fr")
    return fr.low_score_rate


_FUNNEL_BASE: list[Row] = [
    {"language": "fr", "conversation_id": f"c{i}", "score": s}
    for i, s in enumerate([0.9, 0.9, 0.3, 0.9, 0.2])  # 2 low / 5 = 0.4
]


def _funnel_perturb(rows: list[Row]) -> list[Row]:
    return [*rows, {"language": "fr", "conversation_id": "c-new", "score": 0.1}]  # 3/6 = 0.5


def _funnel_duplicate(rows: list[Row]) -> list[Row]:
    return [*rows, *rows]  # low_score_rate is a flat ratio -> verbatim duplication is valid


_funnel_probe: Probe[list[Row]] = Probe(
    key="funnel-per-language#66",
    compute=_funnel_compute,
    observe=_obs_fr_low_score_rate,
    base_source=_FUNNEL_BASE,
    perturb=_funnel_perturb,
    relation="up",
    seam="store",
    declared_class="real-store",
)

_funnel_dup_probe: Probe[list[Row]] = Probe(
    key="funnel-per-language#66-duplication",
    compute=_funnel_compute,
    observe=_obs_fr_low_score_rate,
    base_source=_FUNNEL_BASE,
    perturb=_funnel_duplicate,
    relation="invariant",
    seam="store",
    declared_class="real-store",
)

# --------------------------------------------------------------------------- #
# #21 session-goal-completion — sessions.py:aggregate_sessions. Route:
# read_scores -> (conversation_id, score) pairs -> aggregate_sessions().
# Duplication invariant needs a FRESH conversation-id cohort (see module
# docstring) — verbatim duplication would corrupt single-turn sessions.
# --------------------------------------------------------------------------- #

_Turn = tuple[str | None, float]


def _sessions_extract(rows: list[Row]) -> list[_Turn]:
    return [
        (cast("str | None", r.get("conversation_id")), float(cast("float", r["score"])))
        for r in rows
    ]


def _sessions_compute(rows: list[Row]) -> object:
    return aggregate_sessions(_sessions_extract(rows))


def _obs_single_turn_rate(payload: object) -> float:
    return cast("SessionReport", payload).single_turn_rate


_SESSIONS_BASE: list[Row] = [
    {"conversation_id": "c1", "score": 0.9},  # single-turn session
    {"conversation_id": "c2", "score": 0.9},
    {"conversation_id": "c2", "score": 0.8},  # two-turn session
]  # single_turn_rate = 1/2 = 0.5


def _sessions_perturb(rows: list[Row]) -> list[Row]:
    return [*rows, {"conversation_id": "c1", "score": 0.7}]  # c1 becomes two-turn -> 0/2 = 0.0


def _sessions_dup_perturb(rows: list[Row]) -> list[Row]:
    dup = [{**r, "conversation_id": f"{r['conversation_id']}-dup"} for r in rows]
    return [*rows, *dup]  # fresh ids preserve each session's turn-count shape


_sessions_probe: Probe[list[Row]] = Probe(
    key="session-goal-completion#21",
    compute=_sessions_compute,
    observe=_obs_single_turn_rate,
    base_source=_SESSIONS_BASE,
    perturb=_sessions_perturb,
    relation="down",
    seam="store",
    declared_class="real-store",
)

_sessions_dup_probe: Probe[list[Row]] = Probe(
    key="session-goal-completion#21-duplication",
    compute=_sessions_compute,
    observe=_obs_single_turn_rate,
    base_source=_SESSIONS_BASE,
    perturb=_sessions_dup_perturb,
    relation="invariant",
    seam="store",
    declared_class="real-store",
)

# --------------------------------------------------------------------------- #
# score-series — eval/series.py:compute_score_series. Route:
# read_scores(at, agent, full=True) -> compute_score_series(rows, metric, end,
# days, buckets). A fixed `end` keeps the window (and hence determinism) pinned.
# --------------------------------------------------------------------------- #

_SERIES_END = datetime(2026, 6, 12, 12, 0, tzinfo=UTC)


def _series_compute(rows: list[Row]) -> object:
    return compute_score_series(rows, metric="faithfulness", end=_SERIES_END, days=7, n_buckets=7)


def _obs_series_mean(payload: object) -> float:
    mean = cast("ScoreSeries", payload).mean
    return mean if mean is not None else 0.0


_SERIES_BASE: list[Row] = [
    {"scored_at": "2026-06-10T00:00:00+00:00", "metric": "faithfulness", "score": 0.9},
    {"scored_at": "2026-06-11T00:00:00+00:00", "metric": "faithfulness", "score": 0.9},
]


def _series_perturb(rows: list[Row]) -> list[Row]:
    return [
        *rows,
        {"scored_at": "2026-06-12T00:00:00+00:00", "metric": "faithfulness", "score": 0.0},
    ]


def _series_duplicate(rows: list[Row]) -> list[Row]:
    return [*rows, *rows]


_series_probe: Probe[list[Row]] = Probe(
    key="score-series",
    compute=_series_compute,
    observe=_obs_series_mean,
    base_source=_SERIES_BASE,
    perturb=_series_perturb,
    relation="down",
    seam="store",
    declared_class="real-store",
)

_series_dup_probe: Probe[list[Row]] = Probe(
    key="score-series-duplication",
    compute=_series_compute,
    observe=_obs_series_mean,
    base_source=_SERIES_BASE,
    perturb=_series_duplicate,
    relation="invariant",
    seam="store",
    declared_class="real-store",
)

# --------------------------------------------------------------------------- #
# regression-risk — eval/risk.py:compute_regression_risk. Route: read_scores(at,
# full=True) + release_status() -> compute_regression_risk(rows, status, ...).
# `status` held fixed at a 0/0 baseline to isolate the score-trend seam (the
# row's declared perturbation) from the release-status seam. No duplication
# invariant: risk_score is a weighted composite of three components, not a
# plain ratio/mean.
# --------------------------------------------------------------------------- #

_RISK_END = datetime(2026, 6, 12, 12, 0, tzinfo=UTC)


def _risk_compute(rows: list[Row]) -> object:
    return compute_regression_risk(rows, _BASELINE_STATUS, end=_RISK_END, days=7, n_buckets=7)


def _obs_risk_score(payload: object) -> float:
    risk = cast("RegressionRisk", payload).risk_score
    return risk if risk is not None else 0.0


_RISK_BASE: list[Row] = [
    {"scored_at": "2026-06-05T00:00:00+00:00", "metric": "faithfulness", "score": 0.95},
    {"scored_at": "2026-06-06T00:00:00+00:00", "metric": "faithfulness", "score": 0.95},
]


def _risk_perturb(rows: list[Row]) -> list[Row]:
    low = [
        {"scored_at": f"2026-06-12T0{i}:00:00+00:00", "metric": "faithfulness", "score": 0.1}
        for i in range(3)
    ]
    return [*rows, *low]


_risk_probe: Probe[list[Row]] = Probe(
    key="regression-risk",
    compute=_risk_compute,
    observe=_obs_risk_score,
    base_source=_RISK_BASE,
    perturb=_risk_perturb,
    relation="up",
    seam="store",
    declared_class="real-store",
)

# --------------------------------------------------------------------------- #
# #29 tool-arg-validation — tool_validity.py:compute_tool_validity. Ledger-
# backed (temp file), matching the existing unit test's fixture style exactly.
# --------------------------------------------------------------------------- #


def _write_ledger(path: Path, entries: list[Row]) -> None:
    import json

    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")


def _validity_compute(entries: list[Row]) -> object:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        log = Path(tmp) / "audit.log"
        _write_ledger(log, entries)
        return compute_tool_validity(log)


def _obs_validity_rate(payload: object) -> float:
    return cast("ToolValidityReport", payload).validity_rate


_VALIDITY_BASE: list[Row] = [
    {
        "type": "tessera.guard.audit",
        "target": "account_balance",
        "outcome": "allowed",
        "decisions": [],
    },
    {
        "type": "tessera.guard.audit",
        "target": "account_balance",
        "outcome": "allowed",
        "decisions": [],
    },
]  # validity_rate = 1.0


def _validity_perturb(entries: list[Row]) -> list[Row]:
    denied: Row = {
        "type": "tessera.guard.audit",
        "target": "loan_simulate",
        "outcome": "denied",
        "decisions": [{"policy_rule": "tool.loan_simulate.argument.amount"}],
    }
    return [*entries, denied]  # validity_rate 1.0 -> 2/3


def _validity_duplicate(entries: list[Row]) -> list[Row]:
    return [*entries, *entries]


_validity_probe: Probe[list[Row]] = Probe(
    key="tool-arg-validation#29",
    compute=_validity_compute,
    observe=_obs_validity_rate,
    base_source=_VALIDITY_BASE,
    perturb=_validity_perturb,
    relation="down",
    seam="store",
    declared_class="real-store",
)

_validity_dup_probe: Probe[list[Row]] = Probe(
    key="tool-arg-validation#29-duplication",
    compute=_validity_compute,
    observe=_obs_validity_rate,
    base_source=_VALIDITY_BASE,
    perturb=_validity_duplicate,
    relation="invariant",
    seam="store",
    declared_class="real-store",
)


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #


def test_online_scores_is_wired() -> None:
    r = assert_wired(_online_probe)
    assert r.delta > 0.0
    print(f"WIRED {r.key:40} {r.detail}")


def test_slo_error_budget_is_wired_and_duplication_invariant() -> None:
    r = assert_wired(_slo_probe)
    d = assert_invariant_ok(_slo_dup_probe)
    assert r.delta < 0.0
    print(f"WIRED {r.key:40} {r.detail}")
    print(f"INV   {d.key:40} {d.detail}")


def test_long_horizon_trend_is_wired() -> None:
    r = assert_wired(_trend_probe)
    assert r.delta < 0.0
    print(f"WIRED {r.key:40} {r.detail}")
    print("      (no duplication invariant: slope is a least-squares index coefficient,")
    print("       not a rate/mean)")


def test_funnel_per_language_is_wired_and_duplication_invariant() -> None:
    r = assert_wired(_funnel_probe)
    d = assert_invariant_ok(_funnel_dup_probe)
    assert r.delta > 0.0
    print(f"WIRED {r.key:40} {r.detail}")
    print(f"INV   {d.key:40} {d.detail}")


def test_session_goal_completion_is_wired_and_duplication_invariant() -> None:
    r = assert_wired(_sessions_probe)
    d = assert_invariant_ok(_sessions_dup_probe)
    assert r.delta < 0.0
    print(f"WIRED {r.key:40} {r.detail}")
    print(f"INV   {d.key:40} {d.detail}")


def test_score_series_is_wired_and_duplication_invariant() -> None:
    r = assert_wired(_series_probe)
    d = assert_invariant_ok(_series_dup_probe)
    assert r.delta < 0.0
    print(f"WIRED {r.key:40} {r.detail}")
    print(f"INV   {d.key:40} {d.detail}")


def test_regression_risk_is_wired() -> None:
    r = assert_wired(_risk_probe)
    assert r.delta > 0.0
    print(f"WIRED {r.key:40} {r.detail}")
    print("      (no duplication invariant: risk_score is a weighted 3-component composite,")
    print("       not a rate/mean)")


def test_tool_arg_validation_is_wired_and_duplication_invariant() -> None:
    r = assert_wired(_validity_probe)
    d = assert_invariant_ok(_validity_dup_probe)
    assert r.delta < 0.0
    print(f"WIRED {r.key:40} {r.detail}")
    print(f"INV   {d.key:40} {d.detail}")
