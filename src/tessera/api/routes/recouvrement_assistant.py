"""Structured backend endpoint for the Recouvrement assistant workflow v1.

Audit 2026-07-12, **P0 F-1**: these two POSTs were mounted with no dependency at all —
the exact class closed on 2026-07-11 for the 26 cockpit mutations, missed here because
this router never went through the god-router split that put the guard on
``observability/mutations.py``. Both routes write: the message workflow emits ~30
business events per turn into the ledger, and the action route executes governed
artifact transitions. Worse, ``requested_by`` — the name the ledger records as having
acted — was a **body field with a default**, so the audit attribution was whatever the
caller typed (or "Julie Dubois" if they typed nothing).

Same remedy as the cockpit, same shape: the guard is declared HERE on the router, not at
the mount site, so a route added to this module inherits it by construction. The role
set is the business plane's (``COLLECTIONS_MUTATION_ROLES``): ``collections`` — the role
this console exists for — acts, the ``auditor`` reads and does not write, an anonymous
caller is refused before the body is parsed. ``requested_by`` now derives from the
verified operator assertion (the guard returns it), never from the body.
"""

from __future__ import annotations

import asyncio
import sys
import time
import uuid
from typing import TYPE_CHECKING, Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field

from tessera.agent.recouvrement import (
    DEFAULT_SURFACE,
    DEFAULT_TEXT_INTENT,
    RECOUVREMENT_AGENT_ID,
    RECOUVREMENT_WORKFLOW_ID,
    RecouvrementArtifact,
    classify_recouvrement_text,
    run_recouvrement_action_workflow_v1,
    run_recouvrement_graph_v1,
)
from tessera.agent.state import ConversationMessage
from tessera.api.config_overrides import resolve_understanding_config
from tessera.api.security import actor_of, require_collections_operator
from tessera.api.session import (
    SessionContext,  # noqa: TCH001  — FastAPI resolves Annotated at runtime
)
from tessera.authz import AuthState, Surface
from tessera.guard.adapter import check_user_input
from tessera.guard.audit import AGENT_TURN_ACTOR, turn_context
from tessera.guard.redaction import apply_output_guard, mask_pan
from tessera.memory.transcript import append_messages
from tessera.observability.business_events import BusinessEventName, record_business_event
from tessera.observability.metrics import AGENT_TURNS_TOTAL
from tessera.recouvrement.capabilities import capability_for_task
from tessera.recouvrement.understanding import UnderstandingOutcome, classify_intent_llm
from tessera.settings import LanguageCode, get_settings

if TYPE_CHECKING:
    from collections.abc import Mapping

#: Milliseconds per second — the transcript stores turn latency in ms (as ``/chat`` does).
_MS_PER_SECOND = 1000.0

#: Every route in this module writes (ledger events, governed transitions), so every
#: route requires a verified business-plane operator. Declared on the router, not
#: per-route — the ``observability/mutations.py`` model: a new route cannot forget it.
router = APIRouter(
    tags=["recouvrement-assistant"],
    dependencies=[Depends(require_collections_operator)],
)


class RecouvrementAssistantRequest(BaseModel):
    """Input contract for the minimal Recouvrement assistant workflow."""

    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(default="RC-2048", min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=2_000)
    assistant_state: dict[str, Any] | None = None
    conversation_id: str | None = Field(default=None, max_length=120)
    turn_id: str | None = Field(default=None, max_length=120)
    surface: str = Field(default=DEFAULT_SURFACE, max_length=80)
    language: Literal["fr", "en", "de"] = "fr"


class RecouvrementAssistantActionRequest(BaseModel):
    """Input contract for governed Recouvrement artifact actions."""

    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(default="RC-2048", min_length=1, max_length=80)
    artifact: dict[str, Any]
    action_name: str = Field(min_length=1, max_length=120)
    # NOTE ``requested_by`` is gone deliberately (audit 2026-07-12, P0 F-1): the ledger
    # attribution comes from the verified operator assertion, and ``extra="forbid"``
    # makes a body that still tries to assert an identity a 422 — the spoof is a
    # contract violation, not a silently ignored field.
    conversation_id: str | None = Field(default=None, max_length=120)
    turn_id: str | None = Field(default=None, max_length=120)
    surface: str = Field(default=DEFAULT_SURFACE, max_length=80)
    language: Literal["fr", "en", "de"] = "fr"


