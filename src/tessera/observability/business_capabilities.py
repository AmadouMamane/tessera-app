"""Per-capability business aggregate for the Métier surface (ADR 0017 §A1.4)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from tessera.agent.registry import get_agent
from tessera.observability import business_events, business_scoring
from tessera.observability.spine.adapters import fact_source

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
    "UNKNOWN_CAPABILITY_ID",
    "UNKNOWN_CAPABILITY_LABEL",
    "business_capability_aggregate",
]

UNKNOWN_CAPABILITY_ID = "—"
UNKNOWN_CAPABILITY_LABEL = "non attribué"
_MIN_TREND_POINTS = 2
_EXTERNAL_EFFECT_LEVELS = frozenset({"requires_validation", "external_action"})
_PREVENTED_EFFECT_EVENTS = frozenset({"action.blocked", "validation.requested"})


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


def _manifest_capabilities(agent_id: str | None) -> list[dict[str, object]]:
    if not agent_id:
        return []
    try:
        agent = get_agent(agent_id)
    except KeyError:
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
    scores = business_scoring.score_rows(rows)
    scored_values: list[float] = []
    for score in scores:
        raw_score = score.get("score")
        if score.get("status") == "scored" and isinstance(raw_score, int | float):
            scored_values.append(float(raw_score))
    return _mean_pct(scored_values)


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
        "unknown_capability_id": UNKNOWN_CAPABILITY_ID,
        "unknown_capability_label": UNKNOWN_CAPABILITY_LABEL,
    }
