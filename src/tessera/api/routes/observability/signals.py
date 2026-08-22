"""Observability routes — signals surface."""

from __future__ import annotations

import asyncio
import sys
from collections import Counter
from dataclasses import asdict

from fastapi import APIRouter, Depends

from tessera.agent.registry import QualityRegime, list_agents
from tessera.api.routes.observability._common import (
    _agent_or_none,
    _bundles_for,
    _data_availability_start,
    _read_audit_entries,
    _scores_for,
    _workflow_runs_from_rows,
)
from tessera.api.security import require_bearer
from tessera.observability import (
    anomalies as anomalies_mod,
    business_events as business_events_mod,
    conformance as conformance_mod,
    control_signals as control_signals_mod,
    cost_anomaly as cost_anomaly_mod,
    language_routing as language_routing_mod,
    obs_cost as obs_cost_mod,
    quality_nets as quality_nets_mod,
    reliability as reliability_mod,
    replay as replay_mod,
    routing_intent as routing_intent_mod,
    signal_catalogue as signal_catalogue_mod,
    signal_coverage as signal_coverage_mod,
    slo as slo_mod,
    trends as trends_mod,
    whatchanged as whatchanged_mod,
)
from tessera.observability.agentspec_projection import declares_telemetry, quality_regime_descriptor
from tessera.observability.business_capabilities import business_signal_rows
from tessera.observability.control_series import compute_control_series
from tessera.observability.fleet import registered_agent_ids
from tessera.observability.spine.adapters import read_scores
from tessera.observability.spine.availability import dimension_availability
from tessera.observability.spine.scope import Scope, parse_period_days, window_days
from tessera.observability.spine.snapshot import compute_snapshot

router = APIRouter()

_obs_cost_cache: dict[str, object] | None = None


@router.get("/observability/scores")
def observability_scores(
    at: str | None = None, agent: str = "all", days: str | None = None
) -> dict[str, object]:
    """Online-eval scores — live (newest last), or as of instant ``at`` (ISO).

    ``agent`` scopes the scores to one agent's turns (``all`` = org view); ``days`` scopes
    them to the cockpit's selected period.
    """
    window = parse_period_days(days)
    return {
        "scores": _scores_for(at, _agent_or_none(agent), window),
        "as_of": at,
        "agent": agent,
        "days": window,
    }


@router.get("/observability/snapshot", dependencies=[Depends(require_bearer)])
async def observability_snapshot(
    at: str | None = None,
    agent: str = "all",
    language: str | None = None,
    model: str | None = None,
    signals: str | None = None,
    days: str | None = None,
) -> dict[str, object]:
    """Batched, cached snapshot of every scope-varying signal in one pass (ADR 0015).

    Collapses the ~24-37 per-page fetches into a single round-trip: all hot-path signals
    for one :class:`Scope`, computed over shared store reads and served through a
    read-through cache with single-flight. Each signal carries a ``report`` of which
    dimensions it honoured / ignored, so the UI badges org-wide / synthetic / unavailable
    from data — the filter-shown-but-ignored state is unrepresentable. ``?signals=`` selects
    a comma-separated subset. ``?days=`` is the window LENGTH (a number of days, or a rail
    period key), the lower bound to ``at``'s upper one; a signal without the TIME dimension
    has it dropped and reports it ignored. Scope is a *filter*, never a privilege
    escalation: RBAC is the same ``require_bearer`` posture as the other read surfaces
    (no-op without a token).
    """
    scope = Scope.from_query(
        {"at": at, "agent": agent, "language": language, "model": model, "days": days}
    )
    ids = tuple(part.strip() for part in signals.split(",") if part.strip()) if signals else None
    return await compute_snapshot(scope, ids)


