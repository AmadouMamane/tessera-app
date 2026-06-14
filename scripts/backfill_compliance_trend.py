"""Seed a real, time-spread quality-score history for the Conformité KPI strip.

Dev seeding only. The Conformité "Posture réglementaire" tiles draw a sparkline
and a period-over-period delta from the durable quality-score log
(:func:`tessera.observability.compliance._posture_trend`). On a fresh machine that
log only holds the last day or two, so the trend collapses to a single point. This
script judges the human-labelled calibration gold set with the cheap local judge
(``llama3.2:3b``) and persists each **real** verdict with a ``scored_at`` spread
across the trailing window, so the current *and* the immediately preceding period
are both populated — giving an honest curve and an honest delta. Only the
timestamp is scheduled; every score is a genuine judgement (same epistemic status
as the always-stamped-"now" seed in ``backfill_judge_metrics.py``).

Run from the repo root with the project's source on the path::

    TESSERA_LLM_PROFILE=on_prem PYTHONPATH=src .venv/bin/python \
        scripts/backfill_compliance_trend.py
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from tessera.observability.eval.calibration import load_gold_set
from tessera.observability.eval.judge import FAITHFULNESS, GROUNDING, LLMJudge
from tessera.observability.eval.scores import _persist

# Spread the seed over twice the trend window so both the current period and the
# one before it carry real scores (the delta compares the two).
_SPREAD_DAYS = 28
_METRICS: tuple[str, ...] = (FAITHFULNESS, GROUNDING)


async def main() -> None:
    """Judge each gold case per metric and persist the real score, back-dated."""
    gold = load_gold_set()
    judge = LLMJudge()
    now = datetime.now(UTC)
    n = max(1, len(gold) - 1)
    emitted = 0
    for mi, metric in enumerate(_METRICS):
        for i, case in enumerate(gold):
            verdict = await judge.score(
                metric=metric,
                question=case.question,
                answer=case.answer,
                context=case.context,
            )
            # Oldest case → ~28 days ago, newest → today; offset metrics by a few
            # hours so their buckets don't collide on identical instants.
            day_off = (n - i) * _SPREAD_DAYS / n
            scored_at = now - timedelta(days=day_off, hours=mi * 3)
            _persist(
                {
                    "scored_at": scored_at.isoformat(),
                    "metric": verdict.metric,
                    "score": verdict.score,
                    "language": case.language,
                    "judge_model": verdict.judge_model,
                    "conversation_id": f"backfill-trend-{metric}-{i}",
                    "trace_id": None,
                    "sampled": True,
                }
            )
            emitted += 1
    print(
        f"persisted {emitted} back-dated scores over "
        f"{len(gold)} gold cases x {len(_METRICS)} metrics"
    )


if __name__ == "__main__":
    asyncio.run(main())
