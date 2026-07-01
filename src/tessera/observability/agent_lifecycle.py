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
from tessera.observability.knowledge import _LANG_IDX, _norm_lang
from tessera.settings import get_settings

__all__ = [
    "ReleaseDecision",
    "compute_agent_lifecycle",
    "lifecycle_history",
    "release_decision",
    "request_release",
]

# Localized free-text (fr, de, en).
_TR: dict[str, tuple[str, str, str]] = {
    "r_no_run": (
        "aucun run d'évaluation pour cet agent — lancez son eval set d'abord.",
        "kein Bewertungslauf fuer diesen Agenten - starten Sie zuerst sein Eval-Set.",
        "no evaluation run for this agent - run its eval set first.",
    ),
    "r_validated": (
        "eval-gate validé (socle critique OK + domaine ≥ seuil).",
        "Eval-Gate bestanden (kritische Basis OK + Domaene ≥ Schwelle).",
        "eval-gate passed (critical floor OK + domain >= threshold).",
    ),
    "r_blocked_critical": (
        "bloqué par le socle critique (zéro tolérance) : {cats}",
        "durch die kritische Basis blockiert (Null-Toleranz): {cats}",
        "blocked by the critical floor (zero tolerance): {cats}",
    ),
    "r_blocked_domain": (
        "bloqué : le taux du domaine est sous le seuil de l'eval set.",
        "blockiert: die Domaenenrate liegt unter der Schwelle des Eval-Sets.",
        "blocked: the domain rate is below the eval set threshold.",
    ),
    "r_no_verdict": (
        "aucun verdict de gate sur ce run (relancez via --agent).",
        "kein Gate-Verdikt fuer diesen Lauf (erneut mit --agent ausfuehren).",
        "no gate verdict on this run (re-run via --agent).",
    ),
    "s_live": ("Live", "Live", "Live"),
    "s_ready": ("Prêt à promouvoir", "Bereit zur Promotion", "Ready to promote"),
    "s_blocked": ("Bloqué (eval-gate)", "Blockiert (Eval-Gate)", "Blocked (eval-gate)"),
    "s_awaiting": ("En attente d'évaluation", "Bewertung ausstehend", "Awaiting evaluation"),
}


def _t(key: str, lang: str) -> str:
    return _TR[key][_LANG_IDX.get(lang, 0)]

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


def release_decision(agent_id: str, lang: str = "fr") -> ReleaseDecision:
    """Decide whether ``agent_id`` may go live, from its own eval-gate verdict.

    Live requires a run of the agent's OWN set that cleared the two-level gate.
    No run, or a blocked gate, means the agent cannot be promoted.
    """
    lang = _norm_lang(lang)
    try:
        snap = load_eval_snapshot(agent_id)
    except FileNotFoundError:
        return ReleaseDecision(
            agent_id=agent_id,
            allowed=False,
            reason=_t("r_no_run", lang),
            has_run=False,
            gate_passed=None,
            failed_critical=(),
            run_at="",
        )
    if snap.gate_passed is True:
        reason = _t("r_validated", lang)
    elif snap.gate_failed_critical:
        reason = _t("r_blocked_critical", lang).format(cats=", ".join(snap.gate_failed_critical))
    elif snap.gate_passed is False:
        reason = _t("r_blocked_domain", lang)
    else:
        reason = _t("r_no_verdict", lang)
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


def compute_agent_lifecycle(agent_id: str, lang: str = "fr") -> dict[str, object]:
    """Lifecycle payload: current state, the gated release decision, and history."""
    lang = _norm_lang(lang)
    decision = release_decision(agent_id, lang)
    history = lifecycle_history(agent_id)
    last_phase = str(history[0]["phase"]) if history else "registered"
    # The effective state combines the last recorded transition with gate readiness.
    if last_phase == "live" and decision.allowed:
        state, tone = _t("s_live", lang), "good"
    elif decision.allowed:
        state, tone = _t("s_ready", lang), "good"
    elif decision.has_run:
        state, tone = _t("s_blocked", lang), "bad"
    else:
        state, tone = _t("s_awaiting", lang), "warn"
    return {
        "agent_id": agent_id,
        "state": state,
        "state_tone": tone,
        "last_phase": last_phase,
        "release": decision.as_dict(),
        "history": history,
        "flow": ["proposed", "reviewed", "approved", "live"],
    }
