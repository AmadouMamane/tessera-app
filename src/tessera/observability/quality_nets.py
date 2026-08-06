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

from tessera.agent.registry import get_agent, list_agents
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

__all__ = [
    "canary_descriptor",
    "coverage_descriptor",
    "fleet_coverage",
    "latest_canary_verdict",
    "latest_canary_verdicts",
]

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

    ONE indexed row. This function used to load **every** ledger payload — 29 600 of them, 38 MB
    — into memory and scan them in Python to find the last match, and the fleet called it once
    per agent. Six full table reads, per request, to answer six one-row questions; measured, that
    single mistake was 3.6 of the fleet's 3.9 seconds.

    Reads the active ledger medium-aware (postgres table since the H2 cut, else the flat file —
    a file has no index, so there the scan is irreducible and stays). Best-effort: an unreachable
    ledger yields None (the descriptor then reports the synthetic run as ``never``), never a crash
    and never a fabricated run.
    """
    from tessera.guard.audit import CANARY_INVOCATION_TYPE
    from tessera.guard.ledger_store import (
        latest_entry_of_type_for_agent,
        ledger_source,
        read_ledger_entries,
    )

    try:
        if ledger_source() == "postgres":
            return latest_entry_of_type_for_agent(CANARY_INVOCATION_TYPE, agent_id)
        payloads: list[dict[str, object]] = read_ledger_entries()
    except Exception:  # an unreachable ledger must never break a cockpit read
        return None
    found: Mapping[str, object] | None = None
    for payload in payloads:  # oldest→newest, so the last match is the most recent run
        if payload.get("type") == CANARY_INVOCATION_TYPE and payload.get("agent_id") == agent_id:
            found = payload
    return found


def _verdict_of(run: Mapping[str, object] | None) -> str | None:
    if run is None:
        return None
    verdict = run.get("verdict")
    return str(verdict).lower() if verdict is not None else None


def latest_canary_verdict(agent_id: str) -> str | None:
    """The verdict of the agent's most recent canary invocation, or ``None`` if it never ran.

    The one public reader of that S1 fact, for ONE agent. A canary that never fired must answer
    ``None`` — "no bad news" and "no news" are different facts, and only the caller knows which
    one it may treat as green.

    Asking it about a whole fleet is :func:`latest_canary_verdicts`, which is one query rather
    than N — see there for why that distinction is not cosmetic.
    """
    return _verdict_of(_latest_canary_run(agent_id))


def latest_canary_verdicts() -> dict[str, str]:
    """Every agent's latest canary verdict — ONE query for the whole fleet.

    Both callers that need this need it for *all* agents at once: the fleet's health dots and the
    cockpit's notification bell. Asked one agent at a time it was N round trips; asked as the
    question it actually is, it is one ``DISTINCT ON`` over an index.

    Agents that never ran a canary are simply ABSENT from the mapping — never present with a
    fabricated green. The caller distinguishes "no news" from "good news"; this function refuses
    to make that choice for it.
    """
    from tessera.guard.audit import CANARY_INVOCATION_TYPE
    from tessera.guard.ledger_store import (
        latest_entries_of_type_by_agent,
        ledger_source,
        read_ledger_entries,
    )

    try:
        if ledger_source() == "postgres":
            runs = latest_entries_of_type_by_agent(CANARY_INVOCATION_TYPE)
        else:
            latest: dict[str, dict[str, object]] = {}
            for payload in read_ledger_entries():  # oldest→newest: the last match wins
                agent_id = payload.get("agent_id")
                if payload.get("type") == CANARY_INVOCATION_TYPE and isinstance(agent_id, str):
                    latest[agent_id] = payload
            runs = latest
    except Exception:  # an unreachable ledger must never break a cockpit read
        return {}
    verdicts: dict[str, str] = {}
    for agent_id, run in runs.items():
        verdict = _verdict_of(run)
        if verdict is not None:
            verdicts[agent_id] = verdict
    return verdicts


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

    ``None`` for an un-manifested agent (no L1 obligation). For a manifested agent whose store
    answered with nothing, coverage is ``None`` with ``status="no_evidence"``; when the store
    did not answer at all, ``status="unverifiable"`` — honest-empty in both cases, never a
    fabricated percentage, and never the two collapsed into one word.
    """
    agent = _agent(agent_id)
    if agent is None or agent.observability is None:
        return None
    read = business_events.business_event_read(agent_id=agent_id) if agent_id else None
    return _coverage_from_rows(
        agent.id,
        rows=read.rows if read is not None else [],
        # No agent id to read for is not a store outage — it is a caller that asked nothing,
        # and the honest answer there is the same as an empty answer.
        blind=read.blind if read is not None else False,
        declares_events=_declares_business_signals(agent),
    )


