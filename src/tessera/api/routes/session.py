"""Customer session endpoints — demo login/logout + session introspection (ADR 0008/0009).

These are **customer-facing** (like ``/chat``), not operator surfaces, so they are
not behind the bearer gate. "Login" is demo-fidelity: it establishes a signed
session for the single seeded customer identity — no password, no KYC, no IdP. The
signature, cookie hardening, and server-side ``auth_state`` derivation are real
(see :mod:`tessera.api.session`).
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict
from starlette.requests import (
    Request,  # noqa: TCH002  runtime-needed: FastAPI resolves the handler annotation
)
from starlette.responses import JSONResponse

from tessera.api.session import (
    DEMO_CUSTOMER_ID,
    DEMO_CUSTOMER_LABEL,
    clear_session_cookie,
    issue_session_token,
    resolve_session,
    set_session_cookie,
)
from tessera.authz import AuthState

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
    server reads back, which is what makes recouvrement and the account tools
    reachable (ADR 0008 gating).
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
