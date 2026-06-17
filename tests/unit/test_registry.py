"""Unit tests for the agent registry (multi-agent Phase 1)."""

from __future__ import annotations

from tessera.agent.identity import DEFAULT_AGENT_ID
from tessera.agent.registry import (
    can_handoff,
    get_agent,
    list_agents,
)


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
    # Declared on both ends -> allowed.
    assert can_handoff("support-client", "onboarding")
    assert can_handoff("onboarding", "support-client")
    # recouvrement <-> onboarding is NOT declared -> refused.
    assert not can_handoff("recouvrement", "onboarding")
    # unknown agents -> refused, never raises.
    assert not can_handoff("support-client", "ghost")


def test_get_agent_unknown_raises() -> None:
    import pytest

    with pytest.raises(KeyError):
        get_agent("does-not-exist")
