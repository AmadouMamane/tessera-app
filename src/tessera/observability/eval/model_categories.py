"""Per-model, per-category pass rates from the run archive (image 04 heatmap).

The "Répartition des échecs par catégorie" heatmap in the Comparaison des modèles
tab needs, for each model, how it scores on each failure theme. The eval reports
carry per-case ``category`` + ``passed``, so for each model's most complete recent
run (the same one the comparison table uses) we aggregate pass/fail by category.

Real aggregation, no fabrication: a category absent from a model's run simply
does not appear for that model.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

__all__ = ["ModelCategoryRates", "default_reports_dir", "load_model_category_rates"]


@dataclass(frozen=True, slots=True)
class ModelCategoryRates:
    """One model's pass rate per failure category, from its selected run."""

    model: str
    run_id: str
    rates: dict[str, float]  # category → pass rate in [0, 1]
    counts: dict[str, int]  # category → cases evaluated


def default_reports_dir() -> Path:
    """Repo path of the eval report archive (``eval/reports``)."""
    return Path(__file__).resolve().parents[4] / "eval" / "reports"


def load_model_category_rates(reports_dir: Path | None = None) -> dict[str, ModelCategoryRates]:
    """Per-model category pass rates from each model's most complete recent run.

    The run selected per model matches ``compare_models`` (max case count, ties
    broken by recency), so the heatmap aligns with the comparison table.
    """
    directory = reports_dir or default_reports_dir()
    # Pick the most complete recent run per model.
    best: dict[str, tuple[tuple[int, str], list[dict[str, object]], str]] = {}
    if directory.exists():
        for path in directory.glob("*.json"):
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
            rows = [r for r in results if isinstance(r, dict)]
            key = (len(rows), str(obj.get("run_at", path.stem)))
            if model not in best or key > best[model][0]:
                best[model] = (key, rows, path.stem)

    out: dict[str, ModelCategoryRates] = {}
    for model, (_, rows, run_id) in best.items():
        passed: dict[str, int] = defaultdict(int)
        total: dict[str, int] = defaultdict(int)
        for r in rows:
            cat = str(r.get("category", "unknown"))
            total[cat] += 1
            if r.get("passed"):
                passed[cat] += 1
        rates = {cat: passed[cat] / total[cat] for cat in total if total[cat]}
        out[model] = ModelCategoryRates(
            model=model, run_id=run_id, rates=rates, counts=dict(total)
        )
    return out
