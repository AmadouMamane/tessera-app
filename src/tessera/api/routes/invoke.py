"""The declared cockpit→agent invocation route (ADR 0019 §I3 + §3 + §4).

The Console consumer's server seam: it drives the :class:`HttpTurnInvoker` against an
``http``-binding agent. Every property ADR 0019 §4 demands ("every invocation is a governed
act") is enforced HERE, before the invoker runs:

* **Auth** — the turn is resolved from the *verified* operator assertion (0010 Phase B); a
  non-operator caller is refused (401). No anonymous invocation, ever.
* **Plane** — the agent must be reachable on the operator's surface under its auth
  (``routable``, ADR 0013): a ``collections``-tier console cannot invoke a cockpit-tier
  agent and vice-versa. The same seam that keeps a sensitive agent off a surface.
* **Binding** — only an ``http``-binding agent is invocable here (the in-process console
  streams through ``/chat``); anything else is a 400, never a mis-dispatched POST.
* **Audit** — the invoker emits one S1 event per call (green or red); the route adds nothing
  the ledger does not already record.

The route lives outside the boundary-scanned control plane (``routes/observability.py``), so
it may use the invoker + turn contract; the ratchet is untouched.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Body, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from tessera.agent.registry import InvocationBinding, get_agent, routable
from tessera.api.agent_invoker import HttpTurnInvoker
from tessera.api.operator import OPERATOR_ASSERTION_HEADER, resolve_request_context
from tessera.authz import AuthState

if TYPE_CHECKING:
    from tessera.agent.turn_contract import TurnInput

router = APIRouter(tags=["invoke"])


class InvokeRequest(BaseModel):
    """A single test turn for an http-binding agent (the Console's invocation body)."""

    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=4_000)
    case_id: str | None = Field(default=None, max_length=120)
    language: str | None = Field(default=None, max_length=12)


@router.post("/agents/{agent_id}/invoke")
async def invoke_agent(
    agent_id: str,
    request: Request,
    payload: Annotated[InvokeRequest, Body(...)],
) -> dict[str, object]:
    """Send one operator test turn to an ``http``-binding agent (ADR 0019 §I3).

    Returns the invocation outcome: the green ``result`` (the agent's TurnResult) or an honest
    red ``error`` (+ ``conformance`` violations when the agent broke its declared contract).
    """
    session, surface = resolve_request_context(request)
    if session.auth_state is not AuthState.OPERATOR:
        # No anonymous invocation, ever (§4): a governed console action needs an operator.
        raise HTTPException(status_code=401, detail="operator authentication required")

    try:
        agent = get_agent(agent_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"unknown agent {agent_id!r}") from exc

    # Plane rules (ADR 0013): the agent must be reachable on this operator's surface/auth.
    reachable = {a.id for a in routable(surface, session.auth_state)}
    if agent_id not in reachable:
        raise HTTPException(
            status_code=403, detail=f"agent {agent_id!r} is not reachable on this surface"
        )
    if agent.invocation.binding is not InvocationBinding.HTTP:
        # The in-process console streams through /chat; only http agents are invoked here.
        raise HTTPException(
            status_code=400,
            detail=f"agent {agent_id!r} declares no http invocation binding",
        )

    conversation_id = str(uuid.uuid4())
    turn_id = str(uuid.uuid4())
    turn_input: TurnInput = {
        "user_message": payload.message,
        "conversation_id": conversation_id,
        "turn_id": turn_id,
        "surface": "console",
        "language": payload.language or agent.default_language,
    }
    if payload.case_id:
        turn_input["case_id"] = payload.case_id

    outcome = await HttpTurnInvoker().invoke(
        agent_id,
        turn_input,
        # Forward the verified assertion the caller carried (0010 Phase B) — the invoker
        # refuses an empty one, so a dev with the key unset gets an honest red, not a leak.
        operator_assertion=request.headers.get(OPERATOR_ASSERTION_HEADER) or "",
        actor=session.subject_id or "operator",
        conversation_id=conversation_id,
        turn_id=turn_id,
    )
    return {
        "ok": outcome.ok,
        "verdict": outcome.verdict,
        "status_code": outcome.status_code,
        "duration_ms": outcome.duration_ms,
        "error": outcome.error,
        "conformance": list(outcome.conformance),
        "result": outcome.result,
        "conversation_id": conversation_id,
        "turn_id": turn_id,
    }