@router.get("/observability/fleet-snapshot", dependencies=[Depends(require_bearer)])
async def observability_fleet_snapshot(
    at: str | None = None,
    language: str | None = None,
    model: str | None = None,
    signals: str | None = None,
    days: str | None = None,
) -> dict[str, object]:
    """Every fleet agent's snapshot in ONE round-trip — the per-agent fan-out, collapsed.

    The GOUVERNER breakdown pages asked ``/observability/snapshot?agent=<id>`` once per fleet
    agent — N tunnel round-trips for the operator front, whose intermittent tail is the free
    tunnel serialising them. This returns them all in a single response: for each registered
    agent it calls the SAME :func:`compute_snapshot` builder the single-agent route calls, so
    every per-agent slice is byte-identical to what that route returns — the collapse buys
    round-trips, never trust (``tests/unit/test_fleet_snapshot_parity.py`` pins it). It rides
    the same ``(scope, signal-set)`` read-through/single-flight cache, so a key already warmed
    by the single-agent route is a cache hit here.

    An agent whose compute raises is OMITTED (not zero-filled): the frontend then resolves it
    to ``undefined`` and renders that agent's honest refusal cell, exactly as a failed
    individual fetch does today. ``?signals=`` selects the same comma-separated subset.
    """
    ids = tuple(part.strip() for part in signals.split(",") if part.strip()) if signals else None
    agent_ids = sorted(registered_agent_ids())
    envelopes = await asyncio.gather(
        *(
            compute_snapshot(
                Scope.from_query(
                    {
                        "at": at,
                        "agent": aid,
                        "language": language,
                        "model": model,
                        "days": days,
                    }
                ),
                ids,
            )
            for aid in agent_ids
        ),
        return_exceptions=True,
    )
    agents: list[dict[str, object]] = [
        {"agent_id": aid, "snapshot": envelope}
        for aid, envelope in zip(agent_ids, envelopes, strict=True)
        if not isinstance(envelope, BaseException)
    ]
    return {"agents": agents}


@router.get("/observability/data-range")
def observability_data_range() -> dict[str, object]:
    """Earliest → latest instant for which the cockpit holds real as-of-T data.

    This bounds the time-rail "Aller à une date" calendar honestly: picking a
    window end before ``start`` would land on an empty window — no persisted signal
    exists that far back. The range is derived from the *same durable sources* the
    as-of-T reads recompute from — the full eval score log (the reader seam,
    not the bounded live ring) and the tamper-evident guard audit log — so it never
    promises data the cockpit cannot actually show. ``start`` is null when no data
    exists yet. Timestamps are ISO 8601; ``start`` is the lexicographic minimum,
    matching the timeline's ordering convention.
    """
    from datetime import UTC, datetime

    from tessera.guard.ledger_store import audit_type_min_occurred_and_count, ledger_source

    scores = read_scores(full=True)
    if ledger_source() == "postgres":
        # The guard-audit type is 94 % of the chain; ask the DB for its earliest instant and its
        # count rather than materialising every payload to take a min and a len. Byte-identical to
        # the walk below: the same lexicographic min over the same non-blank stamps, the same total.
        audit_min, n_audit = audit_type_min_occurred_and_count("tessera.guard.audit")
        stamps = [stamp for s in scores if (stamp := str(s.get("scored_at", "")))]
        if audit_min:
            stamps.append(audit_min)
        start = min(stamps) if stamps else None
        n = len(scores) + n_audit
    else:
        audit_entries = _read_audit_entries()
        start = _data_availability_start(scores, audit_entries)
        n = len(scores) + len(audit_entries)
    return {"start": start, "end": datetime.now(UTC).isoformat(), "n": n}


@router.get("/observability/availability")
def observability_availability() -> dict[str, object]:
    """Per-dimension "data available since" boundaries (ADR 0015 §Testing 2).

    Generalises ``/observability/data-range`` to every :class:`Scope` dimension. Because
    stamping is forward-only, a dimension exists in the durable stores only from the instant
    the code started stamping it; each boundary is the earliest row that actually carries
    the dimension (``None`` when it has no data yet). An as-of-T read before a dimension's
    boundary is honestly org-wide — the cockpit never pretends a dimension existed earlier.
    """
    from datetime import UTC, datetime

    return {
        "since": dimension_availability(),
        "now": datetime.now(UTC).isoformat(),
    }


