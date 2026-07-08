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
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from tessera.agent.agentspec import (
    AgentObservabilitySpec,
    BusinessMetricLevel,
    BusinessSignalSource,
    BusinessSignalSpec,
    Capability,
    ExternalEffectLevel,
    InvocationAuth,
    InvocationBinding,
    InvocationSpec,
    PolicyMetadata,
    PolicySeverity,
    SignalEngagement,
    WorkflowBinding,
    parse_invocation,
    parse_observability,
)
from tessera.agent.identity import DEFAULT_AGENT_ID

# Audience / surface / auth (ADR 0008) are the governed agent properties; the
# vocabulary and the satisfaction ladder live in the leaf ``tessera.authz`` so
# the guard layer can share them without an import cycle. Re-exported here for
# back-compat: callers keep importing them from ``tessera.agent.registry``.
from tessera.authz import Audience, Auth, AuthState, Surface, auth_satisfies

if TYPE_CHECKING:
    from collections.abc import Mapping

# AgentSpec observability types are re-exported here so the cockpit / spine can read the
# manifest through the one boundary-allowed seam (``tessera.agent.registry`` /
# ``tessera.agent.identity`` — ADR 0017 §1 import contract) without importing the agent
# runtime. They are defined in ``tessera.agent.agentspec``.
__all__ = [
    "Agent",
    "AgentObservabilitySpec",
    "Audience",
    "Auth",
    "AuthState",
    "BusinessMetricLevel",
    "BusinessSignalSource",
    "BusinessSignalSpec",
    "Capability",
    "ExternalEffectLevel",
    "HandoffContract",
    "InvocationAuth",
    "InvocationBinding",
    "InvocationSpec",
    "PolicyMetadata",
    "PolicySeverity",
    "SignalEngagement",
    "Surface",
    "WorkflowBinding",
    "can_handoff",
    "get_agent",
    "list_agents",
    "registry_path",
    "routable",
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
    audience: Audience
    surface: tuple[Surface, ...]
    auth: Auth
    tags: tuple[str, ...] = ()
    handoff: HandoffContract = field(default_factory=HandoffContract)
    # ADR 0017 §3 — the AgentSpec observability block. Optional: an agent without one is
    # simply un-manifested (no observability level, no Métier surfaces) until it declares
    # one. Recouvrement declares the first manifest (Phase B).
    observability: AgentObservabilitySpec | None = None
    # ADR 0019 §1 — the invocation binding (the declared cockpit→agent seam). Always present:
    # an agent that declares nothing is honestly ``binding: none`` (publish-only), never a
    # broken chat. The three native agents declare ``in_process_chat``; hello-agent ``none``.
    invocation: InvocationSpec = field(default_factory=InvocationSpec)


def registry_path() -> Path:
    """Return the path to the registry YAML (single source of truth)."""
    return _REGISTRY_FILE


def _as_str_tuple(value: object) -> tuple[str, ...]:
    """Coerce a YAML scalar/sequence into a tuple of strings (empty if absent)."""
    if isinstance(value, list):
        return tuple(str(v) for v in value)
    return ()


def _coerce_surface(value: object, agent_id: str) -> tuple[Surface, ...]:
    """Coerce the `surface` binding into a tuple of :class:`Surface`, fail-fast.

    Accepts a single value or a list; an out-of-list value or an empty/absent
    declaration raises at load so the manifest can never name a surface the
    router does not enforce.
    """
    items = value if isinstance(value, list) else [value]
    try:
        surfaces = tuple(Surface(str(v)) for v in items)
    except ValueError as exc:
        raise ValueError(f"agent {agent_id!r}: unknown surface {value!r}") from exc
    if not surfaces:
        raise ValueError(f"agent {agent_id!r}: surface must declare at least one channel")
    return surfaces


def _coerce_enum[E: StrEnum](enum: type[E], value: object, field_name: str, agent_id: str) -> E:
    """Coerce a scalar into ``enum``, raising a clear error on an out-of-list value."""
    try:
        return enum(str(value))
    except ValueError as exc:
        raise ValueError(f"agent {agent_id!r}: unknown {field_name} {value!r}") from exc


def _coerce_agent(raw: Mapping[str, object]) -> Agent:
    agent_id = str(raw["id"])
    handoff_raw = raw.get("handoff")
    handoff_map: Mapping[str, object] = handoff_raw if isinstance(handoff_raw, dict) else {}
    handoff = HandoffContract(
        to=_as_str_tuple(handoff_map.get("to")),
        from_=_as_str_tuple(handoff_map.get("from")),
    )
    # audience / surface / auth are required, governed bindings (ADR 0008): a
    # missing key (KeyError) or an out-of-list value (ValueError) fails the load.
    audience = _coerce_enum(Audience, raw["audience"], "audience", agent_id)
    surface = _coerce_surface(raw["surface"], agent_id)
    auth = _coerce_enum(Auth, raw["auth"], "auth", agent_id)
    # The AgentSpec observability block is validated at load (a manifest is an API):
    # any malformed field raises ValueError, prefixed with the agent id.
    observability_raw = raw.get("observability")
    observability: AgentObservabilitySpec | None = None
    if observability_raw is not None:
        if not isinstance(observability_raw, dict):
            raise ValueError(f"agent {agent_id!r}: observability must be a mapping")
        try:
            observability = parse_observability(observability_raw)
        except ValueError as exc:
            raise ValueError(f"agent {agent_id!r}: {exc}") from exc
    # The AgentSpec invocation block (ADR 0019 §1) — same fail-fast discipline. Absent ⇒ the
    # honest ``binding: none`` default (publish-only); a malformed block fails the load.
    invocation_raw = raw.get("invocation")
    invocation = InvocationSpec()
    if invocation_raw is not None:
        if not isinstance(invocation_raw, dict):
            raise ValueError(f"agent {agent_id!r}: invocation must be a mapping")
        try:
            invocation = parse_invocation(invocation_raw)
        except ValueError as exc:
            raise ValueError(f"agent {agent_id!r}: {exc}") from exc
    return Agent(
        id=agent_id,
        name=str(raw.get("name", agent_id)),
        description=str(raw.get("description", "")),
        owner=str(raw.get("owner", "-")),
        default_language=str(raw.get("default_language", "fr")),
        model=str(raw.get("model", "")),
        prompts=_as_str_tuple(raw.get("prompts")),
        knowledge=_as_str_tuple(raw.get("knowledge")),
        guardrails=str(raw.get("guardrails", "standard")),
        eval_set=str(raw.get("eval_set", "")),
        tools=_as_str_tuple(raw.get("tools")),
        audience=audience,
        surface=surface,
        auth=auth,
        tags=_as_str_tuple(raw.get("tags")),
        handoff=handoff,
        observability=observability,
        invocation=invocation,
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


def routable(surface: Surface, auth_state: AuthState) -> list[Agent]:
    """The pool reachable from an entry ``surface`` under a session ``auth_state``.

    ``routable(surface, auth_state) = { a : surface ∈ a.surface ∧ auth_state ⊇ a.auth }``
    (ADR 0008). This is the *only* set routing and handoff may select from — the
    seam that keeps a sensitive agent off a surface/auth it does not belong on.
    """
    return [
        agent
        for agent in _load().values()
        if surface in agent.surface and auth_satisfies(auth_state, agent.auth)
    ]


def can_handoff(src: str, dst: str, *, surface: Surface, auth_state: AuthState) -> bool:
    """Whether ``src`` may hand off to ``dst`` on ``surface`` under ``auth_state``.

    Two gates, both required (ADR 0008): the contract edge must be declared on the
    source's ``to`` *and* the destination's ``from`` (a handoff is only governed
    when both packages agree), **and** both endpoints must be in the routable pool
    for this surface/auth. The second gate forbids a silent cross-surface or
    under-authenticated handoff — moving a customer from the public widget into a
    customer-auth collections context is never an implicit route.
    """
    agents = _load()
    if src not in agents or dst not in agents:
        return False
    if dst not in agents[src].handoff.to or src not in agents[dst].handoff.from_:
        return False
    pool = {agent.id for agent in routable(surface, auth_state)}
    return src in pool and dst in pool
