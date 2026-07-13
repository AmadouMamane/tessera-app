#!/usr/bin/env python
"""Measure what the catalogue measures — and ratchet the answer.

Two modes, and the difference between them is the whole point:

``--write`` **re-measures.** It reads the raw passes out of the gitignored scratch dir
(``.eval-noise/``), reduces them to the verdict matrix the classifier actually consumes,
hashes each one so the matrix can be traced back to the run it came from, and commits both
the evidence and the classification derived from it. This is the expensive path: it needs
the passes, which cost a GPU-hour to produce.

Default mode **checks.** It re-derives the classification from the *committed* evidence and
asserts three things: the classification has not drifted, the catalogue has not moved out
from under it, and the number of cases that measure the model has not fallen. It needs no
model, no GPU and no services, so CI runs it on every push.

Exit codes — a refusal is not a failure (ADR 0026):

* ``0`` the catalogue's power holds.
* ``1`` BLOCK — the power fell, or the classification drifted.
* ``2`` the evidence is missing or malformed.
* ``3`` REFUSED — the catalogue moved, so the frozen classification describes cases that no
  longer exist. Nothing was judged. Unusable is not the same as failed.

The mapping from the ratchet's :class:`~tessera.verdict.Verdict` to those numbers is written out
below, exhaustively, rather than delegated to :func:`tessera.verdict.exit_code`: this CLI draws a
distinction that the general type deliberately does not (``2`` for *missing evidence* against ``3``
for *a moved catalogue*), and a witness that quietly reused someone else's exit code would be
answering a question it was not asked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, assert_never

from eval.discrimination import (
    ALPHA,
    PassProvenance,
    Sample,
    check_power,
    classify,
    dump_power,
    dump_samples,
    load_power,
    load_samples,
    minimum_viable_samples,
)
from eval.ratchet import load_baseline
from tessera.verdict import CannotSay, NoEffect, NotOk, Ok, Power, Verdict, render

NULL_BASELINE = Path("eval/baselines/null-control.json")
SAMPLES = Path("eval/baselines/discrimination-samples.json")
CLASSIFICATION = Path("eval/baselines/discrimination.json")
RAW = Path(".eval-noise")

#: The catalogue's measured discriminating power — the number the whole exercise produces.
#: **Frozen, and it may only go UP.** Remove a case that separates a good model from a bad one and
#: this goes red; add a dead case and the catalogue version moves, which refuses the classification
#: until someone re-measures and looks at what the density did.
#:
#: Same motif as the ledger's read budget (``OWED_COUNT``): a debt — here an asset — that a human
#: has to argue with a number to change.
#:
#: **These are Holm-certified**, deliberately. The diagnosis reads Benjamini-Hochberg (see
#: ``eval.discrimination``), which is the more generous instrument and the right one for deciding
#: what to *keep*. A frozen number that CI defends is a different job: it must never count a
#: discriminator that isn't one, so it pays the family-wise price. On the measurement of
#: 2026-07-13 the two sets are identical (the correction gap is empty) — but they are computed
#: separately, and the day they come apart, this number stays the conservative one.
#:
#: Measured 2026-07-13 on catalogue ``63-071edbdc``, llama3.2:3b (n=15) against llama3.2:1b
#: (n=15), 30 full-catalogue passes, ~4 GPU-hours. 6 runs over 5 cases: 3 Holm-certified
#: discriminators, 2 reproduced inversions, 1 certified reversal.
POWER_FLOOR_CASES = 5
POWER_FLOOR_RUNS = 6


def _slug(model: str) -> str:
    return model.replace(":", "-").replace("/", "-")


def _collect(model: str, raw: Path) -> tuple[list[dict[str, Any]], list[PassProvenance]]:
    """Load every raw pass of a model, in pass order, with its provenance."""
    paths = sorted(
        raw.glob(f"{_slug(model)}_pass*.json"), key=lambda p: int(p.stem.split("pass")[-1])
    )
    reports: list[dict[str, Any]] = []
    provenance: list[PassProvenance] = []
    for path in paths:
        blob = path.read_bytes()
        report = json.loads(blob)
        cost = report.get("cost") or {}
        reports.append(report)
        provenance.append(
            PassProvenance(
                model=model,
                catalogue_version=str(report.get("catalogue_version") or ""),
                output_tokens=int(cost.get("output_tokens", 0) or 0),
                sha256=hashlib.sha256(blob).hexdigest(),
                source=path.name,
            )
        )
    return reports, provenance


def main() -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="re-measure from the raw passes in .eval-noise/ and commit the evidence",
    )
    parser.add_argument("--strong", default="llama3.2:3b", help="the model the gate must ADMIT")
    parser.add_argument("--weak", default="llama3.2:1b", help="the model the gate must REJECT")
    parser.add_argument("--raw", type=Path, default=RAW)
    parser.add_argument("--samples", type=Path, default=SAMPLES)
    parser.add_argument("--classification", type=Path, default=CLASSIFICATION)
    parser.add_argument("--baseline", type=Path, default=NULL_BASELINE)
    parser.add_argument("--alpha", type=float, default=ALPHA)
    args = parser.parse_args()

    if not args.baseline.exists():
        sys.stderr.write(f"no null floor at {args.baseline} — run `make eval-null-write`\n")
        return 2
    baseline = load_baseline(args.baseline)

    if args.write:
        strong_reports, strong_prov = _collect(args.strong, args.raw)
        weak_reports, weak_prov = _collect(args.weak, args.raw)
        if not strong_reports or not weak_reports:
            sys.stderr.write(
                f"no raw passes under {args.raw}/ for {args.strong} and {args.weak}. "
                f"Produce them first: make eval-noise MODEL={args.strong} PASSES=15\n"
            )
            return 2
        strong = Sample.from_reports(args.strong, strong_reports)
        weak = Sample.from_reports(args.weak, weak_reports)
        keys = sorted(baseline.verdicts)
        note = (
            f"{strong.n} + {weak.n} full-catalogue passes, T2 sampling at temperature 0.2 "
            f"with no seed. The verdict matrix is what eval.ratchet.report_verdicts reduces "
            f"each raw report to — the classifier consumes nothing else. Each pass carries "
            f"the SHA-256 of the raw report it came from and the tokens it generated: the "
            f"witness that a model spoke is tokens, never the report's `model` field."
        )
        args.samples.write_text(
            dump_samples(keys, strong, weak, strong_prov, weak_prov, note=note), encoding="utf-8"
        )
        sys.stdout.write(f"→ {args.samples}  ({strong.n} + {weak.n} passes)\n")
    else:
        if not args.samples.exists():
            sys.stderr.write(
                f"no committed evidence at {args.samples} — re-measure with "
                f"`make eval-power-write` (it needs the raw passes)\n"
            )
            return 2
        keys, strong, weak = load_samples(args.samples)

    power = classify(baseline, strong, weak, alpha=args.alpha)
    sys.stdout.write(power.render() + "\n")

    if args.write:
        viable = minimum_viable_samples(len(power.runs), alpha=args.alpha)
        method = (
            f"Fisher exact, one-tailed, corrected TWICE over all {len(power.runs)} runs as one "
            f"family at alpha={args.alpha}: Holm (family-wise error rate) certifies the number the "
            f"ratchet freezes, Benjamini-Hochberg (false discovery rate) feeds the diagnosis, and "
            f"the gap between the two sets is published. Classes are DERIVED from the null floor "
            f"and the stored passes; no case declares its own power. The minimum viable arm for "
            f"this family is n={viable} — below it no observation the experiment can make would be "
            f"certified, and its 'no effect' would be a property of the design, not of the world."
        )
        args.classification.write_text(dump_power(power, method=method), encoding="utf-8")
        sys.stdout.write(f"→ {args.classification}\n")
        if isinstance(power.power, Power):
            sys.stdout.write(
                f"\nWHAT THIS DESIGN COULD SEE: {power.power}\n"
                f"  Anything smaller is CANNOT SAY — never 'dead', never 'no effect'.\n"
            )
        sys.stdout.write(
            f"\nFREEZE THESE IN scripts/check_discrimination.py:\n"
            f"  POWER_FLOOR_CASES = {power.discriminating_cases}\n"
            f"  POWER_FLOOR_RUNS  = {power.discriminating_runs}\n"
        )
        return 0

    frozen = load_power(args.classification) if args.classification.exists() else None
    verdict = check_power(power, frozen, floor_cases=POWER_FLOOR_CASES, floor_runs=POWER_FLOOR_RUNS)
    sys.stdout.write(render(verdict) + "\n")
    return _exit_code(verdict)


def _exit_code(verdict: Verdict) -> int:
    """This CLI's contract, derived from the verdict — exhaustively, so mypy proves nothing is lost.

    ``tessera.verdict.exit_code`` collapses every non-``Ok`` to ``2``; this script promises callers
    a finer alphabet (``1`` blocked, ``2`` no evidence, ``3`` refused), so it does the mapping in
    the open instead of borrowing one that answers a different question.
    """
    match verdict:
        case Ok():
            return 0
        case NotOk():
            return 1
        case CannotSay():
            # The catalogue moved. Nothing was judged — and *unusable is not the same as failed*
            # (ADR 0026), which is why this is not the red 1.
            return 3
        case NoEffect():
            # A ratchet has no null result to report: it either holds, falls, or cannot look. If one
            # ever arrives here, something upstream built the wrong verdict — and it must not be
            # green.
            return 1
    assert_never(verdict)  # pragma: no cover — exhaustive; the line exists so mypy proves it is


if __name__ == "__main__":  # pragma: no cover  thin CLI shim
    raise SystemExit(main())
