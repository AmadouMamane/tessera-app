"""Per-agent release state — the eval-gate verdict for each governed agent package.

An agent is a governed *package* (model + prompts + knowledge + guardrails + eval
set + tools + handoff contract), versioned and approved as a unit through an
eval-gate (``docs/design/eval-gate-policy.md``). This module surfaces, for every
agent in the registry, the **release verdict** of its own reference run — the same
policy-correct gate the Évaluations page renders, computed per agent over the
agent's OWN eval set, so quality genuinely differs per agent.

Both the fleet `/agents` column ("état de release") and AGIR / Release Control read
this. Agents with no usable run render an honest *évaluation non exécutée* empty
state — never a fabricated verdict.
"""

from __future__ import annotations

from dataclasses import dataclass

from tessera.observability.eval_data import load_eval_snapshot
from tessera.observability.eval_gate_view import build_gate_view

__all__ = ["AgentRelease", "agent_release_state", "fleet_release_states"]


@dataclass(frozen=True, slots=True)
class AgentRelease:
    """The release/eval-gate state of one agent package.

    ``available`` is ``False`` when the agent has no usable reference run; the
    verdict fields are then empty and the UI shows "évaluation non exécutée".
    """

    agent_id: str
    available: bool
    passed: bool = False
    verdict_label: str = ""
    verdict_tone: str = "muted"
    candidate_version: str = ""
    eval_set: str = ""
    executions: int = 0
    passed_exec: int = 0
    socle_ok: bool = False
    blocking_socle: int = 0
    blocking_t1: int = 0
    waived_active: int = 0

    def as_dict(self) -> dict[str, object]:
        """Serialise for the API payload (fleet + release control)."""
        return {
            "agent_id": self.agent_id,
            "available": self.available,
            "passed": self.passed,
            "verdict_label": self.verdict_label,
            "verdict_tone": self.verdict_tone,
            "candidate_version": self.candidate_version,
            "eval_set": self.eval_set,
            "executions": self.executions,
            "passed_exec": self.passed_exec,
            "socle_ok": self.socle_ok,
            "blocking_socle": self.blocking_socle,
            "blocking_t1": self.blocking_t1,
            "waived_active": self.waived_active,
        }


def agent_release_state(agent_id: str) -> AgentRelease:
    """Return the eval-gate release verdict for one agent, or an honest empty state."""
    try:
        snap = load_eval_snapshot(agent_id)
    except (FileNotFoundError, OSError, ValueError):
        return AgentRelease(agent_id=agent_id, available=False, verdict_label="Éval non exécutée")
    gate = build_gate_view(snap)
    return AgentRelease(
        agent_id=agent_id,
        available=True,
        passed=gate.passed,
        verdict_label=gate.verdict_label,
        verdict_tone=gate.verdict_tone,
        candidate_version=gate.candidate_version,
        eval_set=snap.eval_set,
        executions=gate.executions,
        passed_exec=gate.passed_exec,
        socle_ok=gate.socle_ok,
        blocking_socle=gate.blocking_socle,
        blocking_t1=gate.blocking_t1,
        waived_active=gate.waived_active,
    )


def fleet_release_states() -> dict[str, AgentRelease]:
    """Return the release state of every registry agent, keyed by agent id."""
    try:
        from tessera.agent.registry import list_agents

        agents = [a.id for a in list_agents()]
    except (OSError, ValueError):
        agents = []
    return {aid: agent_release_state(aid) for aid in agents}
