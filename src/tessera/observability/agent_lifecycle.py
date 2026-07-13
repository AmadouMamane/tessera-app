"""Governed agent lifecycle — propose → review → approve → release (Phase 4b-③).

This closes the governed-package loop: an agent (or a new version) only goes
**live** once a run of ITS own evaluation set clears the eval-gate — the **critical
floor**, zero tolerance, and only it (ADR 0021 removed the ``domain >= min_pass_rate``
half: every bar it compared against sat below the catalogue's measured null floor, so it
could never deny a release). The decision is read from the agent's own run report; the
transition is recorded as a hash-chained S1 event (``released`` on success,
``release_blocked`` otherwise), so the promotion is opposable and reconstructable in
État à date.

The registry itself is approved as a unit (ADR 0012) and not mutated at runtime —
this module governs the *promotion decision*, not a live registry edit.
"""

from __future__ import annotations

from dataclasses import dataclass

from tessera.guard.audit import emit_agent_lifecycle
from tessera.guard.ledger_store import read_ledger_entries
from tessera.observability.business_capabilities import (
    declares_external_effects,
    resolve_observability_level,
)
from tessera.observability.eval_data import load_eval_snapshot
from tessera.observability.eval_floor import grade_against_own_floor
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
        "eval-gate validé (plancher critique OK, zéro tolérance).",
        "Eval-Gate bestanden (kritische Basis OK, null Toleranz).",
        "eval-gate passed (critical floor OK, zero tolerance).",
    ),
    "r_blocked_critical": (
        "bloqué par le socle critique (zéro tolérance) : {cats}",
        "durch die kritische Basis blockiert (Null-Toleranz): {cats}",
        "blocked by the critical floor (zero tolerance): {cats}",
    ),
    # A gate that failed WITHOUT naming a critical failure. Since ADR 0021 removed the
    # domain bar, the only way the current gate produces this is an empty run — so the
    # message says that, and names the other possibility rather than guessing: a report
    # filed BEFORE the ADR, whose `passed: false` was the removed bar's doing.
    "r_blocked_no_critical": (
        "bloqué sans échec critique nommé : run vide (absence de preuve = bloquant), "
        "ou rapport antérieur à l'ADR 0021 dont le verdict venait de la barre de domaine, "
        "supprimée depuis. Relancer l'eval set tranche.",
        "blockiert ohne benannten kritischen Fehler: leerer Lauf (kein Nachweis = "
        "blockierend) oder ein Bericht von vor ADR 0021, dessen Urteil von der inzwischen "
        "entfernten Domaenen-Schwelle stammte. Das Eval-Set erneut ausfuehren entscheidet.",
        "blocked with no critical failure named: an empty run (absence of proof is "
        "blocking), or a report filed before ADR 0021 whose verdict came from the domain "
        "bar, since removed. Re-running the eval set settles it.",
    ),
    "r_no_verdict": (
        "aucun verdict de gate sur ce run (relancez via --agent).",
        "kein Gate-Verdikt fuer diesen Lauf (erneut mit --agent ausfuehren).",
        "no gate verdict on this run (re-run via --agent).",
    ),
    "r_below_l2_prod": (
        "non promouvable en production : niveau d'observabilité {lvl} < L2 "
        "(garde-fous / eval / audit invisibles au cockpit).",
        "in Produktion nicht freigebbar: Observability-Stufe {lvl} < L2 "
        "(Guardrails / Eval / Audit fuer das Cockpit unsichtbar).",
        "not releasable in production: observability level {lvl} < L2 "
        "(guardrails / eval / audit invisible to the cockpit).",
    ),
    "r_below_l3_external": (
        "L3 requis : l'agent déclare des effets externes mais son niveau est {lvl} "
        "(ses événements métier doivent être vérifiables).",
        "L3 erforderlich: Der Agent deklariert externe Effekte, aber seine Stufe ist {lvl} "
        "(seine Geschaeftsereignisse muessen ueberpruefbar sein).",
        "L3 required: the agent declares external effects but its level is {lvl} "
        "(its business events must be verifiable).",
    ),
    "lvl_none": ("aucun", "keiner", "none"),
    "s_live": ("Live", "Live", "Live"),
    "s_ready": ("Prêt à promouvoir", "Bereit zur Promotion", "Ready to promote"),
    # The eval-gate label may ONLY be shown when the eval-gate is what blocks. When the
    # gate passed but the observability level is below the release requirement, the block
    # is the level, and the label must say so — a generic "Bloqué (eval-gate)" there would
    # be a soft lie (ADR 0017 §A2.4 honesty).
    "s_blocked": ("Bloqué (eval-gate)", "Blockiert (Eval-Gate)", "Blocked (eval-gate)"),
    "s_blocked_level": (
        "Bloqué (niveau d'observabilité)",
        "Blockiert (Observability-Stufe)",
        "Blocked (observability level)",
    ),
    # ADR 0021 Rule 1. Named for what it means, not for the module it comes from: the point
    # an operator must grasp in one glance is that the model made the agent WORSE than
    # running with no model at all — not that some "floor check" failed.
    "s_blocked_floor": (
        "Bloqué (pire que sans modèle)",
        "Blockiert (schlechter als ohne Modell)",
        "Blocked (worse than no model)",
    ),
    "s_awaiting": ("En attente d'évaluation", "Bewertung ausstehend", "Awaiting evaluation"),
}

