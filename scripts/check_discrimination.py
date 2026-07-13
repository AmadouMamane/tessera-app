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
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

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
)
from eval.ratchet import load_baseline

NULL_BASELINE = Path("eval/baselines/null-control.json")
SAMPLES = Path("eval/baselines/discrimination-samples.json")
CLASSIFICATION = Path("eval/baselines/discrimination.json")
RAW = Path(".eval-noise")

#: The catalogue's measured discriminating power — the number the whole exercise produces.
#: **Frozen, and it may only go UP.** Remove a case that separates a good model from a bad
#: one and this goes red; add a dead case and the catalogue version moves, which refuses
#: the classification until someone re-measures and looks at what the density did.
#:
#: Same motif as the ledger's read budget (``OWED_COUNT``): a debt, or an asset, that a
#: human has to argue with a number to change.
POWER_FLOOR_CASES = 0
POWER_FLOOR_RUNS = 0


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
        method = (
            f"Fisher exact, one-tailed, Holm-corrected over all {len(power.runs)} runs at "
            f"alpha={args.alpha}. Classes are DERIVED from the null floor and the stored "
            f"passes; no case declares its own power."
        )
        args.classification.write_text(dump_power(power, method=method), encoding="utf-8")
        sys.stdout.write(f"→ {args.classification}\n")
        sys.stdout.write(
            f"\nFREEZE THESE IN scripts/check_discrimination.py:\n"
            f"  POWER_FLOOR_CASES = {power.discriminating_cases}\n"
            f"  POWER_FLOOR_RUNS  = {power.discriminating_runs}\n"
        )
        return 0

    frozen = load_power(args.classification) if args.classification.exists() else None
    verdict = check_power(power, frozen, floor_cases=POWER_FLOOR_CASES, floor_runs=POWER_FLOOR_RUNS)
    sys.stdout.write(verdict.render() + "\n")
    if verdict.refusal is not None:
        return 3
    return 0 if verdict.ok else 1


if __name__ == "__main__":  # pragma: no cover  thin CLI shim
    raise SystemExit(main())
