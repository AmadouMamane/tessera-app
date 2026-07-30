"""The fleet card must carry what the manifest declares about an agent's purpose.

Without ``description`` and ``tags`` on the card, a visitor reads "5 agents" as five banking
agents — the fleet silently inflates the demo, which the project's honest-positioning rule
forbids. These tests pin the projection and the register the descriptions are written in.

The card also states the agent's two **structural contracts** — it publishes its activity, an
operator can send it a turn. Both are read from declarations (``telemetry_capabilities``,
``invocation.binding``); a chip that switched on an agent id would be a hardcoded fleet.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

from tessera.agent.registry import list_agents
from tessera.observability.agent_console import compute_agent_console
from tessera.observability.agentspec_projection import declares_telemetry, is_invocable
from tessera.observability.fleet import (
    _business_card_facts,
    _pending_items_by_agent,
    _registry_agents,
)

if TYPE_CHECKING:
    import pytest

_WITNESSES = frozenset({"hello-agent", "turn-agent", "duplex-agent"})


def test_projection_carries_description_and_tags() -> None:
    projected = {a["id"]: a for a in _registry_agents()}
    assert projected, "the registry must project at least one agent"
    for agent in list_agents():
        card = projected[agent.id]
        assert card["description"] == agent.description
        assert card["tags"] == list(agent.tags)


def test_every_agent_declares_a_description() -> None:
    """An agent with no description would render a card that cannot say what it is for."""
    missing = [a.id for a in list_agents() if not a.description.strip()]
    assert not missing, f"agents without a description: {missing}"


def test_platform_witnesses_are_tagged_demo() -> None:
    """The `demo` tag is what the card renders as the "Témoin plateforme" chip.

    The tag stays `demo` (it is the manifest's declaration); only the label changed, because
    "Démonstration" is reserved for the surface pill and a second meaning would collide.
    """
    for agent in list_agents():
        tagged = "demo" in agent.tags
        assert tagged is (
            agent.id in _WITNESSES
        ), f"{agent.id}: `demo` tag must mark exactly the platform witnesses {sorted(_WITNESSES)}"


def test_witness_descriptions_are_business_legible() -> None:
    """The card is read by a business audience, not by a reviewer.

    Implementation vocabulary belongs in the module docstring and the YAML comments, never in
    the field the cockpit renders. This is a regression guard against two real slips: the
    witnesses' descriptions were first implementation notes ("out-of-process, pure OTLP, zero
    tessera import"), then a negative property a reader cannot interpret ("écrit sans le code
    de Tessera" — without which code? to what end?). A description states the agent's intent.
    """
    jargon = ("OTLP", "out-of-process", "binding", "ADR", "import", "runtime", "endpoint", "code")
    for agent in list_agents():
        lowered = agent.description.lower()
        found = [term for term in jargon if term.lower() in lowered]
        assert not found, f"{agent.id}: description leaks implementation vocabulary {found}"


def test_the_witnesses_span_the_contract_square() -> None:
    """Each witness proves one contract, and together they cover every combination.

    hello-agent publishes and cannot be tested; turn-agent can be tested and publishes nothing;
    duplex-agent does both — which is the only reason the proof loop closes on it. Should this
    matrix ever collapse, two of the three examples have become the same example.
    """
    matrix = {a.id: (declares_telemetry(a), is_invocable(a)) for a in list_agents()}
    assert matrix["hello-agent"] == (True, False)
    assert matrix["turn-agent"] == (False, True)
    assert matrix["duplex-agent"] == (True, True)


def test_business_agents_are_observable_and_testable() -> None:
    """A banking agent the cockpit can neither watch nor exercise would be a card with no back."""
    for agent in list_agents():
        if agent.id in _WITNESSES:
            continue
        assert declares_telemetry(agent), f"{agent.id}: a business agent must publish its activity"
        assert is_invocable(agent), f"{agent.id}: a business agent must be reachable for a turn"


def test_the_testable_chip_and_the_console_agree() -> None:
    """One declaration, two readers — a card must never advertise a bench that will not open.

    The chip reads ``invocation.binding`` through the projection; the Console reads it again to
    decide between a test bench and the honest-empty state. Drift between them is invisible on
    both sides and only shows up as an operator clicking through to nothing.
    """
    for agent in list_agents():
        invocation = compute_agent_console("fr", agent.id)["invocation"]
        assert isinstance(invocation, dict)
        assert invocation["invocable"] is is_invocable(
            agent
        ), f"{agent.id}: the card and the Console disagree about invocability"


# --- the pending-items dedup: one whole-fleet load, grouped, instead of one load per card --------


def _item(agent_id: str, status: str) -> object:
    """A stand-in operator item — _pending_items_by_agent reads only .agent_id and .status."""
    return SimpleNamespace(agent_id=agent_id, status=status)


def test_pending_items_grouped_from_one_whole_fleet_load(monkeypatch: pytest.MonkeyPatch) -> None:
    """ONE load_items_for(nature, None), grouped by agent, counting status != 'done'.

    This is the dedup that replaced six per-agent loads (~570 ms warm); the grouped count must be
    the same a per-agent filter would give, and the read must happen exactly once.
    """
    calls: list[str | None] = []

    def _fake_load(nature: str, agent_id: str | None = None) -> list[object]:
        calls.append(agent_id)
        return [
            _item("recouvrement", "todo"),
            _item("recouvrement", "progress"),
            _item("recouvrement", "done"),  # excluded — already handled
            _item("support-client", "todo"),
            _item("onboarding", "done"),  # excluded → onboarding absent from the map
        ]

    monkeypatch.setattr("tessera.observability.fleet.load_items_for", _fake_load)
    by_agent = _pending_items_by_agent()
    assert by_agent == {"recouvrement": 2, "support-client": 1}
    assert calls == [None]  # loaded ONCE, whole-fleet, not once per agent


def test_pending_items_empty_on_load_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """A load failure is an empty map → the caller reads 0 for every agent, and never raises."""

    def _boom(nature: str, agent_id: str | None = None) -> list[object]:
        raise RuntimeError("disk gone")

    monkeypatch.setattr("tessera.observability.fleet.load_items_for", _boom)
    assert _pending_items_by_agent() == {}


def test_business_card_facts_takes_the_precomputed_count_and_never_reloads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The card no longer loads the operator queue itself — the dedup moved that read out."""

    def _must_not_load(*_a: object, **_k: object) -> list[object]:
        raise AssertionError("_business_card_facts must not load operator items")

    monkeypatch.setattr("tessera.observability.fleet.load_items_for", _must_not_load)
    # A record-less agent keeps its unchanged contract: pending is 0, no load attempted.
    facts = _business_card_facts("recouvrement", None, 9)
    assert facts["pending_business_items"] == 0
