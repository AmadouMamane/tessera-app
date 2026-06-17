"""Governed agent lifecycle — propose → review → approve → release (Phase 4b-③).

This closes the governed-package loop: an agent (or a new version) only goes
**live** once a run of ITS own evaluation set clears the two-level eval-gate
(critical floor zero-tolerance AND domain ≥ min_pass_rate). The decision is read
from the agent's own run report; the transition is recorded as a hash-chained S1
event (``released`` on success, ``release_blocked`` otherwise), so the promotion
is opposable and reconstructable in État à date.

The registry itself is approved as a unit (ADR 0012) and not mutated at runtime —
this module governs the *promotion decision*, not a live registry edit.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from tessera.guard.audit import emit_agent_lifecycle
from tessera.observability.eval_data import load_eval_snapshot
from tessera.settings import get_settings

__all__ = [
    "ReleaseDecision",
    "compute_agent_lifecycle",
    "lifecycle_history",
    "release_decision",
    "request_release",
]

# Latest governance phase, derived from the S1 chain (most recent wins).
_PHASE_EVENTS: dict[str, str] = {
    "tessera.agent.proposed": "proposed",
    "tessera.agent.reviewed": "reviewed",
    "tessera.agent.approved": "approved",
    "tessera.agent.released": "live",
    "tessera.agent.release_blocked": "blocked",
}


@dataclass(frozen=True, slots=True)
class ReleaseDecision:
    """Whether an agent may be promoted to live, and why."""

    agent_id: str
    allowed: bool
    reason: str
    has_run: bool
    gate_passed: bool | None
    failed_critical: tuple[str, ...]
    run_at: str

    def as_dict(self) -> dict[str, object]:
        """JSON-friendly view for the API + the S1 event detail."""
        return {
            "agent_id": self.agent_id,
            "allowed": self.allowed,
            "reason": self.reason,
            "has_run": self.has_run,
            "gate_passed": self.gate_passed,
            "failed_critical": list(self.failed_critical),
            "run_at": self.run_at,
        }


def release_decision(agent_id: str) -> ReleaseDecision:
    """Decide whether ``agent_id`` may go live, from its own eval-gate verdict.

    Live requires a run of the agent's OWN set that cleared the two-level gate.
    No run, or a blocked gate, means the agent cannot be promoted.
    """
    try:
        snap = load_eval_snapshot(agent_id)
    except FileNotFoundError:
        return ReleaseDecision(
            agent_id=agent_id,
            allowed=False,
            reason="aucun run d'évaluation pour cet agent — lancez son eval set d'abord.",
            has_run=False,
            gate_passed=None,
            failed_critical=(),
            run_at="",
        )
    if snap.gate_passed is True:
        reason = "eval-gate validé (socle critique OK + domaine ≥ seuil)."
    elif snap.gate_failed_critical:
        reason = (
            "bloqué par le socle critique (zéro tolérance) : "
            + ", ".join(snap.gate_failed_critical)
        )
    elif snap.gate_passed is False:
        reason = "bloqué : le taux du domaine est sous le seuil de l'eval set."
    else:
        reason = "aucun verdict de gate sur ce run (relancez via --agent)."
    return ReleaseDecision(
        agent_id=agent_id,
        allowed=snap.gate_passed is True,
        reason=reason,
        has_run=True,
        gate_passed=snap.gate_passed,
        failed_critical=snap.gate_failed_critical,
        run_at=snap.run_at,
    )


def request_release(agent_id: str, *, actor: str = "operator") -> ReleaseDecision:
    """Attempt to promote ``agent_id`` to live, gated by its eval-gate.

    Emits a hash-chained ``released`` event on success or ``release_blocked``
    otherwise — either way the intent + verdict are recorded durably.
    """
    decision = release_decision(agent_id)
    phase = "released" if decision.allowed else "release_blocked"
    emit_agent_lifecycle(agent_id=agent_id, phase=phase, actor=actor, detail=decision.as_dict())
    return decision


def _audit_path() -> Path:
    return Path(get_settings().guard.audit_file)


def lifecycle_history(agent_id: str, limit: int = 12) -> list[dict[str, object]]:
    """Return this agent's governance events (newest first) from the S1 chain."""
    path = _audit_path()
    events: list[dict[str, object]] = []
    if not path.exists():
        return events
    with path.open("r", encoding="utf-8") as fp:
        for raw in fp:
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                obj = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            event_type = str(obj.get("type", ""))
            phase = _PHASE_EVENTS.get(event_type)
            if phase is None:
                continue
            # `proposed` carries proposed_name (no agent_id yet); keep it for the
            # fleet view but skip it when scoping to a concrete agent.
            if obj.get("agent_id") != agent_id:
                continue
            events.append(
                {
                    "phase": phase,
                    "type": event_type,
                    "occurred_at": str(obj.get("occurred_at", "")),
                    "actor": str(obj.get("actor", "")),
                    "reason": str(obj.get("reason", "")),
                }
            )
    events.sort(key=lambda e: str(e.get("occurred_at", "")), reverse=True)
    return events[:limit]


def compute_agent_lifecycle(agent_id: str) -> dict[str, object]:
    """Lifecycle payload: current state, the gated release decision, and history."""
    decision = release_decision(agent_id)
    history = lifecycle_history(agent_id)
    last_phase = str(history[0]["phase"]) if history else "registered"
    # The effective state combines the last recorded transition with gate readiness.
    if last_phase == "live" and decision.allowed:
        state, tone = "Live", "good"
    elif decision.allowed:
        state, tone = "Prêt à promouvoir", "good"
    elif decision.has_run:
        state, tone = "Bloqué (eval-gate)", "bad"
    else:
        state, tone = "En attente d'évaluation", "warn"
    return {
        "agent_id": agent_id,
        "state": state,
        "state_tone": tone,
        "last_phase": last_phase,
        "release": decision.as_dict(),
        "history": history,
        "flow": ["proposed", "reviewed", "approved", "live"],
    }
