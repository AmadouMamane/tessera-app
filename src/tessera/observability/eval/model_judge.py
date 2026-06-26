"""Per-model judge metrics, replayed offline over the report archive (image 04).

``scripts/backfill_model_judge.py`` replays the real local judge over each
model's stored answers (``final_response`` in ``eval/reports``) and writes the
per-model means to ``eval/reports/_model_judge.json``. This module loads that
cache so the API can attach real Faithfulness / Grounding / Hallucination scores
to the model comparison without re-running the judge on every request.

Absent cache (backfill not run yet) yields an empty mapping, and the comparison
simply reports ``null`` for those columns — never a fabricated score.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from tessera.observability.eval.report_paths import resolve_report_file

__all__ = ["ModelJudge", "ModelJudgeReport", "default_cache_path", "load_model_judge"]


@dataclass(frozen=True, slots=True)
class ModelJudge:
    """Mean judge scores for one model (each in [0, 1], higher is better)."""

    model: str
    faithfulness: float | None
    grounding: float | None
    hallucination: float | None
    n: int


@dataclass(frozen=True, slots=True)
class ModelJudgeReport:
    """The per-model judge cache plus provenance."""

    judge_model: str | None
    context_basis: str | None
    models: dict[str, ModelJudge]


def default_cache_path() -> Path:
    """Repo path of the per-model judge cache."""
    return Path(__file__).resolve().parents[4] / "eval" / "reports" / "_model_judge.json"


def _opt_float(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) else None


def load_model_judge(path: Path | None = None) -> ModelJudgeReport:
    """Load the per-model judge cache, or an empty report when it is absent."""
    cache = path or resolve_report_file("_model_judge.json")
    if not cache.exists():
        return ModelJudgeReport(judge_model=None, context_basis=None, models={})
    try:
        obj = json.loads(cache.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ModelJudgeReport(judge_model=None, context_basis=None, models={})
    if not isinstance(obj, dict):
        return ModelJudgeReport(judge_model=None, context_basis=None, models={})
    raw_models = obj.get("models")
    models: dict[str, ModelJudge] = {}
    if isinstance(raw_models, dict):
        for model, entry in raw_models.items():
            if not isinstance(entry, dict):
                continue
            n_val = entry.get("n")
            models[str(model)] = ModelJudge(
                model=str(model),
                faithfulness=_opt_float(entry.get("faithfulness")),
                grounding=_opt_float(entry.get("grounding")),
                hallucination=_opt_float(entry.get("hallucination")),
                n=int(n_val) if isinstance(n_val, int) else 0,
            )
    return ModelJudgeReport(
        judge_model=str(obj.get("judge_model")) if obj.get("judge_model") else None,
        context_basis=str(obj.get("context_basis")) if obj.get("context_basis") else None,
        models=models,
    )