@router.get("/observability/slo")
def observability_slo(
    at: str | None = None, agent: str = "all", days: str | None = None
) -> dict[str, object]:
    """Quality SLO + error-budget burn-rate over the faithfulness scores.

    Live by default; with ``?at=`` the SLO is recomputed over the durable score
    log as of instant T (as-of-T read, ADR 0011). ``agent`` scopes the SLO to one
    agent's own scored turns (``all`` = org view); an agent with no scored turns
    yet reads honestly empty (``n=0``). ``days`` scopes it to the selected period.

    ``by_language`` slices the SAME rows by the language each score row carries —
    one read, one window, three sub-populations of the one judged plane — so the
    cockpit can show where multilingual quality diverges. A language nobody spoke
    reads ``n=0``, never a rate.
    """
    # One derivation, two readers: this route and the snapshot's `slo` signal both call
    # `slo_payload`, so the parity ratchet witnesses one computation instead of two copies.
    return {
        **slo_mod.slo_payload(_scores_for(at, _agent_or_none(agent), parse_period_days(days))),
        "as_of": at,
        "agent": agent,
    }


def _judged_plane_stats(at: str | None, llm_ids: list[str]) -> dict[str, dict[str, object]]:
    """Per-agent judged counts + first/last instants, in ONE score-log read.

    ONE full-history read through the reader seam (``full=True`` — the live ring is a
    200-row cut, not history), counted by the rows' own agent_id. A judged response is one
    faithfulness verdict — the same semantics as the hero's n, over all history instead of
    its window. Rows without an agent_id (pre-tagging history) are org-only and belong to
    no agent's count. The first/last instants ride the same pass: a total without its
    recency reads as alive when it may be a fossil (ADR 0052 — silence is a hole, not
    uptime), so the plane carries WHEN its ruler last spoke, and since when. Per-language
    counts ride it too — the three catalogue languages, always present so a language
    nobody spoke reads 0 instead of silently missing.
    """
    counts: dict[str, int] = dict.fromkeys(llm_ids, 0)
    since: dict[str, str | None] = dict.fromkeys(llm_ids)
    last: dict[str, str | None] = dict.fromkeys(llm_ids)
    languages: dict[str, dict[str, int]] = {aid: {"fr": 0, "de": 0, "en": 0} for aid in llm_ids}
    if llm_ids:
        for score in read_scores(at, None, full=True):
            if score.get("metric") != "faithfulness":
                continue
            scored_agent = score.get("agent_id")
            if not isinstance(scored_agent, str) or scored_agent not in counts:
                continue
            counts[scored_agent] += 1
            language = score.get("language")
            if isinstance(language, str) and language in languages[scored_agent]:
                languages[scored_agent][language] += 1
            scored_at = score.get("scored_at")
            if isinstance(scored_at, str) and scored_at:
                # ISO-8601 strings from one writer order lexicographically — the same
                # comparison the run builder already leans on.
                current_since = since[scored_agent]
                if current_since is None or scored_at < current_since:
                    since[scored_agent] = scored_at
                current_last = last[scored_agent]
                if current_last is None or scored_at > current_last:
                    last[scored_agent] = scored_at
    return {
        aid: {
            "responses_total": counts[aid],
            "since": since[aid],
            "last_scored_at": last[aid],
            "languages": languages[aid],
        }
        for aid in llm_ids
    }


