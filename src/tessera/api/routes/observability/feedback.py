"""Customer-plane feedback endpoint — the 👍/👎 on an assistant reply (ADR 0041).

Customer-plane and self-authenticating, exactly like ``POST /chat`` and
``GET /session/transcript``: there is no operator assertion (the customer is anonymous),
and the write is bound to a conversation by the signed resume capability the browser holds
from ``turn.start`` (ADR 0008, audit P1 F-4). It names no author and writes no governance
ledger entry — it is customer telemetry, not a governed operator act.

The rated turn's agent and test-marker are resolved from the transcript, so the vote is
attributed to the agent that actually handled the turn and a vote on an operator TEST turn
is itself excluded from the real CSAT (ADR 0040). Mounted on a bearer-less router with no
operator dependency; declared in ``test_mutation_routes_carry_auth``'s SELF_AUTHENTICATING
set (anonymous is a legitimate auth state on the customer plane).
"""

from __future__ import annotations

from uuid import UUID  # noqa: TCH003 — pydantic resolves this annotation at runtime

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from tessera.api.session import RESUME_TOKEN_HEADER, verify_resume_token
from tessera.memory.transcript import turn_agent_and_synthetic
from tessera.observability.customer_feedback import RATINGS, record_customer_feedback

router = APIRouter(tags=["customer-feedback"])


class CustomerFeedbackRequest(BaseModel):
    """A customer's vote on one assistant turn."""

    model_config = ConfigDict(extra="forbid")

    conversation_id: UUID
    turn_id: UUID
    rating: str = Field(min_length=1, max_length=8)


@router.post("/observability/customer-feedback")
async def customer_feedback(
    payload: CustomerFeedbackRequest, request: Request
) -> dict[str, object]:
    """Record a customer's 👍/👎 on an assistant reply.

    Self-authenticating: requires the signed resume capability bound to
    ``conversation_id`` (the same gate as ``GET /session/transcript``), so an anonymous
    caller can only rate a conversation the browser provably held — never an arbitrary id.
    The rated turn must exist in the transcript; its agent and test-marker are inherited.
    """
    if payload.rating not in RATINGS:
        raise HTTPException(status_code=422, detail="rating must be 'up' or 'down'")
    presented = request.headers.get(RESUME_TOKEN_HEADER)
    if not presented or not verify_resume_token(presented, str(payload.conversation_id)):
        raise HTTPException(
            status_code=403,
            detail="a valid resume capability is required to leave feedback",
        )
    attribution = await turn_agent_and_synthetic(payload.turn_id)
    if attribution is None:
        raise HTTPException(status_code=404, detail="unknown turn")
    agent_id, synthetic = attribution
    await record_customer_feedback(
        payload.conversation_id,
        payload.turn_id,
        agent_id=agent_id,
        rating=payload.rating,
        synthetic=synthetic,
    )
    return {"ok": True, "rating": payload.rating}
