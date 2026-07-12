"""Unit tests for the inter-agent supervisor and the S1 handoff event (Phase 2)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from tessera.agent import supervisor
from tessera.agent.identity import DEFAULT_AGENT_ID
from tessera.agent.registry import AuthState, Surface
from tessera.guard import audit
from tessera.settings import get_settings

if TYPE_CHECKING:
    from pathlib import Path


# The shared customer widget is the only live surface; tests pin the auth-state
# explicitly to exercise the gating (anonymous vs an authenticated customer).
_WIDGET = Surface.SHARED_CUSTOMER_WIDGET


# --- supervisor routing --------------------------------------------------------


def test_stays_on_current_agent_without_a_clear_intent() -> None:
    d = supervisor.route_turn(
        "support-client", "Quel est mon solde ?", surface=_WIDGET, auth_state=AuthState.ANONYMOUS
    )
    assert d.agent_id == "support-client"
    assert d.handoff is False
    assert d.from_agent is None


def test_new_conversation_defaults_to_the_default_agent() -> None:
    d = supervisor.route_turn(None, "Bonjour", surface=_WIDGET, auth_state=AuthState.ANONYMOUS)
    assert d.agent_id == DEFAULT_AGENT_ID
    assert d.handoff is False


def test_intent_triggers_a_governed_handoff() -> None:
    # support-client -> onboarding is declared on both ends -> allowed.
    d = supervisor.route_turn(
        "support-client",
        "Je voudrais ouvrir un nouveau compte.",
        surface=_WIDGET,
        auth_state=AuthState.ANONYMOUS,
    )
    assert d.agent_id == "onboarding"
    assert d.handoff is True
    assert d.from_agent == "support-client"
    assert "onboarding" in d.reason


def test_handoff_is_refused_when_the_contract_does_not_allow_the_edge() -> None:
    # onboarding -> recouvrement is NOT declared (and recouvrement is off the
    # widget entirely) -> stay put despite the intent, even when authenticated.
    d = supervisor.route_turn(
        "onboarding",
        "J'ai un impayé, je voudrais un échéancier de recouvrement.",
        surface=_WIDGET,
        auth_state=AuthState.CUSTOMER,
    )
    assert d.agent_id == "onboarding"
    assert d.handoff is False


def test_no_self_handoff_when_intent_matches_current_agent() -> None:
    d = supervisor.route_turn(
        "onboarding",
        "Quelles pièces pour ouvrir un compte ?",
        surface=_WIDGET,
        auth_state=AuthState.ANONYMOUS,
    )
    assert d.agent_id == "onboarding"
    assert d.handoff is False


# --- ADR 0008: surface/auth-scoped routing ------------------------------------


def test_anonymous_widget_never_routes_into_recouvrement() -> None:
    # (a) The anonymous widget pool excludes recouvrement: even an explicit
    # recouvrement intent cannot route or hand into the customer-auth agent.
    d = supervisor.route_turn(
        "support-client",
        "J'ai un impayé, je voudrais un échéancier de recouvrement.",
        surface=_WIDGET,
        auth_state=AuthState.ANONYMOUS,
    )
    assert d.agent_id == "support-client"
    assert d.handoff is False


def test_operator_console_lands_on_the_routable_operator_agent() -> None:
    # ADR 0010 Phase B: on the cockpit-embedded operator surface the default
    # support agent is off-surface, so the supervisor falls back to the agent the
    # surface actually permits (recouvrement) rather than the off-surface default.
    d = supervisor.route_turn(
        None,
        "Bonjour",
        surface=Surface.COCKPIT_EMBEDDED,
        auth_state=AuthState.OPERATOR,
    )
    assert d.agent_id == "recouvrement"
    assert d.handoff is False


def test_a_gated_out_parcours_agent_falls_back_to_the_default() -> None:
    # A conversation parked on recouvrement, seen now under an anonymous session,
    # must not retain the gated-out agent — it falls back to the default.
    d = supervisor.route_turn(
        "recouvrement", "Bonjour", surface=_WIDGET, auth_state=AuthState.ANONYMOUS
    )
    assert d.agent_id == DEFAULT_AGENT_ID
    assert d.handoff is False


def test_authenticated_customer_still_cannot_reach_recouvrement() -> None:
    # (b) ADR 0010 Phase A: recouvrement is operator-only, off the customer widget.
    # Even an authenticated customer with an explicit impayé intent stays on
    # support-client — the cross-audience handoff edge no longer exists.
    d = supervisor.route_turn(
        "support-client",
        "J'ai un impayé, je voudrais un échéancier de recouvrement.",
        surface=_WIDGET,
        auth_state=AuthState.CUSTOMER,
    )
    assert d.agent_id == "support-client"
    assert d.handoff is False


# --- S1 handoff event ----------------------------------------------------------


@pytest.fixture
def audit_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "audit.log"
    settings = get_settings()
    monkeypatch.setattr(settings.guard, "audit_file", path)
    monkeypatch.setattr(settings.guard, "audit_sink", "file")
    monkeypatch.setattr(audit, "_last_hash", None)
    return path


def test_handoff_event_is_a_distinct_s1_type_in_the_same_chain(audit_file: Path) -> None:
    # A guard audit, then an agent->agent handoff, share one hash chain.
    audit.emit_audit(
        target="account_balance",
        arguments={},
        decisions=[],
        sink="file",
        outcome="allowed",
        actor=audit.GUARD_ACTOR,
    )
    audit.emit_handoff(
        from_agent="support-client",
        to_agent="onboarding",
        conversation_id="conv-1",
        turn_id="turn-2",
        reason="intent->onboarding",
    )
    lines = [json.loads(line) for line in audit_file.read_text().splitlines() if line.strip()]
    assert lines[0]["type"] == "tessera.guard.audit"
    handoff = lines[1]
    # Distinct event type, never the human-escalation tool.
    assert handoff["type"] == "tessera.agent.handoff"
    assert handoff["from_agent"] == "support-client"
    assert handoff["to_agent"] == "onboarding"
    assert handoff["agent_id"] == "onboarding"  # credited to the receiving agent
    assert handoff["actor"] == "system:supervisor"  # named: not a bare "system" nobody can place
    # Chained onto the previous entry (tamper-evident across event types).
    assert handoff["prev_hash"] == lines[0]["hash"]
    status = audit.verify_audit_chain(audit_file)
    assert status.verified is True
    assert status.length == 2


def test_every_routing_decision_is_audited_with_its_reason(audit_file: Path) -> None:
    # A stay decision AND a switch decision are both recorded (not only handoffs),
    # so routing is opposable from the start.
    audit.emit_routing(
        agent_id="support-client",
        conversation_id="conv-1",
        turn_id="turn-1",
        reason="stay->support-client",
        handoff=False,
    )
    audit.emit_routing(
        agent_id="onboarding",
        conversation_id="conv-1",
        turn_id="turn-2",
        reason="intent->onboarding (handoff support-client->onboarding)",
        handoff=True,
        from_agent="support-client",
    )
    lines = [json.loads(line) for line in audit_file.read_text().splitlines() if line.strip()]
    assert all(line["type"] == "tessera.agent.routing" for line in lines)
    assert lines[0]["handoff"] is False  # the initial "why this agent" is proven
    assert lines[0]["reason"] == "stay->support-client"
    assert lines[1]["handoff"] is True
    assert lines[1]["from_agent"] == "support-client"
    assert audit.verify_audit_chain(audit_file).verified is True