@router.get("/observability/quality-regimes")
def observability_quality_regimes(at: str | None = None) -> dict[str, object]:
    """The declared quality regime of every registry agent (ADR 0017 §Amendment 4).

    Reads each manifest's ``quality_regime`` through the one projector
    (:func:`quality_regime_descriptor`) — a declaration, never an inference from wiring.
    For a ``business_scored`` agent it joins the counts the Métier view already computes,
    through the same builders, so the band and the Métier tab can never disagree (one
    witness, ADR 0026). For an ``llm_judged`` agent it carries the COUNT of responses the
    judge has rated (its faithfulness verdicts over the durable score log) — a count in
    the judged plane's own unit, never a rate: the two regimes' populations stay in
    separate fields with no combined figure anywhere, two rulers never share a
    denominator.

    Public aggregate surface (ADR 0009): counts and declarations only, no subject. The
    counts span all history as of ``at`` — stated by ``window.period_days: null`` rather
    than letting a reader assume a period nobody chose.
    """
    described = [(agent, quality_regime_descriptor(agent)) for agent in list_agents()]
    business_ids = [
        agent.id
        for agent, descriptor in described
        if descriptor is not None and descriptor["regime"] == QualityRegime.BUSINESS_SCORED.value
    ]
    llm_ids = [
        agent.id
        for agent, descriptor in described
        if descriptor is not None and descriptor["regime"] == QualityRegime.LLM_JUDGED.value
    ]
    # ONE grouped ledger read for the WHOLE business-scored population, distributed by the
    # rows' own agent_id — the same exact-equality match the reader's per-agent filter
    # applies, so each bucket is byte-identical to what a scoped read would return. This is
    # the scaling profile of the route: registry iteration is free and the ledger costs one
    # read whether 1 or 200 agents declare business_scored (ratchet:
    # test_the_ledger_is_read_once_for_the_whole_business_population).
    rows_by_agent: dict[str, list[dict[str, object]]] = {aid: [] for aid in business_ids}
    if business_ids:
        for row in business_events_mod.business_event_rows(at=at):
            bucket = rows_by_agent.get(str(row.get("agent_id") or ""))
            if bucket is not None:
                bucket.append(row)
    judged_by_agent = _judged_plane_stats(at, llm_ids)
    regimes: list[dict[str, object]] = []
    for agent, descriptor in described:
        if descriptor is None:
            continue  # unreachable in the shipped registry (conformance ratchet)
        # `observable` rides along (the declared publish-activity contract, ADR 0017 §3):
        # an unrated agent can still be a WATCHED one — turns, telemetry, transversal
        # controls — and the band must be able to say so instead of reading as "absent
        # from the cockpit's metrics altogether" (operator feedback, 2026-08-21).
        entry: dict[str, object] = {
            **descriptor,
            "name": agent.name,
            "observable": declares_telemetry(agent),
            "business": None,
            "judged": None,
        }
        if descriptor["regime"] == QualityRegime.LLM_JUDGED.value:
            entry["judged"] = dict(
                judged_by_agent.get(
                    agent.id,
                    {
                        "responses_total": 0,
                        "since": None,
                        "last_scored_at": None,
                        "languages": {"fr": 0, "de": 0, "en": 0},
                    },
                )
            )
        if descriptor["regime"] == QualityRegime.BUSINESS_SCORED.value:
            # Both derivations run over the agent's OWN bucket — the same two builders the
            # Métier tab quotes (`business_signal_rows`, `_workflow_runs_from_rows`), so
            # the figures cannot disagree with it.
            rows = rows_by_agent.get(agent.id, [])
            signal_rows = business_signal_rows(agent.id, rows)
            statuses = Counter(str(row.get("status")) for row in signal_rows)
            stamps = sorted(
                str(row["timestamp"])
                for row in rows
                if isinstance(row.get("timestamp"), str) and row.get("timestamp")
            )
            entry["business"] = {
                "runs_total": len(_workflow_runs_from_rows(rows)),
                "signals_declared": len(signal_rows),
                "signals_scored": statuses.get("scored", 0),
                "signals_unknown": statuses.get("unknown", 0),
                "signals_not_applicable": statuses.get("not_applicable", 0),
                # When this ruler first and last spoke (same honesty as the judged plane).
                "since": stamps[0] if stamps else None,
                "last_event_at": stamps[-1] if stamps else None,
            }
        regimes.append(entry)
    return {"regimes": regimes, "as_of": at, "window": {"period_days": None}}


@router.get("/observability/trend")
def observability_trend(
    at: str | None = None, agent: str = "all", days: str | None = None
) -> dict[str, object]:
    """Long-horizon faithfulness trend over the score series (#150).

    Live by default; with ``?at=`` the trend is recomputed over the durable
    score log as of instant T (as-of-T read, ADR 0011). ``agent`` scopes the
    trend to one agent's scored turns (``all`` = org view); ``days`` scopes it to
    the selected period.
    """
    points: list[tuple[str, float]] = []
    for s in _scores_for(at, _agent_or_none(agent), parse_period_days(days)):
        if s.get("metric") != "faithfulness":
            continue
        scored_at = s.get("scored_at")
        points.append(
            (
                scored_at if isinstance(scored_at, str) else "",
                float(s["score"]),  # type: ignore[arg-type]
            )
        )
    return {**asdict(trends_mod.analyze_trend(points)), "as_of": at, "agent": agent}


