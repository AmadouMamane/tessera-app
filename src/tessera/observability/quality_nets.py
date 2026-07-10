"""Manifest-generated quality nets — instrumentation coverage (92) + canary freshness (94).

ADR 0017 §4: quality nets attach automatically at onboarding, GENERATED FROM THE MANIFEST,
so the fleet gains quality as it scales instead of artisanal per-agent setup. This module
derives, per agent (reading the registry seam for the manifest, ADR 0017 §1):

* the **instrumentation-coverage** descriptor (signal 92) — the fraction of the required
  turn-span Scope dimensions (the §4 L1 contract) the agent actually stamps, *measured*
  from its most recent **business event**; honest-empty when the agent has no telemetry yet;
* the **canary** descriptor (signal 94) — the workflow(s) a scheduled canary would drive
  (from the manifest) plus the freshness of the agent's last observed turn, so a broken
  pipeline is seen before an operator misses data.

Honesty (0016 / ADR 0017 §Amendment 1): the coverage number is measured, never invented;
the canary reports the freshness of *real* telemetry in ``status``. The scheduled synthetic
execution with a green/red verdict — deferred in step 6b for lack of an invocation primitive —
now exists (ADR 0019 §I4): its last run is reported as a *separate* ``synthetic_run`` facet,
read from the durable ``tessera.agent.canary`` S1 entry, so real-telemetry freshness and the
canary's own run stay honestly distinct — one is organic, the other is the probe.

Coverage source (§A2.4, operator ruling 2026-07-08): the measurement reads the **Scope
dimensions carried on business events**, NOT a span store — spans and events carry the same
Scope dims by design (:data:`_ATTR_TO_ROW_FIELD`), so business-event field presence is the
honestly-available proxy for span coverage. The descriptor therefore names its source
(``evidence_source="business_events"``, ``measures="scope_dimensions"``) and the UI label
must read "couverture Scope — événements métier": never a claim of span coverage. Widening
the proxy to a real span store is a noted future option, not a present claim.
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
    from collections.abc import Mapping

    from tessera.agent.registry import Agent

__all__ = ["canary_descriptor", "coverage_descriptor", "latest_canary_verdict"]

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


def _latest_canary_run(agent_id: str) -> Mapping[str, object] | None:
    """The most recent ``tessera.agent.canary`` S1 entry for the agent, or None.

    Reads the active ledger medium-aware (postgres table since the H2 cut, else the flat file),
    the same pattern the seal facet uses. Best-effort: an unreachable ledger yields None (the
    descriptor then reports the synthetic run as ``never``), never a crash and never a fabricated
    run — reading the S1 entry couples nothing new (the control plane already reads the ledger for
    État à date / session detail; ``tessera.guard`` is not the agent runtime).
    """
    from tessera.guard.audit import CANARY_INVOCATION_TYPE
    from tessera.guard.ledger_store import (
        ledger_source,
        load_ledger_payloads_sync,
        read_ledger_entries,
    )

    try:
        payloads: list[dict[str, object]] = (
            load_ledger_payloads_sync() if ledger_source() == "postgres" else read_ledger_entries()
        )
    except Exception:  # an unreachable ledger must never break a cockpit read
        return None
    found: Mapping[str, object] | None = None
    for payload in payloads:  # oldest→newest, so the last match is the most recent run
        if payload.get("type") == CANARY_INVOCATION_TYPE and payload.get("agent_id") == agent_id:
            found = payload
    return found


def latest_canary_verdict(agent_id: str) -> str | None:
    """The verdict of the agent's most recent canary invocation, or ``None`` if it never ran.

    The one public reader of that S1 fact. The fleet's health dot and the cockpit bell both
    ask this question, and a canary that never fired must answer ``None`` — "no bad news" and
    "no news" are different facts, and only the caller knows which one it may treat as green.
    """
    run = _latest_canary_run(agent_id)
    if run is None:
        return None
    verdict = run.get("verdict")
    return str(verdict).lower() if verdict is not None else None


def _synthetic_run_facet(agent_id: str, *, reference: datetime) -> dict[str, object]:
    """The last scheduled-canary run for the agent (ADR 0019 §I4), read from the S1 ledger.

    ``status`` is the run verdict (``green`` / ``red``) or ``never`` when no canary has run — this
    is the *synthetic* freshness, kept distinct from the descriptor's real-telemetry ``status``.
    """
    run = _latest_canary_run(agent_id)
    if run is None:
        return {"status": "never", "ran_at": None, "age_seconds": None, "error": None}
    ran_at = str(run.get("occurred_at", "")) or None
    parsed = _parse_iso(ran_at) if ran_at else None
    age_seconds = int((reference - parsed).total_seconds()) if parsed is not None else None
    verdict = str(run.get("verdict") or "unknown")
    error = run.get("error")
    return {
        "status": verdict,
        "ran_at": ran_at,
        "age_seconds": age_seconds,
        "error": error if isinstance(error, str) else None,
    }


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
            # The source of the measurement, named so no label may imply span coverage:
            # it is the Scope dims carried on business events (a proxy), not a span store.
            "evidence_source": "business_events",
            "measures": "scope_dimensions",
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
        "evidence_source": "business_events",
        "measures": "scope_dimensions",
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

    Generated from the manifest (which workflows a scheduled canary would drive, and — since ADR
    0019 §I4 — the declared ``cadence_s`` at which it drives them) with the freshness of the
    agent's last observed turn as the pipeline-health proxy. ``None`` for an un-manifested agent or
    one declaring no workflow. ``status`` reports the freshness of *real* telemetry
    (``fresh`` / ``stale`` / ``never``); the ``synthetic_run`` facet reports the last scheduled
    synthetic execution and its green/red verdict — the two are kept honestly distinct.
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
        # The declared scheduler cadence (ADR 0019 §I4); ``None`` ⇒ no scheduled canary declared.
        "cadence_s": agent.invocation.canary_cadence_s,
        "last_seen_at": last_seen,
        "age_seconds": age_seconds,
        "status": status,
        # The last scheduled synthetic execution — fed by the I4 scheduler via its S1 entry.
        "synthetic_run": _synthetic_run_facet(agent.id, reference=reference),
    }
