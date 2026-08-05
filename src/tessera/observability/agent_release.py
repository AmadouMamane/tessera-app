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
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, TypedDict

from tessera.observability.eval_data import load_eval_snapshot
from tessera.observability.eval_floor import grade_against_own_floor
from tessera.observability.eval_gate_view import build_gate_view
from tessera.verdict import NotOk, Ok

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
    "AgentRelease",
    "ReleaseBuckets",
    "ReleaseFacts",
    "agent_release_state",
    "eval_release_state",
    "fleet_release_buckets",
    "fleet_release_states",
]


class ReleaseFacts(TypedDict):
    """The release verdict exactly as the wire carries it (:meth:`AgentRelease.as_dict`).

    Typed at its SOURCE so every consumer inherits the contract instead of restating it.
    ``floor_block`` is the only nullable field: it names what the measured floor holds against
    the run, and is ``None`` when the floor clears it (ADR 0021 Rule 1).
    """

    agent_id: str
    available: bool
    passed: bool
    verdict_label: str
    verdict_tone: str
    candidate_version: str
    eval_set: str
    executions: int
    socle_ok: bool
    blocking_socle: int
    blocking_t1: int
    waived_active: int
    run_at: str
    catalogue_version: str
    current_catalogue_version: str
    verdict_stale: bool
    summary_passed: int
    summary_total: int
    socle_passed: int
    socle_total: int
    floor_ok: bool
    floor_block: str | None


class ReleaseBuckets(TypedDict):
    """Mutually exclusive fleet buckets shared by every release summary."""

    total: int
    evaluated: int
    ready: int
    review: int
    missing: int
    stale: int
    blocked: int


_LANG_IDX = {"fr": 0, "de": 1, "en": 2}

# Localized display of the FR gate-verdict labels (sourced from the shared
# eval-gate view) + the honest empty state. Unmapped labels fall through verbatim.
_VERDICT_FR: dict[str, str] = {
    "BLOQUÉ par le socle": "BLOQUÉ PAR LES TESTS COMMUNS",
    "BLOQUÉ (critiques non dérogés)": "BLOQUÉ PAR UN CAS CRITIQUE",
    "BLOQUÉ (domaine)": "BLOQUÉ PAR UNE EXIGENCE MÉTIER",
    "BLOQUÉ (règle 1)": "BLOQUÉ : MOINS FIABLE QUE SANS MODÈLE",
    "NE PEUT PAS DIRE (plancher)": "ÉVALUATION INSUFFISANTE",
    "PASSE": "PRÊT",
    "Éval non exécutée": "Évaluation non exécutée",
}
_VERDICT_TR: dict[str, tuple[str, str]] = {
    "BLOQUÉ par le socle": ("DURCH GEMEINSAME TESTS BLOCKIERT", "BLOCKED by shared tests"),
    "BLOQUÉ (critiques non dérogés)": (
        "DURCH KRITISCHEN FALL BLOCKIERT",
        "BLOCKED by a critical case",
    ),
    "BLOQUÉ (domaine)": (
        "DURCH FACHLICHE ANFORDERUNG BLOCKIERT",
        "BLOCKED by a business requirement",
    ),
    "BLOQUÉ (règle 1)": (
        "BLOCKIERT: UNZUVERLÄSSIGER ALS OHNE MODELL",
        "BLOCKED: LESS RELIABLE THAN NO MODEL",
    ),
    "NE PEUT PAS DIRE (plancher)": ("BEWERTUNG NICHT AUSREICHEND", "EVALUATION NOT SUFFICIENT"),
    "BLOQUÉ : MOINS FIABLE QUE SANS MODÈLE": (
        "BLOCKIERT: UNZUVERLÄSSIGER ALS OHNE MODELL",
        "BLOCKED: LESS RELIABLE THAN NO MODEL",
    ),
    "ÉVALUATION INSUFFISANTE": ("BEWERTUNG NICHT AUSREICHEND", "EVALUATION NOT SUFFICIENT"),
    "BLOQUÉ : PREUVES DE FONCTIONNEMENT INSUFFISANTES": (
        "BLOCKIERT: UNZUREICHENDE FUNKTIONSNACHWEISE",
        "BLOCKED: INSUFFICIENT EVIDENCE OF OPERATION",
    ),
    "PASSE": ("BEREIT", "READY"),
    "Éval non exécutée": ("Bewertung nicht ausgeführt", "Evaluation not run"),
}


def _verdict_label(label: str, lang: str) -> str:
    """Localize a gate-verdict label for display (de/en); FR is the canonical."""
    idx = _LANG_IDX.get(lang, 0)
    if idx == 0:
        return _VERDICT_FR.get(label, label)
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
    # ADR 0021 Rule 1, as this column's OWN release condition. `floor_ok` is True only when the
    # measured null floor produced an `Ok` for this agent's run; `floor_block` carries the one
    # line naming what the floor holds against it (a certified inversion, a break this run saw,
    # or a blind spot) — the wire speaks in nullable strings, the Verdict lives in eval_floor.
    floor_ok: bool = False
    floor_block: str | None = None

    @property
    def verdict_stale(self) -> bool:
        """True when the run was scored against a SUPERSEDED catalogue version."""
        return bool(
            self.current_catalogue_version
            and self.catalogue_version
            and self.catalogue_version != self.current_catalogue_version
        )

    def as_dict(self) -> ReleaseFacts:
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
            "floor_ok": self.floor_ok,
            "floor_block": self.floor_block,
        }