@router.get("/observability/score-series")
def observability_score_series(
    at: str | None = None,
    metric: str = "faithfulness",
    days: str | None = None,
    buckets: int = 7,
    agent: str = "all",
) -> dict[str, object]:
    """Calendar-time score series + period-over-period delta for the evolution chart.

    Buckets the durable score log into equal time slices over the last ``days``,
    ending now or — with ``?at=`` — at instant T (as-of-T read, ADR 0011). Empty
    buckets carry ``mean=null`` so the chart shows a gap, never a fabricated zero.
    ``agent`` scopes the series to one agent's scored turns (``all`` = org view).

    A period is spelled the same way on every other windowed endpoint of this cockpit —
    ``h24``, ``d7``, ``d14``, ``d30`` — and these endpoints spoke a private dialect of
    bare integers.
    The selector therefore could not reach them: the client never built a ``days`` at all,
    and had it tried, ``days=d30`` would have been a 422. The operator picked thirty days
    and these read seven, silently (audit 2026-08-03).
    """
    import contextlib
    from datetime import UTC, datetime

    from tessera.observability.eval.series import compute_score_series

    end = datetime.now(UTC)
    if at:
        with contextlib.suppress(ValueError):
            end = datetime.fromisoformat(at)
    series = compute_score_series(
        read_scores(at, _agent_or_none(agent), full=True),
        metric=metric,
        end=end,
        days=window_days(days, default=7),
        n_buckets=buckets,
    )
    return {**asdict(series), "as_of": at, "agent": agent}


@router.get("/observability/signal-status-trend")
def observability_signal_status_trend(
    at: str | None = None,
    metric: str = "faithfulness",
    days: str | None = None,
) -> dict[str, object]:
    """Per-severity-band score counts bucketed by day (Signaux KPI strip, image 01).

    Classifies each judged score of ``metric`` into crit / warn / ok against the
    SLO thresholds and counts them per day, so every KPI tile gets a real
    sparkline + a real vs-previous-day delta from the durable score log. Honours
    as-of-T. Empty days are real zeros, never fabricated.

    A period is spelled the same way on every other windowed endpoint of this cockpit —
    ``h24``, ``d7``, ``d14``, ``d30`` — and these endpoints spoke a private dialect of
    bare integers.
    The selector therefore could not reach them: the client never built a ``days`` at all,
    and had it tried, ``days=d30`` would have been a 422. The operator picked thirty days
    and these read seven, silently (audit 2026-08-03).
    """
    import contextlib
    from datetime import UTC, datetime

    from tessera.observability.eval.series import compute_status_counts_trend

    end = datetime.now(UTC)
    if at:
        with contextlib.suppress(ValueError):
            end = datetime.fromisoformat(at)
    trend = compute_status_counts_trend(
        read_scores(at, full=True), metric=metric, end=end, days=window_days(days, default=7)
    )
    return {**asdict(trend), "as_of": at}


@router.get("/observability/metric-pairs")
def observability_metric_pairs(
    x: str = "faithfulness",
    y: str = "grounding",
    at: str | None = None,
) -> dict[str, object]:
    """Per-turn pairs of two metrics for a scatter (e.g. faithfulness vs grounding).

    Pairs are keyed by ``conversation_id`` — a turn that the online evaluator
    scored on both metrics. Honours as-of-T via the durable score log.
    """
    from tessera.observability.eval.series import compute_metric_pairs

    pairs = compute_metric_pairs(read_scores(at, full=True), x_metric=x, y_metric=y)
    return {**asdict(pairs), "as_of": at}


@router.get("/observability/obs-cost")
def observability_obs_cost() -> dict[str, object]:
    """Measured instrumentation overhead vs the turn budget (#84), cached."""
    global _obs_cost_cache
    if _obs_cost_cache is None:
        _obs_cost_cache = asdict(obs_cost_mod.measure_overhead())
    return _obs_cost_cache


