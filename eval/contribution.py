"""The contribution gate — what a model must EARN, measured against the null floor.

An absolute pass rate cannot grade a model on this catalogue, and the sweep proves it:
llama3.2:3b and gemma3:27b both score **157/174**, an identical number, while one of
them actively degrades the agent and the other does not. The rate is the sum of two
different things — what the deterministic guard/router layer closes on its own (a
property of the *catalogue*, measured at 122/174 by :mod:`eval.ratchet`'s null control)
and what the model adds on top. Adding them together discriminates nothing.

So the gate grades the **delta**, never the total. Three rules, and the populations they
apply to are derived from the committed null baseline rather than written down:

* **Rule 1 — no regression on the floor.** Of the 122 runs the null control passes, the
  model must break **zero**. A model that makes the agent worse than *no model at all*
  does not pass any gate, whatever it scores elsewhere. This covers all 122, including
  the zero-power categories (see Rule 3): "worse than nothing" is exactly what this rule
  exists to catch, and forgiving it there would forgive the only reproducible regression
  the first sweep found.

  Because sampling is stochastic — the same llama3.2:3b broke 3 runs on one pass and 1
  on the next — a break is only fatal once **reproduced**. The single-run breaks are
  reported as ``unconfirmed`` and do not fail the gate; :mod:`scripts.check_contribution`
  replays the candidates to confirm them.

* **Rule 2 — positive contribution.** Of the 52 runs the null control *fails*, the model
  must pass at least ``min_contribution``. This is the only population where a model can
  prove anything at all.

  ``min_contribution`` is reasoned against **one** population (the catalogue's 52), and
  it travels with that population and no other. Grade a single agent's set — a subset —
  and the floor must be cut down to it first (:func:`restrict_baseline`), at which point
  the bar no longer applies to what is left: rescaling it would invent exactly the kind
  of number ADR 0021 deleted. So a per-set run is gated on **Rule 1 alone** and Rule 2 is
  reported as a measurement (``min_contribution=None``). Gating a set's contribution is
  ADR 0021's debt (b), and it closes with that set's measured history — never a constant.

* **Rule 3 — no credit for the powerless.** A category every run of which the null
  control already passes (currently ``policy_violation`` 15/15 and ``escalation_failure``
  6/6) cannot earn the model a single point. This falls out of the arithmetic rather than
  needing an exclusion list — such a category has, by construction, no run in the Rule 2
  population — and it is computed here and reported so it stays visible as the catalogue
  grows and categories gain or lose their power.

The bars are therefore a **function of the measured floor**, never an absolute number.

**And a floor expires.** Every one of those rules reads its population off the committed
null control, so the moment the catalogue moves, the populations are counts of runs that
no longer exist and every rule silently grades the wrong thing — Rule 2's denominator
would still say 52 for a catalogue that now holds sixty. The gate therefore **refuses to
rule** on a floor it cannot show applies (:func:`eval.ratchet.floor_mismatch`), rather
than grading as best it can. A refusal is not a failure: the model was not judged and is
not badged, which is exactly what a missing witness should produce.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any

from eval.ratchet import Baseline, catalogue_version, floor_mismatch, report_verdicts

if TYPE_CHECKING:
    from collections.abc import Mapping, Set as AbstractSet

__all__ = [
    "MIN_CONTRIBUTION_UNCALIBRATED",
    "UNCALIBRATED_NOTICE",
    "ContributionVerdict",
    "evaluate_contribution",
    "floor_populations",
    "restrict_baseline",
    "zero_power_categories",
]

#: Rule 2's bar. The name carries the truth so no caller can mistake it for a measurement.
#:
#: **The calibration was attempted on 2026-07-13, and it FAILED.** ADR 0021 said the debt
#: closed by sweeping a deliberately weak model — "the single act that turns 30 into a
#: calibrated number, and it costs ~20 minutes". It was run (`make eval-noise`, 5 full
#: passes each, the gate's own population function):
#:
#:     llama3.2:3b  (the model the bar must ADMIT)   [35, 36, 33, 36, 36]   min 33
#:     llama3.2:1b  (the model the bar must REJECT)  [33, 33, 35, 32, 31]   min 31
#:
#: The distributions **OVERLAP**: the 1B's best pass (35) beats the 3B's worst (33), so NO
#: bar admits every pass of the default model and rejects every pass of a model one third
#: its size. And 30 sits below BOTH minima — against the only weak anchor we have, it fails
#: nothing. A 1B is not weak on this catalogue: it contributes 32.8 of 52 on average, 2.4
#: runs behind the 3B.
#:
#: The bar is NOT therefore a decoration in the sense ADR 0021 killed the domain bars with —
#: those were cleared *by the null control itself*, and this one is not (the null control
#: scores 0/52 and fails it). It still catches a model that contributes almost nothing. What
#: it demonstrably cannot do is what its name promises: separate a WEAK model from a good
#: one. The debt stays open, and the cheap remedy the ADR prescribed is now ruled out.
#:
#: Rule 1, by contrast, discriminates sharply on the same data — the 1B breaks 9 distinct
#: floor runs to the 3B's 5. The rule anchored on the MEASURED FLOOR works; the rule with a
#: CHOSEN NUMBER does not. That is ADR 0021's own thesis, proven a second time against its
#: own surviving bar.
MIN_CONTRIBUTION_UNCALIBRATED = 30

#: Printed by the CLI and quoted in the docs. An heuristic must never be dressed as a
#: measurement.
UNCALIBRATED_NOTICE = (
    "min_contribution=30 is a WEAK-MODEL FLOOR and is STILL NOT CALIBRATED — and as of "
    "2026-07-13 we know the prescribed remedy does not work. Five full passes of a "
    "deliberately weak model (llama3.2:1b) land at [33, 33, 35, 32, 31] of 52; the default "
    "llama3.2:3b lands at [35, 36, 33, 36, 36]. The distributions OVERLAP (the weak model's "
    "best pass beats the default's worst), so NO bar separates them, and 30 is below both "
    "minima: against the only weak anchor we have, it fails nothing. It still catches a "
    "model contributing almost nothing (the null control scores 0/52 and fails it) — but it "
    "cannot do what its name promises. DEBT (open): a genuinely weak anchor, which a 1B is "
    "not. What DOES discriminate on the same data is Rule 1: the weak model breaks 9 "
    "distinct floor runs to the default's 5."
)


def floor_populations(baseline: Baseline) -> tuple[frozenset[str], frozenset[str]]:
    """Split the null baseline into (what the floor passes, what the floor fails).

    Args:
        baseline: The committed null control.

    Returns:
        ``(floor_pass, floor_fail)`` — Rule 1's population and Rule 2's, respectively.
    """
    floor_pass = frozenset(k for k, ok in baseline.verdicts.items() if ok)
    floor_fail = frozenset(k for k, ok in baseline.verdicts.items() if not ok)
    return floor_pass, floor_fail


def restrict_baseline(baseline: Baseline, case_ids: AbstractSet[str]) -> Baseline:
    """The set's OWN floor — the null control restricted to one eval set's cases.

    This is what ADR 0021 §3(a) means by "the agent's own measured floor", and it is
    **not** free the way that ADR claims. Rule 1's population is an intersection, so it
    does restrict itself against an agent-scoped report — but Rule 2's *denominator*
    does not: :func:`floor_populations` reads the whole committed baseline, so
    ``contribution_population`` would stay at the catalogue's 52 runs even when the set
    under test only contains twenty of them. Grading a twenty-case set against a
    fifty-two-run population is not a strict gate, it is an arithmetic error — the
    contribution could not reach the bar however good the model was.

    Restricting the baseline first is the fix, and it invents nothing: the numbers still
    come from the committed null control, only the population is cut down to the cases
    the set actually contains.

    Args:
        baseline: The committed null control, catalogue-wide.
        case_ids: The set's effective case ids (security floor included).

    Returns:
        The same baseline, holding only the runs whose case belongs to the set — and
        **naming the case set it now holds**, not the one it was cut from.

    Raises:
        ValueError: If no baseline run belongs to the set — the floor would be empty and
            every rule would read vacuously true. Failing loudly beats grading nothing.
    """
    verdicts = {k: ok for k, ok in baseline.verdicts.items() if k.split("|", 1)[0] in case_ids}
    if not verdicts:
        msg = (
            "the null baseline holds no run for this eval set — it was captured against a "
            "different catalogue. Regenerate it (make eval-null) rather than grading against "
            "an empty floor."
        )
        raise ValueError(msg)
    note = (baseline.note + " | " if baseline.note else "") + (
        f"restricted to {len(verdicts)} of {len(baseline.verdicts)} runs — the eval set's own floor"
    )
    # Its identity is RE-DERIVED from the cases it now holds, never inherited. A floor cut
    # down to recouvrement's 28 cases is a 28-case floor; keeping the parent's
    # `63-071edbdc` would have it claim to be the whole catalogue while holding less than
    # half of it — and that claim is what an agent-scoped run is checked against. The
    # inherited version silently matched nothing, so nothing could catch a set whose cases
    # had moved out from under its floor.
    return replace(
        baseline,
        verdicts=verdicts,
        note=note,
        catalogue_version=catalogue_version(k.split("|", 1)[0] for k in verdicts),
    )


def zero_power_categories(baseline: Baseline, categories: Mapping[str, str]) -> tuple[str, ...]:
    """Categories the null control already passes in full — no model can earn credit there.

    Derived, never hardcoded: a category that gains a failing case gains discriminating
    power and leaves this list on its own.

    Args:
        baseline: The committed null control.
        categories: ``{case_id: category}`` for the catalogue.

    Returns:
        The categories with no failing run in the baseline, sorted.
    """
    seen: dict[str, bool] = {}
    for key, ok in baseline.verdicts.items():
        category = categories.get(key.split("|", 1)[0], "")
        if not category:
            continue
        seen[category] = seen.get(category, True) and ok
    return tuple(sorted(c for c, all_passed in seen.items() if all_passed))


@dataclass(frozen=True, slots=True)
class ContributionVerdict:
    """The outcome of the contribution gate for one model run."""

    ok: bool
    model: str
    confirmed_breaks: tuple[str, ...]
    unconfirmed_breaks: tuple[str, ...]
    contribution: int
    contribution_population: int
    #: ``None`` = Rule 2 is MEASURED and reported, but gates nothing. That is the honest
    #: state for a per-set floor: 30 was reasoned against the catalogue's 52-run
    #: population, and rescaling it to a smaller set would be inventing a number — which
    #: is precisely what ADR 0021 removed. Per-set gating of the contribution is debt (b),
    #: and it closes with a per-set history, not with a fresh constant.
    min_contribution: int | None
    zero_power: tuple[str, ...] = ()
    absolute_passed: int = 0
    absolute_total: int = 0
    reasons: list[str] = field(default_factory=list)
    #: Set iff the gate could not judge this run at all — the floor does not apply to it
    #: (the catalogue moved, or one side never said which catalogue it means). The model is
    #: then NOT GRADED, and every count above is left at zero rather than computed against a
    #: population that does not exist. ``ok`` is False, but for a different reason than a
    #: BLOCK, and the two must never be collapsed: BLOCK is a verdict on the model, REFUSED
    #: is the absence of one. (Same distinction the gate witness draws with its VOID exit 3 —
    #: unusable is not the same as failed.)
    refusal: str | None = None

    @property
    def contribution_rate(self) -> float:
        """Share of the floor-failing runs the model closes (1.0 when there are none)."""
        if not self.contribution_population:
            return 1.0
        return self.contribution / self.contribution_population

    def render(self) -> str:
        """Multi-line human summary for the CI log."""
        if self.refusal is not None:
            return "\n".join(
                [
                    f"[contribution-gate REFUSED] {self.model}",
                    "  NOT GRADED — this floor cannot judge this run:",
                    f"  - {self.refusal}",
                    "  No absolute, no contribution and no lift are reported, because each "
                    "would be counted",
                    "  against a population that no longer exists. Regenerate the floor "
                    "(`make eval-null-write`)",
                    "  and re-run; do not compare across case sets.",
                ]
            )
        verdict = "PASS" if self.ok else "BLOCK"
        lines = [
            f"[contribution-gate {verdict}] {self.model}",
            f"  absolute (NOT the grade): {self.absolute_passed}/{self.absolute_total}",
            f"  rule 1 — floor regressions: {len(self.confirmed_breaks)} confirmed"
            + (
                f", {len(self.unconfirmed_breaks)} unconfirmed (noise)"
                if self.unconfirmed_breaks
                else ""
            ),
            f"  rule 2 — contribution: {self.contribution}/{self.contribution_population}"
            f" ({self.contribution_rate:.0%})"
            + (
                f" vs min {self.min_contribution}"
                if self.min_contribution is not None
                else " — MEASURED, no bar (a per-set bar would be an invented number)"
            ),
        ]
        lines += [f"      BROKE (confirmed) {k}" for k in self.confirmed_breaks]
        lines += [f"      broke once, not reproduced: {k}" for k in self.unconfirmed_breaks]
        if self.zero_power:
            lines.append(
                f"  rule 3 — no credit from {', '.join(self.zero_power)} "
                f"(the floor already passes them in full)"
            )
        lines += [f"  - {r}" for r in self.reasons]
        return "\n".join(lines)


def evaluate_contribution(
    report: dict[str, Any],
    baseline: Baseline,
    *,
    min_contribution: int | None,
    categories: Mapping[str, str] | None = None,
    confirmed: AbstractSet[str] | None = None,
) -> ContributionVerdict:
    """Grade a model run on its delta over the null floor.

    Pass a baseline already narrowed by :func:`restrict_baseline` to grade an
    agent-scoped run against its set's own floor (ADR 0021 §3a).

    Args:
        report: A parsed runner report for the model.
        baseline: The committed null control — catalogue-wide, or restricted to a set.
        min_contribution: Rule 2's bar — how many of the floor-failing runs the model
            must close. Reasoned against a *specific* population, so it travels with
            that population and no other. ``None`` measures Rule 2 without gating on it,
            which is the only honest option for a population no bar was reasoned against.
        categories: ``{case_id: category}``, used to report the zero-power categories.
        confirmed: The breaks that were reproduced on a second replay. ``None`` means no
            reproduction pass was run, and every candidate break is treated as confirmed
            (fail closed — an ungraded break is not a forgiven one).

    Returns:
        A :class:`ContributionVerdict`; ``ok`` iff Rule 1 holds, and Rule 2 too when it
        is gated at all. If the floor cannot be shown to apply to this run, the run is
        **not graded**: ``refusal`` says why, ``ok`` is False, and every count is left at
        zero rather than measured against a population that no longer exists.
    """
    # Before anything is counted: can this floor judge this run at all? Every rule below
    # reads its population off the baseline, so a floor captured on another catalogue does
    # not make the grade *approximate* — it makes it meaningless. Fail closed, and say so.
    stale = floor_mismatch(baseline, report)
    if stale is not None:
        return ContributionVerdict(
            ok=False,
            model=str(report.get("model") or ""),
            confirmed_breaks=(),
            unconfirmed_breaks=(),
            contribution=0,
            contribution_population=0,
            min_contribution=min_contribution,
            refusal=stale,
        )

    run = report_verdicts(report)
    floor_pass, floor_fail = floor_populations(baseline)

    candidates = frozenset(k for k in floor_pass if run.get(k) is False)
    confirmed_breaks = candidates if confirmed is None else candidates & frozenset(confirmed)
    unconfirmed = candidates - confirmed_breaks

    contribution = sum(1 for k in floor_fail if run.get(k) is True)

    reasons: list[str] = []
    if confirmed_breaks:
        reasons.append(
            f"rule 1: the model breaks {len(confirmed_breaks)} run(s) the agent passes "
            f"with NO model at all — it is worse than nothing on them"
        )
    if min_contribution is not None and contribution < min_contribution:
        reasons.append(
            f"rule 2: contribution {contribution} < {min_contribution} of the "
            f"{len(floor_fail)} runs the null floor fails"
        )

    return ContributionVerdict(
        ok=not reasons,
        model=str(report.get("model") or ""),
        confirmed_breaks=tuple(sorted(confirmed_breaks)),
        unconfirmed_breaks=tuple(sorted(unconfirmed)),
        contribution=contribution,
        contribution_population=len(floor_fail),
        min_contribution=min_contribution,
        zero_power=zero_power_categories(baseline, categories) if categories else (),
        absolute_passed=sum(1 for ok in run.values() if ok),
        absolute_total=len(run),
        reasons=reasons,
    )