def _artifact_from_request(raw: dict[str, Any]) -> RecouvrementArtifact:
    """Coerce the frontend artifact payload into the backend typed shape."""
    content = raw.get("content")
    return {
        "id": str(raw.get("id") or "unknown-artifact"),
        "type": str(raw.get("type") or "unknown_artifact"),
        "task": str(raw.get("task") or "artifact_action"),
        "title": str(raw.get("title") or "Artefact Recouvrement"),
        "status": str(raw.get("status") or "draft"),
        "content": dict(content) if isinstance(content, dict) else {},
    }


async def _persist_recouvrement_turn(
    payload: RecouvrementAssistantRequest,
    result: Mapping[str, object],
    latency_ms: float,
) -> None:
    """Write the recouvrement turn to the durable transcript (ADR 0040).

    The transcript is the single witness of agent turns, but this graph — unlike
    ``/chat`` — never wrote ``conversation_messages``, so recouvrement's Synthèse KPIs
    (conversations / tours / résolution / temps de réponse / utilisateurs servis) read a
    false zero. We mirror the ``/chat`` seam: mask the user text, attribute the turn to
    the recouvrement agent and the served case, and store the measured latency. A COCKPIT
    (operator test) surface is marked ``synthetic`` so it never inflates the Synthèse.
    Any failure degrades to stderr — a transcript write must never break the turn.
    """
    visible_reply = str(result.get("visibleReply") or "")
    if not visible_reply:
        return
    try:
        conv_uuid = uuid.UUID(payload.conversation_id) if payload.conversation_id else uuid.uuid4()
        turn_uuid = uuid.UUID(payload.turn_id) if payload.turn_id else uuid.uuid4()
    except ValueError:
        # A non-UUID client id would break the ``uuid`` column; mint fresh ones so the
        # turn still remonte rather than being lost to a malformed identifier.
        conv_uuid = uuid.uuid4()
        turn_uuid = uuid.uuid4()
    user_msg = ConversationMessage(role="user", content=mask_pan(payload.message).text)
    assistant_msg = ConversationMessage(role="assistant", content=visible_reply)
    synthetic = payload.surface == Surface.COCKPIT_EMBEDDED.value
    try:
        await append_messages(
            conv_uuid,
            turn_uuid,
            [user_msg, assistant_msg],
            agent_id=RECOUVREMENT_AGENT_ID,
            latency_ms=latency_ms,
            subject_id=payload.case_id,
            synthetic=synthetic,
        )
    except Exception as exc:  # persistence must never break the operator's turn
        sys.stderr.write(f"tessera.memory.transcript: recouvrement append failed: {exc}\n")


def _guard_visible_reply(result: Mapping[str, object], *, language: str) -> dict[str, object]:
    """Sweep the recouvrement reply through the output guard before it leaves the server.

    Audit 2026-08-03. The 2026-07-21 audit closed this plane's INPUT leg — it was then the
    only turn path outside the chokepoint — and the output leg stayed open: ``visibleReply``
    was returned to the operator and written to the durable transcript with no
    :func:`apply_output_guard` anywhere, while ``mask_pan`` covered only the *user* message.
    A plane is not guarded because one of its two legs is.

    The guard is idempotent over already-clean text, so a reply built from approved
    templates passes through untouched; what it catches is the case those templates do not
    cover — a case field, an amount, an operator note carrying personal data into a payload
    that is persisted and re-read.
    """
    reply = str(result.get("visibleReply") or "")
    if not reply:
        return dict(result)
    try:
        resolved = LanguageCode(language)
    except ValueError:
        resolved = get_settings().default_language
    guarded, _record = apply_output_guard(reply, language=resolved)
    if guarded == reply:
        return dict(result)
    return {**result, "visibleReply": guarded}


