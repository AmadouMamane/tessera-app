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

import hashlib
from dataclasses import dataclass

from tessera.observability.eval_data import load_eval_snapshot
from tessera.observability.eval_gate_view import build_gate_view

__all__ = ["AgentRelease", "agent_release_state", "fleet_release_states"]

_LANG_IDX = {"fr": 0, "de": 1, "en": 2}

# Localized display of the FR gate-verdict labels (sourced from the shared
# eval-gate view) + the honest empty state. Unmapped labels fall through verbatim.
_VERDICT_TR: dict[str, tuple[str, str]] = {
    "BLOQUÉ par le socle": ("DURCH SOCKEL BLOCKIERT", "BLOCKED by core"),
    "BLOQUÉ (critiques non dérogés)": (
        "BLOCKIERT (kritische ohne Ausnahme)",
        "BLOCKED (unwaived critical)",
    ),
    "BLOQUÉ (domaine)": ("BLOCKIERT (Domaene)", "BLOCKED (domain)"),
    "PASSE": ("BESTANDEN", "PASS"),
    "Éval non exécutée": ("Eval nicht ausgefuehrt", "Eval not run"),
}


def _verdict_label(label: str, lang: str) -> str:
    """Localize a gate-verdict label for display (de/en); FR is the canonical."""
    idx = _LANG_IDX.get(lang, 0)
    if idx == 0:
        return label
    pair = _VERDICT_TR.get(label)
    return pair[idx - 1] if pair else label


def _current_catalogue_version(eval_set_slug: str) -> str:
    """Version (``count-hash``) of an agent's eval set AS IT EXISTS NOW.

    Mirrors ``eval.runner._catalogue_version`` over the set's current effective
    case ids so a run scored against a SUPERSEDED catalogue can be flagged
    "verdict périmé". Real source — the live eval-set manifest + failure
    catalogue — never a fabricated number. Returns ``""`` if it can't be derived
    (so the caller never invents a drift it can't prove).
    """
    try:
        from eval.sets import load_eval_set

        ids = sorted(load_eval_set(eval_set_slug).effective_case_ids)
    except (ImportError, KeyError, OSError, ValueError):
        return ""
    if not ids:
        return ""
    digest = hashlib.sha256("\n".join(ids).encode()).hexdigest()[:8]
    return f"{len(ids)}-{digest}"


@dataclass(frozen=True, slots=True)
class AgentRelease:
    """The release/eval-gate state of one agent package.

    ``available`` is ``False`` when the agent has no usable reference run; the
    verdict fields are then empty and the UI shows "évaluation non exécutée".

    Each agent is governed INDEPENDENTLY (ADR 0010): its run is staggered in time
    (``run_at``) and scored against its OWN catalogue version (``catalogue_version``)
    over its OWN domain set, so ``summary_*`` pass counts are NOT comparable across
    agents — only ``socle_*`` (the shared security floor, identical cases for every
    agent) is a legitimate cross-agent comparator.
    """

    agent_id: str
    available: bool
    passed: bool = False
    verdict_label: str = ""
    verdict_tone: str = "muted"
    candidate_version: str = ""
    eval_set: str = ""
    executions: int = 0
    socle_ok: bool = False
    blocking_socle: int = 0
    blocking_t1: int = 0
    waived_active: int = 0
    # Provenance — what this verdict was actually measured on.
    run_at: str = ""
    catalogue_version: str = ""
    current_catalogue_version: str = ""
    # Pass rate AS THE REPORT/COCKPIT SHOW IT (summary grain: passed / total of
    # this run, against the agent's own set). NOT comparable across agents.
    summary_passed: int = 0
    summary_total: int = 0
    # Shared security floor — the ONLY cross-agent comparable axis.
    socle_passed: int = 0
    socle_total: int = 0

    @property
    def verdict_stale(self) -> bool:
        """True when the run was scored against a SUPERSEDED catalogue version."""
        return bool(
            self.current_catalogue_version
            and self.catalogue_version
            and self.catalogue_version != self.current_catalogue_version
        )

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
            "socle_ok": self.socle_ok,
            "blocking_socle": self.blocking_socle,
            "blocking_t1": self.blocking_t1,
            "waived_active": self.waived_active,
            "run_at": self.run_at,
            "catalogue_version": self.catalogue_version,
            "current_catalogue_version": self.current_catalogue_version,
            "verdict_stale": self.verdict_stale,
            "summary_passed": self.summary_passed,
            "summary_total": self.summary_total,
            "socle_passed": self.socle_passed,
            "socle_total": self.socle_total,
        }


def agent_release_state(agent_id: str, lang: str = "fr") -> AgentRelease:
    """Return the eval-gate release verdict for one agent, or an honest empty state.

    ``lang`` localizes the human-facing ``verdict_label`` (fr / de / en); all
    other fields are language-independent numbers, ids and tone keys.
    """
    try:
        snap = load_eval_snapshot(agent_id)
    except (FileNotFoundError, OSError, ValueError):
        return AgentRelease(
            agent_id=agent_id,
            available=False,
            verdict_label=_verdict_label("Éval non exécutée", lang),
        )
    gate = build_gate_view(snap)
    return AgentRelease(
        agent_id=agent_id,
        available=True,
        passed=gate.passed,
        verdict_label=_verdict_label(gate.verdict_label, lang),
        verdict_tone=gate.verdict_tone,
        candidate_version=gate.candidate_version,
        eval_set=snap.eval_set,
        executions=gate.executions,
        socle_ok=gate.socle_ok,
        blocking_socle=gate.blocking_socle,
        blocking_t1=gate.blocking_t1,
        waived_active=gate.waived_active,
        run_at=snap.run_at,
        catalogue_version=snap.catalogue_version,
        current_catalogue_version=_current_catalogue_version(snap.eval_set),
        summary_passed=snap.passed,
        summary_total=snap.total,
        socle_passed=gate.socle_passed,
        socle_total=gate.socle_total,
    )


def fleet_release_states(lang: str = "fr") -> dict[str, AgentRelease]:
    """Return the release state of every registry agent, keyed by agent id."""
    try:
        from tessera.agent.registry import list_agents

        agents = [a.id for a in list_agents()]
    except (OSError, ValueError):
        agents = []
    return {aid: agent_release_state(aid, lang) for aid in agents}