def eval_release_state(agent_id: str, lang: str = "fr") -> AgentRelease:
    """The EVAL half of the release verdict: the gate plus ADR 0021's measured floor.

    A narrower question than :func:`agent_release_state`, and it exists for one reason: the
    computed L-level reads *this* — an agent counts as ``governed`` when an eval with a socle has
    run — so the level condition cannot be applied here without
    ``resolve_level_state -> _governed -> agent_release_state`` closing on itself. The two
    questions are separated so the recursion is impossible by construction rather than avoided by
    care.

    Nothing operator-facing should render this on its own: it answers "did the evaluation clear",
    not "may this ship".

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
    # ADR 0021 Rule 1, HERE TOO. The Release button on the Évaluations page learned to read the
    # measured floor (the tile and the button used to disagree in the same component file) — and
    # the fleet's "état de release" column plus AGIR/Release Control, the surfaces an operator
    # actually scans, kept reading `gate.passed` alone. On 2026-07-14 they rendered PASSE for two
    # agents whose models are CERTIFIED worse than silence on runs those very agents execute.
    # Same grader, same verdict, every surface: only an `Ok` releases; a `NotOk` names the
    # certified inversion; a `CannotSay` (no floor with the power to clear) ships nothing either,
    # and the label keeps the two refusals distinct — a blind spot must never be dressed as a
    # measured block, nor either of them as a pass.
    floor = grade_against_own_floor(snap)
    floor_ok = isinstance(floor.releasable, Ok)
    verdict_label = gate.verdict_label
    verdict_tone = gate.verdict_tone
    if gate.passed and not floor_ok:
        blocked = isinstance(floor.releasable, NotOk)
        verdict_label = (
            "BLOQUÉ : MOINS FIABLE QUE SANS MODÈLE" if blocked else "ÉVALUATION INSUFFISANTE"
        )
        verdict_tone = "crit" if blocked else "bad"
    return AgentRelease(
        agent_id=agent_id,
        available=True,
        passed=gate.passed and floor_ok,
        verdict_label=_verdict_label(verdict_label, lang),
        verdict_tone=verdict_tone,
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
        floor_ok=floor_ok,
        floor_block=floor.block_reason(),
    )


def agent_release_state(agent_id: str, lang: str = "fr") -> AgentRelease:
    """Return the GOVERNED release verdict for one agent — the question the column asks.

    The fleet's column is headed *"Prêt à être mis en ligne"* and its note says *"dernier
    contrôle avant mise en ligne"*. That is the whole release decision, so this must apply every
    condition :func:`tessera.observability.agent_lifecycle.release_decision` applies, not the two
    it happened to know about.

    **It knew about two.** On 2026-07-14 this surface rendered PASSE for agents certified worse
    than silence, and learned to read the measured floor. It never learned rules 3 and 4 — no
    production below L2, and **L3 when the agent declares external effects**. That stayed
    invisible for as long as a stricter condition happened to fail first: `recouvrement` was
    blocked by the floor, so nobody could see the column ignoring its level. On 2026-08-05 the
    floor stopped blocking it and the column said **PRÊT** for an agent the release gate refuses.
    A screen that reports more than was measured is the defect this repository treats as
    non-negotiable, and one condition masking another is exactly how it survives.

    The level is asked of :mod:`tessera.observability.business_capabilities` lazily: that module
    imports this one, and the import is a cycle at module load. The recursion the *call* would
    otherwise close is broken at :func:`eval_release_state`, which is what ``_governed`` reads.
    """
    facts = eval_release_state(agent_id, lang)
    if not facts.available:
        return facts

    from tessera.observability.business_capabilities import (
        level_at_least,
        required_level_for,
        resolve_observability_level,
    )

    required = required_level_for(agent_id)
    if level_at_least(resolve_observability_level(agent_id), required):
        return facts
    return replace(
        facts,
        passed=False,
        verdict_label=_verdict_label("BLOQUÉ : PREUVES DE FONCTIONNEMENT INSUFFISANTES", lang),
        verdict_tone="bad",
    )


def fleet_release_states(lang: str = "fr") -> dict[str, AgentRelease]:
    """Return the release state of every registry agent, keyed by agent id."""
    try:
        from tessera.agent.registry import list_agents

        agents = [a.id for a in list_agents()]
    except (OSError, ValueError):
        agents = []
    return {aid: agent_release_state(aid, lang) for aid in agents}


def fleet_release_buckets(
    states: Mapping[str, AgentRelease] | None = None,
    *,
    lang: str = "fr",
) -> ReleaseBuckets:
    """Bucket the fleet using the same :class:`AgentRelease` verdicts as the Eval tile.

    A ready agent has a release-authorised verdict on a fresh catalogue. Every other registry
    agent belongs to exactly one review bucket: no verdict, stale verdict, or blocked verdict.
    The function accepts already-read states so callers such as the fleet endpoint never perform
    a second eval read merely to produce the summary.

    Args:
        states: Optional already-read release states keyed by agent id.
        lang: Locale used only when states need to be loaded.

    Returns:
        Mutually exclusive counts whose sum is ``total``.
    """
    releases = states if states is not None else fleet_release_states(lang)
    missing = sum(not release.available for release in releases.values())
    stale = sum(release.available and release.verdict_stale for release in releases.values())
    ready = sum(
        release.available and release.passed and not release.verdict_stale
        for release in releases.values()
    )
    blocked = sum(
        release.available and not release.passed and not release.verdict_stale
        for release in releases.values()
    )
    total = len(releases)
    return {
        "total": total,
        "evaluated": total - missing,
        "ready": ready,
        "review": total - ready,
        "missing": missing,
        "stale": stale,
        "blocked": blocked,
    }
