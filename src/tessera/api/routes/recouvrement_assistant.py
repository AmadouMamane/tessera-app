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

import sys
import time
import uuid
from typing import TYPE_CHECKING, Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field

from tessera.agent.recouvrement import (
    DEFAULT_SURFACE,
    RECOUVREMENT_AGENT_ID,
    RecouvrementArtifact,
    run_recouvrement_action_workflow_v1,
    run_recouvrement_graph_v1,
)
from tessera.agent.state import ConversationMessage
from tessera.api.security import actor_of, require_collections_operator
from tessera.api.session import (
    SessionContext,  # noqa: TCH001  — FastAPI resolves Annotated at runtime
)
from tessera.authz import AuthState, Surface
from tessera.guard.adapter import check_user_input
from tessera.guard.audit import turn_context
from tessera.guard.redaction import apply_output_guard, mask_pan
from tessera.memory.transcript import append_messages
from tessera.observability.metrics import AGENT_TURNS_TOTAL
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
