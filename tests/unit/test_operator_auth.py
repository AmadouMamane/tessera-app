"""Operator-identity forwarding to the agent (ADR 0010 Phase B).

Covers the trust mechanism end to end: (a) a console request carrying a valid
signed operator assertion → OPERATOR on the cockpit surface, and recouvrement
becomes routable/reachable; (b) a request without a valid assertion → not
operator, recouvrement unreachable; (c) the customer widget is never operator;
(d) a forged assertion or a raw unsigned header buys nothing (no escalation);
(e) production without the signing key is fail-closed; (f) the customer/anonymous
path is untouched (still derived from the signed cookie).
"""

from __future__ import annotations

import json

import pytest
from pydantic import SecretStr
from starlette.requests import Request

from tessera.agent import supervisor
from tessera.agent.registry import routable
from tessera.api import operator as operator_mod
from tessera.api.operator import (
    OPERATOR_ASSERTION_HEADER,
    issue_operator_assertion,
    resolve_request_context,
    validate_operator_assertion_key,
    verify_operator_assertion,
)
from tessera.api.session import SESSION_COOKIE, issue_session_token
from tessera.authz import AuthState, Surface
from tessera.settings import Environment, get_settings

_OP_KEY = "operator-assertion-test-key"


@pytest.fixture
def operator_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure a real operator signing key (mint+verify share it)."""
    settings = get_settings()
    monkeypatch.setattr(settings.api, "operator_assertion_signing_key", SecretStr(_OP_KEY))


def _request(*, assertion: str | None = None, customer_cookie: str | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if assertion is not None:
        headers.append((OPERATOR_ASSERTION_HEADER.encode(), assertion.encode()))
    if customer_cookie is not None:
        headers.append((b"cookie", f"{SESSION_COOKIE}={customer_cookie}".encode()))
    return Request({"type": "http", "headers": headers})


# --- (a) console + operator session → OPERATOR → recouvrement reachable --------


def test_valid_assertion_yields_an_operator_session(operator_key: None) -> None:
    token = issue_operator_assertion("admin", "admin")
    verified = verify_operator_assertion(token)
    assert verified is not None
    ctx, surface = verified
    assert ctx.auth_state is AuthState.OPERATOR
    assert ctx.authenticated is True
    assert ctx.subject_id == "admin"
    assert surface is Surface.COCKPIT_EMBEDDED


def test_console_operator_resolves_cockpit_surface_and_reaches_recouvrement(
    operator_key: None,
) -> None:
    token = issue_operator_assertion("auditor", "auditor")
    ctx, surface = resolve_request_context(_request(assertion=token))
    assert ctx.auth_state is AuthState.OPERATOR
    assert surface is Surface.COCKPIT_EMBEDDED
    # The operator pool on the cockpit surface includes recouvrement...
    pool = {a.id for a in routable(surface, ctx.auth_state)}
    assert "recouvrement" in pool
    # ...and the supervisor actually lands the turn on it (off-surface default
    # support agent falls back to the routable operator agent).
    decision = supervisor.route_turn(
        None, "Relance sur un impayé", surface=surface, auth_state=ctx.auth_state
    )
    assert decision.agent_id == "recouvrement"


# --- (b) console without an operator session → not operator --------------------


def test_request_without_assertion_stays_customer_widget(operator_key: None) -> None:
    # The BFF mints nothing without an operator session, so the agent sees no
    # assertion header → it resolves the customer path (anonymous here).
    ctx, surface = resolve_request_context(_request())
    assert ctx.auth_state is AuthState.ANONYMOUS
    assert surface is Surface.SHARED_CUSTOMER_WIDGET
    pool = {a.id for a in routable(surface, ctx.auth_state)}
    assert "recouvrement" not in pool


# --- (c) the customer widget is never operator ---------------------------------


def test_customer_cookie_is_customer_widget_never_operator(operator_key: None) -> None:
    cookie = issue_session_token("demo-customer-001", AuthState.CUSTOMER)
    ctx, surface = resolve_request_context(_request(customer_cookie=cookie))
    assert ctx.auth_state is AuthState.CUSTOMER
    assert surface is Surface.SHARED_CUSTOMER_WIDGET
    pool = {a.id for a in routable(surface, ctx.auth_state)}
    assert "recouvrement" not in pool


# --- (d) forged assertion / raw unsigned header buys nothing -------------------


def test_forged_assertion_is_rejected(operator_key: None) -> None:
    # Edit the payload to claim a role but keep the old signature → MAC fails.
    token = issue_operator_assertion("admin", "admin")
    body, _, signature = token.partition(".")
    forged_payload = operator_mod._b64e(
        json.dumps(
            {
                "principal": "attacker",
                "role": "admin",
                "surface": "cockpit-embedded",
                "iat": 9_999_999_999,
            }
        ).encode()
    )
    forged = f"{forged_payload}.{signature}"
    assert verify_operator_assertion(forged) is None
    # And the request falls back to the customer path (no escalation, no error).
    ctx, surface = resolve_request_context(_request(assertion=forged))
    assert ctx.auth_state is AuthState.ANONYMOUS
    assert surface is Surface.SHARED_CUSTOMER_WIDGET


def test_raw_unsigned_header_is_not_honoured(operator_key: None) -> None:
    # A bare role string (or any unsigned value) in the header is not a valid
    # assertion — the agent trusts the HMAC, never a raw header value.
    for raw in ("admin", "operator", "cockpit-embedded", "not.a.token"):
        assert verify_operator_assertion(raw) is None
        ctx, surface = resolve_request_context(_request(assertion=raw))
        assert ctx.auth_state is AuthState.ANONYMOUS
        assert surface is Surface.SHARED_CUSTOMER_WIDGET


def test_assertion_with_a_non_operator_role_is_rejected(operator_key: None) -> None:
    token = issue_operator_assertion("someone", "visitor")
    assert verify_operator_assertion(token) is None


def test_assertion_must_carry_an_operator_surface_not_the_widget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A validly-signed token claiming the customer widget surface is still refused:
    # an assertion can never claim the widget (only cockpit-embedded / dedicated-ui).
    settings = get_settings()
    monkeypatch.setattr(settings.api, "operator_assertion_signing_key", SecretStr(_OP_KEY))
    import hashlib
    import hmac
    import time

    payload = operator_mod._b64e(
        json.dumps(
            {
                "principal": "admin",
                "role": "admin",
                "surface": "shared-customer-widget",
                "iat": int(time.time()),
            },
            separators=(",", ":"),
        ).encode()
    )
    sig = operator_mod._b64e(
        hmac.new(_OP_KEY.encode(), payload.encode("ascii"), hashlib.sha256).digest()
    )
    assert verify_operator_assertion(f"{payload}.{sig}") is None


# --- Phase C: collections role + dedicated-ui business console ------------------


def test_collections_role_on_dedicated_ui_reaches_recouvrement(operator_key: None) -> None:
    # (a) A collections session, entering recouvrement's business console, mints an
    # assertion {role: collections, surface: dedicated-ui}. The agent verifies it →
    # OPERATOR on dedicated-ui, where the routable pool is exactly {recouvrement},
    # and the supervisor lands the turn on recouvrement (the real chat core).
    token = issue_operator_assertion("collections-001", "collections", Surface.DEDICATED_UI)
    ctx, surface = resolve_request_context(_request(assertion=token))
    assert ctx.auth_state is AuthState.OPERATOR
    assert surface is Surface.DEDICATED_UI
    assert ctx.subject_id == "collections-001"
    pool = {a.id for a in routable(surface, ctx.auth_state)}
    assert pool == {"recouvrement"}
    decision = supervisor.route_turn(None, "Bonjour", surface=surface, auth_state=ctx.auth_state)
    assert decision.agent_id == "recouvrement"


def test_platform_role_may_supervise_the_dedicated_ui_console(operator_key: None) -> None:
    # A platform operator may supervise the business console — the assertion carries
    # its real role but the dedicated-ui surface; it still reaches recouvrement only.
    token = issue_operator_assertion("admin", "admin", Surface.DEDICATED_UI)
    ctx, surface = resolve_request_context(_request(assertion=token))
    assert ctx.auth_state is AuthState.OPERATOR
    assert surface is Surface.DEDICATED_UI


def test_dedicated_ui_does_not_widen_the_customer_or_cockpit_pools(operator_key: None) -> None:
    # (c) dedicated-ui carries only recouvrement; the customer widget and the
    # cockpit pools are unchanged by Phase C.
    assert {a.id for a in routable(Surface.SHARED_CUSTOMER_WIDGET, AuthState.CUSTOMER)} == {
        "support-client",
        "onboarding",
    }
    assert "recouvrement" in {a.id for a in routable(Surface.COCKPIT_EMBEDDED, AuthState.OPERATOR)}


def test_collections_assertion_forged_is_rejected(operator_key: None) -> None:
    # (d) A forged dedicated-ui/collections token (tampered payload, stale sig) is
    # rejected and falls back to the customer path — no business-console access.
    token = issue_operator_assertion("collections-001", "collections", Surface.DEDICATED_UI)
    _, _, signature = token.partition(".")
    forged_payload = operator_mod._b64e(
        json.dumps(
            {
                "principal": "attacker",
                "role": "collections",
                "surface": "dedicated-ui",
                "iat": 9_999_999_999,
            }
        ).encode()
    )
    assert verify_operator_assertion(f"{forged_payload}.{signature}") is None


# --- (e) production without the key is fail-closed -----------------------------


def test_missing_key_in_production_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "environment", Environment.PRODUCTION)
    monkeypatch.setattr(settings.api, "operator_assertion_signing_key", None)
    with pytest.raises(RuntimeError, match="required in production"):
        validate_operator_assertion_key()


def test_dev_without_key_leaves_operator_path_inert(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "environment", Environment.LOCAL)
    monkeypatch.setattr(settings.api, "operator_assertion_signing_key", None)
    validate_operator_assertion_key()  # no raise in dev
    # No key → nothing verifies, and the request resolves to the customer path.
    ctx, surface = resolve_request_context(_request(assertion="anything"))
    assert ctx.auth_state is AuthState.ANONYMOUS
    assert surface is Surface.SHARED_CUSTOMER_WIDGET


# --- (f) customer / anonymous path unchanged -----------------------------------


def test_anonymous_and_customer_paths_are_unchanged(operator_key: None) -> None:
    anon_ctx, anon_surface = resolve_request_context(_request())
    assert anon_ctx.auth_state is AuthState.ANONYMOUS
    assert anon_surface is Surface.SHARED_CUSTOMER_WIDGET

    cookie = issue_session_token("demo-customer-001", AuthState.CUSTOMER)
    cust_ctx, cust_surface = resolve_request_context(_request(customer_cookie=cookie))
    assert cust_ctx.auth_state is AuthState.CUSTOMER
    assert cust_ctx.subject_id == "demo-customer-001"
    assert cust_surface is Surface.SHARED_CUSTOMER_WIDGET
