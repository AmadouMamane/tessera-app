"""Seed grounding/hallucination (and faithfulness) scores over the gold set.

Dev seeding only: judges the human-labelled calibration gold set with the cheap
local judge (``llama3.2:3b`` by default — see ``observability.judge_model``) and
emits the scores as telemetry, so the Qualité IA "Vue d'ensemble" KPI tiles for
the new metrics light up from real judgements rather than staying empty. In
production these metrics are scored online per turn (``eval/online.py``); this is
a one-shot, idempotent-enough seed for development.

Run from the repo root with the project's source on the path::

    PYTHONPATH=src .venv/bin/python scripts/backfill_judge_metrics.py
"""

from __future__ import annotations

import asyncio

from tessera.observability.eval.calibration import load_gold_set
from tessera.observability.eval.judge import (
    FAITHFULNESS,
    GROUNDING,
    HALLUCINATION,
    LLMJudge,
)
from tessera.observability.eval.scores import emit_score

_METRICS: tuple[str, ...] = (FAITHFULNESS, GROUNDING, HALLUCINATION)


async def main() -> None:
    """Judge every gold case on each metric and emit the scores as telemetry."""
    gold = load_gold_set()
    judge = LLMJudge()
    emitted = 0
    for i, case in enumerate(gold):
        for metric in _METRICS:
            verdict = await judge.score(
                metric=metric,
                question=case.question,
                answer=case.answer,
                context=case.context,
            )
            emit_score(
                verdict,
                language="fr",
                conversation_id=f"backfill-gold-{i}",
                sampled=True,
            )
            emitted += 1
    print(f"emitted {emitted} scores over {len(gold)} gold cases x {len(_METRICS)} metrics")


if __name__ == "__main__":
    asyncio.run(main())