#: Strong references to in-flight shadow classifications — a bare ``create_task`` result
#: is garbage-collectable mid-flight; the done-callback discards each task when it lands.
_SHADOW_TASKS: set[asyncio.Task[None]] = set()


def _turn_events(result: Mapping[str, object]) -> list[dict[str, object]]:
    """The turn's own ledger rows, as the graph projected them into the output contract."""
    raw = result.get("businessEvents")
    return [row for row in raw if isinstance(row, dict)] if isinstance(raw, list) else []


def _routed_intent_source(events: list[dict[str, object]]) -> str | None:
    """How the router says it decided this turn — read from ITS event, never re-guessed."""
    for row in events:
        if row.get("event_name") == BusinessEventName.INTENT_ROUTED.value:
            payload = row.get("payload")
            if isinstance(payload, dict):
                source = payload.get("intent_source")
                return str(source) if source is not None else None
    return None


async def _shadow_understanding(
    *,
    message: str,
    language: str,
    routed_intent: str,
    mode: str,
    model: str | None,
    outcome: UnderstandingOutcome | None,
    surface: str,
    conversation_id: str,
    turn_id: str,
    case_id: str,
    environment: str,
) -> None:
    """ADR 0053: record the understanding comparison for this turn, touch nothing.

    In SHADOW mode the LLM is called here, off the hot path. In ACTIVE mode the
    route already called it (``outcome`` is precomputed) and this only writes the
    ledger row — the agreement telemetry survives the flip. ``agree`` compares
    the LLM verdict to the PURE regex answer (ladder or default) so its meaning
    is mode-stable; ``routed_intent`` separately records what actually served.
    Every failure kind is recorded as itself; nothing here may ever reach the
    operator's reply.
    """
    try:
        if outcome is None:
            outcome = await classify_intent_llm(message, language=language, model=model)
        text_verdict = classify_recouvrement_text(message)
        regex_intent = text_verdict[0] if text_verdict is not None else DEFAULT_TEXT_INTENT
        verdict = outcome.verdict
        record_business_event(
            author=AGENT_TURN_ACTOR,
            event_name=BusinessEventName.INTENT_ROUTED,
            payload={
                "shadow": True,
                "mode": mode,
                "routed_intent": routed_intent,
                "regex_intent": regex_intent,
                "llm_status": outcome.status,
                "schema_valid": outcome.status == "verdict",
                "llm_intent": verdict.intent if verdict is not None else None,
                "llm_confidence": verdict.confidence if verdict is not None else None,
                "llm_duration_months": verdict.duration_months if verdict is not None else None,
                "llm_requested_time": verdict.requested_time if verdict is not None else None,
                "agree": (verdict.intent == regex_intent) if verdict is not None else None,
                "llm_latency_ms": round(outcome.latency_ms, 1),
                "llm_detail": outcome.detail,
                "prompt_version": outcome.prompt_version,
            },
            agent_id=RECOUVREMENT_AGENT_ID,
            workflow_id=RECOUVREMENT_WORKFLOW_ID,
            capability_id=None,
            surface=surface,
            conversation_id=conversation_id,
            turn_id=turn_id,
            case_id=case_id,
            node_name="shadow_understanding",
            language=language,
            model=outcome.model or RECOUVREMENT_WORKFLOW_ID,
            environment=environment,
        )
    except Exception as exc:  # the shadow must never surface anywhere but stderr
        sys.stderr.write(f"tessera.recouvrement.understanding: shadow failed: {exc}\n")