@router.get("/observability/quality-nets", dependencies=[Depends(require_bearer)])
def observability_quality_nets(agent: str) -> dict[str, object]:
    """Manifest-generated quality nets for one agent (ADR 0017 §4).

    Instrumentation coverage (signal 92, measured from the agent's most recent telemetry)
    + canary freshness (signal 94, target workflows + last-seen turn). Both ``null`` for an
    un-manifested agent (honest-empty). Degrades to ``available: false`` on any failure.
    """
    try:
        return {
            "available": True,
            "agent_id": agent,
            "coverage": quality_nets_mod.coverage_descriptor(agent),
            "canary": quality_nets_mod.canary_descriptor(agent),
        }
    except Exception as exc:  # never break the page
        sys.stderr.write(f"tessera.observability.quality_nets: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/control-signals")
def observability_control_signals(lang: str = "fr") -> dict[str, object]:
    """Resolve the overview controls to their real catalogue signal + drill-down.

    Grounds each "Contrôles critiques" row in the LIVE signal catalogue (signal id /
    technical name / category) and a real SURVEILLER investigation route — the
    normative "Action recommandée / Case" intent. The two live policy probes
    (toxicity, refusal) are honestly reported as non-catalogued. Static reference
    metadata (no as-of-T): the mapping does not vary with the temporal instant.
    Degrades to ``available: false`` on failure.
    """
    try:
        return {"available": True, **control_signals_mod.compute_control_signals(lang)}
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.control_signals: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/signal-catalogue")
def observability_signal_catalogue(lang: str = "fr") -> dict[str, object]:
    """Signal catalogue overview (page #16).

    Composes the catalogue posture and the filterable signal table from the real
    eval run + guard policy; each row carries its own detail (client-side
    selection). Free-text is localized fr/de/en. Degrades to ``available: false``
    on failure.
    """
    try:
        return {"available": True, **signal_catalogue_mod.compute_signal_catalogue(lang)}
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.signal_catalogue: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/signal-coverage")
def observability_signal_coverage() -> dict[str, object]:
    """How many signals the catalogue DECLARES, split by whether they were ever built.

    The Qualité IA header read "42 of the 200-signal catalogue" from two constants; the real
    numbers are 202 declared, 78 active, 124 planned. The remaining funnel stages (declared by
    the page, wired, sampled, breaching) are facts about what the frontend rendered and are
    counted there — asking this route to guess them would repeat the constants' mistake in a
    place that cannot see the screen.

    NOT wrapped in a ``try``. Every other route here degrades to ``available: false`` because a
    dead panel beats a dead page; this one would degrade into "0 of 0 signals", which reads as a
    clean, fully-covered system. A coverage number computed over a catalogue nobody could open
    is the exact lie the constants were. Let it 500 and be noticed.
    """
    return signal_coverage_mod.compute_signal_coverage()


@router.get("/observability/reliability")
def observability_reliability(
    days: int = 14, anchor: str | None = None, lang: str = "fr"
) -> dict[str, object]:
    """Operational reliability & cost posture from the real signals (#08).

    Token cost, tool success, span overhead, per-language quality and per-model
    run stats are measured; latency is estimated from the token distribution at a
    documented local throughput. The period rail narrows the window via ``days``
    (length) and ``anchor`` (upper-bound day/instant). ``lang`` localizes the
    recommended-actions and incident free-text. Degrades to ``available: false``
    on failure.
    """
    try:
        report = reliability_mod.compute_reliability(days=days, anchor=anchor, lang=lang)
        return {"available": True, "days": days, "anchor": anchor, **asdict(report)}
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.reliability: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/conformance")
def observability_conformance(
    at: str | None = None, agent: str = "all", days: str | None = None
) -> dict[str, object]:
    """Schema/format conformance of tool-call arguments from the audit trail, live or as of T.

    ``agent`` scopes to one agent's tool calls (``all`` = org view); ``days`` to the period.
    """
    return asdict(
        conformance_mod.compute_conformance(
            at=at, agent_id=_agent_or_none(agent), days=parse_period_days(days)
        )
    )


@router.get("/observability/cost")
def observability_cost(
    at: str | None = None, agent: str = "all", days: str | None = None
) -> dict[str, object]:
    """Token-cost distribution and token-burn anomalies over captured turns, live or as of T.

    ``agent`` scopes to one agent's captured turns (``all`` = org view); ``days`` to the period.
    """
    turns = [
        (b.question, f"{b.question}\n{b.context}\n{b.original_answer}")
        for b in _bundles_for(at, _agent_or_none(agent), parse_period_days(days))
    ]
    return asdict(cost_anomaly_mod.analyze_costs(turns))


