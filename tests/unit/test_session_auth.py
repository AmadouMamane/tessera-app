"""Customer-auth wiring end to end (ADR 0008/0009).

Covers the four contract tests: (a) no session → anonymous → the account tools are
excluded; (b) a signed session → customer → the account tools become reachable
(recouvrement does NOT — it is operator-only, off the customer widget, ADR 0010
Phase A — so the customer pool excludes it at every auth state);
(c) auth_state comes from the *signed session*, never the body — a tampered token
buys nothing; (d) the cookie is httpOnly/SameSite and the signing key lives off
the repo (a forged signature is rejected).
"""

from __future__ import annotations

import json

import pytest
from pydantic import SecretStr
from starlette.requests import Request
from starlette.responses import JSONResponse

from tessera.agent.registry import Surface, routable
from tessera.api import session as session_mod
from tessera.api.session import (
    DEMO_CUSTOMER_ID,
    SESSION_COOKIE,
    issue_session_token,
    resolve_session,
    set_session_cookie,
    validate_session_signing_key,
    verify_session_token,
)
from tessera.authz import AuthState
from tessera.guard.adapter import guarded_invoke
from tessera.guard.audit import current_auth_state
from tessera.settings import Environment, LanguageCode, get_settings

_WIDGET = Surface.SHARED_CUSTOMER_WIDGET


def _request_with_cookie(token: str | None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if token is not None:
        headers.append((b"cookie", f"{SESSION_COOKIE}={token}".encode()))
    return Request({"type": "http", "headers": headers})


async def _try_account_balance() -> bool:
    """Invoke account_balance through the real guard chokepoint; return allowed."""

    async def _invoke() -> str:
        return "ok"

    result = await guarded_invoke(
        tool_name="account_balance",
        invoke=_invoke,
        arguments={"customer_id": DEMO_CUSTOMER_ID},
        language=LanguageCode.FR,
    )
    return result.allowed


# --- (a) anonymous: account tools excluded; recouvrement off the widget --------


def test_anonymous_session_is_anonymous_and_excludes_recouvrement() -> None:
    ctx = resolve_session(_request_with_cookie(None))
    assert ctx.auth_state is AuthState.ANONYMOUS
    assert ctx.authenticated is False
    pool = {a.id for a in routable(_WIDGET, ctx.auth_state)}
    assert "recouvrement" not in pool


@pytest.mark.asyncio
async def test_anonymous_session_is_denied_account_tools() -> None:
    token = current_auth_state.set(AuthState.ANONYMOUS)
    try:
        assert await _try_account_balance() is False
    finally:
        current_auth_state.reset(token)


# --- (b) authenticated: account tools reachable; recouvrement still excluded ---


def test_signed_session_is_customer_but_excludes_operator_recouvrement() -> None:
    signed = issue_session_token(DEMO_CUSTOMER_ID, AuthState.CUSTOMER)
    ctx = resolve_session(_request_with_cookie(signed))
    assert ctx.auth_state is AuthState.CUSTOMER
    assert ctx.authenticated is True
    assert ctx.subject_id == DEMO_CUSTOMER_ID
    # A customer login unlocks the account tools (asserted below) but NOT
    # recouvrement: it is operator-only (ADR 0010 Phase A), off the customer pool.
    pool = {a.id for a in routable(_WIDGET, ctx.auth_state)}
    assert "recouvrement" not in pool
    assert pool == {"support-client", "onboarding"}


@pytest.mark.asyncio
async def test_customer_session_is_allowed_account_tools() -> None:
    token = current_auth_state.set(AuthState.CUSTOMER)
    try:
        assert await _try_account_balance() is True
    finally:
        current_auth_state.reset(token)


# --- (c) auth_state from the signed session, never the body --------------------


def test_tampered_token_payload_is_rejected() -> None:
    # Forge an "operator" claim by editing the payload but keeping the old
    # signature → verification fails and the session is ignored (anonymous).
    signed = issue_session_token(DEMO_CUSTOMER_ID, AuthState.CUSTOMER)
    body, _, signature = signed.partition(".")
    forged_payload = session_mod._b64e(
        json.dumps({"sub": "attacker", "auth": "operator", "iat": 9999999999}).encode()
    )
    tampered = f"{forged_payload}.{signature}"
    assert verify_session_token(tampered) is None
    assert resolve_session(_request_with_cookie(tampered)).auth_state is AuthState.ANONYMOUS


def test_subject_swap_without_resign_is_rejected() -> None:
    # Re-signing requires the key (off-repo); without it, any edit breaks the MAC.
    signed = issue_session_token(DEMO_CUSTOMER_ID, AuthState.CUSTOMER)
    body, _, signature = signed.partition(".")
    swapped_body = session_mod._b64e(
        json.dumps({"sub": "someone-else", "auth": "customer", "iat": 9999999999}).encode()
    )
    assert verify_session_token(f"{swapped_body}.{signature}") is None


# --- (d) cookie hardening + signing key off-repo -------------------------------


def test_cookie_is_httponly_samesite_and_secure() -> None:
    response = JSONResponse({})
    set_session_cookie(response, issue_session_token(DEMO_CUSTOMER_ID, AuthState.CUSTOMER))
    set_cookie = response.headers.get("set-cookie", "")
    assert SESSION_COOKIE in set_cookie
    assert "httponly" in set_cookie.lower()
    assert "samesite=lax" in set_cookie.lower()
    assert "secure" in set_cookie.lower()  # tls_terminated defaults to True


def test_signing_key_is_not_in_the_repo_and_forgery_fails() -> None:
    # The key is read from settings (env / Secret Manager), defaulting to None in
    # the repo — there is no committed secret. A token signed with a foreign key
    # must not verify.
    assert get_settings().api.session_signing_key is None
    foreign = "deadbeef.deadbeefsignaturethatdoesnotmatch"
    assert verify_session_token(foreign) is None


# --- prod hardening: fail-closed when the signing key is missing ----------------


def test_production_without_key_refuses_to_start(monkeypatch: pytest.MonkeyPatch) -> None:
    # (a) prod + no key → the startup validation raises (refuse to boot), and the
    # lazy path refuses too (defence in depth) — never a silent ephemeral key.
    settings = get_settings()
    monkeypatch.setattr(settings, "environment", Environment.PRODUCTION)
    monkeypatch.setattr(settings.api, "session_signing_key", None)
    with pytest.raises(RuntimeError, match="required in production"):
        validate_session_signing_key()
    with pytest.raises(RuntimeError, match="required in production"):
        session_mod._signing_key()


def test_non_production_without_key_uses_ephemeral(monkeypatch: pytest.MonkeyPatch) -> None:
    # (b) non-prod + no key → ephemeral fallback, startup passes, signing works.
    settings = get_settings()
    monkeypatch.setattr(settings, "environment", Environment.LOCAL)
    monkeypatch.setattr(settings.api, "session_signing_key", None)
    validate_session_signing_key()  # no raise
    token = issue_session_token(DEMO_CUSTOMER_ID, AuthState.CUSTOMER)
    assert verify_session_token(token) is not None


def test_configured_key_is_used_in_any_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    # (c) key present → it is used, and prod startup passes.
    settings = get_settings()
    monkeypatch.setattr(settings, "environment", Environment.PRODUCTION)
    monkeypatch.setattr(settings.api, "session_signing_key", SecretStr("a-real-secret-key"))
    validate_session_signing_key()  # no raise — key present
    assert session_mod._signing_key() == b"a-real-secret-key"
    token = issue_session_token(DEMO_CUSTOMER_ID, AuthState.CUSTOMER)
    assert verify_session_token(token) is not None
