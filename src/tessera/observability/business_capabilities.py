"""Per-capability business aggregate for the Métier surface (ADR 0017 §A1.4)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from tessera.agent.registry import get_agent
from tessera.observability import business_events, business_scoring, turn_evidence
from tessera.observability.agent_release import agent_release_state
from tessera.observability.agentspec_projection import (
    business_signal_descriptors,
    declared_observability_level,
    observability_level,
)
from tessera.observability.spine.adapters import fact_source

if TYPE_CHECKING:
    from collections.abc import Mapping

    from tessera.agent.registry import Agent
    from tessera.observability.turn_evidence import TurnEvidence

__all__ = [
    "UNKNOWN_CAPABILITY_ID",
    "UNKNOWN_CAPABILITY_LABEL",
    "LevelResolution",
    "business_capability_aggregate",
    "declares_external_effects",
    "resolve_level_state",
    "resolve_observability_level",
]

UNKNOWN_CAPABILITY_ID = "—"
UNKNOWN_CAPABILITY_LABEL = "non attribué"
_MIN_TREND_POINTS = 2
_EXTERNAL_EFFECT_LEVELS = frozenset({"requires_validation", "external_action"})
_PREVENTED_EFFECT_EVENTS = frozenset({"action.blocked", "validation.requested"})
_CONFORMITY_EXCLUDED_METRICS = frozenset({"recouvrement_trace_completeness"})


def _payload(row: Mapping[str, object]) -> Mapping[str, object]:
    raw = row.get("payload")
    return raw if isinstance(raw, dict) else {}


def _capability(row: Mapping[str, object]) -> str:
    raw = row.get("capability_id")
    return raw if isinstance(raw, str) and raw else UNKNOWN_CAPABILITY_ID


def _run_key(row: Mapping[str, object]) -> tuple[str, str]:
    conversation_id = row.get("conversation_id")
    turn_id = row.get("turn_id")
    return (
        conversation_id if isinstance(conversation_id, str) else "",
        turn_id if isinstance(turn_id, str) else "",
    )


def _timestamp(row: Mapping[str, object]) -> datetime | None:
    raw = row.get("timestamp")
    if not isinstance(raw, str) or not raw:
        return None
    try:
        stamp = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if stamp.tzinfo is None:
        return stamp.replace(tzinfo=UTC)
    return stamp.astimezone(UTC)


def _pct(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round((numerator / denominator) * 100, 1)


def _mean_pct(values: list[float]) -> float | None:
    if not values:
        return None
    return round((sum(values) / len(values)) * 100, 1)


def _rows_by_run(rows: list[dict[str, object]]) -> list[list[dict[str, object]]]:
    grouped: dict[tuple[str, str], list[dict[str, object]]] = {}
    for row in rows:
        grouped.setdefault(_run_key(row), []).append(row)
    return list(grouped.values())


def _trend(rows: list[dict[str, object]]) -> dict[str, object]:
    """Return a tiny real trend over the first/last dated buckets, or honest-empty."""
    buckets: dict[str, set[tuple[str, str]]] = {}
    for row in rows:
        stamp = _timestamp(row)
        if stamp is None:
            continue
        buckets.setdefault(stamp.date().isoformat(), set()).add(_run_key(row))
    bucket_counts = [(bucket, len(run_keys)) for bucket, run_keys in sorted(buckets.items())]
    points = [{"bucket": bucket, "volume": volume} for bucket, volume in bucket_counts]
    if len(points) < _MIN_TREND_POINTS:
        return {
            "available": False,
            "direction": "insufficient_data",
            "delta_pct": None,
            "points": points,
        }
    first = bucket_counts[0][1]
    last = bucket_counts[-1][1]
    delta = None if first == 0 else round(((last - first) / first) * 100, 1)
    direction = "up" if last > first else ("down" if last < first else "flat")
    return {"available": True, "direction": direction, "delta_pct": delta, "points": points}


def _agent(agent_id: str | None) -> Agent | None:
    if not agent_id:
        return None
    try:
        return get_agent(agent_id)
    except KeyError:
        return None


def _manifest_capabilities(agent_id: str | None) -> list[dict[str, object]]:
    agent = _agent(agent_id)
    if agent is None:
        return []
    if agent.observability is None:
        return []
    return [
        {
            "capability_id": capability.id,
            "label_key": capability.label_key,
            "external_effect_level": capability.external_effect_level.value,
        }
        for capability in agent.observability.capabilities
    ]


def _score_conformity(rows: list[dict[str, object]]) -> float | None:
    scored_values: list[float] = []
    for run_rows in _rows_by_run(rows):
        for score in business_scoring.score_rows(run_rows):
            raw_score = score.get("score")
            if (
                str(score.get("metric")) not in _CONFORMITY_EXCLUDED_METRICS
                and score.get("status") == "scored"
                and isinstance(raw_score, int | float)
            ):
                scored_values.append(float(raw_score))
    return _mean_pct(scored_values)


def _score_by_metric(rows: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    return {str(score.get("metric")): score for score in business_scoring.score_rows(rows)}


def _aggregate_run_score(metric: str, rows: list[dict[str, object]]) -> dict[str, object] | None:
    run_scores = [
        score
        for run_rows in _rows_by_run(rows)
        if (score := _score_by_metric(run_rows).get(metric)) is not None
    ]
    scored_values: list[float] = []
    for score in run_scores:
        raw_score = score.get("score")
        if score.get("status") == "scored" and isinstance(raw_score, int | float):
            scored_values.append(float(raw_score))
    if scored_values:
        unique_values = set(scored_values)
        scored_reasons = [
            str(score.get("reason"))
            for score in run_scores
            if score.get("status") == "scored" and isinstance(score.get("score"), int | float)
        ]
        reason = (
            scored_reasons[-1] if len(unique_values) == 1 and scored_reasons else "scored_runs_mean"
        )
        return {
            "metric": metric,
            "score": sum(scored_values) / len(scored_values),
            "status": "scored",
            "reason": reason,
        }
    for status in ("unknown", "not_applicable"):
        match = next((score for score in run_scores if score.get("status") == status), None)
        if match is not None:
            return match
    return None


def _signal_evidence(metric: str, rows: list[dict[str, object]]) -> dict[str, object]:
    """What we actually know about ``metric``, independent of whether it scored.

    Punch-list P3 item 18: a signal that is not *decisive* still has a record — how many runs
    the scorer examined, how many of those it could actually score, and when it last looked.
    Rendering that beats rendering a dash, and none of it is inferred: ``observed_runs`` and
    ``checks`` are counted from the same runs :func:`_aggregate_run_score` aggregates, and
    ``last_checked_at`` is the newest real event timestamp among them. A metric no run ever
    produced yields zeros and ``None`` — the genuine zero-data case, which keeps its dash.
    """
    observed_runs = 0
    checks = 0
    last_seen: datetime | None = None
    for run_rows in _rows_by_run(rows):
        score = _score_by_metric(run_rows).get(metric)
        if score is None:
            continue
        observed_runs += 1
        if score.get("status") == "scored" and isinstance(score.get("score"), int | float):
            checks += 1
        for row in run_rows:
            stamp = _timestamp(row)
            if stamp is not None and (last_seen is None or stamp > last_seen):
                last_seen = stamp
    return {
        "observed_runs": observed_runs,
        "checks": checks,
        "last_checked_at": last_seen.isoformat() if last_seen is not None else None,
    }


def _prevents_external_effect(
    row: Mapping[str, object],
    *,
    external_effect_level: str | None,
) -> bool:
    if row.get("event_name") in _PREVENTED_EFFECT_EVENTS:
        return True
    return (
        external_effect_level in _EXTERNAL_EFFECT_LEVELS
        and row.get("event_name") == "action.prepared"
        and row.get("decision") == "prepared"
    )


def _row_for_capability(
    *,
    capability_id: str,
    label_key: str | None,
    external_effect_level: str | None,
    rows: list[dict[str, object]],
) -> dict[str, object]:
    runs = {_run_key(row) for row in rows}
    volume = len(runs)
    validation_runs = {
        _run_key(row)
        for row in rows
        if row.get("event_name") == "validation.requested"
        or row.get("decision") == "validation_required"
        or _payload(row).get("requires_validation") is True
    }
    blocked_runs = {
        _run_key(row)
        for row in rows
        if row.get("event_name") == "action.blocked" or row.get("decision") == "blocked"
    }
    external_effects_prevented = sum(
        1
        for row in rows
        if _prevents_external_effect(row, external_effect_level=external_effect_level)
    )
    return {
        "capability_id": capability_id,
        "label_key": label_key,
        "label": UNKNOWN_CAPABILITY_LABEL if capability_id == UNKNOWN_CAPABILITY_ID else None,
        "external_effect_level": external_effect_level,
        "volume": volume,
        "conformity_pct": _score_conformity(rows),
        "validation_required_pct": _pct(len(validation_runs), volume),
        "blocked_pct": _pct(len(blocked_runs), volume),
        "external_effects_prevented": external_effects_prevented,
        "trend": _trend(rows),
        "event_count": len(rows),
    }


def _signal_trend(metric: str, rows: list[dict[str, object]]) -> dict[str, object]:
    buckets: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        stamp = _timestamp(row)
        if stamp is None:
            continue
        buckets.setdefault(stamp.date().isoformat(), []).append(row)

    points: list[dict[str, object]] = []
    for bucket, bucket_rows in sorted(buckets.items()):
        score = _aggregate_run_score(metric, bucket_rows)
        raw_score = score.get("score") if score else None
        value_pct = round(float(raw_score) * 100, 1) if isinstance(raw_score, int | float) else None
        points.append(
            {
                "bucket": bucket,
                "value_pct": value_pct,
                "status": str(score.get("status")) if score else "unknown",
            }
        )

    scored: list[tuple[str, float]] = []
    for point in points:
        raw_value_pct = point.get("value_pct")
        if isinstance(raw_value_pct, int | float):
            scored.append((str(point["bucket"]), float(raw_value_pct)))
    if len(scored) < _MIN_TREND_POINTS:
        return {
            "available": False,
            "direction": "insufficient_data",
            "delta_pct": None,
            "points": points,
        }

    first = scored[0][1]
    last = scored[-1][1]
    delta = round(last - first, 1)
    direction = "up" if last > first else ("down" if last < first else "flat")
    return {"available": True, "direction": direction, "delta_pct": delta, "points": points}


def _business_signals(
    agent_id: str | None, rows: list[dict[str, object]]
) -> list[dict[str, object]]:
    agent = _agent(agent_id)
    if agent is None:
        return []
    signal_rows: list[dict[str, object]] = []
    for descriptor in business_signal_descriptors(agent):
        key = str(descriptor["key"])
        score = _aggregate_run_score(key, rows)
        raw_score = score.get("score") if score else None
        value = float(raw_score) if isinstance(raw_score, int | float) else None
        value_pct = (
            round(value * 100, 1)
            if value is not None and descriptor.get("unit") == "ratio"
            else None
        )
        signal_rows.append(
            {
                **descriptor,
                "value": value,
                "value_pct": value_pct,
                "status": str(score.get("status")) if score else "unknown",
                "reason": str(score.get("reason")) if score else "no_business_score",
                "trend": _signal_trend(key, rows),
                # P3 item 18 — what is known when the signal is not decisive.
                "evidence": _signal_evidence(key, rows),
            }
        )
    return signal_rows


def _governed(agent_id: str | None) -> bool:
    if not agent_id:
        return False
    try:
        release = agent_release_state(agent_id)
    except (OSError, ValueError):
        return False
    return release.available and release.socle_total > 0


def _has_capability_stamped_events(rows: list[dict[str, object]]) -> bool:
    """≥1 business event stamped with a real ``capability_id`` — the L3 evidence."""
    return any(_capability(row) != UNKNOWN_CAPABILITY_ID for row in rows)


@dataclass(frozen=True, slots=True)
class LevelResolution:
    """What the cockpit knows about an agent's rung, and how firmly.

    ``computed`` rests on observed facts alone. ``declared`` is what the manifest's
    declarations would reach if the turn evidence existed. They are equal exactly when the
    evidence is ``observed``; otherwise ``declared`` is the ambition and ``computed`` the
    truth, and the badge must render the gap rather than hide it.
    """

    computed: str | None
    declared: str | None
    evidence: TurnEvidence

    @property
    def proven(self) -> bool:
        """Whether the computed rung is backed by observed turns — the only releasable state."""
        return self.evidence == "observed"


def resolve_level_state(agent_id: str | None) -> LevelResolution:
    """Resolve both rungs and the reason the evidence is (or is not) there."""
    agent = _agent(agent_id)
    evidence = turn_evidence.turn_evidence_state(agent_id)
    if agent is None:
        return LevelResolution(computed=None, declared=None, evidence=evidence)
    rows = business_events.business_event_rows(agent_id=agent_id) if agent_id else []
    governed = _governed(agent_id)
    stamped = _has_capability_stamped_events(rows)
    return LevelResolution(
        computed=observability_level(
            agent,
            governed=governed,
            business_events=stamped,
            has_turn_evidence=evidence == "observed",
        ),
        declared=declared_observability_level(agent, governed=governed, business_events=stamped),
        evidence=evidence,
    )


def resolve_observability_level(agent_id: str | None) -> str | None:
    """The agent's **computed** L-level (ADR 0017 §4), resolved from observed facts.

    The single place ``governed`` + business-event facts become a level, reused by the §A2.4
    release gate — which must see the computed rung and nothing else, so that an unproven
    level can never satisfy a gate. Returns ``None`` for an un-manifested agent.
    """
    return resolve_level_state(agent_id).computed


def declares_external_effects(agent_id: str | None) -> bool:
    """True iff the agent declares a capability reaching outside the system (§A2.4 → L3)."""
    agent = _agent(agent_id)
    if agent is None or agent.observability is None:
        return False
    return any(
        capability.external_effect_level.value in _EXTERNAL_EFFECT_LEVELS
        for capability in agent.observability.capabilities
    )


def _level_payload(agent_id: str | None, rows: list[dict[str, object]]) -> dict[str, object]:
    agent = _agent(agent_id)
    governed = _governed(agent_id)
    has_business_events = _has_capability_stamped_events(rows)
    # The Métier readiness payload answers "what do this agent's DECLARATIONS still lack to
    # reach L3?" — a contract question, not an emission one. It asks for the declared rung
    # explicitly rather than inheriting it from a defaulted flag.
    level = (
        declared_observability_level(agent, governed=governed, business_events=has_business_events)
        if agent is not None
        else None
    )

    missing: list[str] = []
    if agent is None or agent.observability is None:
        missing.append("manifest")
    elif not (agent.observability.workflows and agent.observability.telemetry_capabilities):
        missing.append("observable_contract")
    if not governed:
        missing.append("governance")
    if not rows:
        missing.append("business_events")
    elif not has_business_events:
        missing.append("capability_stamps")

    return {
        "observability_level": level,
        "required_level": "L3",
        "missing_requirements": missing if level != "L3" else [],
    }


def business_capability_aggregate(
    *,
    at: str | None = None,
    agent_id: str | None = None,
    workflow_id: str | None = None,
    conversation_id: str | None = None,
    turn_id: str | None = None,
    case_id: str | None = None,
) -> dict[str, object]:
    """Aggregate business-event facts by manifest capability id.

    Reads use :func:`business_events.business_event_rows`, which resolves the
    ``business_events`` fact source (jsonl/spine/shadow) inside the existing spine seam.
    Events without a stamp stay grouped under ``—`` / ``non attribué`` and are never reassigned.
    """
    rows = business_events.business_event_rows(
        at=at,
        agent_id=agent_id,
        workflow_id=workflow_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
        case_id=case_id,
    )
    level_payload = _level_payload(agent_id, rows)
    by_capability: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        by_capability.setdefault(_capability(row), []).append(row)

    manifest_rows = _manifest_capabilities(agent_id)
    capability_rows = [
        _row_for_capability(
            capability_id=str(capability["capability_id"]),
            label_key=str(capability["label_key"]),
            external_effect_level=str(capability["external_effect_level"]),
            rows=by_capability.pop(str(capability["capability_id"]), []),
        )
        for capability in manifest_rows
    ]
    for capability_id, capability_rows_raw in sorted(by_capability.items()):
        capability_rows.append(
            _row_for_capability(
                capability_id=capability_id,
                label_key=None,
                external_effect_level=None,
                rows=capability_rows_raw,
            )
        )
    return {
        "capabilities": capability_rows,
        "event_count": len(rows),
        "as_of": at,
        "agent": agent_id or "all",
        "workflow_id": workflow_id,
        "conversation_id": conversation_id,
        "turn_id": turn_id,
        "case_id": case_id,
        "source": fact_source("business_events"),
        "fact": "business_events",
        "business_signals": _business_signals(agent_id, rows),
        **level_payload,
        "unknown_capability_id": UNKNOWN_CAPABILITY_ID,
        "unknown_capability_label": UNKNOWN_CAPABILITY_LABEL,
    }