@router.get("/observability/routing")
def observability_routing(
    at: str | None = None, agent: str = "all", days: str | None = None
) -> dict[str, object]:
    """Language-routing health: served vs detected language, code-switching."""
    turns = [
        (b.question, b.language)
        for b in _bundles_for(at, _agent_or_none(agent), parse_period_days(days))
    ]
    return asdict(language_routing_mod.aggregate_routing(turns))


@router.get("/observability/intent")
def observability_intent(
    at: str | None = None, agent: str = "all", days: str | None = None
) -> dict[str, object]:
    """Business-intent mix and routing confidence over captured questions."""
    questions = [
        b.question for b in _bundles_for(at, _agent_or_none(agent), parse_period_days(days))
    ]
    return asdict(routing_intent_mod.aggregate_intents(questions))


@router.get("/observability/anomalies")
def observability_anomalies(
    at: str | None = None, agent: str = "all", days: str | None = None
) -> dict[str, object]:
    """Detect long/looping/repetitive sessions among captured turns, live or as of T.

    ``agent`` scopes to one agent's captured turns (``all`` = org view); ``days`` to the period.
    """
    by_conversation: dict[str, list[str]] = {}
    for bundle in _bundles_for(at, _agent_or_none(agent), parse_period_days(days)):
        key = bundle.conversation_id or "<none>"
        by_conversation.setdefault(key, []).append(bundle.question)
    return asdict(anomalies_mod.detect_anomalies(by_conversation))


@router.get("/observability/what-changed")
def observability_what_changed(at: str | None = None, agent: str = "all") -> dict[str, object]:
    """Attribute a score change to the lineage diff of the last two turns, live or as of T.

    ``agent`` scopes to one agent's captured turns (``all`` = org view).
    """
    with_lineage = [
        b for b in replay_mod.recent_bundles(at, _agent_or_none(agent)) if b.lineage is not None
    ]
    if len(with_lineage) < 2:  # noqa: PLR2004 — need two turns to diff
        return {"available": False}
    prev, curr = with_lineage[-2], with_lineage[-1]
    assert prev.lineage is not None  # narrowed by the filter above
    assert curr.lineage is not None
    report = whatchanged_mod.what_changed(
        prev_lineage=prev.lineage,
        prev_score=prev.original_score,
        curr_lineage=curr.lineage,
        curr_score=curr.original_score,
    )
    return {"available": True, **asdict(report)}


@router.get("/observability/control-series", dependencies=[Depends(require_bearer)])
async def observability_control_series(
    days: str | None = None,
    buckets: int | None = None,
    agent: str = "all",
    at: str | None = None,
) -> dict[str, object]:
    """A curve for every control that can honestly have one, over the selected window.

    Each bucket carries the SAME payload shape the point value is computed from, produced by
    the SAME handler with the bucket as its scope — the front then runs its own
    ``readControls`` over it. Nothing here derives a metric, so a curve cannot disagree with
    the number printed under it.

    ``unwindowed`` names the sources deliberately absent from every bucket and why: a
    fixed-corpus probe re-run inside a narrower window returns the same corpus, and a
    whole-sample statistic (a clustering, an inter-rater κ) is not smaller-but-similar when
    you take one slice of its input. Both would draw a flat line that reads as a stable
    metric, which is worse than no line.

    ``buckets`` overrides the resolution; omitted, the WINDOW chooses it
    (:func:`~tessera.observability.control_series.buckets_for_window`). It was a flat 8 until
    2026-08-02, which meant a 7-day window was cut into slices 21 h wide — wide enough for a
    day's traffic to fall entirely inside one, leaving a single measured point and no curve at
    all on the cockpit's DEFAULT period.

    Without ``days`` the report is empty: "all history" has no width to slice, and picking one
    from the oldest row present would make the axis depend on how long the process has run.
    """
    scope = Scope.from_query({"at": at, "agent": agent, "days": days})
    report = await compute_control_series(scope, buckets)
    return asdict(report)
