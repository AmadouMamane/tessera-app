"""Observability routes — evals surface."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict

from fastapi import APIRouter

from tessera.api.routes.observability._common import (
    _CALIBRATION_FILE,
    _CALIBRATION_JUDGE_MODEL,
    _CONSENSUS_PANEL,
    _load_failure_items,
)
from tessera.observability import (
    contradiction as contradiction_mod,
    failure_clustering as failure_clustering_mod,
    failure_predictor as failure_predictor_mod,
    replay as replay_mod,
    reproducibility as reproducibility_mod,
    sft_export as sft_export_mod,
)
from tessera.observability.eval.calibration import calibrate, gold_consensus, load_gold_set
from tessera.observability.eval.judge import LLMJudge
from tessera.observability.spine.adapters import read_scores

router = APIRouter()

_calibration_cache: dict[str, object] | None = None
_consensus_cache: dict[str, object] | None = None
_clustering_cache: dict[str, object] | None = None


@router.get("/observability/reproducibility")
async def observability_reproducibility() -> dict[str, object]:
    """Trace-shape reproducibility / non-determinism across repeated questions (#86)."""
    turns = [(b.question, list((b.latency_ms or {}).keys())) for b in replay_mod.recent_bundles()]
    return asdict(reproducibility_mod.detect_nondeterminism(turns))


@router.get("/observability/judge-drift")
async def observability_judge_drift(
    at: str | None = None,
    metric: str = "faithfulness",
    days: int = 7,
    buckets: int = 7,
) -> dict[str, object]:
    """Judge score-drift for ``metric`` over the window ending now or at instant T.

    Measures how much the judge's per-bucket mean disperses over time (the drift
    magnitude) plus its net direction, from the same durable score log — so it
    honours as-of-T (ADR 0011). Powers the "Drift du juge" signal on the
    Calibration juge tab. ``divergence=null``/``level="unknown"`` when there are
    too few populated buckets to judge drift, never a fabricated value.
    """
    import contextlib
    from datetime import UTC, datetime

    from tessera.observability.eval.series import compute_judge_drift

    end = datetime.now(UTC)
    if at:
        with contextlib.suppress(ValueError):
            end = datetime.fromisoformat(at)
    drift = compute_judge_drift(
        read_scores(at, full=True), metric=metric, end=end, days=days, n_buckets=buckets
    )
    return {**asdict(drift), "as_of": at}


@router.get("/observability/regression-risk")
async def observability_regression_risk(
    at: str | None = None,
    metric: str = "faithfulness",
    days: int = 7,
    buckets: int = 7,
) -> dict[str, object]:
    """Forward-looking regression risk for the "Signaux prédictifs" column.

    Composes a transparent risk score from real signals only — the recent judge
    score trend (``score-series`` delta), judge drift divergence, and the
    empirical share of compared models that regressed run-over-run
    (``release-status``). The 7-day regression probability is that empirical base
    rate, not an invented forecast. Honours as-of-T via the durable score log;
    every component is returned alongside the composite so the risk is explainable.
    With neither judge scores nor compared models the composite is ``null`` and the
    level is ``"unknown"`` rather than fabricated.
    """
    import contextlib
    from datetime import UTC, datetime

    from tessera.observability.eval.releases import release_status
    from tessera.observability.eval.risk import compute_regression_risk

    end = datetime.now(UTC)
    if at:
        with contextlib.suppress(ValueError):
            end = datetime.fromisoformat(at)
    risk = compute_regression_risk(
        read_scores(at, full=True),
        release_status(),
        end=end,
        metric=metric,
        days=days,
        n_buckets=buckets,
    )
    return {**asdict(risk), "as_of": at}


@router.get("/observability/calibration")
async def observability_calibration() -> dict[str, object]:
    """Return the judge's calibration against the human gold set (cached).

    The first call runs the judge over the gold set and may take a few seconds;
    subsequent calls return the cached report. Degrades to ``available: false``
    when the judge or gold set is unavailable, so the dashboard never errors.
    """
    global _calibration_cache
    if _calibration_cache is None:
        # Prefer the precomputed backfill (real llama3.2:3b scores over the gold set).
        if _CALIBRATION_FILE.exists():
            try:
                _calibration_cache = json.loads(_CALIBRATION_FILE.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                sys.stderr.write(f"tessera.observability.calibration: cache read failed: {exc}\n")
        if _calibration_cache is None:
            try:
                report = await calibrate(LLMJudge(model=_CALIBRATION_JUDGE_MODEL), load_gold_set())
                _calibration_cache = {"available": True, **asdict(report)}
            except Exception as exc:  # never break the dashboard on a judge/IO error
                sys.stderr.write(f"tessera.observability.calibration: failed: {exc}\n")
                return {"available": False}
    return _calibration_cache


@router.get("/observability/model-catalogue")
async def observability_model_catalogue(lang: str = "fr", agent: str = "all") -> dict[str, object]:
    """CONFIGURER model catalogue (configurer/modeles): the real LLM model layer.

    The configured models (vertex / ollama / openai) + the indicative tariff +
    real cumulative usage + the consuming agents (re-gate blast radius). Filterable
    by agent. Degrades to ``available: false`` on failure.
    """
    from tessera.observability import model_catalogue as mc_mod

    try:
        return {"available": True, **mc_mod.build_model_catalogue(lang, agent_scope=agent)}
    except Exception as exc:  # never break the page
        sys.stderr.write(f"tessera.observability.model_catalogue: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/judge-consensus")
async def observability_judge_consensus() -> dict[str, object]:
    """Multi-judge consensus over the gold set (cached).

    Runs a panel of different local judges over the human gold set and reports how
    often they concur — the unanimous-consensus rate, mean pairwise agreement and
    Fleiss' κ. The first call scores the panel and may take a while; later calls
    return the cache. Degrades to ``available: false`` if a judge model is missing
    so the dashboard never errors.
    """
    global _consensus_cache
    if _consensus_cache is None:
        try:
            judges = [LLMJudge(model=m) for m in _CONSENSUS_PANEL]
            report = await gold_consensus(judges, load_gold_set(), labels=list(_CONSENSUS_PANEL))
            _consensus_cache = {"available": True, **asdict(report)}
        except Exception as exc:  # never break the dashboard on a judge/IO error
            sys.stderr.write(f"tessera.observability.judge_consensus: failed: {exc}\n")
            return {"available": False}
    return _consensus_cache


@router.get("/observability/failure-clusters")
async def observability_failure_clusters() -> dict[str, object]:
    """Auto-clustered themes across the documented failure corpus (#123), cached."""
    global _clustering_cache
    if _clustering_cache is None:
        from tessera.retrieval.embeddings import embed

        try:
            report = await failure_clustering_mod.cluster_failures(
                _load_failure_items(), k=6, embedder=embed
            )
            _clustering_cache = {"available": True, **asdict(report)}
        except Exception as exc:  # embedder offline — never break the dashboard
            sys.stderr.write(f"tessera.observability.failure_clustering: failed: {exc}\n")
            return {"available": False}
    return _clustering_cache


@router.get("/observability/failed-cases")
async def observability_failed_cases(
    language: str = "fr", limit: int | None = None
) -> dict[str, object]:
    """Structured failed-case catalogue + category/severity distributions (image 03).

    Reads the documented-failure corpus (``eval/failures``) — real in-repo cases.
    Severity is a documented triage heuristic over the category, not a runtime
    score. Sorted worst-severity first; ``limit`` caps the rows (the distributions
    always count the full catalogue).
    """
    from tessera.observability.eval.failed_cases import load_failed_cases

    report = load_failed_cases(language=language, limit=limit)
    return asdict(report)


@router.get("/observability/runs")
async def observability_runs() -> dict[str, object]:
    """Eval run registry from the report archive (Runs & datasets tab, image 02).

    One row per real report under ``eval/reports`` (model, language, pass rate,
    cost, latency, catalogue version), newest first. No fabrication — a free
    local run keeps ``est_cost_eur: null``.
    """
    from tessera.observability.eval.runs import load_runs

    return asdict(load_runs())


@router.get("/observability/failed-runs")
async def observability_failed_runs() -> dict[str, object]:
    """Real failed cases from the run archive (Cas échoués tab, image 03).

    Every ``passed: false`` result in each model/language's most recent
    full-catalogue run, joined with ``eval/failures`` for the triggering prompt
    and expected behaviour. Per-case ``status`` is ``new`` (a fresh regression vs
    the previous run) or ``recurrent``; ``owner`` is the documented governance
    team. There is no per-case judge score in the reports, so none is invented.
    """
    from tessera.observability.eval.failed_runs import load_failed_runs

    return asdict(load_failed_runs())


@router.get("/observability/eval-datasets")
async def observability_eval_datasets() -> dict[str, object]:
    """Themed quality datasets from the failure catalogue joined to runs (image 02).

    Tessera's real "eval datasets" are the failure-catalogue **themes** (categories):
    per theme we derive case count, languages, version, latest-run pass rate, drift
    (delta between the two most recent full-catalogue runs), coverage and last-run
    timestamp — all from ``eval/failures`` joined with ``eval/reports``. Absent
    signals (a theme not in the latest run, pipeline workers/queue/evidence TTL)
    stay ``null`` so the dashboard renders "—", never an invented value.
    """
    from tessera.observability.eval.datasets import load_quality_datasets

    return asdict(load_quality_datasets())


@router.get("/observability/model-comparison")
async def observability_model_comparison() -> dict[str, object]:
    """Per-model comparison from the latest run of each model (image 04).

    Aggregates the real report archive: pass rate, cost, latency and a documented
    verdict per model. Each row is enriched with real per-model signals: the
    judge metrics (faithfulness / grounding / hallucination) replayed offline over
    the model's stored answers (``eval/reports/_model_judge.json``; ``null`` until
    the backfill runs), a pass-rate ``evolution`` sparkline, and a run-over-run
    ``non_regression`` retention ratio. Nothing is fabricated.
    """
    from tessera.observability.eval.model_categories import load_model_category_rates
    from tessera.observability.eval.model_judge import load_model_judge
    from tessera.observability.eval.runs import compare_models, load_runs

    registry = load_runs()
    judge = load_model_judge()
    categories = load_model_category_rates()

    min_run_cases = 10  # ignore tiny smoke runs in the per-model sparkline

    def _evolution_and_nonreg(model: str) -> tuple[list[float], float | None]:
        runs = sorted(
            (r for r in registry.runs if r.model == model and r.total >= min_run_cases),
            key=lambda r: r.run_at,
        )
        evolution = [round(r.pass_rate, 4) for r in runs][-8:]
        non_reg: float | None = None
        if len(runs) >= 2:  # noqa: PLR2004 — needs a pair to compare
            prev, last = runs[-2].pass_rate, runs[-1].pass_rate
            non_reg = round(min(1.0, last / prev), 4) if prev > 0 else None
        return evolution, non_reg

    models: list[dict[str, object]] = []
    for stat in compare_models(registry.runs):
        row = asdict(stat)
        mj = judge.models.get(stat.model)
        evolution, non_reg = _evolution_and_nonreg(stat.model)
        cats = categories.get(stat.model)
        row.update(
            faithfulness=mj.faithfulness if mj else None,
            grounding=mj.grounding if mj else None,
            hallucination=mj.hallucination if mj else None,
            evolution=evolution,
            non_regression=non_reg,
            categories=cats.rates if cats else {},
        )
        models.append(row)
    return {"models": models, "n_runs": registry.n, "judge_model": judge.judge_model}


@router.get("/observability/sft-dataset")
async def observability_sft_dataset() -> dict[str, object]:
    """Distil high-scoring captured turns into an SFT dataset (#122)."""
    turns = [
        (b.question, b.context, b.original_answer, b.language, b.original_score)
        for b in replay_mod.recent_bundles()
    ]
    return asdict(sft_export_mod.build_sft_dataset(turns))


@router.get("/observability/failure-predictor")
async def observability_failure_predictor() -> dict[str, object]:
    """Back-test the pre-judge failure predictor against captured turns (#121)."""
    turns = [(b.question, b.context, b.original_score) for b in replay_mod.recent_bundles()]
    return asdict(failure_predictor_mod.evaluate_predictor(turns))


@router.get("/observability/contradictions")
async def observability_contradictions() -> dict[str, object]:
    """Detect self-contradictions across the turns of each captured session."""
    by_conversation: dict[str, list[tuple[str, str]]] = {}
    for bundle in replay_mod.recent_bundles():
        key = bundle.conversation_id or "<none>"
        by_conversation.setdefault(key, []).append((bundle.question, bundle.original_answer))

    n_turns = 0
    pairs: list[dict[str, object]] = []
    for conversation_id, turns in by_conversation.items():
        n_turns += len(turns)
        report = await contradiction_mod.detect_contradictions(turns)
        for pair in report.contradictions:
            pairs.append({"conversation_id": conversation_id, **asdict(pair)})

    return {
        "n_sessions": len(by_conversation),
        "n_turns": n_turns,
        "n_contradictions": len(pairs),
        "pairs": pairs,
    }
