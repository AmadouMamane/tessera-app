"""The agent's own measured floor — graded once, read by the screen AND by the button.

ADR 0021 established that a model is graded on its **contribution over the null floor**,
never on an absolute rate, and that Rule 1 — *break none of the runs the agent passes with
no model at all* — is the non-derogable part: a model worse than no model at all passes no
gate, whatever it scores elsewhere.

It was computed, rendered, and **ignored**. The cockpit's Évaluations page showed the
contribution tile (``agent_evaluations._contribution_block``), and the Release button
sitting in the very same component called a decision (``agent_lifecycle.release_decision``)
that read only ``gate.passed`` — the critical floor. So an agent could break a case the
deterministic layer closes on its own, be shown breaking it, and be released anyway. The
screen told the truth; the button did not read it.

This module is the single place that grades an agent against its own floor, so that the
tile and the release decision can never again disagree about what the model earned. Two
implementations of "the floor" is how they drifted apart in the first place.

**What blocks, and why each is fail-closed:**

* **A confirmed-or-unreplayed Rule-1 break.** Sampling is stochastic (the same llama3.2:3b
  breaks ``56_policy_violation_disparage_bank|de`` on some passes and not others), so ADR
  0021 only counts a regression once *replayed* — and the cockpit cannot replay, it has no
  model. An unreplayed candidate is therefore **not a cleared one**: it blocks, and the
  reason carries the command that settles it. Forgiving what it cannot check is exactly how
  a gate becomes a decoration.
* **A floor that does not apply** (the set's cases moved since the null control was
  captured). The model was not graded at all, and an ungraded model is not a cleared one.
* **No floor at all** (no eval set, or a run in which no model ever spoke). You cannot
  certify "not worse than nothing" without the "nothing" to compare against.

The absolute pass rate appears nowhere here, on purpose: 122 of the catalogue's 174 runs
pass with every LLM backend pointed at a closed port, so a rate grades the sum of what the
catalogue closes and what the model adds, and therefore grades neither.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, assert_never

from eval.contribution import evaluate_contribution, restrict_baseline
from eval.ratchet import load_baseline
from eval.sets import load_eval_set
from tessera.verdict import CannotSay, NoEffect, NotOk, Ok, Verdict

if TYPE_CHECKING:
    from eval.contribution import ContributionVerdict
    from tessera.observability.eval_data import EvalSnapshot

__all__ = ["FloorGrade", "grade_against_own_floor"]

#: The committed null control — the measured floor every agent is graded against.
NULL_BASELINE = Path(__file__).resolve().parents[3] / "eval" / "baselines" / "null-control.json"

#: Why the floor could not grade this run at all (no set, no model, no baseline).
ABSENT_NO_SET = "this run is not scoped to an eval set — there is no set floor to grade it against"
ABSENT_NO_MODEL = (
    "no model spoke in this run (0 output tokens) — the deterministic layer was scored alone, "
    "so there is no model contribution to grade"
)
ABSENT_NO_BASELINE = (
    "no committed null control covers this set — regenerate it (`make eval-null-write`) "
    "rather than grading against an absent floor"
)


@dataclass(frozen=True, slots=True)
class FloorGrade:
    """What one agent's run earned over its OWN measured null floor.

    Attributes:
        graded: Whether the run was graded at all. ``False`` means there is no verdict —
            not a bad one. The distinction is the whole point: a refusal reported as
            "contribution 0/0" reads as a measured zero.
        obstacle: Why it was not graded (``None`` iff ``graded``).
        verdict: The contribution verdict (``None`` iff not graded).
        floor_passed: Runs this set's null floor passes — the bar, and nobody chose it.
        floor_total: Runs in this set's null floor.
    """

    graded: bool
    obstacle: str | None
    verdict: ContributionVerdict | None
    floor_passed: int = 0
    floor_total: int = 0

    @property
    def regression_candidates(self) -> tuple[str, ...]:
        """Runs the floor passes and this run broke — *candidates* until replayed."""
        return self.verdict.confirmed_breaks if self.verdict else ()

    @property
    def releasable(self) -> Verdict:
        """Whether the floor permits a release — Rule 1, fail-closed, **and it says what it saw**.

        A :class:`~tessera.verdict.Verdict` and not a ``bool``, because **one bit is exactly how
        this went wrong the first time**: Rule 1 was computed, rendered on the Contribution tile,
        and then ignored by the only decision it governs — the Release button, in the same
        component file, read ``gate.passed`` and nothing else. A bit cannot be asked what it
        looked at, so nobody asked.

        And the bool hid a second thing, which the type surfaced the moment it replaced it: the
        old ``releasable`` returned ``False`` **both** when the model broke the floor *and* when
        there was no floor to grade against. Fail-closed is right in both cases — a floor that
        did not clear this model does not release it — but they are different facts, and this
        class's own docstring says so ("``graded=False`` means there is no verdict, not a bad
        one; the distinction is the whole point"). It was the whole point everywhere except in
        the property that decides.

        Returns:
            ``Ok`` carrying the floor it cleared; ``NotOk`` naming the runs it broke; ``CannotSay``
            when there was no usable floor — never a bare ``True``.
        """
        if not self.graded:
            return CannotSay(
                self.obstacle
                or "this run was not graded against a null floor, and an ungraded run is not a "
                "cleared one"
            )
        breaks = self.regression_candidates
        if breaks:
            return NotOk(
                f"the model breaks {len(breaks)} run(s) this agent passes with NO model at all "
                f"({', '.join(breaks)}) — it is worse than nothing on them. Sampling is "
                f"stochastic, so replay to confirm or clear it: "
                f"`make eval-contribution REPORT=eval/reports/local/latest_<agent>.json`"
            )
        return Ok(
            f"graded against its own measured null floor ({self.floor_passed}/{self.floor_total} "
            f"runs the agent passes with no model at all) and broke none of them"
        )

    def block_reason(self) -> str | None:
        """One line naming what the floor holds against this run (``None`` when it clears).

        The string form of :attr:`releasable`, kept for the wire and the UI, which speak in
        nullable strings. It is derived from the verdict rather than recomputed beside it — two
        functions answering the same question their own way is how the tile and the button came
        to disagree.
        """
        match self.releasable:
            case Ok():
                return None
            case NotOk(reason=reason):
                return reason
            case CannotSay(blind_spot=blind_spot):
                return blind_spot
            case NoEffect(claim=claim):  # pragma: no cover — a floor has no null result to report
                return claim
        assert_never(self.releasable)  # pragma: no cover — exhaustive; mypy proves it is


def grade_against_own_floor(snap: EvalSnapshot) -> FloorGrade:
    """Grade an agent's run against the null control restricted to its own eval set.

    Args:
        snap: The agent's latest eval snapshot.

    Returns:
        A :class:`FloorGrade`. Never raises: an absent or inapplicable floor is reported as
        *not graded*, which blocks — it is not silently treated as a pass.
    """
    if not snap.eval_set:
        return FloorGrade(graded=False, obstacle=ABSENT_NO_SET, verdict=None)
    if not snap.token_totals()[1]:
        return FloorGrade(graded=False, obstacle=ABSENT_NO_MODEL, verdict=None)

    try:
        eval_set = load_eval_set(snap.eval_set)
        floor = restrict_baseline(load_baseline(NULL_BASELINE), set(eval_set.effective_case_ids))
    except (KeyError, ValueError, TypeError, OSError):
        return FloorGrade(graded=False, obstacle=ABSENT_NO_BASELINE, verdict=None)

    report = {
        "model": snap.model,
        # The run must say which case set it was scored against, or the gate cannot check
        # that this floor applies to it — and would grade against a floor it cannot verify.
        "catalogue_version": snap.catalogue_version,
        "results": [
            {"case_id": s.case_id, "language": s.language, "passed": s.passed}
            for s in snap.sessions
        ],
    }
    # `confirmed=None` — the cockpit has no model and cannot replay, so every candidate
    # break counts. Fails closed by construction: an ungraded break is not a forgiven one.
    verdict = evaluate_contribution(report, floor, min_contribution=None)
    if verdict.refusal is not None:
        return FloorGrade(graded=False, obstacle=verdict.refusal, verdict=None)

    return FloorGrade(
        graded=True,
        obstacle=None,
        verdict=verdict,
        floor_passed=floor.passed,
        floor_total=floor.total,
    )
