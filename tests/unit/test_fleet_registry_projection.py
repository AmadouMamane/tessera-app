"""The fleet card must carry what the manifest declares about an agent's purpose.

Without ``description`` and ``tags`` on the card, a visitor reads "5 agents" as five banking
agents — the fleet silently inflates the demo, which the project's honest-positioning rule
forbids. These tests pin the projection and the register the descriptions are written in.
"""

from __future__ import annotations

from tessera.agent.registry import list_agents
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