def _declares_business_signals(agent: Agent) -> bool:
    """Whether this agent's manifest says it emits business events at all (ADR 0017 §4 L3).

    The whole coverage measurement is taken on business-event fields. For an agent that declares
    no business signals, that evidence does not exist and never will — which is a fact about the
    manifest, not about the agent's instrumentation.
    """
    observability = agent.observability
    return bool(observability is not None and getattr(observability, "business_signals", None))


def _coverage_from_rows(
    agent_id: str, *, rows: list[dict[str, object]], blind: bool, declares_events: bool = True
) -> dict[str, object]:
    """Build one agent's coverage descriptor from rows already read (pure).

    Split out so the fleet read can serve every agent from ONE whole-ledger read instead of one
    read per agent — the shape ``business_capabilities.fleet_ledger_facts`` established, and for
    the same reason: two whole-ledger reads that can disagree with each other is a bug this
    codebase keeps paying for.

    ``blind`` is carried in rather than inferred from ``rows`` being empty. That inference is
    precisely what :func:`business_events.business_event_rows` warns against in its own
    docstring — *"wrong for anything that derives a coverage claim from the absence"* — and this
    function is that coverage claim. A store that is down must degrade the claim to *cannot say*,
    never to a measured shortfall.
    """
    required = list(REQUIRED_TURN_SPAN_ATTRIBUTES)
    base: dict[str, object] = {
        "agent_id": agent_id,
        "signal": "instrumentation-coverage",
        # The source of the measurement, named so no label may imply span coverage:
        # it is the Scope dims carried on business events (a proxy), not a span store.
        "evidence_source": "business_events",
        "measures": "scope_dimensions",
        "required_attributes": required,
    }
    if blind:
        return {
            **base,
            "covered_pct": None,
            # NOT the required list: naming every attribute as "missing" when nobody could look
            # renders as a total instrumentation failure. Nothing is known to be missing.
            "missing_attributes": [],
            "evidence_at": None,
            "status": "unverifiable",
        }
    if not rows:
        # Zero rows has TWO causes and they are opposite findings. An agent whose manifest
        # declares no business signals is not *failing* to emit them — it has no business
        # grammar, so this evidence does not exist for it and never will. Reporting that as
        # "no telemetry" reads as an instrumentation failure and is how five correctly-behaving
        # agents came to be listed as emitting nothing, next to the whole contract marked
        # missing, while Prometheus showed them serving turns. Measuring the neighbourhood and
        # publishing it as a fact about the thing (ADR 0026), one layer up.
        return {
            **base,
            "covered_pct": None,
            "missing_attributes": [] if not declares_events else required,
            "evidence_at": None,
            "status": "no_evidence" if declares_events else "not_applicable",
        }
    latest = max(rows, key=lambda row: str(row.get("timestamp", "")))
    missing = [
        attr
        for attr in REQUIRED_TURN_SPAN_ATTRIBUTES
        if not str(latest.get(_ATTR_TO_ROW_FIELD[attr], "")).strip()
    ]
    covered = len(required) - len(missing)
    return {
        **base,
        "covered_pct": round(100.0 * covered / len(required), 1),
        "missing_attributes": missing,
        "evidence_at": str(latest.get("timestamp", "")),
        "status": "measured",
    }


def fleet_coverage() -> dict[str, object]:
    """Instrumentation coverage for every manifested agent, from ONE read of the ledger.

    Signal 92 has existed since step 6b and was reachable only as
    ``/observability/quality-nets?agent=<id>`` — one agent at a time, on a page that never
    called it. A fleet has no per-agent page to ask from, so the number that answers *"is the
    fleet instrumented?"* was computable and never computed.

    Returns:
        ``agents`` — one descriptor per manifested agent, worst coverage first so the row that
        needs work leads; ``blind`` — the store did not answer, in which case every descriptor
        reads ``unverifiable`` and the caller must render *cannot say*, never 0 %; and
        ``observed_at``, the instant of the read.
    """
    read = business_events.business_event_read()
    grouped: dict[str, list[dict[str, object]]] = {}
    for row in read.rows:
        row_agent = row.get("agent_id")
        if isinstance(row_agent, str) and row_agent:
            grouped.setdefault(row_agent, []).append(row)

    descriptors = [
        _coverage_from_rows(
            agent.id,
            rows=grouped.get(agent.id, []),
            blind=read.blind,
            declares_events=_declares_business_signals(agent),
        )
        for agent in list_agents()
        if agent.observability is not None
    ]
    # Worst first: unverifiable and no-evidence sort ahead of every measured percentage, because
    # "I cannot tell you" is the row an operator must act on before any 96 %.
    descriptors.sort(
        key=lambda d: (
            d["covered_pct"] if isinstance(d["covered_pct"], int | float) else -1.0,
            str(d["agent_id"]),
        )
    )
    return {
        "observed_at": datetime.now(UTC).isoformat(),
        "blind": read.blind,
        "required_attributes": list(REQUIRED_TURN_SPAN_ATTRIBUTES),
        "evidence_source": "business_events",
        "measures": "scope_dimensions",
        "agents": descriptors,
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
