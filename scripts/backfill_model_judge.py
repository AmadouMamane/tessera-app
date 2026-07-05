"""Backfill real per-model judge metrics over the eval report archive.

For the Qualité IA "Comparaison des modèles" tab (image 04), each model needs
real Faithfulness / Grounding / Hallucination scores. The eval reports store
every model's actual answer (``final_response``) per case, so we can replay the
**real local judge** over those stored answers — no fabrication.

For each model we take the same run the comparison table shows (the most
complete recent run, ties broken by recency), and score each case with the local
judge on the three metrics. The judge needs a CONTEXT: the reports do not store
the retrieved passages, so we use the case's ``expected_behavior`` as the
reference context. The absolute values are therefore a proxy, but because every
model is judged on the **same cases against the same reference**, the
cross-model comparison is valid and real.

The result is cached to ``eval/reports/_model_judge.json`` so the API can serve
it instantly. The run is incremental and resumable: per-case scores are cached
keyed by ``model|case_id|metric`` and skipped on re-run.

Run from the repo root with the project's source on the path::

    PYTHONPATH=src .venv/bin/python scripts/backfill_model_judge.py
"""

from __future__ import annotations

import asyncio
import json

from tessera.observability.eval.judge import (
    FAITHFULNESS,
    GROUNDING,
    HALLUCINATION,
    LLMJudge,
)
from tessera.observability.eval.report_paths import iter_report_files, reports_write_dir
from tessera.settings import get_settings

_METRICS: tuple[str, ...] = (FAITHFULNESS, GROUNDING, HALLUCINATION)
_CONCURRENCY = 5
# Per-env cache (ADR 0014, layer 3): write to eval/reports/<env>/ exclusively.
_CACHE = reports_write_dir() / "_model_judge.json"


def _select_runs() -> dict[str, dict[str, object]]:
    """The most-complete recent run per model (matches compare_models selection)."""
    best: dict[str, tuple[tuple[int, str], dict[str, object]]] = {}
    for path in iter_report_files():
        if path.name.startswith("_"):
            continue
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(obj, dict):
            continue
        model = obj.get("model")
        results = obj.get("results")
        if not isinstance(model, str) or not isinstance(results, list) or not results:
            continue
        key = (len(results), str(obj.get("run_at", path.stem)))
        if model not in best or key > best[model][0]:
            best[model] = (key, obj)
    return {model: obj for model, (_, obj) in best.items()}


def _load_detail() -> dict[str, float]:
    """Per-(model|case|metric) score cache for resumability."""
    if not _CACHE.exists():
        return {}
    try:
        obj = json.loads(_CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    detail = obj.get("_detail") if isinstance(obj, dict) else None
    return detail if isinstance(detail, dict) else {}


async def _score_model(
    judge: LLMJudge,
    model: str,
    run: dict[str, object],
    detail: dict[str, float],
    sem: asyncio.Semaphore,
    seen_model: list[str],
) -> dict[str, object]:
    """Score every case of ``run`` on the three metrics, reusing cached scores."""
    results = [r for r in run.get("results", []) if isinstance(r, dict)]

    async def one(case: dict[str, object], metric: str) -> None:
        case_id = str(case.get("case_id", ""))
        cache_key = f"{model}|{case_id}|{metric}"
        if cache_key in detail:
            return
        answer = str(case.get("final_response", ""))
        context = str(case.get("expected_behavior", ""))
        question = str(case.get("title", ""))
        if not answer:
            return
        async with sem:
            try:
                verdict = await judge.score(
                    metric=metric, question=question, answer=answer, context=context
                )
            except Exception as exc:  # keep going, log and skip
                print(f"  ! {cache_key}: {type(exc).__name__} {exc}")
                return
        detail[cache_key] = verdict.score
        if verdict.judge_model and not seen_model:
            seen_model.append(verdict.judge_model)  # the real model that scored

    await asyncio.gather(*(one(c, m) for c in results for m in _METRICS))

    means: dict[str, float | int | str] = {"n": len(results), "run_id": str(run.get("run_at", ""))}
    for metric in _METRICS:
        vals = [
            detail[f"{model}|{c.get('case_id')}|{metric}"]
            for c in results
            if f"{model}|{c.get('case_id')}|{metric}" in detail
        ]
        means[metric] = round(sum(vals) / len(vals), 4) if vals else None  # type: ignore[assignment]
    return means


async def main() -> None:
    """Judge every selected model's stored answers and cache per-model means."""
    runs = _select_runs()
    judge = LLMJudge()
    detail = _load_detail()
    models: dict[str, object] = {}
    seen_model: list[str] = []
    for model, run in runs.items():
        print(f"scoring {model} ({len(run.get('results', []))} cases)…")  # type: ignore[arg-type]
        means = await _score_model(
            judge, model, run, detail, asyncio.Semaphore(_CONCURRENCY), seen_model
        )
        models[model] = means
        # The real judge model comes from a verdict; fall back to the configured one.
        judge_model = seen_model[0] if seen_model else get_settings().observability.judge_model
        # Persist after each model so the run is resumable.
        _CACHE.parent.mkdir(parents=True, exist_ok=True)
        _CACHE.write_text(
            json.dumps(
                {
                    "judge_model": judge_model,
                    "context_basis": "expected_behavior",
                    "models": models,
                    "_detail": detail,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"  {model}: {means}")
    print(f"done → {_CACHE}")


if __name__ == "__main__":
    asyncio.run(main())
