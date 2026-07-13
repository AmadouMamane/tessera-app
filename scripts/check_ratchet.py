#!/usr/bin/env python
"""Check an eval report against its committed baseline (the ratchet).

Two modes, taken from the baseline's ``kind``:

* ``null_control`` — exact match against the modelless control. Any movement
  fails, including an improvement: refresh the baseline with ``--write`` and let
  the diff carry the evidence.
* ``model_run`` — monotone ratchet on a model replay: nothing may regress, the
  pass count may not drop, and the run must prove a model actually answered.

Usage:
    uv run python scripts/check_ratchet.py --report eval/reports/local/latest.json \\
        --baseline eval/baselines/null-control.json
    uv run python scripts/check_ratchet.py --report ... --baseline ... --write
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from eval.ratchet import (
    baseline_from_report,
    check_model_run,
    check_null_control,
    dump_baseline,
    load_baseline,
)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check an eval report against its baseline.")
    parser.add_argument("--report", type=Path, required=True, help="Runner report JSON.")
    parser.add_argument("--baseline", type=Path, required=True, help="Committed baseline JSON.")
    parser.add_argument(
        "--write",
        action="store_true",
        help="Overwrite the baseline from this report instead of checking against it.",
    )
    parser.add_argument(
        "--kind",
        choices=["null_control", "model_run"],
        help="Baseline kind (required with --write on a new baseline; otherwise read from it).",
    )
    parser.add_argument("--note", default="", help="Provenance note stored in the baseline.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point; the exit code is the ratchet verdict."""
    args = _parse_args(argv)

    # A MISSING REPORT IS A BLIND SPOT, AND A BLIND SPOT IS NOT A PASS — but it must also not be
    # a traceback. `make eval-null` runs the harness under a `-` (its exit code cannot distinguish
    # "52 cases need a model" from "the runner crashed"), then deletes the report directory so that
    # what lands here can only have come from THIS run. If nothing is here, the runner did not
    # produce it, and that is the fact worth printing — not a FileNotFoundError whose reader has to
    # reconstruct why.
    if not args.report.exists():
        sys.stderr.write(
            f"✗ no report at {args.report} — the runner did not produce one.\n"
            "  The ratchet grades an ARTEFACT, and there is no artefact. This is not a pass and it "
            "is not a regression: the run did not happen.\n"
            "  Look above this line for what the harness said before it died.\n"
        )
        return 1

    report = json.loads(args.report.read_text(encoding="utf-8"))

    if args.write:
        kind = args.kind
        if kind is None:
            if not args.baseline.exists():
                sys.stderr.write("--kind is required when creating a new baseline\n")
                return 2
            kind = load_baseline(args.baseline).kind
        baseline = baseline_from_report(report, kind=kind, note=args.note)
        args.baseline.parent.mkdir(parents=True, exist_ok=True)
        args.baseline.write_text(dump_baseline(baseline), encoding="utf-8")
        sys.stdout.write(
            f"baseline written → {args.baseline} "
            f"({baseline.passed}/{baseline.total} passing, kind={baseline.kind})\n"
        )
        return 0

    baseline = load_baseline(args.baseline)
    check = check_null_control if baseline.kind == "null_control" else check_model_run
    verdict = check(report, baseline)
    sys.stdout.write(verdict.render() + "\n")
    return 0 if verdict.ok else 1


if __name__ == "__main__":  # pragma: no cover  thin CLI shim
    raise SystemExit(main())
