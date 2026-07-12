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

* **Rule 3 — no credit for the powerless.** A category every run of which the null
  control already passes (currently ``policy_violation`` 15/15 and ``escalation_failure``
  6/6) cannot earn the model a single point. This falls out of the arithmetic rather than
  needing an exclusion list — such a category has, by construction, no run in the Rule 2
  population — and it is computed here and reported so it stays visible as the catalogue
  grows and categories gain or lose their power.

The bars are therefore a **function of the measured floor**, never an absolute number.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from eval.ratchet import report_verdicts

if TYPE_CHECKING:
    from collections.abc import Mapping, Set as AbstractSet

    from eval.ratchet import Baseline

__all__ = [
    "MIN_CONTRIBUTION_UNCALIBRATED",
    "UNCALIBRATED_NOTICE",
    "ContributionVerdict",
    "evaluate_contribution",
    "floor_populations",
    "zero_power_categories",
]

#: Rule 2's bar. The name carries the truth so no caller can mistake it for a measurement.
#:
#: The three models of the 2026-07-12 sweep land at 36 / 35 / 36 out of 52. 30 sits 5-6
#: cases below the lowest of them — enough margin to absorb the sampling noise we measured
#: (several cases flip run to run), while still failing a model that contributes materially
#: less. That is a *reasoned* choice, not a *calibrated* one, and the difference matters:
#: we have never observed a weak model on this catalogue. The only low point we hold is the
#: null control at 0/52, which bounds nothing useful from above.
MIN_CONTRIBUTION_UNCALIBRATED = 30

#: Printed by the CLI and quoted in the docs. An heuristic must never be dressed as a
#: measurement.
UNCALIBRATED_NOTICE = (
    "min_contribution=30 is a WEAK-MODEL FLOOR and is NOT CALIBRATED: it was chosen to "
    "leave 5-6 cases of margin above the measured sampling noise, NOT measured against a "
    "population of weak models — none has ever been observed on this catalogue (the only "
    "low point held is the null control at 0/52). DEBT: sweep a deliberately weak model "
    "(a 1B, or a degraded config) and see where it lands; that is the single act that "
    "turns 30 into a calibrated number, and it costs ~20 minutes."
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
    min_contribution: int
    zero_power: tuple[str, ...] = ()
    absolute_passed: int = 0
    absolute_total: int = 0
    reasons: list[str] = field(default_factory=list)

    @property
    def contribution_rate(self) -> float:
        """Share of the floor-failing runs the model closes (1.0 when there are none)."""
        if not self.contribution_population:
            return 1.0
        return self.contribution / self.contribution_population

    def render(self) -> str:
        """Multi-line human summary for the CI log."""
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
            f" ({self.contribution_rate:.0%}) vs min {self.min_contribution}",
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
    min_contribution: int,
    categories: Mapping[str, str] | None = None,
    confirmed: AbstractSet[str] | None = None,
) -> ContributionVerdict:
    """Grade a model run on its delta over the null floor.

    Args:
        report: A parsed runner report for the model.
        baseline: The committed null control.
        min_contribution: Rule 2's bar — how many of the floor-failing runs the model
            must close. Calibrated on a sweep, never invented.
        categories: ``{case_id: category}``, used to report the zero-power categories.
        confirmed: The breaks that were reproduced on a second replay. ``None`` means no
            reproduction pass was run, and every candidate break is treated as confirmed
            (fail closed — an ungraded break is not a forgiven one).

    Returns:
        A :class:`ContributionVerdict`; ``ok`` iff Rule 1 and Rule 2 both hold.
    """
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
    if contribution < min_contribution:
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
