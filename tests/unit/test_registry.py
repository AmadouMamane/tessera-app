"""Unit tests for the agent registry (multi-agent Phase 1)."""

from __future__ import annotations

import pytest

from tessera.agent.identity import DEFAULT_AGENT_ID
from tessera.agent.registry import (
    AuthState,
    Surface,
    _coerce_agent,
    can_handoff,
    get_agent,
    list_agents,
    routable,
)

_WIDGET = Surface.SHARED_CUSTOMER_WIDGET


def test_registry_has_the_three_seeded_agents() -> None:
    ids = [a.id for a in list_agents()]
    assert ids == ["support-client", "onboarding", "recouvrement"]


def test_default_agent_is_present_and_matches_identity() -> None:
    assert DEFAULT_AGENT_ID in {a.id for a in list_agents()}
    assert get_agent(DEFAULT_AGENT_ID).name == "Support Client"


def test_agents_bind_catalogue_blocks() -> None:
    support = get_agent("support-client")
    # Bindings reference catalogue items by id (define/choose/govern), not free text.
    assert "credit_aurore" in support.knowledge
    assert "account_balance" in support.tools
    assert support.model == "llama3.2:3b"
    assert support.owner == "Équipe Support"


def test_handoff_contract_is_bidirectional_and_governed() -> None:
    # Declared on both ends, both routable on the widget -> allowed.
    assert can_handoff(
        "support-client", "onboarding", surface=_WIDGET, auth_state=AuthState.ANONYMOUS
    )
    assert can_handoff(
        "onboarding", "support-client", surface=_WIDGET, auth_state=AuthState.ANONYMOUS
    )
    # recouvrement <-> onboarding is NOT declared -> refused (even authenticated).
    assert not can_handoff(
        "recouvrement", "onboarding", surface=_WIDGET, auth_state=AuthState.CUSTOMER
    )
    # unknown agents -> refused, never raises.
    assert not can_handoff(
        "support-client", "ghost", surface=_WIDGET, auth_state=AuthState.ANONYMOUS
    )


def test_get_agent_unknown_raises() -> None:
    with pytest.raises(KeyError):
        get_agent("does-not-exist")


# --- ADR 0008: audience / surface / auth bindings + scoped pool ----------------


def test_agents_declare_audience_surface_auth() -> None:
    from tessera.agent.registry import Audience, Auth

    recouvrement = get_agent("recouvrement")
    assert recouvrement.audience is Audience.CUSTOMER
    assert _WIDGET in recouvrement.surface
    # The single behavioural change: recouvrement is gated to customer-auth.
    assert recouvrement.auth is Auth.CUSTOMER_AUTH
    assert get_agent("support-client").auth is Auth.ANONYMOUS_OK


def test_anonymous_widget_pool_excludes_recouvrement() -> None:
    # (a) The least-privileged surface cannot reach the most sensitive agent.
    pool = {a.id for a in routable(_WIDGET, AuthState.ANONYMOUS)}
    assert "recouvrement" not in pool
    assert {"support-client", "onboarding"} <= pool


def test_authenticated_widget_pool_includes_recouvrement() -> None:
    # (c) An authenticated customer session reaches recouvrement.
    pool = {a.id for a in routable(_WIDGET, AuthState.CUSTOMER)}
    assert "recouvrement" in pool


def test_no_cross_surface_handoff() -> None:
    # (b) A handoff legal on the widget is refused from a different surface: no
    # agent is exposed on dedicated-ui in the interim fleet, so the pool is empty
    # there and the otherwise-legal support<->onboarding edge cannot fire.
    assert can_handoff(
        "support-client", "onboarding", surface=_WIDGET, auth_state=AuthState.ANONYMOUS
    )
    assert not can_handoff(
        "support-client",
        "onboarding",
        surface=Surface.DEDICATED_UI,
        auth_state=AuthState.OPERATOR,
    )


def _valid_raw() -> dict[str, object]:
    return {
        "id": "probe",
        "name": "Probe",
        "audience": "customer",
        "surface": ["shared-customer-widget"],
        "auth": "anonymous-ok",
    }


def test_invalid_auth_enum_is_rejected_at_load() -> None:
    raw = _valid_raw() | {"auth": "superuser"}
    with pytest.raises(ValueError, match="unknown auth"):
        _coerce_agent(raw)


def test_invalid_surface_enum_is_rejected_at_load() -> None:
    raw = _valid_raw() | {"surface": ["mainframe-terminal"]}
    with pytest.raises(ValueError, match="unknown surface"):
        _coerce_agent(raw)


def test_invalid_audience_enum_is_rejected_at_load() -> None:
    raw = _valid_raw() | {"audience": "robot"}
    with pytest.raises(ValueError, match="unknown audience"):
        _coerce_agent(raw)
