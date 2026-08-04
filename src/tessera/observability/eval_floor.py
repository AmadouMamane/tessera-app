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

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, assert_never

from eval.contribution import evaluate_contribution, restrict_baseline
from eval.ratchet import catalogue_on_disk, grader_criteria_sha_for, load_baseline
from eval.sets import load_eval_set
from tessera.verdict import CannotSay, NoEffect, NotOk, Ok, Verdict

if TYPE_CHECKING:
    from collections.abc import Iterable

    from eval.contribution import ContributionVerdict
    from eval.ratchet import Baseline
    from tessera.observability.eval_data import EvalSnapshot

__all__ = [
    "CertifiedInversions",
    "FloorGrade",
    "certified_inversions",
    "grade_against_own_floor",
]

#: The committed null control — the measured floor every agent is graded against.
NULL_BASELINE = Path(__file__).resolve().parents[3] / "eval" / "baselines" / "null-control.json"

#: The committed **measurement** of what the catalogue measures: 15 passes of the reference model
#: against 15 of a weak one, classified run by run, frozen, and defended by CI
#: (``scripts/check_discrimination.py``). It is the only artefact in this repository that can say
#: *"this model is reproducibly worse than silence here"* — with enough passes to mean it.
CLASSIFICATION = Path(__file__).resolve().parents[3] / "eval" / "baselines" / "discrimination.json"

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


def _absent_ruler_unknown(run_at: str) -> str:
    return (
        f"this run ({run_at or 'undated'}) does not record which grading criteria judged it, so "
        f"it cannot be compared with a floor that does. `catalogue_version` pins WHICH cases "
        f"exist and is blind to WHAT they assert — re-run it, or re-derive its judgements from "
        f"its recorded responses (`make eval-regrade`), which costs no tokens"
    )


def _absent_floor_ruler(stamped: str, current: str) -> str:
    return (
        f"the null control was measured under criteria {stamped or 'it does not record'} and the "
        f"catalogue now says {current} — the FLOOR is the stale side of this comparison, and a "
        f"stale floor blocks a release as confidently as a bad model would. Re-measure it: "
        f"`make eval-null-write`"
    )


def _absent_ruler_moved(run_ruler: str, floor_ruler: str) -> str:
    return (
        f"this run was judged by criteria {run_ruler} and the floor by {floor_ruler} — two "
        f"different rulers, so 'the model breaks a run the floor passes' is not a fact about the "
        f"model. On 2026-08-03 fifty-nine criteria changed and the floor was re-measured; the "
        f"agents' reports were not, and this comparison reported three models as worse than no "
        f"model at all. Re-grade the run under today's criteria (`make eval-regrade`) or re-run it"
    )


@dataclass(frozen=True, slots=True)
class CertifiedInversions:
    """The runs on which a model is **reproducibly worse than silence** — measured, not sampled.

    An inversion is a run the null control passes with **zero tokens** and the model **breaks**.
    It is the definition of "worse than nothing", and ADR 0021 makes it non-derogable: a model
    worse than no model at all is not shippable, whatever it scores elsewhere.

    **This class exists because the release gate could not see one.** On 2026-07-13 the gate said
    ``allowed=True`` for a model that breaks ``56_policy_violation_disparage_bank|de`` in **13 of
    15 passes** — a run the null control passes. It was not wrong about what it looked at. It was
    wrong about **how much**: it read exactly one report, that report was one of the ~2 lucky
    passes in 15, and the gate published *"broke none of them"* as a fact. Its green had an 87 %
    chance of being false.

    So the gate now reads a measurement instead of a sample. This is the *fact* bucket of
    ``eval/discrimination.py``, restricted to the runs a given agent actually executes.

    Attributes:
        model: The model the certification speaks about. It speaks about **no other** — a
            classification of ``llama3.2:3b`` says nothing about ``gemma3:27b``.
        catalogue_version: The case set it was measured on, **verified against the case files on
            disk** and not merely quoted from the artefact.
        passes: How many full passes of the model it is built on. This is the power, and it is
            carried, not implied.
        runs: The ``case_id|language`` runs of *this agent* on which the model is certified worse
            than silence. **One is enough to refuse.**
    """

    model: str
    catalogue_version: str
    passes: int
    runs: tuple[str, ...]
    #: The model's measured pass rate on each entry of ``runs``, in the same order ("9/15").
    #: Empty for a measurement taken before the rates were carried; the refusal degrades to its
    #: previous wording rather than inventing a number.
    rates: tuple[str, ...] = ()

    def described_runs(self) -> str:
        """``run (9/15)`` for each inversion, or just the run when no rate was recorded."""
        if len(self.rates) != len(self.runs):
            return ", ".join(self.runs)
        return ", ".join(f"{run} ({rate})" for run, rate in zip(self.runs, self.rates, strict=True))


