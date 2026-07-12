"""Customer session endpoints — demo login/logout + session introspection (ADR 0008/0009).

These are **customer-facing** (like ``/chat``), not operator surfaces, so they are
not behind the bearer gate. "Login" is demo-fidelity: it establishes a signed
session for the single seeded customer identity — no password, no KYC, no IdP. The
signature, cookie hardening, and server-side ``auth_state`` derivation are real
(see :mod:`tessera.api.session`).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict
from starlette import status
from starlette.requests import (
    Request,  # noqa: TCH002  runtime-needed: FastAPI resolves the handler annotation
)
from starlette.responses import JSONResponse

from tessera.api.session import (
    DEMO_CUSTOMER_ID,
    DEMO_CUSTOMER_LABEL,
    RESUME_TOKEN_HEADER,
    clear_session_cookie,
    issue_session_token,
    resolve_session,
    set_session_cookie,
    verify_resume_token,
)
from tessera.authz import AuthState
from tessera.memory.transcript import load_transcript

router = APIRouter(tags=["session"])


class SessionState(BaseModel):
    """The current session, as the frontend reflects it."""

    model_config = ConfigDict(extra="forbid")

    authenticated: bool
    auth_state: str
    subject_id: str | None
    label: str | None
    demo: bool


def _state_payload(request: Request) -> dict[str, object]:
    ctx = resolve_session(request)
    return SessionState(
        authenticated=ctx.authenticated,
        auth_state=ctx.auth_state.value,
        subject_id=ctx.subject_id,
        label=ctx.label,
        demo=ctx.demo,
    ).model_dump()


@router.get("/session", response_model=SessionState)
async def session_state(request: Request) -> SessionState:
    """Return the caller's current session (anonymous when no valid cookie)."""
    return SessionState.model_validate(_state_payload(request))


@router.post("/session/login", response_model=SessionState)
async def session_login() -> JSONResponse:
    """Demo login — establish a CUSTOMER session for the seeded demo identity.

    Demo-assumed: no credentials are checked; this authenticates as the single
    seeded customer. Real part: it issues a signed cookie whose ``auth_state`` the
    server reads back, which is what makes the account tools reachable (ADR 0008
    gating). It does not unlock recouvrement — that agent is operator-only
    (ADR 0010 Phase A), off every customer-reachable surface.
    """
    token = issue_session_token(DEMO_CUSTOMER_ID, AuthState.CUSTOMER)
    body = SessionState(
        authenticated=True,
        auth_state=AuthState.CUSTOMER.value,
        subject_id=DEMO_CUSTOMER_ID,
        label=DEMO_CUSTOMER_LABEL,
        demo=True,
    )
    response = JSONResponse(body.model_dump())
    set_session_cookie(response, token)
    return response


@router.post("/session/logout", response_model=SessionState)
async def session_logout() -> JSONResponse:
    """Logout — clear the session cookie, returning to anonymous."""
    body = SessionState(
        authenticated=False,
        auth_state=AuthState.ANONYMOUS.value,
        subject_id=None,
        label=None,
        demo=False,
    )
    response = JSONResponse(body.model_dump())
    clear_session_cookie(response)
    return response


class OwnTranscriptMessage(BaseModel):
    """One persisted message of the caller's own conversation."""

    model_config = ConfigDict(extra="forbid")

    role: str
    content: str


class OwnTranscript(BaseModel):
    """The caller's own conversation, replayed for the widget after a reload."""

    model_config = ConfigDict(extra="forbid")

    conversation_id: str
    messages: list[OwnTranscriptMessage]


@router.get("/session/transcript", response_model=OwnTranscript)
async def own_transcript(request: Request, conversation_id: str) -> OwnTranscript:
    """Replay the caller's OWN conversation, against a signed resume capability.

    Audit 2026-07-12, **P1 F-4**. The product widget used to resume by asking
    ``/observability/conversation-messages`` for a raw id — an operator endpoint that
    answered anyone, for any conversation. That surface is now gated
    (:func:`~tessera.api.security.require_subject_reader`), and the customer keeps its own
    resume here, where the grant is *proved* rather than assumed: the caller must present
    the :func:`~tessera.api.session.issue_resume_token` capability this server minted, for
    **this** conversation, at ``turn.start``.

    Self-authenticating by design — like ``/chat`` and ``/session/login``, it belongs to the
    customer plane, which has no operator assertion and (today) no per-person identity. The
    capability is what stands in for one, and it is honest about being a bearer grant: it
    proves *this browser was told this id by this server*, not *who* the browser belongs to.

    Refusals, in the repo's two-code doctrine — and note that BOTH are 403, deliberately:
    there is no "log in and retry" here, since logging in would not help. A caller either
    holds the capability or does not.

    * **403** — no capability presented. The id alone is not a grant (it never was; the
      conversations directory published it next to the opening user message).
    * **403** — a capability that does not verify for THIS conversation: forged, edited,
      expired, or a valid token for a *different* conversation being swapped onto this id.
    """
    presented = request.headers.get(RESUME_TOKEN_HEADER)
    if not presented or not verify_resume_token(presented, conversation_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="a valid resume capability is required for this conversation",
        )
    try:
        stored = await load_transcript(UUID(conversation_id))
    except ValueError:  # malformed id — the capability cannot have verified for it anyway
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="a valid resume capability is required for this conversation",
        ) from None
    return OwnTranscript(
        conversation_id=conversation_id,
        messages=[
            OwnTranscriptMessage(role=m.role, content=m.content)
            for m in stored
            if m.role in ("user", "assistant")
        ],
    )
