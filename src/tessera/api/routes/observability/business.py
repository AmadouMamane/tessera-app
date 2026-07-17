"""Observability routes — business surface."""

from __future__ import annotations

import sys
from dataclasses import asdict

from fastapi import APIRouter, Depends

from tessera.api.routes.observability._common import (
    _agent_or_none,
    _business_runs_response,
    _read_audit_entries,
    _scores_for,
)
from tessera.api.security import require_bearer
from tessera.observability import (
    automations as automations_mod,
    business_capabilities as business_capabilities_mod,
    business_events as business_events_mod,
    business_scoring as business_scoring_mod,
    curation as curation_mod,
    etat_a_date as etat_a_date_mod,
    funnel as funnel_mod,
    improvement as improvement_mod,
    inbox as inbox_mod,
    journey as journey_mod,
    sessions as sessions_mod,
)
from tessera.observability.spine.adapters import read_scores

router = APIRouter()


@router.get("/observability/business-events", dependencies=[Depends(require_bearer)])
async def observability_business_events(
    at: str | None = None,
    agent: str = "all",
    workflow_id: str | None = None,
    conversation_id: str | None = None,
    turn_id: str | None = None,
    case_id: str | None = None,
    capability_id: str | None = None,
    event_name: str | None = None,
    artifact_type: str | None = None,
    decision: str | None = None,
) -> dict[str, object]:
    """Business workflow events and deterministic métier scores."""
    rows = business_events_mod.business_event_rows(
        at=at,
        agent_id=_agent_or_none(agent),
        workflow_id=workflow_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
        case_id=case_id,
        capability_id=capability_id,
        event_name=event_name,
        artifact_type=artifact_type,
        decision=decision,
    )
    return {
        "events": rows,
        "scores": business_scoring_mod.score_rows(rows),
        "as_of": at,
        "agent": agent,
        "workflow_id": workflow_id,
        "conversation_id": conversation_id,
        "turn_id": turn_id,
        "case_id": case_id,
        "capability_id": capability_id,
        "event_name": event_name,
        "artifact_type": artifact_type,
        "decision": decision,
    }


@router.get("/observability/business/capabilities", dependencies=[Depends(require_bearer)])
async def observability_business_capabilities(
    at: str | None = None,
    agent: str = "all",
    workflow_id: str | None = None,
    conversation_id: str | None = None,
    turn_id: str | None = None,
    case_id: str | None = None,
) -> dict[str, object]:
    """Per-capability business aggregate, computed server-side from business events."""
    return business_capabilities_mod.business_capability_aggregate(
        at=at,
        agent_id=_agent_or_none(agent),
        workflow_id=workflow_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
        case_id=case_id,
    )


@router.get("/observability/business/runs", dependencies=[Depends(require_bearer)])
async def observability_business_runs(
    at: str | None = None,
    agent: str = "all",
    workflow_id: str | None = None,
    conversation_id: str | None = None,
    turn_id: str | None = None,
    case_id: str | None = None,
    capability_id: str | None = None,
    limit: int = 20,
) -> dict[str, object]:
    """Workflow business runs for ANY agent — dimension filters only, no domain knowledge.

    ADR 0017 Phase A: the generic read that replaces per-agent hardcoded routes. Filters are
    the declared ADR 0016 dimensions (``agent``, ``workflow_id``, ``conversation_id``,
    ``turn_id``, ``case_id``, ``at``); the projection reads envelope fields and the grammar
    order — never domain payload semantics.
    """
    return _business_runs_response(
        at=at,
        agent_id=_agent_or_none(agent),
        workflow_id=workflow_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
        case_id=case_id,
        capability_id=capability_id,
        limit=limit,
    )


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


@router.get("/observability/automations")
async def observability_automations(lang: str = "fr", at: str | None = None) -> dict[str, object]:
    """Automations overview (page #13).

    Composes the automation posture, rule catalogue, execution pipeline, type /
    environment breakdowns, execution journal, pending approvals, most-used
    guardrails, performance / savings trends and governance context. ``lang``
    localizes the free-text fixture fields. ``at`` folds every projection to
    instant T (registre §6 — AGIR reads As-of, acts Live; mutations stay
    live-only). Degrades to ``available: false`` on failure.
    """
    try:
        return {"available": True, **automations_mod.compute_automations_overview(lang, at=at)}
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.automations: failed: {exc}\n")
        return {"available": False}


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
