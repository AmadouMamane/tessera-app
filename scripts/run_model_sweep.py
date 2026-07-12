#!/usr/bin/env python
"""Replay the whole catalogue against several models, and score them against the null control.

This is the run that answers "what does the model actually buy us?" — a question the
raw pass rate cannot answer, because 122 of the catalogue's 174 (case, language) runs
are closed by the deterministic guard/router layer with no LLM at all
(`eval/baselines/null-control.json`). Every number here is therefore reported as a
**delta over that floor**, not as a bare percentage.

Each model runs in its own subprocess: the chat backend is `lru_cache`d per process and
the budget tracker is process-wide, so one process per model is what keeps the token
accounting and the backend selection honest.

Reports land in their own directory (default `eval/reports/sweep/`) rather than in
`eval/reports/<env>/`, so a sweep never republishes the last model it happened to run
as the project's "latest" eval result.

Usage:
    uv run python scripts/run_model_sweep.py                      # the three local models
    uv run python scripts/run_model_sweep.py --models gemma3:27b
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from eval.ratchet import load_baseline, model_spoke, report_verdicts

DEFAULT_MODELS = ["llama3.2:3b", "gemma3:27b", "llama3.3:70b"]
NULL_BASELINE = Path("eval/baselines/null-control.json")


def _slug(model: str) -> str:
    return model.replace(":", "-").replace("/", "-")


def _run_one(model: str, out_dir: Path) -> tuple[dict[str, Any], float]:
    """Replay the full catalogue against one model, in its own process."""
    report_path = out_dir / f"{_slug(model)}.json"
    started = time.monotonic()
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/run_eval.py",
            "--model",
            model,
            "--report",
            str(report_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    elapsed = time.monotonic() - started
    if not report_path.exists():
        sys.stderr.write(proc.stdout[-2000:] + proc.stderr[-2000:])
        msg = f"{model}: the runner produced no report (exit {proc.returncode})"
        raise RuntimeError(msg)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    # A model that never answered is not a result. The runner does not crash on a dead
    # backend — it silently scores the deterministic layer — so this is the only check
    # standing between a broken sweep and a table of plausible-looking lies.
    if not model_spoke(report):
        msg = (
            f"{model}: 0 output tokens generated — no model answered. "
            f"Is `ollama serve` up, and is `ollama pull {model}` done?"
        )
        raise RuntimeError(msg)
    return report, elapsed


def _render(
    rows: list[tuple[str, dict[str, Any], float]],
    null_verdicts: dict[str, bool],
) -> str:
    """Render the comparison: every model measured as a delta over the null floor."""
    null_passed = sum(1 for ok in null_verdicts.values() if ok)
    total = len(null_verdicts)
    out: list[str] = [
        "# Model sweep — the catalogue replayed against each model",
        "",
        "Every score is reported against the **null control**: the same catalogue run",
        "with no LLM reachable at all, where the deterministic guard/router layer alone",
        f"passes **{null_passed}/{total}**. A model's real contribution is the delta over",
        "that floor, and it can be negative — a model can fail a case the guard would",
        "otherwise have closed.",
        "",
        "| Run | Score | vs null floor | Fixed | Broke | Wall clock | Output tokens |",
        "| --- | --- | --- | --- | --- | --- | --- |",
        f"| **Null control** (no LLM) | **{null_passed}/{total}** "
        f"({null_passed / total:.0%}) | — | — | — | ~5s | 0 |",
    ]
    details: list[str] = []
    for model, report, elapsed in rows:
        run = report_verdicts(report)
        passed = sum(1 for ok in run.values() if ok)
        fixed = sorted(k for k, ok in run.items() if ok and not null_verdicts.get(k, False))
        broke = sorted(k for k, ok in run.items() if not ok and null_verdicts.get(k, False))
        cost = report.get("cost") or {}
        tokens = int(cost.get("output_tokens", 0) or 0)
        delta = passed - null_passed
        out.append(
            f"| {model} | {passed}/{total} ({passed / total:.0%}) | "
            f"{delta:+d} | {len(fixed)} | {len(broke)} | {elapsed / 60:.1f} min | {tokens:,} |"
        )
        details.append(f"\n### {model}\n")
        details.append(
            f"Fixed {len(fixed)} runs the deterministic layer could not close; "
            f"**broke {len(broke)}** that it had closed.\n"
        )
        if broke:
            details.append("\nBroke (the guard passed these, the model then failed them):\n")
            details += [f"- `{k}`\n" for k in broke]

    out.append("")
    out.append(
        "The **Broke** column is the one to read first: those are cases where adding a "
        "model made the agent *worse* than having none."
    )
    out += details
    return "".join(line if line.endswith("\n") else line + "\n" for line in out)


def main(argv: list[str] | None = None) -> int:
    """Run the sweep and write the comparison."""
    parser = argparse.ArgumentParser(description="Replay the catalogue against several models.")
    parser.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    parser.add_argument("--out", type=Path, default=Path("eval/reports/sweep"))
    parser.add_argument("--baseline", type=Path, default=NULL_BASELINE)
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    null_verdicts = load_baseline(args.baseline).verdicts

    rows: list[tuple[str, dict[str, Any], float]] = []
    for model in args.models:
        sys.stdout.write(f"\n=== {model} — replaying 174 (case, language) runs ===\n")
        sys.stdout.flush()
        report, elapsed = _run_one(model, args.out)
        run = report_verdicts(report)
        passed = sum(1 for ok in run.values() if ok)
        sys.stdout.write(f"{model}: {passed}/{len(run)} in {elapsed / 60:.1f} min\n")
        sys.stdout.flush()
        rows.append((model, report, elapsed))

    comparison = args.out / "comparison.md"
    comparison.write_text(_render(rows, null_verdicts), encoding="utf-8")
    sys.stdout.write(f"\nComparison written → {comparison}\n")
    return 0


if __name__ == "__main__":  # pragma: no cover  thin CLI shim
    raise SystemExit(main())
