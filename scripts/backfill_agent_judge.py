"""Backfill real per-agent judge metrics over the per-agent eval reports.

For the per-agent Evaluations page (Phase 4b), each agent needs real
Faithfulness / Grounding / Hallucination scores that genuinely differ from the
other agents — because each agent is judged on its OWN run over its OWN curated
set. The per-agent reports store every answer (``final_response``) per case, so
we replay the **real local judge** over those stored answers — no fabrication.

For each agent we take its richest recent run (the report whose ``agent_id``
matches, ties broken by recency) and score each case with the local judge on the
three metrics. The judge needs a CONTEXT: the reports do not store the retrieved
passages, so we use the case's ``expected_behavior`` as the reference context —
the same basis as the per-model backfill, so the values are a comparable proxy.

The result is cached to ``eval/reports/_agent_judge.json`` so the API serves it
instantly. The run is incremental and resumable: per-case scores are cached
keyed by ``agent_id|case_id|language|metric`` and skipped on re-run.

Run from the repo root with the project's source on the path::

    PYTHONPATH=src TESSERA_LLM_PROFILE=on_prem uv run python scripts/backfill_agent_judge.py
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
_CACHE = reports_write_dir() / "_agent_judge.json"


def _select_runs() -> dict[str, dict[str, object]]:
    """The richest recent run per agent_id (matches the dashboard's selection)."""
    best: dict[str, tuple[tuple[int, str], dict[str, object]]] = {}
    for path in iter_report_files():
        if path.name.startswith("_"):
            continue
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # best-effort: skip an unreadable/corrupt eval-report JSON — non-gating (0015)
            continue
        if not isinstance(obj, dict):
            continue
        agent_id = obj.get("agent_id")
        results = obj.get("results")
        if not isinstance(agent_id, str) or not agent_id:
            continue
        if not isinstance(results, list) or not results:
            continue
        key = (len(results), str(obj.get("run_at", path.stem)))
        if agent_id not in best or key > best[agent_id][0]:
            best[agent_id] = (key, obj)
    return {agent_id: obj for agent_id, (_, obj) in best.items()}


def _load_detail() -> dict[str, float]:
    """Per-(agent|case|language|metric) score cache for resumability."""
    if not _CACHE.exists():
        return {}
    try:
        obj = json.loads(_CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    detail = obj.get("_detail") if isinstance(obj, dict) else None
    return detail if isinstance(detail, dict) else {}


async def _score_agent(
    judge: LLMJudge,
    agent_id: str,
    run: dict[str, object],
    detail: dict[str, float],
    sem: asyncio.Semaphore,
    seen_model: list[str],
) -> dict[str, object]:
    """Score every case of ``run`` on the three metrics, reusing cached scores."""
    results = [r for r in run.get("results", []) if isinstance(r, dict)]

    def _key(case: dict[str, object], metric: str) -> str:
        return f"{agent_id}|{case.get('case_id')}|{case.get('language')}|{metric}"

    async def one(case: dict[str, object], metric: str) -> None:
        cache_key = _key(case, metric)
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
            seen_model.append(verdict.judge_model)

    await asyncio.gather(*(one(c, m) for c in results for m in _METRICS))

    means: dict[str, float | int | str] = {
        "n": len(results),
        "run_id": str(run.get("run_at", "")),
    }
    for metric in _METRICS:
        vals = [detail[_key(c, metric)] for c in results if _key(c, metric) in detail]
        means[metric] = round(sum(vals) / len(vals), 4) if vals else None  # type: ignore[assignment]
    return means


async def main() -> None:
    """Judge every agent's stored answers and cache per-agent means."""
    runs = _select_runs()
    if not runs:
        print("no per-agent reports found (run scripts/run_eval.py --agent <id> first)")
        return
    judge = LLMJudge()
    detail = _load_detail()
    agents: dict[str, object] = {}
    seen_model: list[str] = []
    for agent_id, run in runs.items():
        print(f"scoring {agent_id} ({len(run.get('results', []))} cases)…")  # type: ignore[arg-type]
        means = await _score_agent(
            judge, agent_id, run, detail, asyncio.Semaphore(_CONCURRENCY), seen_model
        )
        agents[agent_id] = means
        judge_model = seen_model[0] if seen_model else get_settings().observability.judge_model
        _CACHE.parent.mkdir(parents=True, exist_ok=True)
        _CACHE.write_text(
            json.dumps(
                {
                    "judge_model": judge_model,
                    "context_basis": "expected_behavior",
                    "agents": agents,
                    "_detail": detail,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"  {agent_id}: {means}")
    print(f"done → {_CACHE}")


if __name__ == "__main__":
    asyncio.run(main())
