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


def test_registry_has_the_seeded_agents() -> None:
    ids = [a.id for a in list_agents()]
    # hello-agent (ADR 0017 §F) is the publish-only second-runtime acceptance agent;
    # turn-agent (ADR 0019 §I3) is the invocable one — out-of-process, http turn binding.
    assert ids == ["support-client", "onboarding", "recouvrement", "hello-agent", "turn-agent"]


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
    # support-client -> recouvrement is removed (ADR 0010 Phase A: no cross-audience
    # handoff into collections) -> refused even on an authenticated customer session.
    assert not can_handoff(
        "support-client", "recouvrement", surface=_WIDGET, auth_state=AuthState.CUSTOMER
    )
    # unknown agents -> refused, never raises.
    assert not can_handoff(
        "support-client", "ghost", surface=_WIDGET, auth_state=AuthState.ANONYMOUS
    )


def test_get_agent_unknown_raises() -> None:
    with pytest.raises(KeyError):
        get_agent("does-not-exist")


# --- ADR 0008: audience / surface / auth bindings + scoped pool ----------------


def test_recouvrement_is_an_internal_operator_agent() -> None:
    # ADR 0010 Phase A: recouvrement is reclassified off the customer widget onto
    # an operator surface, gated by operator-rbac — and it has no handoff edges.
    from tessera.agent.registry import Audience, Auth, Surface

    recouvrement = get_agent("recouvrement")
    assert recouvrement.audience is Audience.OPERATOR
    # Two operator surfaces: cockpit-embedded (Phase B) + dedicated-ui (Phase C).
    assert recouvrement.surface == (Surface.COCKPIT_EMBEDDED, Surface.DEDICATED_UI)
    assert _WIDGET not in recouvrement.surface
    assert recouvrement.auth is Auth.OPERATOR_RBAC
    assert recouvrement.handoff.to == ()
    assert recouvrement.handoff.from_ == ()
    # support-client no longer wires the cross-audience edge to/from collections.
    support = get_agent("support-client")
    assert "recouvrement" not in support.handoff.to
    assert "recouvrement" not in support.handoff.from_
    assert support.auth is Auth.ANONYMOUS_OK


def test_customer_widget_pool_excludes_recouvrement_at_every_auth() -> None:
    # (a) recouvrement is off every customer-reachable pool by construction: it is
    # not on the widget surface, so neither anonymous nor an authenticated customer
    # can reach it. The customer pool is exactly {support-client, onboarding}.
    for auth_state in (AuthState.ANONYMOUS, AuthState.CUSTOMER):
        pool = {a.id for a in routable(_WIDGET, auth_state)}
        assert "recouvrement" not in pool
        assert pool == {"support-client", "onboarding"}


def test_recouvrement_is_parked_on_the_operator_surface_not_deleted() -> None:
    # The agent is moved, not removed: it sits on the cockpit-embedded operator
    # pool (static contract). Honest reachability note — no interactive session yet
    # produces AuthState.OPERATOR (ADR 0010 Phase A parks it until Phase B).
    from tessera.agent.registry import Surface

    pool = {a.id for a in routable(Surface.COCKPIT_EMBEDDED, AuthState.OPERATOR)}
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
