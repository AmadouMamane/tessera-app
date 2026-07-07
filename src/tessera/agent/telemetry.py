"""Agent-side adapters that publish runtime telemetry into the spine ports.

ADR 0017 §1 "agents publish; the cockpit reads the spine." This module imports
the agent runtime (``reporter``, ``router``, ``graph``) — which the §1 boundary
forbids in the control plane — and installs a
:class:`~tessera.observability.spine.runtime.RuntimeProvider` the cockpit routes
read through the spine port. It lives outside ``tessera.observability`` so it is
*not* boundary-scanned. Wired once at app build
(:func:`tessera.api.main.build_app`); in a cockpit-only deployment it is simply
never imported and the spine serves honest-empty defaults.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tessera.observability.spine.runtime import SandboxDefaults, set_runtime_provider

if TYPE_CHECKING:
    from tessera.settings import LanguageCode


class AgentRuntimeProvider:
    """Reads runtime facts from the live LangGraph agent (the in-process profile)."""

    def sandbox_defaults(self, language: LanguageCode) -> SandboxDefaults:
        """Read the live system prompt + policy-rule count from the agent runtime."""
        # Imported lazily: reporter/router pull heavy runtime at import time, and
        # a cockpit-only process must be able to import this module without them.
        from tessera.agent.reporter import load_prompts
        from tessera.agent.router import _POLICY_RULES

        prompts = load_prompts(language)
        return SandboxDefaults(
            system_prompt=prompts.get("system", ""),
            policy_rule_count=len(_POLICY_RULES.get(language, [])),
        )


def install_runtime_provider() -> None:
    """Install the in-process agent runtime provider into the spine port."""
    set_runtime_provider(AgentRuntimeProvider())