def certified_inversions(  # noqa: PLR0911
    model: str, agent_runs: frozenset[str], *, classification: Path = CLASSIFICATION
) -> CertifiedInversions | CannotSay:
    """The measured inversions of ``model`` among the runs this agent actually executes.

    ``PLR0911`` is suppressed on the signature: there are six distinct ways a measurement can fail
    to apply, and each returns a ``CannotSay`` that NAMES which one. Folding two of them together
    to please a counter would put two different blind spots behind one sentence — which is the
    failure this module exists to undo.

    Returns a ``CannotSay`` — never an empty certification — whenever the measurement cannot be
    shown to apply. *"I have not measured this"* and *"I measured it and found nothing"* are
    different facts, and only the second may open a gate.

    Four ways it refuses, and each is a real hole it was written to close:

    * **No classification at all.** Nobody has measured this catalogue over enough passes.
    * **The catalogue moved.** The classification names a case set the disk no longer holds — so
      every run key in it may point at a case that does not exist. Checked against
      :func:`eval.ratchet.catalogue_on_disk`, **the one function allowed to open the source**. A
      chain of artefacts agreeing with each other is how the discrimination ratchet came to be
      green with two of its three discriminators deleted.
    * **A different model.** The certification is about the model it sampled. A gate that let a
      ``llama3.2:3b`` measurement clear a ``gemma3:27b`` release would be reading a neighbour.
    * **No passes recorded.** A certification that does not say how many passes it rests on is a
      claim, not a measurement.

    Args:
        model: The model whose run is being graded.
        agent_runs: The ``case_id|language`` runs the agent actually executed.
        classification: The committed measurement.

    Returns:
        The inversions of ``model`` inside ``agent_runs`` — possibly empty, which is then a
        **well-powered** absence — or a ``CannotSay`` naming what could not be established.
    """
    try:
        payload = json.loads(classification.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return CannotSay(
            f"no committed measurement of what the catalogue measures ({classification.name}). "
            f"Nobody has replayed this catalogue enough times to establish whether the model is "
            f"worse than silence anywhere — and ONE pass cannot: the reference model breaks its "
            f"worst floor run in 13 of 15 passes, so a single clean report is a coin, not a "
            f"clearance. Measure it: `make eval-power-write`."
        )
    if not isinstance(payload, dict) or payload.get("kind") != "catalogue_power":
        return CannotSay(f"{classification.name} is not a catalogue-power measurement")

    measured_on = str(payload.get("catalogue_version") or "")
    on_disk = catalogue_on_disk()
    if on_disk is None:
        return CannotSay(
            "the catalogue is not there to be read — the measurement cannot be shown to describe "
            "any case that still exists"
        )
    if measured_on != on_disk:
        return CannotSay(
            f"the catalogue MOVED: the measurement was taken on {measured_on!r} and the case files "
            f"on disk are {on_disk!r}. Its inversions name runs that may no longer exist, so none "
            f"of them may clear — or block — a release. Re-measure (`make eval-power-write`)."
        )

    certified_model = str(payload.get("strong_model") or "")
    if certified_model != model:
        return CannotSay(
            f"the measurement is about {certified_model!r} and this run is {model!r}. A model that "
            f"has never been replayed against the null floor cannot be shown to be no worse than "
            f"silence — and ADR 0021's Rule 1 is non-derogable, so it does not get the benefit of "
            f"the doubt. Measure it: `make eval-power-write --strong {model}`."
        )

    passes = int(payload.get("strong_n") or 0)
    if passes <= 0:
        return CannotSay(
            f"the measurement of {model!r} records no passes — a certification that cannot say how "
            f"many times it looked is a claim, not a measurement"
        )

    runs = payload.get("runs") or {}
    inverted = tuple(
        sorted(
            key
            for key, run in runs.items()
            if isinstance(run, dict) and run.get("class") == "inverted" and key in agent_runs
        )
    )
    # The measured pass rate of each inverted run, as the classifier recorded it ("13/15").
    # Carried so the refusal can STATE it instead of asserting "reproducibly breaks them" over
    # every inversion alike: on 2026-08-04 one agent was refused on a run the model breaks 6
    # times in 15 and another on a run it breaks 2 times in 15, and both were reported in the
    # same words. Both refusals are correct — ADR 0021 Rule 1 counts runs, not p-values — but an
    # operator deciding what to fix first cannot read that sentence and learn which is which.
    rates = tuple(
        str(runs[key].get("strong") or "?") for key in inverted if isinstance(runs.get(key), dict)
    )
    return CertifiedInversions(
        model=model,
        catalogue_version=measured_on,
        passes=passes,
        runs=inverted,
        rates=rates,
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
        certified: What is **measured** about this model over many passes, restricted to this
            agent's runs — or a ``CannotSay`` when no measurement applies. The single report above
            is one sample of a stochastic process; this is the population.
    """

    graded: bool
    obstacle: str | None
    verdict: ContributionVerdict | None
    floor_passed: int = 0
    floor_total: int = 0
    certified: CertifiedInversions | CannotSay | None = None

    @property
    def regression_candidates(self) -> tuple[str, ...]:
        """Runs the floor passes and **this one report** broke — *candidates* until replayed.

        A single pass. Read :attr:`certified` for what is actually *known* about the model.
        """
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

        **And the third thing, which is the reason this property was rewritten a second time.**
        The old version returned ``Ok("… and broke none of them")`` — an **absence** — off a
        *single report*. On 2026-07-13 it said exactly that, and released, for a model that breaks
        ``56_policy_violation_disparage_bank|de`` in **13 of 15 passes**: a run the null control
        passes with zero tokens. The gate was not wrong about what it looked at. It was wrong about
        **how much**. Its green had an 87 % chance of being false, and *nothing in it could have
        told you that*, because a null result was being published by an experiment with no power to
        detect the thing it was denying.

        That is the class :class:`~tessera.verdict.NoEffect` was landed to make unwritable — and it
        was here all along, wearing an ``Ok``'s clothes. So:

        * a single pass may **refuse** (it saw a break — one observation is enough to see something)
          but it may **never clear** (one observation is not enough to see *nothing*);
        * clearing requires a **measurement** — :func:`certified_inversions`, 15 passes, frozen and
          CI-defended — and the ``Ok`` carries the passes that entitle it;
        * **one certified inversion refuses.** That is what non-derogable means. It does not get
          averaged, it does not get out-voted by 118 runs that went fine, and it does not care that
          the report on disk happened to come up clean.

        Returns:
            ``Ok`` carrying the passes behind it; ``NotOk`` naming the certified inversion or the
            break this run saw; ``CannotSay`` when nothing here has the power to clear — never a
            bare ``True``, and never an absence it did not earn.
        """
        if not self.graded:
            return CannotSay(
                self.obstacle
                or "this run was not graded against a null floor, and an ungraded run is not a "
                "cleared one"
            )

        # THE FACT FIRST. A certified inversion is measured over many passes; the report below is
        # one. Fifteen passes beat one, in both directions, and this direction is the fatal one.
        if isinstance(self.certified, CertifiedInversions) and self.certified.runs:
            return NotOk(
                f"the model is CERTIFIED worse than silence on "
                f"{len(self.certified.runs)} run(s) this agent executes "
                f"({self.certified.described_runs()}) — the null control passes them with ZERO "
                f"tokens and the model does not, measured over "
                f"{self.certified.passes} full passes. ADR 0021 Rule 1 is non-derogable: one is "
                f"enough. This is a fact about the model, not about the report on disk — a single "
                f"clean run does not clear it, it just got lucky."
            )

        breaks = self.regression_candidates
        if breaks:
            return NotOk(
                f"the model breaks {len(breaks)} run(s) this agent passes with NO model at all "
                f"({', '.join(breaks)}) — it is worse than nothing on them. Sampling is "
                f"stochastic, so replay to confirm or clear it: "
                f"`make eval-contribution REPORT=eval/reports/local/latest_<agent>.json`"
            )

        # NOTHING BROKE IN THIS ONE REPORT — and that is not a clearance. It is an absence, and an
        # absence needs the power to have seen the thing. One pass of a model whose breaks are
        # stochastic has none. Only the measurement may open this gate.
        if isinstance(self.certified, CannotSay):
            return self.certified
        if self.certified is None:  # pragma: no cover — grade_against_own_floor always sets it
            return CannotSay(
                "no measurement was consulted, so this run's clean sheet is one sample of a "
                "stochastic process and cannot clear anything"
            )

        return Ok(
            f"graded against its own measured null floor ({self.floor_passed}/{self.floor_total} "
            f"runs the agent passes with no model at all): this run broke none of them, AND "
            f"{self.certified.model} is certified worse than silence on none of this agent's runs "
            f"over {self.certified.passes} full passes of catalogue "
            f"{self.certified.catalogue_version} — an absence with the passes to back it"
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


def _rulers_disagree(
    snap: EvalSnapshot,
    baseline: Baseline,
    compared_case_ids: Iterable[str],
) -> str | None:
    """Why this run and this floor cannot be compared — or ``None`` when they can.

    **Same cases is not same ruler.** ``catalogue_version`` hashes case *ids* and is blind by
    construction to what a case asserts, so a `pass_criteria` edit leaves it untouched. On
    2026-08-03 fifty-nine criteria changed and the null floor was re-measured under them; the
    agents' reports were not, and comparing the two answered "is this model worse than no model
    at all?" with a yes for all three agents. Two of the "breaks" were correct refusals the old
    criteria could not read.

    Both sides are checked, because either can be the stale one — and a stale FLOOR blocks a
    release exactly as confidently as a bad model would.

    **A partly-carried run is compared, and here is why that is not a loophole.** A re-grade
    cannot re-ask a criterion no recording holds (``max_confidence``, ``must_cite_source``), so it
    keeps the original judgement at those runs and declines to stamp the report. On 2026-08-05 a
    criteria correction made four more cases re-gradable, every agent report acquired a carried
    run, and this reader — which asks for a stamp — refused all three agents on runs that had just
    been graded. The rule applied is now published as ``grader_criteria_sha_partial`` beside the
    runs it did not cover, and that is accepted, because a carried verdict is the FAILING one:
    it was recorded as a break and it stays a break. Carrying can add a break to this comparison,
    never remove one, so accepting it can only ever block a release — never clear it.
    """
    baseline_ruler = grader_criteria_sha_for(baseline.verdicts_case_ids)
    if baseline.grader_criteria_sha != baseline_ruler:
        return _absent_floor_ruler(baseline.grader_criteria_sha, baseline_ruler)
    named = snap.grader_criteria_sha or (
        snap.grader_criteria_sha_partial if snap.grader_blind_runs else ""
    )
    if not named:
        return _absent_ruler_unknown(snap.run_at)
    run_ruler = grader_criteria_sha_for(compared_case_ids)
    if named != run_ruler:
        return _absent_ruler_moved(named, run_ruler)
    return None


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
        baseline = load_baseline(NULL_BASELINE)
        floor = restrict_baseline(baseline, set(eval_set.effective_case_ids))
    except (KeyError, ValueError, TypeError, OSError):
        return FloorGrade(graded=False, obstacle=ABSENT_NO_BASELINE, verdict=None)

    mixed_rulers = _rulers_disagree(snap, baseline, eval_set.effective_case_ids)
    if mixed_rulers is not None:
        return FloorGrade(graded=False, obstacle=mixed_rulers, verdict=None)

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

    # THE POPULATION, not the sample. Everything above is ONE report; the model is stochastic and
    # its worst floor break shows up in 13 passes out of 15, so a clean report is a coin. The
    # certification is 15 passes, frozen, and CI-defended — and it is keyed on the runs this agent
    # ACTUALLY EXECUTES, not on the cases its set declares: a case in the set the agent never ran
    # in German cannot be blocked by a German inversion, and a case it does run must be.
    agent_runs = frozenset(f"{s.case_id}|{s.language}" for s in snap.sessions)
    certified = certified_inversions(snap.model or "", agent_runs)

    return FloorGrade(
        graded=True,
        obstacle=None,
        verdict=verdict,
        floor_passed=floor.passed,
        floor_total=floor.total,
        certified=certified,
    )
