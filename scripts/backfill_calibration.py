"""Backfill the judge-calibration report over the human gold set.

For the Qualité IA "Calibration juge" tab (image 05), the page needs *real*
judge↔human agreement broken down by language, rubric and segment. This replays
the small sovereign judge (``llama3.2:3b``, idea #2) over the labelled gold set
(``eval/calibration/judge_gold.json``) and caches the full
:class:`~tessera.observability.eval.calibration.CalibrationReport` — including the
per-language / per-category / per-segment agreement, the disagreement-by-rubric
breakdown, false-positive/negative counts and human-override count — to
``eval/calibration/_calibration.json`` so the API serves it instantly.

Run from the repo root with the project's source on the path::

    PYTHONPATH=src .venv/bin/python scripts/backfill_calibration.py
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from pathlib import Path

from tessera.observability.eval.calibration import calibrate, load_gold_set
from tessera.observability.eval.judge import LLMJudge

_JUDGE_MODEL = "llama3.2:3b"
_OUT = Path(__file__).resolve().parents[1] / "eval" / "calibration" / "_calibration.json"


async def main() -> None:
    """Score the gold set with the small local judge and cache the report."""
    gold = load_gold_set()
    print(f"calibrating judge {_JUDGE_MODEL} over {len(gold)} gold cases…")
    report = await calibrate(LLMJudge(model=_JUDGE_MODEL), gold)
    payload = {"available": True, **asdict(report)}
    _OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"  κ={report.kappa:.2f} accord={report.agreement:.0%} "
        f"désaccords={report.n_disagree} (FP={report.fp} FN={report.fn}) "
        f"overrides={report.n_overrides}"
    )
    for g in report.by_language:
        print(f"  langue {g.label}: n={g.n} accord={g.agreement:.0%} κ={g.kappa:.2f}")
    print(f"done → {_OUT}")


if __name__ == "__main__":
    asyncio.run(main())
