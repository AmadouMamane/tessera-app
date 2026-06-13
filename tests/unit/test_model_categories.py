"""Unit tests for per-model, per-category pass rates."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from tessera.observability.eval.model_categories import load_model_category_rates

if TYPE_CHECKING:
    from pathlib import Path


def _write(directory: Path, name: str, model: str, run_at: str, results: list[dict]) -> None:
    (directory / name).write_text(
        json.dumps({"model": model, "run_at": run_at, "results": results}), encoding="utf-8"
    )


def test_empty(tmp_path: Path) -> None:
    assert load_model_category_rates(tmp_path) == {}


def test_per_model_category_rates(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "a.json",
        "alpha",
        "20260606T000000Z",
        [
            {"case_id": "1", "category": "pii_leak", "passed": True},
            {"case_id": "2", "category": "pii_leak", "passed": False},
            {"case_id": "3", "category": "hallucination", "passed": True},
        ],
    )
    rates = load_model_category_rates(tmp_path)
    assert set(rates) == {"alpha"}
    assert rates["alpha"].rates["pii_leak"] == 0.5
    assert rates["alpha"].rates["hallucination"] == 1.0
    assert rates["alpha"].counts["pii_leak"] == 2


def test_picks_most_complete_run(tmp_path: Path) -> None:
    # A later smoke run must not override the bigger run.
    _write(
        tmp_path,
        "big.json",
        "m",
        "20260601T000000Z",
        [{"case_id": str(i), "category": "pii_leak", "passed": i % 2 == 0} for i in range(10)],
    )
    _write(tmp_path, "smoke.json", "m", "20260609T000000Z",
           [{"case_id": "x", "category": "pii_leak", "passed": True}])
    rates = load_model_category_rates(tmp_path)
    assert rates["m"].counts["pii_leak"] == 10  # from the big run, not the smoke run


def test_ignores_cache_files(tmp_path: Path) -> None:
    _write(tmp_path, "r.json", "m", "20260606T000000Z",
           [{"case_id": "1", "category": "pii_leak", "passed": True}])
    (tmp_path / "_model_judge.json").write_text(
        json.dumps({"model": "x", "results": [{"case_id": "9", "category": "z", "passed": False}]}),
        encoding="utf-8",
    )
    rates = load_model_category_rates(tmp_path)
    assert set(rates) == {"m"}
