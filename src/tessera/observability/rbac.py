"""RBAC role x agent matrix (multi-agent, Tier 3).

Surfaces the **real** access model crossed with the fleet: the roles the system
actually enforces (mirrored from the Next auth model — ``admin`` / ``auditor`` /
``superadmin``, see ``lib/auth/session.ts``) against the real registry agents.

The cockpit supervises multiple agents, so access can in principle be scoped per
agent ("ML Eng on support-client", "Compliance on all"). The honest current state
is that the enforced roles are **org-wide** (every role covers every agent): there
is no per-agent role-binding store yet. We render that truthfully — a role x agent
grid where the scope reads "org" — rather than fabricating per-agent grants. The
per-agent binding store is a logged follow-up.
"""

from __future__ import annotations

__all__ = ["ROLE_CAPS", "rbac_matrix"]

# Capabilities mirror lib/auth/session.ts (the real enforcement): what each role
# may reach. Kept as stable keys the frontend labels + a French display label.
ROLE_CAPS: dict[str, dict[str, object]] = {
    "admin": {
        "label": "Administrateur",
        "caps": ["cockpit", "produit", "configurer", "release"],
    },
    "auditor": {
        "label": "Auditeur (lecture)",
        "caps": ["cockpit_lecture", "audit_lecture"],
    },
    "superadmin": {
        "label": "Super-admin",
        "caps": ["cockpit", "produit", "configurer", "release", "modeles_frontier"],
    },
}


def _agents() -> list[dict[str, str]]:
    try:
        from tessera.agent.registry import list_agents

        return [{"id": a.id, "name": a.name} for a in list_agents()]
    except (OSError, ValueError):
        return []


def rbac_matrix(agent_scope: str = "all") -> dict[str, object]:
    """Return the role x agent matrix: real roles x real agents, org-wide scope.

    Args:
        agent_scope: when a concrete agent id, restrict the agent columns to it
            (the global ?agent= filter); ``"all"`` returns every registry agent.
    """
    agents = _agents()
    if agent_scope != "all":
        agents = [a for a in agents if a["id"] == agent_scope]

    roles: list[dict[str, object]] = []
    for role_id, meta in ROLE_CAPS.items():
        # Every enforced role currently covers every agent (org-wide) — stated
        # truthfully as scope "org", not fabricated per-agent assignments.
        cells = [
            {"agent_id": a["id"], "name": a["name"], "granted": True, "scope": "org"}
            for a in agents
        ]
        roles.append(
            {
                "role": role_id,
                "label": meta["label"],
                "caps": meta["caps"],
                "scope": "org",
                "agent_count": len(cells),
                "cells": cells,
            }
        )

    return {"roles": roles, "agents": agents, "scope_model": "org-wide"}