#: The specific condition that blocks a release, surfaced so the state label never claims
#: "eval-gate" when the gate passed and the observability level is what actually blocks.
BLOCKED_BY_EVAL_GATE = "eval_gate"
BLOCKED_BY_OBSERVABILITY_LEVEL = "observability_level"
#: ADR 0021's Rule 1, finally binding on the decision it was written for: the model broke a
#: run this agent passes with NO model at all. Its own condition, never folded into
#: ``eval_gate`` — the critical floor and the null floor fail for different reasons and are
#: fixed by different work, and a label that conflates them sends the operator to the wrong
#: place.
BLOCKED_BY_FLOOR = "null_floor"

#: Block reason → state label. Exhaustive by construction: a `blocked_by` with no entry here
#: would read as the critical eval-gate, which is exactly the misattribution `blocked_by`
#: exists to prevent — `test_every_block_reason_has_its_own_label` fails if one is added
#: without its label.
_BLOCK_LABEL: dict[str | None, str] = {
    BLOCKED_BY_EVAL_GATE: "s_blocked",
    BLOCKED_BY_FLOOR: "s_blocked_floor",
    BLOCKED_BY_OBSERVABILITY_LEVEL: "s_blocked_level",
}


def _t(key: str, lang: str) -> str:
    return _TR[key][_LANG_IDX.get(lang, 0)]


# ADR 0017 §4 ladder order, for the §A2.4 "at least L2 / L3" release conditions.
_LEVEL_ORDER: dict[str | None, int] = {None: -1, "L0": 0, "L1": 1, "L2": 2, "L3": 3}


def _level_at_least(level: str | None, required: str | None) -> bool:
    """Whether ``level`` meets a required minimum on the L0-L3 ladder (None required = always)."""
    if required is None:
        return True
    return _LEVEL_ORDER.get(level, -1) >= _LEVEL_ORDER.get(required, 99)


def _blocked_by(*, eval_passed: bool, floor_ok: bool, level_ok: bool) -> str | None:
    """Which condition blocks the release (``None`` when nothing does).

    Reported in the order an operator must fix them: a failed critical case first, then a
    model that is worse than no model at all, then an unobservable agent. Each block names
    its own cause — the state label never attributes a floor break or a level shortfall to
    the critical eval-gate, because they are three different problems with three different
    fixes (ADR 0017 §A2.4 honesty, extended to ADR 0021's Rule 1).
    """
    if not eval_passed:
        return BLOCKED_BY_EVAL_GATE
    if not floor_ok:
        return BLOCKED_BY_FLOOR
    if not level_ok:
        return BLOCKED_BY_OBSERVABILITY_LEVEL
    return None


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
    # ADR 0017 §A2.4 — the observability level is a release condition, not a parallel
    # lifecycle: the agent's current L-level and the minimum this release requires.
    observability_level: str | None = None
    required_level: str | None = None
    # Which condition blocks the release, when one does (``None`` when allowed):
    # ``"eval_gate"`` (the two-level gate failed) or ``"observability_level"`` (the gate
    # passed but the L-level is below the requirement). Lets the UI label the block
    # truthfully instead of always attributing it to the eval-gate.
    blocked_by: str | None = None
    # ADR 0021 Rule 1 — the null-floor condition. `floor_graded` False means the model was
    # NOT graded against its floor (no set, no model, or a floor that no longer applies), and
    # that blocks: an ungraded model is not a cleared one. Recorded in the S1 event so the
    # audit trail says which floor released the agent, not merely that something did — a
    # verdict that cannot name what it judged is unfalsifiable.
    floor_graded: bool = False
    floor_regressions: tuple[str, ...] = ()

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
            "observability_level": self.observability_level,
            "required_level": self.required_level,
            "blocked_by": self.blocked_by,
            "floor_graded": self.floor_graded,
            "floor_regressions": list(self.floor_regressions),
        }


