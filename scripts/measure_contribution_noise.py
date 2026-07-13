#!/usr/bin/env python
"""Measure what Rule 2's bar has to clear: sampling noise, and a weak model's floor.

``eval.contribution.MIN_CONTRIBUTION_UNCALIBRATED`` is 30, and its name says why it is
not a measurement: it was *reasoned* — three strong models landed at 36/35/36 of the 52
runs the null control fails, and 30 left "5-6 cases of margin". Two quantities were
guessed in that sentence and neither had ever been measured:

* **The noise.** The T2 sampling temperature is 0.2 with no seed, so the same model does
  not score the same twice. "5-6 cases of margin" assumed a spread nobody had counted.
  One pass per model tells you nothing about a distribution; this runs ``--passes`` of
  them and reports the real spread.
* **The weak end.** A bar exists to FAIL something. No weak model had ever been run
  against this catalogue, so the bar had no lower anchor at all — the only low point held
  was the null control at 0/52, which bounds nothing useful from above. This replays a
  deliberately weak model (``llama3.2:1b``) and reads its contribution off the same code
  path the gate uses.

A bar is calibrated iff the two distributions **separate**: it must sit above every pass
of the weak model and below every pass of the model it is meant to admit. If they
overlap, no bar separates them and this script says so rather than inventing one —
picking a number inside the overlap would be exactly the invented threshold ADR 0021
deleted.

The contribution is computed by :func:`eval.contribution.floor_populations`, the gate's
own function, so what is measured here is what the gate will read — not a reimplementation
that could drift from it.

Reports land OUTSIDE ``eval/reports/``: the runner drops a sibling ``latest.json`` next to
``--report``, so writing a calibration pass there would republish it as the project's
latest eval result (the trap ``make eval-null`` documents).

Usage:
    uv run python scripts/measure_contribution_noise.py \\
        --model llama3.2:3b --passes 5
    uv run python scripts/measure_contribution_noise.py \\
        --model llama3.2:1b --passes 5 --label weak
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from eval.contribution import floor_populations
from eval.ratchet import load_baseline, model_spoke, report_verdicts

NULL_BASELINE = Path("eval/baselines/null-control.json")
#: Gitignored, like `.eval-control/`. A calibration pass is not a published result.
DEFAULT_OUT = Path(".eval-noise")


def _slug(model: str) -> str:
    return model.replace(":", "-").replace("/", "-")


def _run_pass(model: str, report_path: Path) -> dict[str, Any]:
    """Replay the full catalogue once, in its own process.

    Raises:
        RuntimeError: If the runner produced no report, or if no model answered — a
            modelless run scores the deterministic layer alone and would be recorded here
            as a contribution of zero, which would silently drag the measured floor down.
    """
    proc = subprocess.run(
        [sys.executable, "scripts/run_eval.py", "--model", model, "--report", str(report_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if not report_path.exists():
        sys.stderr.write(proc.stdout[-2000:] + proc.stderr[-2000:])
        msg = f"{model}: the runner produced no report (exit {proc.returncode})"
        raise RuntimeError(msg)
    report: dict[str, Any] = json.loads(report_path.read_text(encoding="utf-8"))
    if not model_spoke(report):
        msg = (
            f"{model}: 0 output tokens — no model answered. A modelless pass would be "
            f"recorded as a contribution of 0 and would corrupt the calibration. "
            f"Is `ollama serve` up, and is `ollama pull {model}` done?"
        )
        raise RuntimeError(msg)
    return report


def main(argv: list[str] | None = None) -> int:
    """Run N passes and report the distribution of the contribution."""
    parser = argparse.ArgumentParser(description="Measure Rule 2's sampling noise.")
    parser.add_argument("--model", required=True)
    parser.add_argument("--passes", type=int, default=5)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--baseline", type=Path, default=NULL_BASELINE)
    parser.add_argument(
        "--label",
        default="",
        help="Free-form tag for the artefact (e.g. 'weak') — provenance, not behaviour.",
    )
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    baseline = load_baseline(args.baseline)
    floor_pass, floor_fail = floor_populations(baseline)

    passes: list[dict[str, Any]] = []
    for i in range(1, args.passes + 1):
        report_path = args.out / f"{_slug(args.model)}_pass{i}.json"
        sys.stdout.write(f"=== {args.model} — pass {i}/{args.passes} ===\n")
        sys.stdout.flush()
        started = time.monotonic()
        report = _run_pass(args.model, report_path)
        elapsed = time.monotonic() - started

        run = report_verdicts(report)
        # The gate's own populations, read off the committed floor — not recomputed here.
        contribution = sum(1 for k in floor_fail if run.get(k) is True)
        breaks = sorted(k for k in floor_pass if run.get(k) is False)
        passes.append(
            {
                "pass": i,
                "catalogue_version": str(report.get("catalogue_version") or ""),
                "absolute_passed": sum(1 for ok in run.values() if ok),
                "absolute_total": len(run),
                "contribution": contribution,
                "contribution_population": len(floor_fail),
                "rule1_candidate_breaks": breaks,
                "elapsed_min": round(elapsed / 60, 1),
            }
        )
        sys.stdout.write(
            f"  contribution {contribution}/{len(floor_fail)}, "
            f"{len(breaks)} candidate break(s), {elapsed / 60:.1f} min\n"
        )
        sys.stdout.flush()

    values = [p["contribution"] for p in passes]
    versions = {p["catalogue_version"] for p in passes}
    summary = {
        "model": args.model,
        "label": args.label,
        "passes": args.passes,
        "catalogue_version": versions.pop() if len(versions) == 1 else sorted(versions),
        "contribution_population": len(floor_fail),
        "contribution": {
            "values": values,
            "min": min(values),
            "max": max(values),
            "mean": round(statistics.mean(values), 2),
            "stdev": round(statistics.stdev(values), 2) if len(values) > 1 else 0.0,
            "spread": max(values) - min(values),
        },
        # A break that appears in SOME passes and not others is noise; one that appears in
        # every pass is a reproduced regression. This is the same distinction
        # check_contribution.py makes with its replay, measured over the whole run instead.
        "rule1_breaks_by_pass": [p["rule1_candidate_breaks"] for p in passes],
        "rule1_breaks_in_every_pass": sorted(
            set.intersection(*(set(p["rule1_candidate_breaks"]) for p in passes))
            if passes
            else set()
        ),
        "runs": passes,
    }

    artefact = args.out / f"noise_{_slug(args.model)}.json"
    artefact.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    c = summary["contribution"]
    assert isinstance(c, dict)
    sys.stdout.write(
        f"\n{args.model} over {args.passes} passes — contribution of {len(floor_fail)}:\n"
        f"  values {values}\n"
        f"  min {c['min']}  max {c['max']}  mean {c['mean']}  stdev {c['stdev']}  "
        f"spread {c['spread']}\n"
        f"  reproduced breaks (every pass): {summary['rule1_breaks_in_every_pass'] or 'none'}\n"
        f"\n→ {artefact}\n"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover  thin CLI shim
    raise SystemExit(main())
