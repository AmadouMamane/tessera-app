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


def _agent_release_row(agent_id: str, lang: str = "fr") -> dict[str, object]:
    """Per-agent release row: policy verdict + lifecycle state + governance history.

    ``decision`` is the lifecycle's :class:`ReleaseDecision`, carried WHOLE. This row used
    to keep only the decision's shadow (``state``/``state_tone``) and drop the fields that
    say WHY — ``blocked_by``, the achieved vs required observability level, the floor grade —
    so the one payload listing every agent could label a block but never attribute it, and
    the attribution lived one endpoint away (``/observability/agent-lifecycle``), one agent
    at a time.
    """
    name, owner = _agent_meta(agent_id)
    rel = agent_release_state(agent_id, lang)
    lifecycle = compute_agent_lifecycle(agent_id, lang)
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
        "decision": lifecycle["release"],
    }


def compute_release_control(agent_id: str | None = None, lang: str = "fr") -> dict[str, object]:
    """Return the release-control payload: per-agent rows + an org summary.

    Args:
        agent_id: when set (and not ``"all"``), scope to that one agent; otherwise
            return every registry agent (the default, global view).
        lang: UI language (``fr`` / ``de`` / ``en``) for the localized free-text.
    """
    ids = _agent_ids()
    if agent_id and agent_id != "all" and agent_id in ids:
        ids = [agent_id]

    rows = [_agent_release_row(aid, lang) for aid in ids]

    # Org summary over the (filtered) population — counts of distinct agents by release
    # readiness, following the level-aware lifecycle decision (§A2.4). A "blocked" agent is
    # one the release gate stops for ANY reason — a failed eval-gate OR an observability
    # level below the requirement — so the KPI and the per-agent state labels never disagree
    # (a level-blocked agent is never miscounted as "ready to promote"). Counting from the
    # lifecycle tone keeps the summary and the rows a single truth.
    tones = [str(r.get("state_tone", "")) for r in rows]
    passing = sum(1 for tone in tones if tone == "good")
    blocked = sum(1 for tone in tones if tone == "bad")
    not_run = sum(1 for tone in tones if tone == "warn")
    return {
        "agents": rows,
        "summary": {
            "total": len(rows),
            "passing": passing,
            "blocked": blocked,
            "not_run": not_run,
        },
    }
