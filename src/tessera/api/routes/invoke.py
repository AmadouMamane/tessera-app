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
from pydantic import BaseModel, ConfigDict, Field, model_validator

from tessera.agent.capability_schema import load_input_schema, validate_params
from tessera.agent.registry import Agent, InvocationBinding, get_agent, routable
from tessera.api.agent_invoker import HttpTurnInvoker
from tessera.api.operator import OPERATOR_ASSERTION_HEADER, resolve_request_context
from tessera.authz import AuthState

if TYPE_CHECKING:
    from tessera.agent.turn_contract import TurnAction, TurnInput

router = APIRouter(tags=["invoke"])


class InvokeAction(BaseModel):
    """A typed capability invocation — the generated form's submission (ADR 0018 §2)."""

    model_config = ConfigDict(extra="forbid")

    capability_id: str = Field(min_length=1, max_length=120)
    params: dict[str, object] = Field(default_factory=dict)


class InvokeRequest(BaseModel):
    """A single test turn for an http-binding agent (the Console's invocation body).

    Exactly one of ``message`` / ``action`` (ADR 0018 §2 + §7): buttons and generated forms
    dispatch typed actions, free messages go through the agent's own intent router. Sending both
    would leave the agent to guess which one the operator meant, and it must never have to.
    """

    model_config = ConfigDict(extra="forbid")

    message: str | None = Field(default=None, min_length=1, max_length=4_000)
    action: InvokeAction | None = None
    case_id: str | None = Field(default=None, max_length=120)
    language: str | None = Field(default=None, max_length=12)

    @model_validator(mode="after")
    def _exactly_one_input(self) -> InvokeRequest:
        if (self.message is None) == (self.action is None):
            msg = "exactly one of 'message' or 'action' is required"
            raise ValueError(msg)
        return self


def _checked_action(agent: Agent, action: InvokeAction) -> TurnAction:
    """Turn a form submission into a `TurnAction`, refusing anything the agent did not declare.

    The platform declared the capability's shape, so it is the platform that refuses a turn which
    does not match it — before the request leaves the process. Forwarding unvalidated params would
    make the agent's contract advisory, and make a 500 from a foreign runtime look like the
    operator's fault.
    """
    spec = agent.observability
    capabilities = {c.id: c for c in spec.capabilities} if spec is not None else {}
    capability = capabilities.get(action.capability_id)
    if capability is None:
        raise HTTPException(
            status_code=400,
            detail=f"agent {agent.id!r} declares no capability {action.capability_id!r}",
        )
    if not capability.input_schema:
        raise HTTPException(
            status_code=400,
            detail=f"capability {action.capability_id!r} declares no input_schema",
        )
    violations = validate_params(load_input_schema(capability.input_schema), action.params)
    if violations:
        raise HTTPException(status_code=422, detail={"params": violations})
    return {"type": action.capability_id, "params": action.params}


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
        "conversation_id": conversation_id,
        "turn_id": turn_id,
        "surface": "console",
        "language": payload.language or agent.default_language,
    }
    if payload.action is not None:
        turn_input["action"] = _checked_action(agent, payload.action)
    else:
        # The validator guarantees exactly one of the two is set.
        turn_input["user_message"] = payload.message or ""
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
        # This route IS the Console test bench: operator-only, never on a product path
        # (an anonymous or customer session is refused above). Every turn it drives is a
        # test turn, so it declares the posture the agent must propagate (ADR 0019 §A1.1).
        synthetic=True,
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
