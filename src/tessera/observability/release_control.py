"""Release Control (AGIR) — the per-agent release pipeline + eval-gate verdict.

Each agent is a governed *package* approved as a unit through its own eval-gate
(``docs/design/eval-gate-policy.md``). Release Control is the GOUVERNER/AGIR
surface that shows, for **every** agent, where its candidate version sits in the
``proposed → reviewed → approved → live`` flow and the **policy-correct gate
verdict** that gates promotion — so an operator can see at a glance which packages
are releasable and which are blocked, and why.

This combines two real sources per agent: the policy-correct verdict
(:mod:`agent_release`, ``build_gate_view`` over the agent's OWN run) and the
governed lifecycle state + S1 history (:mod:`agent_lifecycle`). Nothing is
fabricated; agents with no run render an honest "en attente d'évaluation".
"""

from __future__ import annotations

from tessera.observability.agent_lifecycle import compute_agent_lifecycle
from tessera.observability.agent_release import agent_release_state

__all__ = ["compute_release_control"]


def _agent_ids() -> list[str]:
    try:
        from tessera.agent.registry import list_agents

        return [a.id for a in list_agents()]
    except (OSError, ValueError):
        return []


def _agent_meta(agent_id: str) -> tuple[str, str]:
    """Return ``(name, owner)`` from the registry, falling back to the id."""
    try:
        from tessera.agent.registry import get_agent

        agent = get_agent(agent_id)
        return agent.name, agent.owner
    except (OSError, ValueError, KeyError):
        return agent_id, ""


def _agent_release_row(agent_id: str) -> dict[str, object]:
    """Per-agent release row: policy verdict + lifecycle state + governance history."""
    name, owner = _agent_meta(agent_id)
    rel = agent_release_state(agent_id)
    lifecycle = compute_agent_lifecycle(agent_id)
    return {
        "agent_id": agent_id,
        "name": name,
        "owner": owner,
        "state": lifecycle["state"],
        "state_tone": lifecycle["state_tone"],
        "last_phase": lifecycle["last_phase"],
        "flow": lifecycle["flow"],
        "history": lifecycle["history"],
        "release": rel.as_dict(),
    }


def compute_release_control(agent_id: str | None = None) -> dict[str, object]:
    """Return the release-control payload: per-agent rows + an org summary.

    Args:
        agent_id: when set (and not ``"all"``), scope to that one agent; otherwise
            return every registry agent (the default, global view).
    """
    ids = _agent_ids()
    if agent_id and agent_id != "all" and agent_id in ids:
        ids = [agent_id]

    rows = [_agent_release_row(aid) for aid in ids]

    # Org summary over the (filtered) population — counts of distinct agents by
    # release readiness. These are agent counts, not deduped conversation totals.
    passing = sum(1 for r in rows if _release(r).get("available") and _release(r).get("passed"))
    blocked = sum(1 for r in rows if _release(r).get("available") and not _release(r).get("passed"))
    not_run = sum(1 for r in rows if not _release(r).get("available"))
    return {
        "agents": rows,
        "summary": {
            "total": len(rows),
            "passing": passing,
            "blocked": blocked,
            "not_run": not_run,
        },
    }


def _release(row: dict[str, object]) -> dict[str, object]:
    rel = row.get("release")
    return rel if isinstance(rel, dict) else {}
