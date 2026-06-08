"""Observability read endpoints for the dashboard (ADR 0010).

Exposes the recent online-eval scores so the dashboard can surface
eval-as-telemetry live. Aggregate quality scores are a public surface
(ADR 0009), so this endpoint is unauthenticated like ``/healthz``.
"""

from __future__ import annotations

import sys
from dataclasses import asdict

from fastapi import APIRouter

from tessera.observability.eval.calibration import calibrate, load_gold_set
from tessera.observability.eval.judge import LLMJudge
from tessera.observability.eval.scores import recent_scores

router = APIRouter(tags=["observability"])

# Calibration runs the judge over the gold set (slow), so cache it per process.
_calibration_cache: dict[str, object] | None = None


@router.get("/observability/scores")
async def observability_scores() -> dict[str, object]:
    """Return the most recent online-eval scores (newest last)."""
    return {"scores": recent_scores()}


@router.get("/observability/calibration")
async def observability_calibration() -> dict[str, object]:
    """Return the judge's calibration against the human gold set (cached).

    The first call runs the judge over the gold set and may take a few seconds;
    subsequent calls return the cached report. Degrades to ``available: false``
    when the judge or gold set is unavailable, so the dashboard never errors.
    """
    global _calibration_cache
    if _calibration_cache is None:
        try:
            report = await calibrate(LLMJudge(), load_gold_set())
            _calibration_cache = {"available": True, **asdict(report)}
        except Exception as exc:  # never break the dashboard on a judge/IO error
            sys.stderr.write(f"tessera.observability.calibration: failed: {exc}\n")
            return {"available": False}
    return _calibration_cache