def _spawn_shadow_understanding(
    payload: RecouvrementAssistantRequest,
    result: Mapping[str, object],
    *,
    message: str | None = None,
    mode: str = "shadow",
    model: str | None = None,
    outcome: UnderstandingOutcome | None = None,
) -> None:
    """Fire the layer-1 comparison off the hot path; the reply never waits for it.

    A declared intent is skipped — a pressed button is an answer, and a classifier
    has nothing to add (ADR 0053 §1). The turn identifiers are read from the
    turn's own event rows so the row joins the exact turn it describes. In active
    mode ``outcome`` carries the call the route already made, so no second spend.
    """
    events = _turn_events(result)
    if not events or _routed_intent_source(events) == "declared":
        return
    first = events[0]
    decisions = result.get("decisions")
    routed = decisions.get("intent") if isinstance(decisions, dict) else None
    if not routed:
        return
    routed_intent = str(routed)
    task = asyncio.create_task(
        _shadow_understanding(
            message=message if message is not None else payload.message,
            language=payload.language,
            routed_intent=routed_intent,
            mode=mode,
            model=model,
            outcome=outcome,
            surface=str(first.get("surface", payload.surface)),
            conversation_id=str(first.get("conversation_id", "")),
            turn_id=str(first.get("turn_id", "")),
            case_id=payload.case_id,
            environment=str(first.get("environment", "dev")),
        )
    )
    _SHADOW_TASKS.add(task)
    task.add_done_callback(_SHADOW_TASKS.discard)


@router.post("/recouvrement-assistant/message")
@router.post("/api/recouvrement-assistant/message")
async def recouvrement_assistant_message(
    payload: RecouvrementAssistantRequest,
    session: Annotated[SessionContext, Depends(require_collections_operator)],
) -> dict[str, object]:
    """Run the first specialised Recouvrement graph and return drawer-ready cards.

    The graph is a *synchronous* LangGraph ``.invoke()`` that performs store I/O and
    emits ~30 business events per turn. Called directly from this async route it would
    block the event loop for the whole turn — starving every other in-flight request,
    including the SSE streams. Offloaded to the threadpool instead.

    The finished turn is then written to the durable transcript (ADR 0040) so
    recouvrement's Synthèse and the Flotte reflect real traffic; the latency is measured
    here because the graph does not return it.

    It also **counts the turn** (``tessera_agent_turns_total``), for the same reason and after
    the same omission. That counter was incremented in ``/chat`` alone, so the cockpit's L1
    evidence read — which asks it whether an agent has been observed emitting — never saw the
    one agent in the fleet actually serving turns, and pinned ``recouvrement`` at L0 while it
    wrote 1281 business events. Third time this route has been found outside a ``/chat`` seam
    (input guard 2026-07-21, transcript ADR 0040, this); hence the ratchet in
    ``test_a_route_that_serves_a_turn_counts_it.py`` rather than a fourth fix in isolation.

    The message passes the SAME input guard as every other plane before the graph sees
    it (2026-07-21 audit: this workflow was the one turn path outside the chokepoint —
    "sécurité à chaque message" must hold here too, operator-only or not). A denial is
    already audited inside :func:`check_user_input`; the refusal is an explicit 400, not
    a fabricated drawer payload — the contract's ``artifact`` cannot be honestly built
    for a turn that never ran.
    """
    check = check_user_input(payload.message, actor=actor_of(session))
    if not check.allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="message refused by the input guard",
        )
    started = time.perf_counter()
    # ADR 0053 §5: which layer-1 mode this turn serves under is a GOVERNED state, read from
    # the override store (fails open to shadow, loudly). In active mode the LLM classifies
    # on the hot path, bounded by the governed timeout; its acceptance (schema-valid AND
    # confidence over the calibrated threshold) is decided HERE — the graph only consumes.
    # A declared intent skips the model in every mode: a pressed button is an answer.
    understanding_config = await resolve_understanding_config()
    active_outcome: UnderstandingOutcome | None = None
    llm_understanding: dict[str, object] | None = None
    assistant_state = payload.assistant_state or {}
    if (
        understanding_config.mode == "active"
        and capability_for_task(assistant_state.get("declaredIntent")) is None
    ):
        active_outcome = await classify_intent_llm(
            check.sanitised_text,
            language=payload.language,
            timeout_s=understanding_config.timeout_s,
            model=understanding_config.model,
        )
        verdict = active_outcome.verdict
        threshold = understanding_config.threshold
        llm_understanding = {
            "accepted": verdict is not None
            and threshold is not None
            and verdict.confidence >= threshold,
            "intent": verdict.intent if verdict is not None else None,
            "confidence": verdict.confidence if verdict is not None else None,
            "duration_months": verdict.duration_months if verdict is not None else None,
            "requested_time": verdict.requested_time if verdict is not None else None,
        }
    # The guard's per-turn state, on this plane too (audit 2026-08-03). It was installed only
    # in /chat, so this workflow ran with no call-count map at all — meaning
    # `max_calls_per_turn` was not enforced here, and the auth floor saw the ANONYMOUS default
    # for a turn a verified collections operator had just authenticated. `run_in_threadpool`
    # copies the context, so the state reaches the graph.
    try:
        with turn_context(auth_state=AuthState.OPERATOR):
            result = await run_in_threadpool(
                run_recouvrement_graph_v1,
                case_id=payload.case_id,
                message=check.sanitised_text,
                assistant_state=payload.assistant_state,
                conversation_id=payload.conversation_id,
                turn_id=payload.turn_id,
                surface=payload.surface,
                language=payload.language,
                llm_understanding=llm_understanding,
            )
    except Exception:
        # A failed turn is still a turn served, and `/chat` counts its failures too. Counting
        # only successes would make the evidence read say "dormant" for an agent that is being
        # asked and failing — the loudest case, silenced.
        AGENT_TURNS_TOTAL.labels(
            agent_id=RECOUVREMENT_AGENT_ID, language=payload.language, outcome="error"
        ).inc()
        raise
    AGENT_TURNS_TOTAL.labels(
        agent_id=RECOUVREMENT_AGENT_ID, language=payload.language, outcome="complete"
    ).inc()
    latency_ms = (time.perf_counter() - started) * _MS_PER_SECOND
    guarded = _guard_visible_reply(result, language=payload.language)
    await _persist_recouvrement_turn(payload, guarded, latency_ms)
    _spawn_shadow_understanding(
        payload,
        guarded,
        message=check.sanitised_text,
        mode=understanding_config.mode,
        model=understanding_config.model,
        outcome=active_outcome,
    )
    return dict(guarded)


