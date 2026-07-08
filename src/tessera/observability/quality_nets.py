"""Manifest-generated quality nets — instrumentation coverage (92) + canary freshness (94).

ADR 0017 §4: quality nets attach automatically at onboarding, GENERATED FROM THE MANIFEST,
so the fleet gains quality as it scales instead of artisanal per-agent setup. This module
derives, per agent (reading the registry seam for the manifest, ADR 0017 §1):

* the **instrumentation-coverage** descriptor (signal 92) — the fraction of the required
  turn-span Scope dimensions (the §4 L1 contract) the agent actually stamps, *measured*
  from its most recent business event; honest-empty when the agent has no telemetry yet;
* the **canary** descriptor (signal 94) — the workflow(s) a scheduled canary would drive
  (from the manifest) plus the freshness of the agent's last observed turn, so a broken
  pipeline is seen before an operator misses data.

Honesty (0016 / ADR 0017 §Amendment 1): the coverage number is measured, never invented;
the canary reports the freshness of *real* telemetry — scheduled synthetic execution with
a green/red verdict is the runtime piece (no in-tree scheduler yet), declared here, not faked.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from tessera.agent.registry import get_agent
from tessera.observability import business_events, replay
from tessera.observability.semconv import (
    DEPLOYMENT_ENVIRONMENT,
    GEN_AI_CONVERSATION_ID,
    REQUIRED_TURN_SPAN_ATTRIBUTES,
    TESSERA_AGENT_ID,
    TESSERA_LANGUAGE,
    TESSERA_TURN_ID,
)

if TYPE_CHECKING:
    from tessera.agent.registry import Agent

__all__ = ["canary_descriptor", "coverage_descriptor"]

# Each required turn-span attribute (semconv key) → the business-event row field carrying
# the same Scope dimension (the measurable coverage evidence). Span attrs and envelope
# fields differ by design; this is the one place the two vocabularies meet.
_ATTR_TO_ROW_FIELD: dict[str, str] = {
    TESSERA_AGENT_ID: "agent_id",
    TESSERA_LANGUAGE: "language",
    GEN_AI_CONVERSATION_ID: "conversation_id",
    TESSERA_TURN_ID: "turn_id",
    DEPLOYMENT_ENVIRONMENT: "environment",
}

#: A telemetry gap beyond this many seconds reads as "stale" (pipeline likely broken).
_CANARY_FRESH_WINDOW_S = 24 * 3600


def _agent(agent_id: str | None) -> Agent | None:
    if not agent_id:
        return None
    try:
        return get_agent(agent_id)
    except KeyError:
        return None


def _parse_iso(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def coverage_descriptor(agent_id: str | None) -> dict[str, object] | None:
    """Instrumentation-coverage (signal 92) for one agent, measured from live telemetry.

    ``None`` for an un-manifested agent (no L1 obligation). For a manifested agent with no
    telemetry yet, coverage is ``None`` with ``status="no_evidence"`` — honest-empty, never
    a fabricated percentage.
    """
    agent = _agent(agent_id)
    if agent is None or agent.observability is None:
        return None
    required = list(REQUIRED_TURN_SPAN_ATTRIBUTES)
    rows = business_events.business_event_rows(agent_id=agent_id) if agent_id else []
    if not rows:
        return {
            "agent_id": agent.id,
            "signal": "instrumentation-coverage",
            "required_attributes": required,
            "covered_pct": None,
            "missing_attributes": required,
            "evidence_at": None,
            "status": "no_evidence",
        }
    latest = max(rows, key=lambda row: str(row.get("timestamp", "")))
    missing = [
        attr
        for attr in REQUIRED_TURN_SPAN_ATTRIBUTES
        if not str(latest.get(_ATTR_TO_ROW_FIELD[attr], "")).strip()
    ]
    covered = len(required) - len(missing)
    return {
        "agent_id": agent.id,
        "signal": "instrumentation-coverage",
        "required_attributes": required,
        "covered_pct": round(100.0 * covered / len(required), 1),
        "missing_attributes": missing,
        "evidence_at": str(latest.get("timestamp", "")),
        "status": "measured",
    }


def canary_descriptor(
    agent_id: str | None, *, now: datetime | None = None
) -> dict[str, object] | None:
    """Canary descriptor (signal 94): the manifest's canary target workflows + freshness.

    Generated from the manifest (which workflows a scheduled canary would drive) with the
    freshness of the agent's last observed turn as the pipeline-health proxy. ``None`` for
    an un-manifested agent or one declaring no workflow. Scheduled synthetic execution with
    a green/red verdict is the runtime piece (declared, not faked): ``status`` reports the
    freshness of *real* telemetry (``fresh`` / ``stale`` / ``never``), not a synthetic run.
    """
    agent = _agent(agent_id)
    if agent is None or agent.observability is None or not agent.observability.workflows:
        return None
    reference = now or datetime.now(UTC)
    targets = [workflow.workflow_id for workflow in agent.observability.workflows]
    bundles = replay.persisted_bundles(agent_id=agent_id) if agent_id else []
    last_seen = max((bundle.captured_at for bundle in bundles), default=None)
    parsed = _parse_iso(last_seen) if last_seen else None
    if parsed is None:
        status = "never" if last_seen is None else "unknown"
        age_seconds: int | None = None
    else:
        age_seconds = int((reference - parsed).total_seconds())
        status = "fresh" if age_seconds <= _CANARY_FRESH_WINDOW_S else "stale"
    return {
        "agent_id": agent.id,
        "signal": "canary-tagging",
        "targets": targets,
        "last_seen_at": last_seen,
        "age_seconds": age_seconds,
        "status": status,
    }
