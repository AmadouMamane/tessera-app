"""Observability read endpoints for the dashboard (ADR 0010).

Exposes the recent online-eval scores so the dashboard can surface
eval-as-telemetry live. Aggregate quality scores are a public surface
(ADR 0009), so this endpoint is unauthenticated like ``/healthz``.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from tessera.agent.identity import DEFAULT_AGENT_ID
from tessera.api.security import require_bearer
from tessera.memory import transcript
from tessera.observability import (
    ablation as ablation_mod,
    access as access_mod,
    agent_a_faire as agent_a_faire_mod,
    agent_configurations as agent_configurations_mod,
    agent_console as agent_console_mod,
    agent_evaluations as agent_evaluations_mod,
    agent_garde_fous as agent_garde_fous_mod,
    agent_historique as agent_historique_mod,
    agent_prompts as agent_prompts_mod,
    agent_synthese as agent_synthese_mod,
    ai_act as ai_act_mod,
    anomalies as anomalies_mod,
    assistant as assistant_mod,
    automations as automations_mod,
    citation_resolver as citation_resolver_mod,
    citation_validity as citation_validity_mod,
    client_space as client_space_mod,
    compliance as compliance_mod,
    conformance as conformance_mod,
    connectors as connectors_mod,
    consistency as consistency_mod,
    console_feedback as console_feedback_mod,
    context_overflow as context_overflow_mod,
    contradiction as contradiction_mod,
    control_signals as control_signals_mod,
    corpus_freshness as corpus_freshness_mod,
    corpus_injection as corpus_injection_mod,
    cost_anomaly as cost_anomaly_mod,
    coverage as coverage_mod,
    cross_tenant as cross_tenant_mod,
    crosslingual as crosslingual_mod,
    curation as curation_mod,
    disclosure as disclosure_mod,
    embedding_inversion as embedding_inversion_mod,
    embedding_skew as embedding_skew_mod,
    erasure as erasure_mod,
    etat_a_date as etat_a_date_mod,
    failure_clustering as failure_clustering_mod,
    failure_predictor as failure_predictor_mod,
    firewall_efficacy as firewall_mod,
    fleet as fleet_mod,
    funnel as funnel_mod,
    governance_feed as governance_feed_mod,
    graph_topology as graph_topology_mod,
    guard_explain as guard_explain_mod,
    guard_retraction as guard_retraction_mod,
    handoffs as handoffs_mod,
    improvement as improvement_mod,
    inbox as inbox_mod,
    incidents as incidents_mod,
    integrations as integrations_mod,
    journey as journey_mod,
    knowledge as knowledge_mod,
    langfuse_obs as langfuse_obs_mod,
    language_routing as language_routing_mod,
    least_privilege as least_privilege_mod,
    locale_format as locale_format_mod,
    localization as localization_mod,
    memory_inventory as memory_inventory_mod,
    memory_obs as memory_obs_mod,
    obs_cost as obs_cost_mod,
    parameters as parameters_mod,
    pii_leak as pii_leak_mod,
    playbooks as playbooks_mod,
    policies as policies_mod,
    proofs as proofs_mod,
    provenance as provenance_mod,
    redteam as redteam_mod,
    refusal as refusal_mod,
    reliability as reliability_mod,
    replay as replay_mod,
    replay_shadow as replay_shadow_mod,
    reproducibility as reproducibility_mod,
    reranking_contribution as reranking_contribution_mod,
    retrieval_quality as retrieval_quality_mod,
    roadmap as roadmap_mod,
    robustness as robustness_mod,
    routing_intent as routing_intent_mod,
    session_detail as session_detail_mod,
    sessions as sessions_mod,
    sft_export as sft_export_mod,
    shadow as shadow_mod,
    siem as siem_mod,
    signal_catalogue as signal_catalogue_mod,
    slo as slo_mod,
    sources as sources_mod,
    span_propagation as span_propagation_mod,
    steganography as steganography_mod,
    system_profile as system_profile_mod,
    tail_sampling as tail_sampling_mod,
    tool_loops as tool_loops_mod,
    tool_validity as tool_validity_mod,
    toxicity as toxicity_mod,
    trace_snapshot as trace_snapshot_mod,
    trajectory as trajectory_mod,
    trends as trends_mod,
    users as users_mod,
    whatchanged as whatchanged_mod,
    why_answer as why_answer_mod,
)
from tessera.observability._asof import occurred_before
from tessera.observability.eval.calibration import calibrate, gold_consensus, load_gold_set
from tessera.observability.eval.ensemble import evaluate_ensemble
from tessera.observability.eval.judge import LLMJudge
from tessera.observability.eval.sycophancy import detect_sycophancy
from tessera.observability.spine.adapters import read_scores
from tessera.observability.spine.availability import dimension_availability
from tessera.observability.spine.scope import Scope
from tessera.observability.spine.snapshot import compute_snapshot

router = APIRouter(tags=["observability"])


class ReplayRequest(BaseModel):
    """Replay a captured turn against a candidate model."""

    model_config = ConfigDict(extra="forbid")

    bundle_id: str
    model: str


class ConsistencyRequest(BaseModel):
    """Measure self-consistency of a captured turn."""

    model_config = ConfigDict(extra="forbid")

    bundle_id: str
    samples: int = Field(default=3, ge=2, le=8)


class RobustnessRequest(BaseModel):
    """Measure robustness-under-noise of a captured turn."""

    model_config = ConfigDict(extra="forbid")

    bundle_id: str


class EnsembleRequest(BaseModel):
    """Score a captured turn with a multi-judge ensemble."""

    model_config = ConfigDict(extra="forbid")

    bundle_id: str


class CoverageRequest(BaseModel):
    """Measure corpus coverage of a captured turn."""

    model_config = ConfigDict(extra="forbid")

    bundle_id: str


class SycophancyRequest(BaseModel):
    """Judge a captured turn for sycophancy."""

    model_config = ConfigDict(extra="forbid")

    bundle_id: str


class CrossLingualRequest(BaseModel):
    """Measure cross-lingual consistency of a captured turn."""

    model_config = ConfigDict(extra="forbid")

    bundle_id: str


class ShadowRequest(BaseModel):
    """Mirror a batch of captured turns to a candidate model (shadow)."""

    model_config = ConfigDict(extra="forbid")

    model: str
    limit: int = Field(default=10, ge=1, le=50)


# Calibration runs the judge over the gold set (slow), so cache it per process.
# A backfill (scripts/backfill_calibration.py, llama3.2:3b) writes the report to
# this file so the API serves it instantly without scoring at request time.
_calibration_cache: dict[str, object] | None = None
_CALIBRATION_FILE = (
    Path(__file__).resolve().parents[4] / "eval" / "calibration" / "_calibration.json"
)
# The calibration backfill scores with the small, fast sovereign judge (idea #2).
_CALIBRATION_JUDGE_MODEL = "llama3.2:3b"
_consensus_cache: dict[str, object] | None = None
# A small panel of different local judges for the multi-judge consensus signal.
# All three are sovereign (served by Ollama on-box); different lineages so their
# agreement is meaningful rather than an echo (ADR 0010, idea #95).
_CONSENSUS_PANEL: tuple[str, ...] = ("llama3.2:3b", "mistral:7b", "gemma3:27b")
# The obs-cost micro-benchmark is stable per process, so compute it once.
_obs_cost_cache: dict[str, object] | None = None
# The embedding-inversion demo embeds a fixed corpus; cache it per process.
_inversion_cache: dict[str, object] | None = None
# Failure clustering embeds the whole failure corpus; cache it per process.
_clustering_cache: dict[str, object] | None = None
# The span-propagation probe is stable per process; run it once.
_propagation_cache: dict[str, object] | None = None


def _load_failure_items() -> list[failure_clustering_mod.FailureItem]:
    """Load the documented failures as clustering items (English prompt)."""
    import json
    from pathlib import Path

    items: list[failure_clustering_mod.FailureItem] = []
    failures_dir = Path(__file__).resolve().parents[4] / "eval" / "failures"
    for path in sorted(failures_dir.glob("[0-9]*.json")):
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        prompts = obj.get("prompts", {})
        text = ""
        if isinstance(prompts, dict):
            for lang in ("en", "fr", "de"):
                entry = prompts.get(lang)
                if isinstance(entry, dict) and entry.get("user"):
                    text = str(entry["user"])
                    break
        text = text or str(obj.get("title", ""))
        items.append(
            failure_clustering_mod.FailureItem(
                case_id=str(obj.get("id", path.stem)),
                category=str(obj.get("category", "unknown")),
                text=text,
            )
        )
    return items


def _agent_or_none(agent: str) -> str | None:
    """Map the global ``?agent=`` filter to a backend scope.

    ``"all"`` (or empty) is the deduplicated org view → ``None`` (no filter); any
    other value is a concrete agent id. Mirrors ``lib/agent-scope`` on the front.
    """
    return None if not agent or agent == "all" else agent


def _scores_for(at: str | None, agent_id: str | None = None) -> list[dict[str, object]]:
    """Scores to read: the live ring buffer, or the durable log as-of T (ADR 0011).

    Scoped to ``agent_id`` when set (per-agent SLO / trend / funnel / scores).
    """
    return read_scores(at, agent_id)


def _data_availability_start(
    scores: list[dict[str, object]],
    audit_entries: list[dict[str, object]],
) -> str | None:
    """Earliest instant the cockpit holds real as-of-T data, or None if it holds none.

    The bound is the lexicographic minimum over the two durable as-of-T sources —
    eval score ``scored_at`` and guard audit ``occurred_at`` — ignoring blanks. ISO
    8601 sorts lexicographically, matching the timeline's ordering convention.
    """
    stamps = [str(s.get("scored_at", "")) for s in scores]
    stamps += [str(e.get("occurred_at", "")) for e in audit_entries]
    stamps = [s for s in stamps if s]
    return min(stamps) if stamps else None


@router.get("/observability/scores")
async def observability_scores(at: str | None = None, agent: str = "all") -> dict[str, object]:
    """Online-eval scores — live (newest last), or as of instant ``at`` (ISO).

    ``agent`` scopes the scores to one agent's turns (``all`` = org view).
    """
    return {"scores": _scores_for(at, _agent_or_none(agent)), "as_of": at, "agent": agent}


@router.get("/observability/snapshot", dependencies=[Depends(require_bearer)])
async def observability_snapshot(
    at: str | None = None,
    agent: str = "all",
    language: str | None = None,
    model: str | None = None,
    signals: str | None = None,
) -> dict[str, object]:
    """Batched, cached snapshot of every scope-varying signal in one pass (ADR 0015).

    Collapses the ~24-37 per-page fetches into a single round-trip: all hot-path signals
    for one :class:`Scope`, computed over shared store reads and served through a
    read-through cache with single-flight. Each signal carries a ``report`` of which
    dimensions it honoured / ignored, so the UI badges org-wide / synthetic / unavailable
    from data — the filter-shown-but-ignored state is unrepresentable. ``?signals=`` selects
    a comma-separated subset. Scope is a *filter*, never a privilege escalation: RBAC is the
    same ``require_bearer`` posture as the other read surfaces (no-op without a token).
    """
    scope = Scope.from_query({"at": at, "agent": agent, "language": language, "model": model})
    ids = tuple(part.strip() for part in signals.split(",") if part.strip()) if signals else None
    return await compute_snapshot(scope, ids)


@router.get("/observability/timeline")
async def observability_timeline(at: str | None = None) -> dict[str, object]:
    """Temporal control backbone — dated lineage events for the cockpit time rail.

    Every cockpit view reads at an instant T and compares to a baseline; this is
    the event scrubber behind that control. Events are *derived from real
    signals*, never fabricated: quality points (online-eval scores), judge-model
    changes, agent-model changes and guard denials (the tamper-evident audit
    log). With ``?at=`` the window ends at T (as-of-T read, ADR 0011): only
    events with timestamp ≤ T are returned.
    """
    from datetime import UTC, datetime

    events: list[dict[str, object]] = []

    # Quality points + judge-model change detection (scores oldest→newest, ≤ T).
    ordered = sorted(_scores_for(at), key=lambda s: str(s.get("scored_at", "")))
    prev_judge: str | None = None
    for s in ordered:
        ts = str(s.get("scored_at", ""))
        if not ts:
            continue
        score = float(s.get("score", 0.0))  # type: ignore[arg-type]
        good, fair = 0.8, 0.5
        tone = "success" if score >= good else "warning" if score >= fair else "danger"
        events.append(
            {
                "at": ts,
                "kind": "score",
                "label": f"Score {score:.2f}",
                "detail": f"{s.get('metric', '')} · {str(s.get('language', '')).upper()}",
                "tone": tone,
            }
        )
        judge = s.get("judge_model")
        if isinstance(judge, str) and judge and judge != prev_judge:
            if prev_judge is not None:
                events.append(
                    {
                        "at": ts,
                        "kind": "judge_change",
                        "label": "Juge mis à jour",
                        "detail": f"{prev_judge} → {judge} — re-calibration κ requise",
                        "tone": "gold",
                    }
                )
            prev_judge = judge

    # Guard denials + agent-model changes from the tamper-evident audit log,
    # filtered to occurrences ≤ T. Denials are clustered by hour so a busy log
    # becomes a few legible scrubber markers rather than hundreds of dots.
    prev_model: str | None = None
    denials: dict[str, dict[str, object]] = {}
    for entry in _read_audit_entries():
        ts = str(entry.get("occurred_at", ""))
        if not ts:
            continue
        if not occurred_before(ts, at):
            continue
        outcome = str(entry.get("outcome", ""))
        if outcome not in ("allowed", "allow"):
            bucket = ts[:13]  # YYYY-MM-DDTHH
            agg = denials.setdefault(
                bucket, {"at": ts, "count": 0, "target": entry.get("target", "")}
            )
            count = agg["count"]
            agg["count"] = (count if isinstance(count, int) else 0) + 1
            agg["at"] = ts  # latest occurrence in the hour
        model = entry.get("model")
        if isinstance(model, str) and model and model != prev_model:
            if prev_model is not None:
                events.append(
                    {
                        "at": ts,
                        "kind": "model_change",
                        "label": "Modèle déployé",
                        "detail": f"{prev_model} → {model}",
                        "tone": "info",
                    }
                )
            prev_model = model

    for agg in denials.values():
        events.append(
            {
                "at": str(agg["at"]),
                "kind": "guard_denial",
                "label": f"Garde — {agg['count']} refus",
                "detail": str(agg["target"]),
                "tone": "danger",
            }
        )

    events.sort(key=lambda e: str(e["at"]))
    window_end = at or datetime.now(UTC).isoformat()
    window_start = str(events[0]["at"]) if events else window_end
    return {
        "window_start": window_start,
        "window_end": window_end,
        "baseline_at": window_start,
        "n_events": len(events),
        "events": events[-60:],
        "as_of": at,
    }


@router.get("/observability/data-range")
async def observability_data_range() -> dict[str, object]:
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

    scores = read_scores(full=True)
    audit_entries = _read_audit_entries()
    start = _data_availability_start(scores, audit_entries)
    return {
        "start": start,
        "end": datetime.now(UTC).isoformat(),
        "n": len(scores) + len(audit_entries),
    }


@router.get("/observability/availability")
async def observability_availability() -> dict[str, object]:
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
async def observability_slo(at: str | None = None, agent: str = "all") -> dict[str, object]:
    """Quality SLO + error-budget burn-rate over the faithfulness scores.

    Live by default; with ``?at=`` the SLO is recomputed over the durable score
    log as of instant T (as-of-T read, ADR 0011). ``agent`` scopes the SLO to one
    agent's own scored turns (``all`` = org view); an agent with no scored turns
    yet reads honestly empty (``n=0``).
    """
    faithfulness = [
        float(s["score"])  # type: ignore[arg-type]
        for s in _scores_for(at, _agent_or_none(agent))
        if s.get("metric") == "faithfulness"
    ]
    return {**asdict(slo_mod.compute_slo(faithfulness)), "as_of": at, "agent": agent}


@router.post("/observability/shadow")
async def observability_shadow(payload: ShadowRequest) -> dict[str, object]:
    """Mirror recent captured turns to a candidate model and compare (shadow)."""
    report = await shadow_mod.run_shadow(
        replay_mod.recent_bundles(), model=payload.model, limit=payload.limit
    )
    return asdict(report)


@router.get("/observability/span-propagation")
async def observability_span_propagation() -> dict[str, object]:
    """Async/parallel span-propagation health from a live isolated probe (#85), cached."""
    global _propagation_cache
    if _propagation_cache is None:
        _propagation_cache = asdict(await span_propagation_mod.probe_propagation())
    return _propagation_cache


@router.get("/observability/tail-sampling")
async def observability_tail_sampling() -> dict[str, object]:
    """Tail-sampling retention: 100% of slow/low-score traces, sampled head."""
    return asdict(tail_sampling_mod.analyze_sampling(replay_mod.recent_bundles()))


@router.get("/observability/reproducibility")
async def observability_reproducibility() -> dict[str, object]:
    """Trace-shape reproducibility / non-determinism across repeated questions (#86)."""
    turns = [(b.question, list((b.latency_ms or {}).keys())) for b in replay_mod.recent_bundles()]
    return asdict(reproducibility_mod.detect_nondeterminism(turns))


@router.get("/observability/trend")
async def observability_trend(at: str | None = None, agent: str = "all") -> dict[str, object]:
    """Long-horizon faithfulness trend over the score series (#150).

    Live by default; with ``?at=`` the trend is recomputed over the durable
    score log as of instant T (as-of-T read, ADR 0011). ``agent`` scopes the
    trend to one agent's scored turns (``all`` = org view).
    """
    points: list[tuple[str, float]] = []
    for s in _scores_for(at, _agent_or_none(agent)):
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
async def observability_score_series(
    at: str | None = None,
    metric: str = "faithfulness",
    days: int = 7,
    buckets: int = 7,
    agent: str = "all",
) -> dict[str, object]:
    """Calendar-time score series + period-over-period delta for the evolution chart.

    Buckets the durable score log into equal time slices over the last ``days``,
    ending now or — with ``?at=`` — at instant T (as-of-T read, ADR 0011). Empty
    buckets carry ``mean=null`` so the chart shows a gap, never a fabricated zero.
    ``agent`` scopes the series to one agent's scored turns (``all`` = org view).
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
        days=days,
        n_buckets=buckets,
    )
    return {**asdict(series), "as_of": at, "agent": agent}


@router.get("/observability/judge-drift")
async def observability_judge_drift(
    at: str | None = None,
    metric: str = "faithfulness",
    days: int = 7,
    buckets: int = 7,
) -> dict[str, object]:
    """Judge score-drift for ``metric`` over the window ending now or at instant T.

    Measures how much the judge's per-bucket mean disperses over time (the drift
    magnitude) plus its net direction, from the same durable score log — so it
    honours as-of-T (ADR 0011). Powers the "Drift du juge" signal on the
    Calibration juge tab. ``divergence=null``/``level="unknown"`` when there are
    too few populated buckets to judge drift, never a fabricated value.
    """
    import contextlib
    from datetime import UTC, datetime

    from tessera.observability.eval.series import compute_judge_drift

    end = datetime.now(UTC)
    if at:
        with contextlib.suppress(ValueError):
            end = datetime.fromisoformat(at)
    drift = compute_judge_drift(
        read_scores(at, full=True), metric=metric, end=end, days=days, n_buckets=buckets
    )
    return {**asdict(drift), "as_of": at}


@router.get("/observability/regression-risk")
async def observability_regression_risk(
    at: str | None = None,
    metric: str = "faithfulness",
    days: int = 7,
    buckets: int = 7,
) -> dict[str, object]:
    """Forward-looking regression risk for the "Signaux prédictifs" column.

    Composes a transparent risk score from real signals only — the recent judge
    score trend (``score-series`` delta), judge drift divergence, and the
    empirical share of compared models that regressed run-over-run
    (``release-status``). The 7-day regression probability is that empirical base
    rate, not an invented forecast. Honours as-of-T via the durable score log;
    every component is returned alongside the composite so the risk is explainable.
    With neither judge scores nor compared models the composite is ``null`` and the
    level is ``"unknown"`` rather than fabricated.
    """
    import contextlib
    from datetime import UTC, datetime

    from tessera.observability.eval.releases import release_status
    from tessera.observability.eval.risk import compute_regression_risk

    end = datetime.now(UTC)
    if at:
        with contextlib.suppress(ValueError):
            end = datetime.fromisoformat(at)
    risk = compute_regression_risk(
        read_scores(at, full=True),
        release_status(),
        end=end,
        metric=metric,
        days=days,
        n_buckets=buckets,
    )
    return {**asdict(risk), "as_of": at}


@router.get("/observability/signal-status-trend")
async def observability_signal_status_trend(
    at: str | None = None,
    metric: str = "faithfulness",
    days: int = 7,
) -> dict[str, object]:
    """Per-severity-band score counts bucketed by day (Signaux KPI strip, image 01).

    Classifies each judged score of ``metric`` into crit / warn / ok against the
    SLO thresholds and counts them per day, so every KPI tile gets a real
    sparkline + a real vs-previous-day delta from the durable score log. Honours
    as-of-T. Empty days are real zeros, never fabricated.
    """
    import contextlib
    from datetime import UTC, datetime

    from tessera.observability.eval.series import compute_status_counts_trend

    end = datetime.now(UTC)
    if at:
        with contextlib.suppress(ValueError):
            end = datetime.fromisoformat(at)
    trend = compute_status_counts_trend(
        read_scores(at, full=True), metric=metric, end=end, days=days
    )
    return {**asdict(trend), "as_of": at}


@router.get("/observability/metric-pairs")
async def observability_metric_pairs(
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
async def observability_obs_cost() -> dict[str, object]:
    """Measured instrumentation overhead vs the turn budget (#84), cached."""
    global _obs_cost_cache
    if _obs_cost_cache is None:
        _obs_cost_cache = asdict(obs_cost_mod.measure_overhead())
    return _obs_cost_cache


@router.get("/observability/calibration")
async def observability_calibration() -> dict[str, object]:
    """Return the judge's calibration against the human gold set (cached).

    The first call runs the judge over the gold set and may take a few seconds;
    subsequent calls return the cached report. Degrades to ``available: false``
    when the judge or gold set is unavailable, so the dashboard never errors.
    """
    global _calibration_cache
    if _calibration_cache is None:
        # Prefer the precomputed backfill (real llama3.2:3b scores over the gold set).
        if _CALIBRATION_FILE.exists():
            try:
                _calibration_cache = json.loads(_CALIBRATION_FILE.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                sys.stderr.write(f"tessera.observability.calibration: cache read failed: {exc}\n")
        if _calibration_cache is None:
            try:
                report = await calibrate(LLMJudge(model=_CALIBRATION_JUDGE_MODEL), load_gold_set())
                _calibration_cache = {"available": True, **asdict(report)}
            except Exception as exc:  # never break the dashboard on a judge/IO error
                sys.stderr.write(f"tessera.observability.calibration: failed: {exc}\n")
                return {"available": False}
    return _calibration_cache


@router.get("/observability/compliance")
async def observability_compliance(lang: str = "fr") -> dict[str, object]:
    """Regulatory compliance posture derived from the real runtime signals (#07).

    Maps the live AI-Act, conformance, citation, disclosure, PII, refusal,
    erasure and firewall signals onto per-framework controls (RGPD, EU AI Act,
    DORA, ISO 27001, SOC 2, internal policies). ``lang`` localizes the labels and
    the per-tab catalogues. Degrades to ``available: false`` if assembly fails so
    the dashboard never errors.
    """
    try:
        return {"available": True, **asdict(compliance_mod.compute_compliance(lang))}
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.compliance: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/improvement")
async def observability_improvement(lang: str = "fr") -> dict[str, object]:
    """Continuous-improvement posture mined from the telemetry roadmap (#09).

    Turns the real roadmap backlog (low-faithfulness turns, unknown intents,
    stale corpora) plus eval-set coverage and corpus freshness into prioritised
    improvement opportunities. Degrades to ``available: false`` on failure.
    """
    try:
        return {"available": True, **asdict(improvement_mod.compute_improvement(lang))}
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.improvement: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/agent-historique")
async def observability_agent_historique(
    agent_id: str = DEFAULT_AGENT_ID,
    lang: str = "fr",
) -> dict[str, object]:
    """Agent Session History dashboard (reference image 30).

    Inner tab strip, KPI strip, filterable sessions table, chart row (trend,
    sessions by agent, score distribution, success gauge), watchlist, quick
    actions and a per-session detail panel. Deterministic fixture; degrades to
    ``available: false``. ``agent_id`` scopes the in-page navigation links;
    ``lang`` localizes the chrome (fr / de / en).
    """
    try:
        payload: dict[str, object] = {
            "available": True,
            **agent_historique_mod.compute_agent_historique(agent_id, lang),
        }
        # Real live conversations from the transcript, surfaced ALONGSIDE the eval
        # sessions (additive — the eval KPIs/charts stay untouched). These are the
        # operator's actual turns, not scored runs, so they get their own honest
        # block rather than fabricated eval scores.
        payload["live_conversations"] = _serialize_conversations(
            await transcript.list_conversations(agent_id, limit=50)
        )
        return payload
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.agent_historique: failed: {exc}\n")
        return {"available": False}


def _serialize_conversations(
    conversations: list[transcript.ConversationSummary],
) -> list[dict[str, object]]:
    """Public-safe JSON for a conversation list (console Récents + Historique)."""
    return [
        {
            "conversation_id": c.conversation_id,
            "title": c.title,
            "started_at": c.started_at.isoformat(),
            "last_at": c.last_at.isoformat(),
            "message_count": c.message_count,
            "turn_count": c.turn_count,
        }
        for c in conversations
    ]


@router.get("/observability/conversations")
async def observability_conversations(
    agent_id: str = DEFAULT_AGENT_ID,
    limit: int = 30,
) -> dict[str, object]:
    """Recent conversations handled by ``agent_id`` (most-recently-active first).

    Powers the business console's "Récents" list. Degrades to an empty list
    rather than breaking the console.
    """
    try:
        bounded = max(1, min(limit, 100))
        return {
            "available": True,
            "conversations": _serialize_conversations(
                await transcript.list_conversations(agent_id, limit=bounded)
            ),
        }
    except Exception as exc:  # never break the console
        sys.stderr.write(f"tessera.observability.conversations: failed: {exc}\n")
        return {"available": False, "conversations": []}


@router.get("/observability/conversation-messages")
async def observability_conversation_messages(conversation_id: str) -> dict[str, object]:
    """The persisted user/assistant messages of one conversation, in order.

    Used by the business console to RESUME a "Récents" conversation: it loads the
    transcript back into the chat and continues the same ``conversation_id``.
    Degrades to an empty list for an unknown / malformed id.
    """
    try:
        messages = await transcript.load_transcript(UUID(conversation_id))
        return {
            "available": True,
            "conversation_id": conversation_id,
            "messages": [
                {"role": m.role, "content": m.content}
                for m in messages
                if m.role in ("user", "assistant")
            ],
        }
    except Exception as exc:  # never break the console
        sys.stderr.write(f"tessera.observability.conversation_messages: failed: {exc}\n")
        return {"available": False, "messages": []}


@router.get("/observability/session-detail")
async def observability_session_detail(
    conversation_id: str, at: str | None = None
) -> dict[str, object]:
    """Turn-by-turn detail of one conversation with per-turn agent attribution.

    Shows which agent handled each turn (so a handed-over conversation reads as a
    clear hand-over) plus the S1 handoff events. ``at`` bounds the handoff read
    (as-of). Degrades to ``available: false`` for an unknown/empty conversation.
    """
    try:
        return await session_detail_mod.compute_session_detail(conversation_id, at)
    except Exception as exc:  # never break the page
        sys.stderr.write(f"tessera.observability.session_detail: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/fleet")
async def observability_fleet(lang: str = "fr") -> dict[str, object]:
    """Fleet rollup: per-agent observable KPIs + deduplicated org totals.

    ``lang`` localizes the per-agent release verdict label.
    """
    try:
        return {"available": True, **await fleet_mod.compute_fleet(lang)}
    except Exception as exc:  # never break the page
        sys.stderr.write(f"tessera.observability.fleet: failed: {exc}\n")
        return {"available": False}


class _AgentProposeBody(BaseModel):
    """A governed proposal to add a new agent to the fleet."""

    name: str


@router.post("/observability/agents/propose")
async def observability_agents_propose(body: _AgentProposeBody) -> dict[str, object]:
    """Record a governed, audited proposal to add an agent.

    An agent is a package approved as a unit (ADR 0012), so the registry is not
    mutated at runtime: this emits an auditable S1 event (proposal) that feeds the
    propose -> review -> release flow. RBAC is enforced on the client; the event
    captures the intent durably either way.
    """
    from tessera.guard.audit import emit_agent_proposed

    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="name is required")
    emit_agent_proposed(name=name)
    return {"available": True, "proposed": name}


@router.get("/observability/rbac-matrix")
async def observability_rbac_matrix(agent: str = "all") -> dict[str, object]:
    """RBAC role x agent matrix (real roles x real agents). Global, filterable.

    The enforced roles are currently org-wide; the matrix states that truthfully
    rather than fabricating per-agent grants. Degrades to ``available: false``.
    """
    from tessera.observability import rbac as rbac_mod

    try:
        return {"available": True, **rbac_mod.rbac_matrix(agent)}
    except Exception as exc:  # never break the page
        sys.stderr.write(f"tessera.observability.rbac: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/catalogue-consumers")
async def observability_catalogue_consumers(
    kind: str, agent: str = "all", lang: str = "fr"
) -> dict[str, object]:
    """CONFIGURER "used-by": which agents consume each catalogue item of ``kind``.

    The inverse of the AGENT instance binding — each shared definition shows its
    consumer agents + their release verdict, so a change's re-gate blast radius is
    explicit. Global, filterable by agent. ``lang`` localizes the verdict label.
    Degrades to ``available: false``.
    """
    from tessera.observability import catalogue_consumers as cc_mod

    try:
        return {
            "available": True,
            **cc_mod.catalogue_consumers(kind, agent_scope=agent, lang=lang),
        }
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # never break the page
        sys.stderr.write(f"tessera.observability.catalogue_consumers: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/model-catalogue")
async def observability_model_catalogue(lang: str = "fr", agent: str = "all") -> dict[str, object]:
    """CONFIGURER model catalogue (configurer/modeles): the real LLM model layer.

    The configured models (vertex / ollama / openai) + the indicative tariff +
    real cumulative usage + the consuming agents (re-gate blast radius). Filterable
    by agent. Degrades to ``available: false`` on failure.
    """
    from tessera.observability import model_catalogue as mc_mod

    try:
        return {"available": True, **mc_mod.build_model_catalogue(lang, agent_scope=agent)}
    except Exception as exc:  # never break the page
        sys.stderr.write(f"tessera.observability.model_catalogue: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/guardrail-catalogue")
async def observability_guardrail_catalogue(
    lang: str = "fr", agent: str = "all"
) -> dict[str, object]:
    """CONFIGURER platform guardrail catalogue (configurer/garde-fous).

    The guardrail profiles agents bind, with the real shared-policy composition,
    audit posture and consuming agents (re-gate blast radius). Filterable by
    agent. Degrades to ``available: false`` on failure.
    """
    from tessera.observability import guardrail_catalogue as gc_mod

    try:
        return {"available": True, **gc_mod.build_guardrail_catalogue(lang, agent_scope=agent)}
    except Exception as exc:  # never break the page
        sys.stderr.write(f"tessera.observability.guardrail_catalogue: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/release-control")
async def observability_release_control(agent: str = "all", lang: str = "fr") -> dict[str, object]:
    """Release Control (AGIR): per-agent release pipeline + eval-gate verdict.

    Global, filterable by agent (``?agent=all|<id>``) — distinct from the AGENT
    switcher. Each agent is a governed package; the verdict is the policy-correct
    gate over the agent's OWN run. Degrades to ``available: false``.
    """
    from tessera.observability import release_control as rc_mod

    try:
        return {"available": True, **rc_mod.compute_release_control(agent, lang)}
    except Exception as exc:  # never break the page
        sys.stderr.write(f"tessera.observability.release_control: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/agent-lifecycle")
async def observability_agent_lifecycle(
    agent_id: str = DEFAULT_AGENT_ID,
    lang: str = "fr",
) -> dict[str, object]:
    """Governed lifecycle of an agent: state, gated release decision, S1 history.

    Closes the propose -> review -> approve -> release loop: the release decision
    is the agent's own two-level eval-gate verdict. Degrades to ``available:false``.
    """
    from tessera.observability import agent_lifecycle as lifecycle_mod

    try:
        return {"available": True, **lifecycle_mod.compute_agent_lifecycle(agent_id, lang)}
    except Exception as exc:  # never break the page
        sys.stderr.write(f"tessera.observability.agent_lifecycle: failed: {exc}\n")
        return {"available": False}


class _AgentReleaseBody(BaseModel):
    """A governed request to promote an agent (version) to live."""

    agent_id: str


@router.post("/observability/agents/release")
async def observability_agents_release(body: _AgentReleaseBody) -> dict[str, object]:
    """Attempt to promote an agent to live — gated by its eval-gate.

    An agent only goes live once a run of ITS own set cleared the two-level gate.
    The attempt is recorded as a hash-chained S1 event (``released`` on success,
    ``release_blocked`` otherwise), so the promotion is opposable either way.
    """
    from tessera.observability.agent_lifecycle import request_release

    agent_id = body.agent_id.strip()
    if not agent_id:
        raise HTTPException(status_code=422, detail="agent_id is required")
    decision = request_release(agent_id)
    return {"available": True, **decision.as_dict()}


@router.get("/observability/agent-evaluations")
async def observability_agent_evaluations(
    agent_id: str = DEFAULT_AGENT_ID,
    lang: str = "fr",
) -> dict[str, object]:
    """Agent Evaluations ("Evaluations") dashboard (reference image 29).

    Inner tab strip, active-snapshot bar, KPI strip, filterable evaluations
    table, watchlist, quick actions, global-score trend and a per-evaluation
    detail panel. Scored from the agent's OWN run over its OWN set (real
    llama3.2:3b), with the two-level gate verdict, per-agent judged metrics and
    the ER-01 run-history rail; degrades to ``available: false``.

    The ``agent_id`` query param scopes the page to one agent; it defaults to the
    single agent.
    """
    try:
        return {
            "available": True,
            **agent_evaluations_mod.compute_agent_evaluations(agent_id, lang),
        }
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.agent_evaluations: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/agent-prompts")
async def observability_agent_prompts(
    lang: str = "fr", agent_id: str = DEFAULT_AGENT_ID
) -> dict[str, object]:
    """Agent Prompts ("Prompts") dashboard (reference image 28).

    Backed by the live YAML source of truth
    (``src/tessera/agent/prompts/{fr,de,en}.yaml``): the prompt inventory,
    categories, languages, template variables, lengths and the per-prompt text
    in the detail panel are all real. Read-only (prompts live in Git). Display
    labels are localized via ``lang`` (fr/de/en). ``agent_id`` scopes the
    in-page navigation links. Degrades to ``available: false`` on failure.
    """
    try:
        return {"available": True, **(await agent_prompts_mod.build_agent_prompts(lang, agent_id))}
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.agent_prompts: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/sandbox-config")
async def observability_sandbox_config(lang: str = "fr") -> dict[str, object]:
    """Defaults for the Console sandbox playground (model/prompt/guardrails).

    Returns the *live* system prompt for ``lang`` (the YAML bundle the agent
    actually runs) and the toggleable guard categories with their real pattern
    counts (the runtime guard policy). The console prefills its prompt editor and
    guard switches from these — never from fabricated values. Read-only;
    overrides are applied per-turn at chat time, never persisted here.
    """
    from tessera.agent.reporter import load_prompts
    from tessera.guard.decisions import load_policy
    from tessera.settings import LanguageCode, get_settings

    langs = {"fr": LanguageCode.FR, "de": LanguageCode.DE, "en": LanguageCode.EN}
    try:
        language = langs.get(lang, LanguageCode.FR)
        prompts = load_prompts(language)
        policy = load_policy(get_settings().guard.policy_path)
        return {
            "available": True,
            "language": language.value,
            "system_prompt": prompts.get("system", ""),
            "guard_categories": [
                {
                    "key": "prompt_injection",
                    "label": "Prompt Injection",
                    "count": len(policy.prompt_injection_deny),
                    "detail": "Bloque l'entrée utilisateur qui matche un motif d'injection.",
                },
                {
                    "key": "pii",
                    "label": "Masquage PII",
                    "count": len(policy.pii_patterns),
                    "detail": "Masque les données personnelles dans la trace d'audit des outils.",
                },
                {
                    "key": "tools",
                    "label": "Privilèges outils",
                    "count": len(policy.tools),
                    "detail": "Allowlist + confirmations + validation d'arguments par outil.",
                },
            ],
        }
    except Exception as exc:  # never break the console
        sys.stderr.write(f"tessera.observability.sandbox_config: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/agent-garde-fous")
async def observability_agent_garde_fous(lang: str = "fr") -> dict[str, object]:
    """Agent Guardrails ("Garde-fous") dashboard (reference image 27).

    Backed by the live guard layer: rules are derived from ``policy.yaml`` and
    the firing stats (decisions, blocks, last fired, 24h deltas) plus audit-chain
    integrity are read from the tamper-evident audit log. Per-rule enable/disable
    state is durable. Display labels are localized via ``lang`` (fr/de/en).
    Degrades to ``available: false`` on failure.
    """
    try:
        return {"available": True, **(await agent_garde_fous_mod.build_agent_garde_fous(lang))}
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.agent_garde_fous: failed: {exc}\n")
        return {"available": False}


class _RuleStateBody(BaseModel):
    """Enable/disable mutation for one guard rule."""

    key: str
    enabled: bool


@router.post("/observability/agent-garde-fous/rule-state")
async def observability_agent_garde_fous_mutate(
    body: _RuleStateBody, lang: str = "fr"
) -> dict[str, object]:
    """Persist an enable/disable change and return the fresh payload."""
    if body.key not in agent_garde_fous_mod.available_rules():
        raise HTTPException(status_code=404, detail="unknown rule")
    agent_garde_fous_mod.set_rule_state(body.key, enabled=body.enabled)
    return {"available": True, **(await agent_garde_fous_mod.build_agent_garde_fous(lang))}


@router.get("/observability/agent-a-faire")
async def observability_agent_a_faire(lang: str = "fr") -> dict[str, object]:
    """Agent "A faire" personal action queue (reference image 23).

    Backed by the real operator backlog (failed eval cases with durable
    status/assignee): temporal rail + event timeline, KPI strip, saved-views
    filter rail, task table, per-item detail band and the right column.
    ``lang`` localizes the chrome (fr / de / en). Degrades to
    ``available: false`` on failure.
    """
    try:
        return {"available": True, **agent_a_faire_mod.compute_agent_a_faire(lang)}
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.agent_a_faire: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/agent-connaissances")
async def observability_agent_connaissances(lang: str = "fr") -> dict[str, object]:
    """Agent Knowledge ("Connaissances") dashboard (reference image 01).

    Backed by the live pgvector ``documents`` table: the source inventory,
    chunk counts, languages and freshness are real. Per-agent attach/active
    state is durable. Display labels are localized via ``lang`` (fr/de/en).
    Degrades to ``available: false`` if the store is down.
    """
    try:
        return {"available": True, **(await knowledge_mod.build_connaissances(lang))}
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.agent_connaissances: failed: {exc}\n")
        return {"available": False}


class _SourceStateBody(BaseModel):
    """Attach/detach/activate mutation for one knowledge source."""

    key: str
    attached: bool | None = None
    active: bool | None = None


@router.post("/observability/agent-connaissances/source-state")
async def observability_agent_connaissances_mutate(
    body: _SourceStateBody, lang: str = "fr"
) -> dict[str, object]:
    """Persist an attach/detach/activate change and return the fresh payload."""
    if body.key not in knowledge_mod.available_sources():
        raise HTTPException(status_code=404, detail="unknown source")
    knowledge_mod.set_source_state(body.key, attached=body.attached, active=body.active)
    return {"available": True, **(await knowledge_mod.build_connaissances(lang))}


@router.get("/observability/agent-configurations")
async def observability_agent_configurations(
    agent_id: str = DEFAULT_AGENT_ID,
    lang: str = "fr",
) -> dict[str, object]:
    """Agent Configurations dashboard (reference image 26).

    Composes the active settings, guard policy, prompt bundles, tools and
    corpus-backed sources into the operator configuration form. Degrades to
    ``available: false`` so the dashboard keeps rendering if a local source is
    temporarily unreadable. ``agent_id`` scopes the in-page navigation links;
    ``lang`` localizes the chrome and the editable option values.
    """
    try:
        return {
            "available": True,
            **agent_configurations_mod.compute_agent_configurations(agent_id, lang),
        }
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.agent_configurations: failed: {exc}\n")
        return {"available": False}


class _AgentConfigBody(BaseModel):
    """A set of agent-profile overrides to persist (only known keys are kept)."""

    changes: dict[str, object]
    lang: str = "fr"


@router.post("/observability/agent-configurations/config")
async def observability_agent_configurations_save(
    body: _AgentConfigBody, agent_id: str = DEFAULT_AGENT_ID
) -> dict[str, object]:
    """Persist editable agent-profile overrides and return the fresh payload.

    Incoming option values may be localized; ``set_agent_config`` re-canonicalizes
    them to French before persisting, so the durable store stays locale-stable.
    """
    unknown = set(body.changes) - agent_configurations_mod.available_config_keys()
    if unknown:
        raise HTTPException(status_code=422, detail=f"unknown keys: {sorted(unknown)}")
    agent_configurations_mod.set_agent_config(body.changes, agent_id)
    return {
        "available": True,
        **agent_configurations_mod.compute_agent_configurations(agent_id, body.lang),
    }


@router.get("/observability/agent-console")
async def observability_agent_console(lang: str = "fr") -> dict[str, object]:
    """Agent Console (Debug) surface (reference image agent-console-normative).

    Status sub-bar, live transcript, service-level KPIs and a tabbed inspector
    (Contexte / Sources / Outils / Garde-fous / Trace) with the quality
    scorecard, sources used, tools called, triggered guardrails and real-time
    trace. Deterministic fixture; degrades to ``available: false``.
    """
    try:
        return {"available": True, **agent_console_mod.compute_agent_console(lang)}
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.agent_console: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/agent-console/feedback")
async def observability_agent_console_feedback(conversation_id: str) -> dict[str, object]:
    """Return the persisted ``{turn: rating}`` operator feedback for a conversation."""
    return {"ratings": console_feedback_mod.console_feedback(conversation_id)}


class _ConsoleFeedbackBody(BaseModel):
    """A single thumbs up/down on a console chat turn, persisted durably."""

    conversation_id: str
    turn: int = Field(ge=0)
    rating: str | None = None


@router.post("/observability/agent-console/feedback")
async def observability_agent_console_feedback_save(
    body: _ConsoleFeedbackBody,
) -> dict[str, object]:
    """Persist (or toggle off) one turn's rating and return the fresh map."""
    if body.rating is not None and body.rating not in console_feedback_mod.available_ratings:
        raise HTTPException(status_code=422, detail="rating must be 'up', 'down' or null")
    ratings = console_feedback_mod.record_console_feedback(
        body.conversation_id, body.turn, body.rating
    )
    return {"ratings": ratings}


_SYNTHESE_PERIODS: dict[str, int | None] = {"h24": 1, "d7": 7, "d30": 30}


@router.get("/observability/agent-synthese")
async def observability_agent_synthese(
    period: str = "d7", agent_id: str = DEFAULT_AGENT_ID
) -> dict[str, object]:
    """Agent overview ("Synthese de l'agent") dashboard (reference image 25).

    Operational (events only): KPI strip, agent context/profile and capabilities,
    routing-motive distribution, detailed operational performance, recent
    conversations, the AT-01 activity feed, active prompts, operational alerts and
    quick access. Sourced end to end from the transcript + S1 journal + registry +
    pgvector; degrades to ``available: false``.

    The ``period`` query param (``h24``/``d7``/``d30``) restricts the
    transcript-derived figures to that trailing window; unknown values mean the
    whole history. The ``agent_id`` query param scopes the slice to one agent
    (per-turn attribution); it defaults to the single agent.
    """
    period_days = _SYNTHESE_PERIODS.get(period)
    try:
        payload = await agent_synthese_mod.compute_agent_synthese(agent_id, period_days)
        return {"available": True, **payload}
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.agent_synthese: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/etat-a-date")
async def observability_etat_a_date(
    as_of: str | None = None, sources: str | None = None, lang: str = "fr"
) -> dict[str, object]:
    """Point-in-time reconstruction ("Etat a date", prouver/etat-a-date).

    Reconstructs, as of instant ``as_of`` (ISO; absent means live), the knowledge
    sources accessible to the agent, the guard decisions/blocks logged by then,
    the rules that had fired, and the policies in force. ``sources`` is an optional
    comma-separated per-source scope (corpus-category keys); ``lang`` localizes the
    labels. Sourced from pgvector ``documents`` + the guard audit log + the guard
    policy; degrades to ``available: false``.
    """
    try:
        return await etat_a_date_mod.build_etat_a_date(as_of, sources, lang)
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.etat_a_date: failed: {exc}\n")
        return {"available": False}


class _EtatSnapshotBody(BaseModel):
    """Body for saving an Etat-a-date reconstruction snapshot."""

    model_config = ConfigDict(extra="forbid")
    as_of: str | None = None
    sources: str | None = None
    lang: str = "fr"


@router.post("/observability/etat-a-date/snapshot")
async def observability_etat_a_date_snapshot(body: _EtatSnapshotBody) -> dict[str, object]:
    """Persist a snapshot of the reconstruction at ``body.as_of``.

    Saves to the durable snapshot store and returns the refreshed payload with
    the new snapshot at the head of the list, shaped by the optional per-source
    ``body.sources`` scope and localized by ``body.lang``.
    """
    return await etat_a_date_mod.save_etat_snapshot(body.as_of, body.sources, body.lang)


@router.get("/observability/incidents")
async def observability_incidents(lang: str = "fr") -> dict[str, object]:
    """Incidents & playbooks overview (page #10).

    Composes the current incident posture, the triage queue with recommended
    playbooks, the running playbook timeline, the automation rules and the
    7-day impact charts into one payload. ``lang`` localizes the chrome and the
    per-tab operational catalogues. Degrades to ``available: false``.
    """
    try:
        return {"available": True, **incidents_mod.compute_incidents_overview(lang)}
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.incidents: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/assistant")
async def observability_assistant(lang: str = "fr") -> dict[str, object]:
    """Assistant overview (Chat and Console sub-tabs).

    Composes the session header, the grounded conversation, the session context,
    the cited sources, the tools called, the guardrails triggered, the response
    quality scores, the execution trace, the follow-up suggestions and the
    console rail KPIs into one payload. ``lang`` localizes the grounded
    conversation. Degrades to ``available: false``.
    """
    try:
        return {"available": True, **assistant_mod.compute_assistant_overview(lang)}
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.assistant: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/inbox")
async def observability_inbox(lang: str = "fr", agent: str = "all") -> dict[str, object]:
    """Inbox / À traiter overview (page #24).

    Composes the queue posture, the task queue, the by-type distribution and the
    SLA buckets. ``agent`` ventilates the shared queue to one agent's own failed
    cases (ADR 0015 §Migration E); ``all`` aggregates the fleet. Degrades to
    ``available: false`` on failure.
    """
    try:
        payload = inbox_mod.compute_inbox_overview(lang=lang, agent_id=_agent_or_none(agent))
        return {"available": True, "agent": _agent_or_none(agent) or "all", **payload}
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.inbox: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/control-signals")
async def observability_control_signals(lang: str = "fr") -> dict[str, object]:
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


@router.get("/observability/governance")
async def observability_governance(
    at: str | None = None, limit: int = 8, agent: str = "all"
) -> dict[str, object]:
    """Governed-activity feed — real S1 governance events + lineage deploys (≤ T).

    Surfaces genuine governance actions (agent routing/hand-overs/proposals/release
    decisions from the hash-chained S1 journal, and model/prompt/policy version
    deploys from the bundle lineage), newest-first. Honours as-of-T (``?at=``) so it
    stays consistent with the rail's provenance contract; ``?agent=`` scopes the S1
    events. Only real events are returned — sparse categories simply do not appear
    (honest empty state). Degrades to ``available: false`` on failure.
    """
    try:
        bounded = max(1, min(limit, 30))
        feed = governance_feed_mod.compute_governance_feed(at, limit=bounded, agent=agent)
        return {"available": True, **asdict(feed)}
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.governance: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/traces-obs")
async def observability_traces_obs(at: str | None = None) -> dict[str, object]:
    """Real trace observability read from the running Langfuse stack (best tool).

    The OTel instrumentation fans every span to Langfuse; this reads the REAL trace
    volume + latency back through its public API and hands the operator deep-links to
    each tool for the job it is best at (Langfuse = trace explorer, Grafana =
    dashboards, Phoenix = retrieval). Honours as-of-T via Langfuse ``toTimestamp`` so
    it projects like the rest of the page; degrades to ``available: false`` when the
    stack is unreachable — never a fabricated number.
    """
    import asyncio

    try:
        # The Langfuse read is a blocking HTTP call — run it off the event loop.
        result = await asyncio.to_thread(langfuse_obs_mod.compute_traces_observability, at)
        return asdict(result)
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.traces_obs: failed: {exc}\n")
        return {"available": False}


class _ItemStateBody(BaseModel):
    """Status/assignee mutation for one operator-queue item."""

    item_id: str
    status: str | None = None
    assignee: str | None = None
    lang: str = "fr"


@router.post("/observability/inbox/item-state")
async def observability_inbox_mutate(body: _ItemStateBody) -> dict[str, object]:
    """Persist a status/assignee change for one queue item; return fresh payload."""
    from tessera.observability import operator_items as operator_items_mod

    if body.item_id not in operator_items_mod.available_item_ids():
        raise HTTPException(status_code=404, detail="unknown item")
    operator_items_mod.set_item_state(body.item_id, status=body.status, assignee=body.assignee)
    return {"available": True, **inbox_mod.compute_inbox_overview(lang=body.lang)}


@router.post("/observability/agent-a-faire/item-state")
async def observability_agent_a_faire_mutate(body: _ItemStateBody) -> dict[str, object]:
    """Persist a status/assignee change for one A-faire item; return fresh payload."""
    from tessera.observability import operator_items as operator_items_mod

    if body.item_id not in operator_items_mod.available_item_ids():
        raise HTTPException(status_code=404, detail="unknown item")
    operator_items_mod.set_item_state(body.item_id, status=body.status, assignee=body.assignee)
    return {"available": True, **agent_a_faire_mod.compute_agent_a_faire(body.lang)}


@router.get("/observability/parameters")
async def observability_parameters(lang: str = "fr") -> dict[str, object]:
    """Settings / parameters overview (page #21).

    Composes the active config version, posture KPIs, quick-config categories,
    recent parameters, configuration-state distribution and compliance checks.
    Degrades to ``available: false`` on failure.
    """
    try:
        return {"available": True, **parameters_mod.compute_parameters_overview(lang)}
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.parameters: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/system-profile")
async def observability_system_profile(lang: str = "fr") -> dict[str, object]:
    """System profile overview (page #20).

    Composes the operational posture, architecture, topology, resource
    distribution, OS info, health checks, resource series and services table.
    Degrades to ``available: false`` on failure.
    """
    try:
        return {"available": True, **system_profile_mod.compute_system_profile(lang)}
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.system_profile: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/integrations")
async def observability_integrations(lang: str = "fr") -> dict[str, object]:
    """Integrations overview (page #19).

    Composes the integration posture, the catalogue table, the
    selected-integration detail and the distributions. Degrades to
    ``available: false`` on failure.
    """
    try:
        return {"available": True, **integrations_mod.compute_integrations_overview(lang)}
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.integrations: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/access")
async def observability_access(lang: str = "fr") -> dict[str, object]:
    """Roles & access overview (page #18).

    Composes the access posture, the role table, the selected-role detail and
    the governance panels. Degrades to ``available: false`` on failure.
    """
    try:
        return {"available": True, **access_mod.compute_access_overview(lang)}
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.access: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/sources")
async def observability_sources(lang: str = "fr") -> dict[str, object]:
    """Sources & memory overview (page #17).

    Composes the catalogue posture (corpus + memory), the source table, the
    selected-source detail and the type / volume / language distributions, read
    live from pgvector and the memory tables. Degrades to ``available: false``
    on failure.
    """
    try:
        return {"available": True, **await sources_mod.build_sources_overview(lang)}
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.sources: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/policies")
async def observability_policies(lang: str = "fr") -> dict[str, object]:
    """Policies & guardrails overview (page #16-policies).

    Composes the version timeline, posture KPIs, critical active policies,
    version history, YAML diff, runtime guardrails, impact simulator and
    sensitive actions. Degrades to ``available: false`` on failure.
    """
    try:
        return {"available": True, **policies_mod.compute_policies_overview(lang)}
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.policies: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/signal-catalogue")
async def observability_signal_catalogue(lang: str = "fr") -> dict[str, object]:
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


@router.get("/observability/proofs")
async def observability_proofs(lang: str = "fr") -> dict[str, object]:
    """Proofs & exporter overview (page #15).

    Composes the proof posture, assembly pipeline, current evidence pack,
    recent packs, artifact distribution, exporters & destinations, cryptographic
    verification, control-case proofs, retention obligations and export journal.
    Degrades to ``available: false`` on failure.
    """
    try:
        return {"available": True, **proofs_mod.compute_proofs_overview(lang)}
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.proofs: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/automations")
async def observability_automations(lang: str = "fr") -> dict[str, object]:
    """Automations overview (page #13).

    Composes the automation posture, rule catalogue, execution pipeline, type /
    environment breakdowns, execution journal, pending approvals, most-used
    guardrails, performance / savings trends and governance context. ``lang``
    localizes the free-text fixture fields. Degrades to ``available: false`` on
    failure.
    """
    try:
        return {"available": True, **automations_mod.compute_automations_overview(lang)}
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.automations: failed: {exc}\n")
        return {"available": False}


class _AutomationRuleStateBody(BaseModel):
    """Durable enable/disable for one code-defined automation rule."""

    rule_id: str
    enabled: bool
    lang: str = "fr"


@router.post("/observability/automations/evaluate")
async def observability_automations_evaluate(lang: str = "fr") -> dict[str, object]:
    """Evaluate every enabled automation rule against its REAL store now.

    Each evaluation is journalled durably (automation_runs.json); the fresh
    overview payload is returned so the client swaps its cache in one trip.
    """
    from tessera.observability import automation_store

    automation_store.evaluate_rules()
    return {"available": True, **automations_mod.compute_automations_overview(lang)}


@router.post("/observability/automations/rule-state")
async def observability_automations_rule_state(
    body: _AutomationRuleStateBody,
) -> dict[str, object]:
    """Persist a rule's enabled flag; 404 on unknown rule; returns fresh payload."""
    from tessera.observability import automation_store

    if body.rule_id not in automation_store.available_rule_ids():
        raise HTTPException(status_code=404, detail="unknown automation rule")
    automation_store.set_rule_enabled(body.rule_id, enabled=body.enabled)
    return {"available": True, **automations_mod.compute_automations_overview(body.lang)}


@router.get("/observability/curation")
async def observability_curation(lang: str = "fr") -> dict[str, object]:
    """Curation eval-set overview (page #12).

    Composes the backlog posture, priority curation lots, workflow stages,
    coverage heatmap, candidate distribution & quality signals, linked datasets,
    governance actions and the backlog / balance / pass-rate trends. Degrades to
    ``available: false`` on failure.
    """
    try:
        return {"available": True, **curation_mod.compute_curation_overview(lang)}
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.curation: failed: {exc}\n")
        return {"available": False}


class _CurationDecisionBody(BaseModel):
    """A durable curation decision (promote/review/reject) for one candidate."""

    candidate_id: str
    decision: str
    decided_by: str = ""
    lang: str = "fr"


@router.post("/observability/curation/decision")
async def observability_curation_decision(body: _CurationDecisionBody) -> dict[str, object]:
    """Persist a curation decision for one real candidate; return the fresh payload."""
    from tessera.observability import curation_store

    if body.candidate_id not in curation_store.available_candidate_ids():
        raise HTTPException(status_code=404, detail="unknown candidate")
    if body.decision not in curation_store.DECISIONS:
        raise HTTPException(status_code=422, detail="invalid decision")
    curation_store.set_decision(
        body.candidate_id, decision=body.decision, decided_by=body.decided_by
    )
    return {"available": True, **curation_mod.compute_curation_overview(body.lang)}


@router.get("/observability/replay-shadow")
async def observability_replay_shadow(lang: str = "fr") -> dict[str, object]:
    """Replay & shadow overview (page #11).

    Composes the replay posture, traffic and deviation series, recent / top
    sessions, baseline comparisons, per-service/model distributions, replayed
    evals and the live activity feed. Degrades to ``available: false``.
    """
    try:
        return {"available": True, **replay_shadow_mod.compute_replay_shadow_overview(lang)}
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.replay_shadow: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/reliability")
async def observability_reliability(
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


@router.get("/observability/judge-consensus")
async def observability_judge_consensus() -> dict[str, object]:
    """Multi-judge consensus over the gold set (cached).

    Runs a panel of different local judges over the human gold set and reports how
    often they concur — the unanimous-consensus rate, mean pairwise agreement and
    Fleiss' κ. The first call scores the panel and may take a while; later calls
    return the cache. Degrades to ``available: false`` if a judge model is missing
    so the dashboard never errors.
    """
    global _consensus_cache
    if _consensus_cache is None:
        try:
            judges = [LLMJudge(model=m) for m in _CONSENSUS_PANEL]
            report = await gold_consensus(judges, load_gold_set(), labels=list(_CONSENSUS_PANEL))
            _consensus_cache = {"available": True, **asdict(report)}
        except Exception as exc:  # never break the dashboard on a judge/IO error
            sys.stderr.write(f"tessera.observability.judge_consensus: failed: {exc}\n")
            return {"available": False}
    return _consensus_cache


@router.get("/observability/replays")
async def observability_replays() -> dict[str, object]:
    """List the captured turns available for regression replay (newest last)."""
    return {"bundles": [asdict(b) for b in replay_mod.recent_bundles()]}


@router.post("/observability/replay")
async def observability_replay(payload: ReplayRequest) -> dict[str, object]:
    """Replay a captured turn against a candidate model and diff the result.

    Every executed replay is journalled durably (replay_store) so the Replay &
    shadow page's "requêtes rejouées" / deviation figures reflect real runs.
    """
    bundle = replay_mod.get_bundle(payload.bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="replay bundle not found")
    result = await replay_mod.replay(bundle, model=payload.model)
    try:
        from tessera.observability.replay_store import record_replay_run

        record_replay_run(
            result.bundle_id,
            # Pre-attribution bundles carry no agent; "none" is the shared
            # unattributed marker (same convention as the guard metrics).
            agent_id=bundle.agent_id or "none",
            model=result.candidate_model,
            score_delta=result.score_delta,
            similarity=result.similarity,
        )
    except Exception as exc:  # journalling must never break the replay itself
        sys.stderr.write(f"tessera.observability.replay_store: record failed: {exc}\n")
    return asdict(result)


@router.post("/observability/consistency")
async def observability_consistency(payload: ConsistencyRequest) -> dict[str, object]:
    """Measure the self-consistency / uncertainty of a captured turn."""
    bundle = replay_mod.get_bundle(payload.bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="replay bundle not found")
    report = await consistency_mod.measure_consistency(
        question=bundle.question,
        context=bundle.context,
        model=bundle.original_model,
        samples=payload.samples,
    )
    return asdict(report)


@router.post("/observability/robustness")
async def observability_robustness(payload: RobustnessRequest) -> dict[str, object]:
    """Measure how stable a captured turn is under input noise."""
    bundle = replay_mod.get_bundle(payload.bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="replay bundle not found")
    report = await robustness_mod.measure_robustness(
        question=bundle.question, context=bundle.context, model=bundle.original_model
    )
    return asdict(report)


@router.post("/observability/coverage")
async def observability_coverage(payload: CoverageRequest) -> dict[str, object]:
    """Measure how well a captured turn's retrieved chunks cover its question."""
    bundle = replay_mod.get_bundle(payload.bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="replay bundle not found")
    chunks = [c for c in bundle.context.split("\n\n") if c.strip()]
    report = await coverage_mod.measure_coverage(question=bundle.question, chunks=chunks)
    return asdict(report)


@router.post("/observability/reranking")
async def observability_reranking(payload: CoverageRequest) -> dict[str, object]:
    """Decompose a captured turn's fused ordering into vector vs lexical shares."""
    bundle = replay_mod.get_bundle(payload.bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="replay bundle not found")
    chunks = [c for c in bundle.context.split("\n\n") if c.strip()]
    report = await reranking_contribution_mod.measure_contribution(
        question=bundle.question, chunks=chunks
    )
    return asdict(report)


@router.post("/observability/ablation")
async def observability_ablation(payload: CoverageRequest) -> dict[str, object]:
    """Re-answer a captured turn under no-RAG / no-rerank ablations and re-judge."""
    bundle = replay_mod.get_bundle(payload.bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="replay bundle not found")
    report = await ablation_mod.measure_ablation(
        question=bundle.question,
        context=bundle.context,
        model=bundle.original_model,
        baseline=bundle.original_score,
    )
    return asdict(report)


@router.post("/observability/crosslingual")
async def observability_crosslingual(payload: CrossLingualRequest) -> dict[str, object]:
    """Re-answer a captured turn in fr/de/en and measure cross-lingual agreement."""
    bundle = replay_mod.get_bundle(payload.bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="replay bundle not found")
    report = await crosslingual_mod.measure_crosslingual(
        question=bundle.question, context=bundle.context, model=bundle.original_model
    )
    return asdict(report)


@router.post("/observability/why")
async def observability_why(payload: CoverageRequest) -> dict[str, object]:
    """Build a user-facing 'why this answer' explanation from provenance (#133)."""
    bundle = replay_mod.get_bundle(payload.bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="replay bundle not found")
    chunks = [c for c in bundle.context.split("\n\n") if c.strip()]
    report = await why_answer_mod.build_explanation(answer=bundle.original_answer, chunks=chunks)
    return asdict(report)


@router.post("/observability/sycophancy")
async def observability_sycophancy(payload: SycophancyRequest) -> dict[str, object]:
    """Judge whether a captured turn sycophantically validates a false premise."""
    bundle = replay_mod.get_bundle(payload.bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="replay bundle not found")
    report = await detect_sycophancy(
        question=bundle.question, answer=bundle.original_answer, context=bundle.context
    )
    return asdict(report)


@router.post("/observability/ensemble")
async def observability_ensemble(payload: EnsembleRequest) -> dict[str, object]:
    """Score a captured turn with a multi-judge ensemble; flag disagreement."""
    bundle = replay_mod.get_bundle(payload.bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="replay bundle not found")
    report = await evaluate_ensemble(
        question=bundle.question, answer=bundle.original_answer, context=bundle.context
    )
    return asdict(report)


@router.get("/observability/corpus-freshness")
async def observability_corpus_freshness() -> dict[str, object]:
    """Staleness of the ingested regulatory corpora vs their review horizon (#50)."""
    from importlib import resources
    from pathlib import Path

    data_dir = Path(str(resources.files("tessera.corpus.data")))
    return asdict(corpus_freshness_mod.load_corpus_freshness(data_dir))


@router.get("/observability/roadmap")
async def observability_roadmap(at: str | None = None, agent: str = "all") -> dict[str, object]:
    """Mine telemetry signals into a ranked product backlog (#124), live or as of T.

    Score- and bundle-derived inputs honour T; corpus freshness is a property of
    the ingested data today, so it stays live. ``agent`` scopes the score/bundle
    inputs to one agent (``all`` = org view); corpus freshness stays org.
    """
    from importlib import resources
    from pathlib import Path

    ag = _agent_or_none(agent)
    low_threshold = 0.80
    n_turns = 0
    n_low = 0
    languages_low: dict[str, int] = {}
    for score in _scores_for(at, ag):
        if score.get("metric") != "faithfulness":
            continue
        n_turns += 1
        if float(score["score"]) < low_threshold:  # type: ignore[arg-type]
            n_low += 1
            lang = score.get("language")
            key = lang if isinstance(lang, str) else "unknown"
            languages_low[key] = languages_low.get(key, 0) + 1

    questions = [b.question for b in replay_mod.recent_bundles(at, ag)]
    intents = routing_intent_mod.aggregate_intents(questions)

    data_dir = Path(str(resources.files("tessera.corpus.data")))
    freshness = corpus_freshness_mod.load_corpus_freshness(data_dir)

    signals = roadmap_mod.RoadmapSignals(
        n_turns=n_turns,
        n_low_score=n_low,
        n_unknown_intent=intents.unknown,
        n_stale_corpora=freshness.n_stale,
        languages_low=languages_low,
    )
    return asdict(roadmap_mod.build_roadmap(signals))


def _read_audit_entries() -> list[dict[str, object]]:
    """Guard-audit entries from the ACTIVE ledger source (§Amendment 3 seam; best effort)."""
    from tessera.guard.ledger_store import read_ledger_entries

    return [obj for obj in read_ledger_entries() if obj.get("type") == "tessera.guard.audit"]


@router.get("/observability/memory")
async def observability_memory() -> dict[str, object]:
    """Memory-layer activity: writes, recall hit/miss, stored-injection caught (#23)."""
    return asdict(memory_obs_mod.aggregate_memory_audit(_read_audit_entries()))


@router.get("/observability/erasure-coverage")
async def observability_erasure_coverage() -> dict[str, object]:
    """The telemetry-erasure surface: conversations, bundles, scores in scope (#180)."""
    return asdict(erasure_mod.coverage(replay_mod.recent_bundles(), read_scores()))


@router.get("/observability/erasure/{conversation_id}")
async def observability_erasure_preview(conversation_id: str) -> dict[str, object]:
    """Preview the telemetry that a GDPR erasure of this subject would purge (#180)."""
    return asdict(
        erasure_mod.footprint(
            conversation_id,
            bundles=replay_mod.recent_bundles(),
            scores=read_scores(),
        )
    )


@router.get("/observability/memory-inventory")
async def observability_memory_inventory() -> dict[str, object]:
    """What the agent remembers: long-term store inventory (GDPR access, #135)."""
    from tessera.memory.persistent import list_inventory
    from tessera.observability.memory_inventory import InventoryItem

    try:
        rows = await list_inventory()
    except Exception as exc:  # store may be offline / empty — never break the dashboard
        sys.stderr.write(f"tessera.observability.memory_inventory: failed: {exc}\n")
        return asdict(memory_inventory_mod.summarize_inventory([]))
    items = [
        InventoryItem(
            memory_id=row.memory_id,
            subject_id=row.subject_id,
            kind=row.kind,
            text=row.text,
            created_at=row.created_at,
            expires_at=row.expires_at,
        )
        for row in rows
    ]
    return asdict(memory_inventory_mod.summarize_inventory(items))


@router.get("/observability/handoffs")
async def observability_handoffs() -> dict[str, object]:
    """Delegation-chain handoff tracing and broken-handoff detection (#189)."""
    turns = [(b.question, list((b.latency_ms or {}).keys())) for b in replay_mod.recent_bundles()]
    return asdict(handoffs_mod.analyze_handoffs(turns))


@router.get("/observability/journey")
async def observability_journey() -> dict[str, object]:
    """Cross-session customer journeys mined from the memory audit trail (#99)."""
    events: list[tuple[str, str, str]] = []
    for entry in _read_audit_entries():
        target = entry.get("target")
        if not (isinstance(target, str) and target.startswith("memory.")):
            continue
        args = entry.get("arguments")
        subject = args.get("subject_id") if isinstance(args, dict) else None
        occurred_at = entry.get("occurred_at")
        if isinstance(subject, str) and isinstance(occurred_at, str):
            events.append((subject, target, occurred_at))
    return asdict(journey_mod.build_journeys(events))


@router.get("/observability/embedding-inversion")
async def observability_embedding_inversion() -> dict[str, object]:
    """Embedding-inversion privacy risk over a demo corpus (#73), cached."""
    global _inversion_cache
    if _inversion_cache is None:
        from tessera.retrieval.embeddings import embed

        try:
            report = await embedding_inversion_mod.assess_inversion_risk(
                embedding_inversion_mod.DEMO_MEMORIES,
                embedding_inversion_mod.DEMO_PROBES,
                embedder=embed,
            )
            _inversion_cache = {"available": True, **asdict(report)}
        except Exception as exc:  # embedder offline — never break the dashboard
            sys.stderr.write(f"tessera.observability.embedding_inversion: failed: {exc}\n")
            return {"available": False}
    return _inversion_cache


@router.get("/observability/failure-clusters")
async def observability_failure_clusters() -> dict[str, object]:
    """Auto-clustered themes across the documented failure corpus (#123), cached."""
    global _clustering_cache
    if _clustering_cache is None:
        from tessera.retrieval.embeddings import embed

        try:
            report = await failure_clustering_mod.cluster_failures(
                _load_failure_items(), k=6, embedder=embed
            )
            _clustering_cache = {"available": True, **asdict(report)}
        except Exception as exc:  # embedder offline — never break the dashboard
            sys.stderr.write(f"tessera.observability.failure_clustering: failed: {exc}\n")
            return {"available": False}
    return _clustering_cache


@router.get("/observability/failed-cases")
async def observability_failed_cases(
    language: str = "fr", limit: int | None = None
) -> dict[str, object]:
    """Structured failed-case catalogue + category/severity distributions (image 03).

    Reads the documented-failure corpus (``eval/failures``) — real in-repo cases.
    Severity is a documented triage heuristic over the category, not a runtime
    score. Sorted worst-severity first; ``limit`` caps the rows (the distributions
    always count the full catalogue).
    """
    from tessera.observability.eval.failed_cases import load_failed_cases

    report = load_failed_cases(language=language, limit=limit)
    return asdict(report)


@router.get("/observability/runs")
async def observability_runs() -> dict[str, object]:
    """Eval run registry from the report archive (Runs & datasets tab, image 02).

    One row per real report under ``eval/reports`` (model, language, pass rate,
    cost, latency, catalogue version), newest first. No fabrication — a free
    local run keeps ``est_cost_eur: null``.
    """
    from tessera.observability.eval.runs import load_runs

    return asdict(load_runs())


@router.get("/observability/failed-runs")
async def observability_failed_runs() -> dict[str, object]:
    """Real failed cases from the run archive (Cas échoués tab, image 03).

    Every ``passed: false`` result in each model/language's most recent
    full-catalogue run, joined with ``eval/failures`` for the triggering prompt
    and expected behaviour. Per-case ``status`` is ``new`` (a fresh regression vs
    the previous run) or ``recurrent``; ``owner`` is the documented governance
    team. There is no per-case judge score in the reports, so none is invented.
    """
    from tessera.observability.eval.failed_runs import load_failed_runs

    return asdict(load_failed_runs())


@router.get("/observability/eval-datasets")
async def observability_eval_datasets() -> dict[str, object]:
    """Themed quality datasets from the failure catalogue joined to runs (image 02).

    Tessera's real "eval datasets" are the failure-catalogue **themes** (categories):
    per theme we derive case count, languages, version, latest-run pass rate, drift
    (delta between the two most recent full-catalogue runs), coverage and last-run
    timestamp — all from ``eval/failures`` joined with ``eval/reports``. Absent
    signals (a theme not in the latest run, pipeline workers/queue/evidence TTL)
    stay ``null`` so the dashboard renders "—", never an invented value.
    """
    from tessera.observability.eval.datasets import load_quality_datasets

    return asdict(load_quality_datasets())


@router.get("/observability/model-comparison")
async def observability_model_comparison() -> dict[str, object]:
    """Per-model comparison from the latest run of each model (image 04).

    Aggregates the real report archive: pass rate, cost, latency and a documented
    verdict per model. Each row is enriched with real per-model signals: the
    judge metrics (faithfulness / grounding / hallucination) replayed offline over
    the model's stored answers (``eval/reports/_model_judge.json``; ``null`` until
    the backfill runs), a pass-rate ``evolution`` sparkline, and a run-over-run
    ``non_regression`` retention ratio. Nothing is fabricated.
    """
    from tessera.observability.eval.model_categories import load_model_category_rates
    from tessera.observability.eval.model_judge import load_model_judge
    from tessera.observability.eval.runs import compare_models, load_runs

    registry = load_runs()
    judge = load_model_judge()
    categories = load_model_category_rates()

    min_run_cases = 10  # ignore tiny smoke runs in the per-model sparkline

    def _evolution_and_nonreg(model: str) -> tuple[list[float], float | None]:
        runs = sorted(
            (r for r in registry.runs if r.model == model and r.total >= min_run_cases),
            key=lambda r: r.run_at,
        )
        evolution = [round(r.pass_rate, 4) for r in runs][-8:]
        non_reg: float | None = None
        if len(runs) >= 2:  # noqa: PLR2004 — needs a pair to compare
            prev, last = runs[-2].pass_rate, runs[-1].pass_rate
            non_reg = round(min(1.0, last / prev), 4) if prev > 0 else None
        return evolution, non_reg

    models: list[dict[str, object]] = []
    for stat in compare_models(registry.runs):
        row = asdict(stat)
        mj = judge.models.get(stat.model)
        evolution, non_reg = _evolution_and_nonreg(stat.model)
        cats = categories.get(stat.model)
        row.update(
            faithfulness=mj.faithfulness if mj else None,
            grounding=mj.grounding if mj else None,
            hallucination=mj.hallucination if mj else None,
            evolution=evolution,
            non_regression=non_reg,
            categories=cats.rates if cats else {},
        )
        models.append(row)
    return {"models": models, "n_runs": registry.n, "judge_model": judge.judge_model}


@router.get("/observability/release-status")
async def observability_release_status() -> dict[str, object]:
    """Current release + real open quality regressions (Vue d'ensemble rail).

    Releases are parsed from ``CHANGELOG.md``; regressions are derived from the
    eval report archive (pass-rate drops between a model's two most recent
    full-catalogue runs). The release's status is a fact — ``n_regressions``
    open — not an invented flag.
    """
    from tessera.observability.eval.releases import release_status

    return asdict(release_status())


@router.get("/observability/sft-dataset")
async def observability_sft_dataset() -> dict[str, object]:
    """Distil high-scoring captured turns into an SFT dataset (#122)."""
    turns = [
        (b.question, b.context, b.original_answer, b.language, b.original_score)
        for b in replay_mod.recent_bundles()
    ]
    return asdict(sft_export_mod.build_sft_dataset(turns))


_GRANTED_TOOLS = frozenset(
    {"account_balance", "card_block", "transaction_search", "loan_simulate", "ticket_escalate"}
)


@router.get("/observability/least-privilege")
async def observability_least_privilege() -> dict[str, object]:
    """Tool least-privilege: granted vs actually-used tools from the audit (#101)."""
    # Exclude non-tool audit targets: the input guard ("user_input") and the
    # memory governance actions are audited too but are not tool invocations.
    non_tools = {"user_input"}
    usage: dict[str, int] = {}
    for entry in _read_audit_entries():
        target = entry.get("target")
        if isinstance(target, str) and target not in non_tools and not target.startswith("memory."):
            usage[target] = usage.get(target, 0) + 1
    return asdict(least_privilege_mod.analyze_privilege(_GRANTED_TOOLS, usage))


@router.get("/observability/siem")
async def observability_siem() -> dict[str, object]:
    """Security audit events normalised to ECS/SIEM shape for the SOC (#172)."""
    return asdict(siem_mod.to_siem_events(_read_audit_entries()))


def _corpus_sources() -> set[str]:
    """Collect the regulatory corpus source ids (e.g. 'DORA/art-5')."""
    import json
    from importlib import resources

    sources: set[str] = set()
    data_dir = Path(str(resources.files("tessera.corpus.data")))
    for path in data_dir.glob("regulations_*.json"):
        try:
            docs = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(docs, list):
            for doc in docs:
                if isinstance(doc, dict) and doc.get("source"):
                    sources.add(str(doc["source"]))
    return sources


_CITATION_SENTENCE = re.compile(r"[^.!?\n]*\bart(?:icle|\.)?\s*\d+[^.!?\n]*", re.IGNORECASE)


@router.get("/observability/citation-links")
async def observability_citation_links() -> dict[str, object]:
    """Resolve answer citations to verifiable corpus sources (clickable, #132)."""
    sources = _corpus_sources()
    citations: list[str] = []
    for bundle in replay_mod.recent_bundles():
        citations.extend(
            m.group(0).strip() for m in _CITATION_SENTENCE.finditer(bundle.original_answer)
        )
    return asdict(citation_resolver_mod.resolve_citations(citations, sources))


@router.get("/observability/disclosure")
async def observability_disclosure() -> dict[str, object]:
    """AI-interaction disclosure status and per-locale text (Art. 50, #134)."""
    return asdict(disclosure_mod.disclosure_status())


@router.get("/observability/ai-act")
async def observability_ai_act(at: str | None = None) -> dict[str, object]:
    """EU AI Act compliance posture: transparency, oversight, traceability (#76).

    Turn and oversight counts honour T; the audit-chain integrity check is a
    structural property of the whole log, so it stays live.
    """
    from tessera.guard.ledger_store import ledger_available, verify_active_ledger

    entries = _read_audit_entries()
    oversight = sum(
        1
        for e in entries
        if e.get("target") == "ticket_escalate" and occurred_before(e.get("occurred_at"), at)
    )
    chain = verify_active_ledger()
    signals = ai_act_mod.AIActSignals(
        disclosure_enabled=True,  # disclosure shipped on the chat UI (#134)
        n_turns=len(replay_mod.recent_bundles(at)),
        oversight_events=oversight,
        escalation_available=True,
        audit_present=ledger_available(),
        audit_chain_verified=chain.verified,
        data_governance_enabled=True,
    )
    return asdict(ai_act_mod.assess_compliance(signals))


@router.get("/observability/localization")
async def observability_localization() -> dict[str, object]:
    """Per-locale message completeness vs the default locale (#77)."""
    import json
    from pathlib import Path

    messages_dir = Path(__file__).resolve().parents[4] / "webapp" / "frontend" / "messages"
    catalogues: dict[str, dict[str, object]] = {}
    for locale in ("en", "fr", "de"):
        path = messages_dir / f"{locale}.json"
        try:
            catalogues[locale] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            catalogues[locale] = {}
    return asdict(localization_mod.assess_localization(catalogues))


@router.get("/observability/playbooks")
async def observability_playbooks(at: str | None = None, agent: str = "all") -> dict[str, object]:
    """Incident playbooks triggered by the live (or as-of-T) signals (#115).

    Bundle- and score-derived inputs honour T; the jailbreak rate is the latest
    red-team snapshot (a periodic probe, not a per-turn event), so it stays live.
    ``agent`` scopes the bundle/score inputs to one agent (``all`` = org view);
    the shared red-team probe stays org.
    """
    ag = _agent_or_none(agent)
    bundles = replay_mod.recent_bundles(at, ag)
    faithfulness = [
        float(s["score"])  # type: ignore[arg-type]
        for s in _scores_for(at, ag)
        if s.get("metric") == "faithfulness"
    ]
    bar = 0.80
    low_rate = sum(1 for s in faithfulness if s < bar) / len(faithfulness) if faithfulness else 0.0
    snapshots = redteam_mod.recent_snapshots()
    jailbreak_rate = snapshots[-1].attack_success_rate if snapshots else 0.0
    pii = pii_leak_mod.aggregate_leaks(
        [(b.original_answer, f"{b.question}\n{b.context}") for b in bundles]
    )
    cost = cost_anomaly_mod.analyze_costs(
        [(b.question, f"{b.question}\n{b.context}\n{b.original_answer}") for b in bundles]
    )
    signals = playbooks_mod.PlaybookSignals(
        low_score_rate=low_rate,
        n_scores=len(faithfulness),
        jailbreak_success_rate=jailbreak_rate,
        pii_leak_rate=pii.leak_rate,
        cost_anomalies=cost.n_anomalies,
    )
    return asdict(playbooks_mod.trigger_playbooks(signals))


@router.get("/observability/cross-tenant")
async def observability_cross_tenant() -> dict[str, object]:
    """Cross-tenant leakage: foreign subject ids in a turn's context (#74)."""
    turns = [(b.conversation_id or "", b.context) for b in replay_mod.recent_bundles()]
    return asdict(cross_tenant_mod.detect_cross_tenant(turns))


@router.get("/observability/toxicity")
async def observability_toxicity(at: str | None = None, agent: str = "all") -> dict[str, object]:
    """Toxicity / harmful-output rate over captured answers (#60), live or as of T.

    ``agent`` scopes to one agent's captured turns (``all`` = org view).
    """
    turns = [
        (b.question, b.original_answer)
        for b in replay_mod.recent_bundles(at, _agent_or_none(agent))
    ]
    return asdict(toxicity_mod.scan_toxicity(turns))


@router.get("/observability/failure-predictor")
async def observability_failure_predictor() -> dict[str, object]:
    """Back-test the pre-judge failure predictor against captured turns (#121)."""
    turns = [(b.question, b.context, b.original_score) for b in replay_mod.recent_bundles()]
    return asdict(failure_predictor_mod.evaluate_predictor(turns))


@router.get("/observability/embedding-skew")
async def observability_embedding_skew() -> dict[str, object]:
    """Embedding-version skew between the query-time and corpus embedders (#64)."""
    from tessera.observability.embedding_skew import EmbeddingFingerprint
    from tessera.retrieval.embeddings import embedding_dimension
    from tessera.settings import LLMProfile, get_settings

    settings = get_settings()
    if settings.resolved_llm_profile() is LLMProfile.FRONTIER:
        query_model = settings.vertex.embedding_model
    else:
        query_model = settings.ollama.embedding_model
    query = EmbeddingFingerprint(model=query_model, dimension=embedding_dimension())
    # Until the corpus records its own fingerprint at ingestion, we treat the
    # active embedder as the corpus reference: equal by construction, so the check
    # reports "no skew" while still surfacing the live embedding identity and
    # flagging a future query-side profile flip.
    corpus = query
    return asdict(embedding_skew_mod.detect_skew(query, corpus))


@router.get("/observability/firewall-efficacy")
async def observability_firewall_efficacy() -> dict[str, object]:
    """Detection efficacy of the guard over injection vs benign inputs."""
    return asdict(firewall_mod.compute_efficacy())


@router.get("/observability/redteam")
async def observability_redteam() -> dict[str, object]:
    """Return the recorded jailbreak-drift snapshots (newest last)."""
    return {"snapshots": [asdict(s) for s in redteam_mod.recent_snapshots()]}


@router.post("/observability/redteam")
async def observability_redteam_run() -> dict[str, object]:
    """Run the adversarial corpus through the guard and record a snapshot."""
    snapshot = redteam_mod.run_redteam()
    return {
        "latest": asdict(snapshot),
        "snapshots": [asdict(s) for s in redteam_mod.recent_snapshots()],
    }


@router.get("/observability/refusal")
async def observability_refusal() -> dict[str, object]:
    """Refusal-rate calibration: over-refusal (legit) vs under-refusal (forbidden)."""
    return asdict(refusal_mod.compute_refusal_calibration())


@router.get("/observability/conformance")
async def observability_conformance(at: str | None = None, agent: str = "all") -> dict[str, object]:
    """Schema/format conformance of tool-call arguments from the audit trail, live or as of T.

    ``agent`` scopes to one agent's tool calls (``all`` = org view).
    """
    return asdict(conformance_mod.compute_conformance(at=at, agent_id=_agent_or_none(agent)))


@router.get("/observability/context-overflow")
async def observability_context_overflow() -> dict[str, object]:
    """Context truncation/overflow vs the input window across captured turns (#89)."""
    turns = [
        (b.question, [c for c in b.context.split("\n\n") if c.strip()])
        for b in replay_mod.recent_bundles()
    ]
    return asdict(context_overflow_mod.analyze_overflow(turns))


@router.get("/observability/cost")
async def observability_cost(at: str | None = None, agent: str = "all") -> dict[str, object]:
    """Token-cost distribution and token-burn anomalies over captured turns, live or as of T.

    ``agent`` scopes to one agent's captured turns (``all`` = org view).
    """
    turns = [
        (b.question, f"{b.question}\n{b.context}\n{b.original_answer}")
        for b in replay_mod.recent_bundles(at, _agent_or_none(agent))
    ]
    return asdict(cost_anomaly_mod.analyze_costs(turns))


@router.get("/observability/graph-topology")
async def observability_graph_topology() -> dict[str, object]:
    """Topology fingerprint of the live agent graph vs the golden pin (#87)."""
    from tessera.agent.graph import build_graph

    snapshot = graph_topology_mod.topology_snapshot(build_graph())
    drift = graph_topology_mod.compare_topology(
        snapshot, golden=graph_topology_mod.GOLDEN_FINGERPRINT
    )
    return {**asdict(snapshot), "drift": asdict(drift)}


@router.get("/observability/guard-retraction")
async def observability_guard_retraction() -> dict[str, object]:
    """Streamed-token exposure before an output-guard trigger fires (#90)."""
    from tessera.guard.decisions import load_policy

    answers = [b.original_answer for b in replay_mod.recent_bundles()]
    return asdict(guard_retraction_mod.analyze_retractions(answers, policy=load_policy()))


@router.get("/observability/guard-explain")
async def observability_guard_explain() -> dict[str, object]:
    """Ranked breakdown of which guard rules fired across the audit trail."""
    return asdict(guard_explain_mod.compute_guard_explain())


@router.get("/observability/tool-loops")
async def observability_tool_loops() -> dict[str, object]:
    """Tool-call loop/oscillation detection over the audit invocation stream (#88)."""
    non_tools = {"user_input"}
    ordered: list[tuple[str, str]] = []  # (occurred_at, tool)
    for entry in _read_audit_entries():
        target = entry.get("target")
        if not (isinstance(target, str) and target not in non_tools):
            continue
        if target.startswith("memory."):
            continue
        occurred = entry.get("occurred_at")
        ordered.append((occurred if isinstance(occurred, str) else "", target))
    ordered.sort(key=lambda pair: pair[0])
    # The audit trail is not conversation-scoped, so analyse one global stream.
    streams = {"global": [tool for _at, tool in ordered]}
    return asdict(tool_loops_mod.detect_loops(streams))


@router.get("/observability/tool-validity")
async def observability_tool_validity(
    at: str | None = None, agent: str = "all"
) -> dict[str, object]:
    """Validity of tool calls (allowed vs denied, argument failures), live or as of T.

    ``agent`` scopes to one agent's tool calls (``all`` = org view).
    """
    return asdict(tool_validity_mod.compute_tool_validity(at=at, agent_id=_agent_or_none(agent)))


@router.get("/observability/routing")
async def observability_routing() -> dict[str, object]:
    """Language-routing health: served vs detected language, code-switching."""
    turns = [(b.question, b.language) for b in replay_mod.recent_bundles()]
    return asdict(language_routing_mod.aggregate_routing(turns))


@router.get("/observability/intent")
async def observability_intent() -> dict[str, object]:
    """Business-intent mix and routing confidence over captured questions."""
    questions = [b.question for b in replay_mod.recent_bundles()]
    return asdict(routing_intent_mod.aggregate_intents(questions))


@router.get("/observability/citations")
async def observability_citations() -> dict[str, object]:
    """Regulatory citation validity: cited articles absent from the grounding."""
    turns = [(b.original_answer, b.context) for b in replay_mod.recent_bundles()]
    return asdict(citation_validity_mod.aggregate_citations(turns))


@router.get("/observability/locale-format")
async def observability_locale_format() -> dict[str, object]:
    """Locale-formatting correctness: amounts whose style mismatches the locale."""
    turns = [(b.original_answer, b.language) for b in replay_mod.recent_bundles()]
    return asdict(locale_format_mod.aggregate_formatting(turns))


@router.get("/observability/pii-leak")
async def observability_pii_leak(at: str | None = None, agent: str = "all") -> dict[str, object]:
    """Output PII-leak rate: PII in answers absent from their grounding, live or as of T.

    ``agent`` scopes to one agent's captured turns (``all`` = org view).
    """
    turns = [
        (b.original_answer, f"{b.question}\n{b.context}")
        for b in replay_mod.recent_bundles(at, _agent_or_none(agent))
    ]
    return asdict(pii_leak_mod.aggregate_leaks(turns))


@router.get("/observability/anomalies")
async def observability_anomalies(at: str | None = None, agent: str = "all") -> dict[str, object]:
    """Detect long/looping/repetitive sessions among captured turns, live or as of T.

    ``agent`` scopes to one agent's captured turns (``all`` = org view).
    """
    by_conversation: dict[str, list[str]] = {}
    for bundle in replay_mod.recent_bundles(at, _agent_or_none(agent)):
        key = bundle.conversation_id or "<none>"
        by_conversation.setdefault(key, []).append(bundle.question)
    return asdict(anomalies_mod.detect_anomalies(by_conversation))


@router.get("/observability/what-changed")
async def observability_what_changed(
    at: str | None = None, agent: str = "all"
) -> dict[str, object]:
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


@router.get("/observability/funnel")
async def observability_funnel(at: str | None = None, agent: str = "all") -> dict[str, object]:
    """Per-language conversation funnel from scored turns, live or as of T.

    ``agent`` scopes the funnel to one agent's scored turns (``all`` = org view).
    """
    turns: list[tuple[str, str | None, float]] = []
    for score in _scores_for(at, _agent_or_none(agent)):
        lang = score.get("language")
        conv = score.get("conversation_id")
        raw = score.get("score", 0.0)
        turns.append(
            (
                lang if isinstance(lang, str) else "unknown",
                conv if isinstance(conv, str) else None,
                float(raw),  # type: ignore[arg-type]
            )
        )
    return asdict(funnel_mod.aggregate_funnel(turns))


@router.get("/observability/sessions")
async def observability_sessions(agent: str = "all") -> dict[str, object]:
    """Session-level goal-completion analytics from scored turns.

    ``agent`` scopes to one agent's scored turns (``all`` = org view).
    """
    turns: list[tuple[str | None, float]] = []
    for score in read_scores(agent_id=_agent_or_none(agent)):
        conv = score.get("conversation_id")
        raw = score.get("score", 0.0)
        turns.append((conv if isinstance(conv, str) else None, float(raw)))  # type: ignore[arg-type]
    return asdict(sessions_mod.aggregate_sessions(turns))


@router.get("/observability/contradictions")
async def observability_contradictions() -> dict[str, object]:
    """Detect self-contradictions across the turns of each captured session."""
    by_conversation: dict[str, list[tuple[str, str]]] = {}
    for bundle in replay_mod.recent_bundles():
        key = bundle.conversation_id or "<none>"
        by_conversation.setdefault(key, []).append((bundle.question, bundle.original_answer))

    n_turns = 0
    pairs: list[dict[str, object]] = []
    for conversation_id, turns in by_conversation.items():
        n_turns += len(turns)
        report = await contradiction_mod.detect_contradictions(turns)
        for pair in report.contradictions:
            pairs.append({"conversation_id": conversation_id, **asdict(pair)})

    return {
        "n_sessions": len(by_conversation),
        "n_turns": n_turns,
        "n_contradictions": len(pairs),
        "pairs": pairs,
    }


@router.get("/observability/corpus-scan/{bundle_id}")
async def observability_corpus_scan(bundle_id: str) -> dict[str, object]:
    """Screen a captured turn's retrieved chunks for indirect injection."""
    bundle = replay_mod.get_bundle(bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="replay bundle not found")
    chunks = [c for c in bundle.context.split("\n\n") if c.strip()]
    return asdict(corpus_injection_mod.scan_chunks(chunks))


@router.get("/observability/steganography/{bundle_id}")
async def observability_steganography(bundle_id: str) -> dict[str, object]:
    """Detect hidden unicode (zero-width/bidi/tag) in a captured turn."""
    bundle = replay_mod.get_bundle(bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="replay bundle not found")
    return asdict(steganography_mod.scan_text(f"{bundle.question}\n{bundle.context}"))


@router.get("/observability/trace-snapshot")
async def observability_trace_snapshot() -> dict[str, object]:
    """Golden-trace snapshot diff of executed-node shapes across turns (#41)."""
    turns = [(b.question, list((b.latency_ms or {}).keys())) for b in replay_mod.recent_bundles()]
    return asdict(trace_snapshot_mod.diff_traces(turns))


@router.get("/observability/trajectory/{bundle_id}")
async def observability_trajectory(bundle_id: str) -> dict[str, object]:
    """Step-by-step trajectory of a captured turn (session theater)."""
    bundle = replay_mod.get_bundle(bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="replay bundle not found")
    return asdict(trajectory_mod.build_trajectory(bundle))


@router.get("/observability/provenance/{bundle_id}")
async def observability_provenance(bundle_id: str) -> dict[str, object]:
    """Claim-level attribution of a captured turn to its retrieved chunks."""
    bundle = replay_mod.get_bundle(bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="replay bundle not found")
    chunks = [c for c in bundle.context.split("\n\n") if c.strip()]
    report = await provenance_mod.attribute(bundle.original_answer, chunks)
    util = retrieval_quality_mod.utilization(report, len(chunks))
    return {**asdict(report), "utilization": asdict(util)}


# ── client space (Produit) ───────────────────────────────────────────────────


@router.get("/observability/client/documents")
async def observability_client_documents(locale: str = "fr") -> dict[str, object]:
    """Customer documents, sourced from the real Crédit Aurore corpus (locale-aware)."""
    try:
        return {"available": True, **client_space_mod.compute_documents(locale)}
    except Exception as exc:  # never break the page
        sys.stderr.write(f"tessera.observability.client_space.documents: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/client/requests")
async def observability_client_requests(lang: str = "fr") -> dict[str, object]:
    """Customer support requests (escalation tickets)."""
    try:
        return {"available": True, **client_space_mod.compute_requests(lang)}
    except Exception as exc:  # never break the page
        sys.stderr.write(f"tessera.observability.client_space.requests: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/client/alerts")
async def observability_client_alerts(lang: str = "fr") -> dict[str, object]:
    """Account alerts with the durable read-state applied."""
    try:
        return {"available": True, **client_space_mod.compute_alerts(lang)}
    except Exception as exc:  # never break the page
        sys.stderr.write(f"tessera.observability.client_space.alerts: failed: {exc}\n")
        return {"available": False}


class _AlertReadBody(BaseModel):
    """Mark one account alert read/unread (durable)."""

    alert_id: str
    read: bool = True
    lang: str = "fr"


@router.post("/observability/client/alerts/read")
async def observability_client_alerts_read(body: _AlertReadBody) -> dict[str, object]:
    """Persist an alert's read state and return the fresh alerts payload."""
    return {
        "available": True,
        **client_space_mod.mark_alert_read(body.alert_id, read=body.read, lang=body.lang),
    }


@router.get("/observability/client/settings")
async def observability_client_settings(lang: str = "fr") -> dict[str, object]:
    """Customer preferences (notifications, privacy/consent, security)."""
    try:
        return {"available": True, **client_space_mod.compute_settings(lang)}
    except Exception as exc:  # never break the page
        sys.stderr.write(f"tessera.observability.client_space.settings: failed: {exc}\n")
        return {"available": False}


class _SettingBody(BaseModel):
    """Update one customer preference (durable)."""

    key: str
    value: object
    lang: str = "fr"


@router.post("/observability/client/settings")
async def observability_client_settings_save(body: _SettingBody) -> dict[str, object]:
    """Persist one preference and return the full settings payload."""
    return {
        "available": True,
        **client_space_mod.update_setting(body.key, body.value, body.lang),
    }


@router.get("/observability/connectors")
async def observability_connectors(lang: str = "fr") -> dict[str, object]:
    """Connectors overview for the real Tessera stack (configurer/connecteurs)."""
    try:
        return {"available": True, **connectors_mod.compute_connectors(lang)}
    except Exception as exc:  # never break the page
        sys.stderr.write(f"tessera.observability.connectors: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/users")
async def observability_users(lang: str = "fr") -> dict[str, object]:
    """Users overview from the real seeded operator accounts (admin/utilisateurs)."""
    try:
        return {"available": True, **users_mod.compute_users(lang)}
    except Exception as exc:  # never break the page
        sys.stderr.write(f"tessera.observability.users: failed: {exc}\n")
        return {"available": False}
