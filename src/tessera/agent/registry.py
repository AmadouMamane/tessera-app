"""Agent registry — the governed fleet (multi-agent Phase 1).

Loads the versioned registry (`agents.yaml`) into immutable :class:`Agent`
records. Each agent BINDS reusable building blocks from the CONFIGURER catalogue
(model, prompts, knowledge, guardrails, eval set, tools) and declares a
``handoff`` contract — the governed agent graph (who it may hand to / receive
from), checked at runtime and reconstructable in État à date.

The registry is the single source of truth for *which agents exist* and *what
each one is bound to*. Per-agent editable overrides (tone, sliders, …) layer on
top in the durable config store; this module never mutates anything.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from tessera.agent.identity import DEFAULT_AGENT_ID

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
    "Agent",
    "HandoffContract",
    "can_handoff",
    "get_agent",
    "list_agents",
    "registry_path",
]

_REGISTRY_FILE = Path(__file__).resolve().parent / "agents.yaml"


@dataclass(frozen=True, slots=True)
class HandoffContract:
    """The governed agent graph for one agent: who it may hand to / receive from."""

    to: tuple[str, ...] = ()
    from_: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Agent:
    """A governed agent package: identity + catalogue bindings + handoff contract."""

    id: str
    name: str
    description: str
    owner: str
    default_language: str
    model: str
    prompts: tuple[str, ...]
    knowledge: tuple[str, ...]
    guardrails: str
    eval_set: str
    tools: tuple[str, ...]
    tags: tuple[str, ...] = ()
    handoff: HandoffContract = field(default_factory=HandoffContract)


def registry_path() -> Path:
    """Return the path to the registry YAML (single source of truth)."""
    return _REGISTRY_FILE


def _as_str_tuple(value: object) -> tuple[str, ...]:
    """Coerce a YAML scalar/sequence into a tuple of strings (empty if absent)."""
    if isinstance(value, list):
        return tuple(str(v) for v in value)
    return ()


def _coerce_agent(raw: Mapping[str, object]) -> Agent:
    handoff_raw = raw.get("handoff")
    handoff_map: Mapping[str, object] = handoff_raw if isinstance(handoff_raw, dict) else {}
    handoff = HandoffContract(
        to=_as_str_tuple(handoff_map.get("to")),
        from_=_as_str_tuple(handoff_map.get("from")),
    )
    return Agent(
        id=str(raw["id"]),
        name=str(raw.get("name", raw["id"])),
        description=str(raw.get("description", "")),
        owner=str(raw.get("owner", "-")),
        default_language=str(raw.get("default_language", "fr")),
        model=str(raw.get("model", "")),
        prompts=_as_str_tuple(raw.get("prompts")),
        knowledge=_as_str_tuple(raw.get("knowledge")),
        guardrails=str(raw.get("guardrails", "standard")),
        eval_set=str(raw.get("eval_set", "")),
        tools=_as_str_tuple(raw.get("tools")),
        tags=_as_str_tuple(raw.get("tags")),
        handoff=handoff,
    )


@lru_cache(maxsize=1)
def _load() -> dict[str, Agent]:
    """Parse the registry YAML once into an ordered {id: Agent} mapping."""
    data = yaml.safe_load(_REGISTRY_FILE.read_text(encoding="utf-8")) or {}
    raw_agents = data.get("agents") or []
    agents = {a.id: a for a in (_coerce_agent(r) for r in raw_agents)}
    if not agents:
        raise ValueError("agent registry is empty")
    # The YAML default must be a real agent and must agree with DEFAULT_AGENT_ID,
    # so data (agent_id stamps) and URLs (/agents/<default>/...) never diverge.
    declared_default = str(data.get("default", DEFAULT_AGENT_ID))
    if declared_default not in agents:
        raise ValueError(f"registry default {declared_default!r} is not a known agent")
    if declared_default != DEFAULT_AGENT_ID:
        raise ValueError(
            f"registry default {declared_default!r} != DEFAULT_AGENT_ID {DEFAULT_AGENT_ID!r}"
        )
    return agents


def list_agents() -> list[Agent]:
    """Return all registered agents, in declaration order."""
    return list(_load().values())


def get_agent(agent_id: str) -> Agent:
    """Return one agent by id, or raise ``KeyError`` if unknown."""
    agents = _load()
    if agent_id not in agents:
        raise KeyError(agent_id)
    return agents[agent_id]


def can_handoff(src: str, dst: str) -> bool:
    """Whether ``src`` may hand off to ``dst`` per both ends of the contract.

    The edge must be declared on the source's ``to`` *and* the destination's
    ``from`` — a handoff is only governed when both packages agree.
    """
    agents = _load()
    if src not in agents or dst not in agents:
        return False
    return dst in agents[src].handoff.to and src in agents[dst].handoff.from_