def release_decision(agent_id: str, lang: str = "fr") -> ReleaseDecision:
    """Decide whether ``agent_id`` may go live (ADR 0017 §A2.4).

    From its own eval-gate verdict, its measured null floor AND its observability level —
    four conditions, all required:
    1. a run of the agent's OWN set that cleared the critical floor (zero tolerance);
    2. **not worse than no model at all** (ADR 0021, Rule 1) — the model must break none of
       the runs the agent already passes with every LLM backend unreachable. The critical
       floor structurally cannot see this: 70% of the catalogue is closed by the
       deterministic guard/router layer before a token is generated, so an agent can clear
       every critical case while having *degraded* what worked without it;
    3. **no production below L2** — an agent whose guard/eval/audit facts the cockpit
       cannot see is not releasable, whatever its scores;
    4. **L3 when it declares external effects** — a capability reaching outside the
       system (``requires_validation`` / ``external_action``) must have verifiable
       business events. The L-level is a *condition*, not a parallel lifecycle.
    """
    lang = _norm_lang(lang)
    level = resolve_observability_level(agent_id)
    if declares_external_effects(agent_id):
        required_level: str | None = "L3"
    elif get_settings().is_production():
        required_level = "L2"
    else:
        required_level = None
    level_ok = _level_at_least(level, required_level)

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
            observability_level=level,
            required_level=required_level,
        )

    eval_passed = snap.gate_passed is True

    # ADR 0021's Rule 1, as a RELEASE CONDITION. The critical floor above cannot see a model
    # that is worse than no model at all: 122 of the catalogue's 174 runs pass with every LLM
    # backend pointed at a closed port, so an agent can clear every critical case and still
    # have BROKEN a run its own deterministic guard/router layer closes unaided. That was
    # computed and rendered on the Évaluations page all along — and the Release button on
    # that same page did not read it. It does now.
    floor = grade_against_own_floor(snap)
    floor_ok = floor.releasable

    if not eval_passed:
        if snap.gate_failed_critical:
            reason = _t("r_blocked_critical", lang).format(
                cats=", ".join(snap.gate_failed_critical)
            )
        elif snap.gate_passed is False:
            reason = _t("r_blocked_no_critical", lang)
        else:
            reason = _t("r_no_verdict", lang)
    elif not floor_ok:
        # Not translated through _t(): the reason names case ids and the command that
        # settles them, and a paraphrase of those would be less useful in every language.
        reason = floor.block_reason() or ""
    elif not level_ok:
        lvl = level or _t("lvl_none", lang)
        key = "r_below_l3_external" if required_level == "L3" else "r_below_l2_prod"
        reason = _t(key, lang).format(lvl=lvl)
    else:
        reason = _t("r_validated", lang)

    return ReleaseDecision(
        agent_id=agent_id,
        allowed=eval_passed and floor_ok and level_ok,
        reason=reason,
        has_run=True,
        gate_passed=snap.gate_passed,
        failed_critical=snap.gate_failed_critical,
        run_at=snap.run_at,
        observability_level=level,
        required_level=required_level,
        floor_graded=floor.graded,
        floor_regressions=floor.regression_candidates,
        # Attribute the block to its real cause so the UI label never lies (§A2.4).
        blocked_by=_blocked_by(eval_passed=eval_passed, floor_ok=floor_ok, level_ok=level_ok),
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


def lifecycle_history(agent_id: str, limit: int = 12) -> list[dict[str, object]]:
    """Return this agent's governance events (newest first) from the S1 chain."""
    events: list[dict[str, object]] = []
    for obj in read_ledger_entries():
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
        # Label the block by its real cause. This was an if/else that fell back to the
        # eval-gate label for anything it did not recognise — so a new block reason would
        # silently be attributed to the critical gate, which is the very soft lie §A2.4
        # added `blocked_by` to prevent. A mapping cannot fall through by accident.
        blocked_key = _BLOCK_LABEL.get(decision.blocked_by, "s_blocked")
        state, tone = _t(blocked_key, lang), "bad"
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
