"""Spine port for agent-runtime facts the cockpit reads but cannot compute.

ADR 0017 §1: *"agents publish; the cockpit reads the spine; nobody queries an
agent."* Two cockpit read endpoints need a fact only the live agent runtime
holds — the Console sandbox defaults (system prompt + guard-rule counts) and the
graph-topology fingerprint. Rather than import ``tessera.agent.*`` from the
(boundary-scanned) route, the route reads this port; the concrete adapter that
*does* import the runtime lives outside the scanned tree
(:mod:`tessera.agent.telemetry`) and installs itself at app build.

The default is an honest-empty null provider, so a cockpit-only deployment (no
agent in-process) serves empty defaults instead of crashing — the separable
control plane the ADR promises, exercised by construction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from tessera.settings import LanguageCode


@dataclass(frozen=True, slots=True)
class SandboxDefaults:
    """Live defaults the **cockpit Console** pre-fills its sandbox with.

    The Console is a *generated operator surface* — **ADR 0019 §2 (increment I2)**: it composes
    from the agent's own declarations, with no per-agent console code. These two values are the
    live runtime facts it cannot declare: the system prompt actually in force and how many guard
    rules the active policy carries.

    They exist so an operator can *see* what they are about to relax. Relaxing it is governed
    elsewhere and narrowly: ``sandbox_overrides_allowed`` (``api/routes/chat.py``) honours
    ``system_prompt_override`` / ``guard_overrides`` **only** for
    ``Surface.COCKPIT_EMBEDDED`` + ``AuthState.OPERATOR``, both server-derived — the audit's
    P0 ``guard-bypass``. Reading the defaults is not permission to change them.

    This docstring used to cite *"ADR 0010 Phase C"*, and that was **false**. ``Phase C`` exists
    only in the recouvrement ADR, where it names the **business** console (``dedicated-ui``) —
    and ADR 0013 forbids exactly this payload (a system prompt, a guard-rule count) on a business
    surface. The citation pointed at the one ADR that rules the behaviour *out*. Corrected rather
    than renumbered: a wrong reference is a defect on its own, not a casualty of a duplicate
    number.
    """

    system_prompt: str
    policy_rule_count: int


class RuntimeProvider(Protocol):
    """The agent-runtime facts the cockpit reads through the spine, never by import."""

    def sandbox_defaults(self, language: LanguageCode) -> SandboxDefaults:
        """Return the live Console-sandbox defaults for ``language``."""
        ...

    def graph_topology(self) -> dict[str, object]:
        """Return the live agent graph's topology fingerprint + golden drift (#87)."""
        ...


class _NullRuntimeProvider:
    """Honest-empty default — no agent wired in-process (cockpit-only deploy)."""

    def sandbox_defaults(self, language: LanguageCode) -> SandboxDefaults:  # noqa: ARG002
        """Serve honest-empty defaults — no agent runtime is installed."""
        return SandboxDefaults(system_prompt="", policy_rule_count=0)

    def graph_topology(self) -> dict[str, object]:
        """Serve honest-empty topology — no agent runtime is installed."""
        return {}


_provider: RuntimeProvider = _NullRuntimeProvider()


def get_runtime_provider() -> RuntimeProvider:
    """Return the installed runtime provider (honest-empty null until installed)."""
    return _provider


def set_runtime_provider(provider: RuntimeProvider | None) -> None:
    """Install the runtime provider; ``None`` resets to the null default (tests)."""
    global _provider
    _provider = provider if provider is not None else _NullRuntimeProvider()
