#!/usr/bin/env python
"""Grade a model on its contribution over the null floor (the eval gate).

The absolute pass rate is not the grade and cannot be: llama3.2:3b and gemma3:27b both
score 157/174, yet one of them breaks a case the agent passes with no model at all. This
gate reads the delta instead (see :mod:`eval.contribution`):

* Rule 1 — the model must break **zero** of the 122 runs the null control passes. A break
  is only fatal once **reproduced**: sampling is stochastic (the same llama3.2:3b broke 3
  runs on one pass, 1 on the next), so every candidate break is replayed before it counts.
* Rule 2 — the model must close at least ``--min-contribution`` of the 52 runs the null
  control fails. That is the only population where a model can prove anything.

Usage:
    uv run python scripts/check_contribution.py \\
        --report eval/reports/sweep/gemma3-27b.json --min-contribution 30
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from eval.contribution import evaluate_contribution, floor_populations
from eval.ratchet import load_baseline, model_spoke, report_verdicts
from eval.sets import catalogue_categories

NULL_BASELINE = Path("eval/baselines/null-control.json")


def _replay(case_id: str, language: str, model: str, tmp: Path) -> bool | None:
    """Replay one (case, language) against the model. True/False = passed; None = no verdict."""
    report = tmp / f"{case_id}_{language}.json"
    subprocess.run(
        [
            sys.executable,
            "scripts/run_eval.py",
            "--case",
            case_id,
            "--lang",
            language,
            "--model",
            model,
            "--report",
            str(report),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if not report.exists():
        return None
    payload = json.loads(report.read_text(encoding="utf-8"))
    if not model_spoke(payload):
        # A replay in which no model answered proves nothing either way; refuse to let it
        # silently "confirm" or "clear" a break.
        return None
    verdicts = report_verdicts(payload)
    return verdicts.get(f"{case_id}|{language}")


def _confirm_breaks(candidates: list[str], model: str) -> tuple[set[str], list[str]]:
    """Replay each candidate break; return (confirmed, inconclusive)."""
    confirmed: set[str] = set()
    inconclusive: list[str] = []
    with tempfile.TemporaryDirectory(prefix="tessera-reproduce-") as raw:
        tmp = Path(raw)
        for key in candidates:
            case_id, language = key.split("|", 1)
            sys.stdout.write(f"  replaying {key} … ")
            sys.stdout.flush()
            again = _replay(case_id, language, model, tmp)
            if again is None:
                inconclusive.append(key)
                sys.stdout.write("no verdict (no model answered)\n")
            elif again is False:
                confirmed.add(key)
                sys.stdout.write("FAILED AGAIN — confirmed regression\n")
            else:
                sys.stdout.write("passed this time — sampling noise, not counted\n")
    return confirmed, inconclusive


def main(argv: list[str] | None = None) -> int:
    """Exit code is the gate verdict."""
    parser = argparse.ArgumentParser(description="Grade a model on its contribution.")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, default=NULL_BASELINE)
    parser.add_argument(
        "--min-contribution",
        type=int,
        required=True,
        help="Rule 2's bar: how many of the floor-failing runs the model must close.",
    )
    parser.add_argument(
        "--no-reproduce",
        action="store_true",
        help="Skip the replay pass. Every candidate break then counts (fails closed).",
    )
    args = parser.parse_args(argv)

    report = json.loads(args.report.read_text(encoding="utf-8"))
    if not model_spoke(report):
        sys.stderr.write(
            f"no model spoke in {args.report}: 0 output tokens. A modelless run has no "
            f"contribution to grade.\n"
        )
        return 1

    baseline = load_baseline(args.baseline)
    model = str(report.get("model") or "")
    run = report_verdicts(report)
    floor_pass, _ = floor_populations(baseline)
    candidates = sorted(k for k in floor_pass if run.get(k) is False)

    confirmed: set[str] | None = None
    if candidates and not args.no_reproduce:
        sys.stdout.write(
            f"{len(candidates)} candidate floor regression(s) — replaying to separate a real "
            f"regression from sampling noise:\n"
        )
        confirmed, inconclusive = _confirm_breaks(candidates, model)
        if inconclusive:
            sys.stderr.write(
                f"inconclusive replays (no model answered): {', '.join(inconclusive)}\n"
            )
            return 2

    verdict = evaluate_contribution(
        report,
        baseline,
        min_contribution=args.min_contribution,
        categories=catalogue_categories(),
        confirmed=confirmed,
    )
    sys.stdout.write(verdict.render() + "\n")
    return 0 if verdict.ok else 1


if __name__ == "__main__":  # pragma: no cover  thin CLI shim
    raise SystemExit(main())
