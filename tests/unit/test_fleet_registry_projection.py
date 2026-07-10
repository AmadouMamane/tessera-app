"""The fleet card must carry what the manifest declares about an agent's purpose.

Without ``description`` and ``tags`` on the card, a visitor reads "5 agents" as five banking
agents — the fleet silently inflates the demo, which the project's honest-positioning rule
forbids. These tests pin the projection and the register the descriptions are written in.

The card also states the agent's two **structural contracts** — it publishes its activity, an
operator can send it a turn. Both are read from declarations (``telemetry_capabilities``,
``invocation.binding``); a chip that switched on an agent id would be a hardcoded fleet.
"""

from __future__ import annotations

from tessera.agent.registry import list_agents
from tessera.observability.agent_console import compute_agent_console
from tessera.observability.agentspec_projection import declares_telemetry, is_invocable
from tessera.observability.fleet import _registry_agents

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
