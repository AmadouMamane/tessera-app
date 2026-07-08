"""AgentSpec invocation block — schema + validation (ADR 0019 §1, phase I1).

The invocation block is the declared cockpit→agent seam. Like the rest of the manifest it is
an API, not config: ``extra="forbid"`` + closed vocabularies + a shape validator make every
illegal state a load error. These tests are the CI gate for that contract. The runtime pieces
(the http invoker = I3, the canary scheduler = I4) are out of scope here — this phase ships the
declaration only, and asserts it changes no behaviour for the three native agents.
"""

from __future__ import annotations

import pytest

from tessera.agent.agentspec import (
    InvocationAuth,
    InvocationBinding,
    InvocationSpec,
    parse_invocation,
)
from tessera.agent.registry import get_agent, list_agents

# --- defaults + the three bindings parse ----------------------------------------


def test_default_binding_is_none() -> None:
    # The honest default: an agent that declares nothing is publish-only, never a broken chat.
    spec = InvocationSpec()
    assert spec.binding is InvocationBinding.NONE
    assert spec.endpoint is None and spec.timeout_ms is None and spec.auth is None


def test_none_binding_parses() -> None:
    spec = parse_invocation({"binding": "none"})
    assert spec.binding is InvocationBinding.NONE


def test_in_process_chat_binding_parses() -> None:
    spec = parse_invocation({"binding": "in_process_chat"})
    assert spec.binding is InvocationBinding.IN_PROCESS_CHAT


def test_http_binding_parses_with_required_fields() -> None:
    spec = parse_invocation(
        {
            "binding": "http",
            "endpoint": "https://agent.example/turn",
            "timeout_ms": 15000,
            "auth": "operator-assertion",
        }
    )
    assert spec.binding is InvocationBinding.HTTP
    assert spec.endpoint == "https://agent.example/turn"
    assert spec.timeout_ms == 15000
    assert spec.auth is InvocationAuth.OPERATOR_ASSERTION


# --- the manifest is an API (extra=forbid, closed vocabularies) ------------------


def test_unknown_key_is_rejected() -> None:
    with pytest.raises(ValueError, match="invocation block"):
        parse_invocation({"binding": "none", "bindng": "oops"})


def test_unknown_binding_is_rejected() -> None:
    with pytest.raises(ValueError, match="invocation block"):
        parse_invocation({"binding": "grpc"})


def test_unknown_auth_is_rejected() -> None:
    with pytest.raises(ValueError, match="invocation block"):
        parse_invocation({"binding": "http", "endpoint": "https://x/turn", "auth": "anonymous"})


# --- shape: illegal states are unrepresentable -----------------------------------


def test_http_without_endpoint_is_rejected() -> None:
    with pytest.raises(ValueError, match="requires an endpoint"):
        parse_invocation({"binding": "http", "auth": "operator-assertion"})


def test_http_without_auth_is_rejected() -> None:
    # No anonymous invocation, ever (ADR 0019 §4): http must name the auth posture.
    with pytest.raises(ValueError, match="requires auth"):
        parse_invocation({"binding": "http", "endpoint": "https://x/turn"})


def test_http_non_positive_timeout_is_rejected() -> None:
    with pytest.raises(ValueError, match="timeout_ms must be positive"):
        parse_invocation(
            {
                "binding": "http",
                "endpoint": "https://x/turn",
                "auth": "operator-assertion",
                "timeout_ms": 0,
            }
        )


@pytest.mark.parametrize(
    "raw",
    [
        {"binding": "none", "endpoint": "https://x/turn"},
        {"binding": "in_process_chat", "timeout_ms": 15000},
        {"binding": "none", "auth": "operator-assertion"},
        {"binding": "in_process_chat", "endpoint": "https://x/turn"},
    ],
)
def test_http_only_fields_forbidden_on_other_bindings(raw: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="must not set http-only fields"):
        parse_invocation(raw)


# --- the native declarations (no behaviour change) -------------------------------


def test_native_agents_declare_in_process_chat() -> None:
    for aid in ("support-client", "onboarding", "recouvrement"):
        assert get_agent(aid).invocation.binding is InvocationBinding.IN_PROCESS_CHAT


def test_hello_agent_declares_none() -> None:
    assert get_agent("hello-agent").invocation.binding is InvocationBinding.NONE


def test_every_agent_carries_an_invocation_posture() -> None:
    # Always present (never None): every agent has an honest invocation posture — the seam is
    # enumerable across the whole fleet, which is what makes the cockpit→agent surface auditable.
    for agent in list_agents():
        assert isinstance(agent.invocation, InvocationSpec)