@router.post("/recouvrement-assistant/action")
@router.post("/api/recouvrement-assistant/action")
async def recouvrement_assistant_action(
    payload: RecouvrementAssistantActionRequest,
    session: Annotated[SessionContext, Depends(require_collections_operator)],
) -> dict[str, object]:
    """Run a governed action cycle for a Recouvrement artifact.

    Synchronous and store-backed like the message workflow above — same reason, same
    offload. The audit named only the message path; this one blocks identically.

    ``session`` is the router guard's own return value (FastAPI caches the dependency
    per-request — the guard runs once). ``actor_of(session)`` is the verified principal from the
    signed assertion: the ledger records who *proved* they asked, not who the body *claimed*
    asked.

    This call used to read ``requested_by=session.subject_id or "operator"`` and the docstring
    defended the fallback as "unreachable in practice". It was two lies stacked, and the second
    hid the first: the ``or "operator"`` was a literal this file would never reach, feeding a
    parameter whose *own* default — one call away, in ``recouvrement.py`` — was ``"Julie
    Dubois"``. Both are gone. ``actor_of`` raises on an unverified session rather than inventing
    a name, and the parameter it feeds has no default left to fall back to.
    """
    return dict(
        await run_in_threadpool(
            run_recouvrement_action_workflow_v1,
            case_id=payload.case_id,
            artifact=_artifact_from_request(payload.artifact),
            action_name=payload.action_name,
            actor=actor_of(session),
            conversation_id=payload.conversation_id,
            turn_id=payload.turn_id,
            surface=payload.surface,
            language=payload.language,
        )
    )
