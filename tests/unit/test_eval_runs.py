"""Unit tests for the eval run registry + model comparison."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from tessera.observability.eval.runs import compare_models, load_runs

if TYPE_CHECKING:
    from pathlib import Path


def _write_run(directory: Path, name: str, obj: dict[str, object]) -> None:
    (directory / name).write_text(json.dumps(obj), encoding="utf-8")


def _run(
    model: str,
    run_at: str,
    *,
    total: int = 10,
    passed: int = 8,
    cost: float | None = None,
) -> dict[str, object]:
    obj: dict[str, object] = {
        "run_at": run_at,
        "lang": "fr",
        "model": model,
        "catalogue_version": "63-abc",
        "summary": {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": passed / total,
        },
        "results": [
            {
                "case_id": "01",
                "start_time": "2026-06-06T07:54:07.000000+00:00",
                "end_time": "2026-06-06T07:54:07.500000+00:00",
            }
        ],
    }
    if cost is not None:
        obj["cost"] = {"estimated_cost_eur": cost}
    return obj


def test_empty_directory(tmp_path: Path) -> None:
    reg = load_runs(tmp_path)
    assert reg.n == 0
    assert reg.runs == []
    assert compare_models(reg.runs) == []


def test_registry_newest_first_and_latency(tmp_path: Path) -> None:
    _write_run(tmp_path, "a.json", _run("llama3.2:3b", "20260601T000000Z"))
    _write_run(tmp_path, "b.json", _run("mistral:7b", "20260604T000000Z"))
    _write_run(tmp_path, "skip.json", {"not": "a run"})
    reg = load_runs(tmp_path)
    assert reg.n == 2
    assert reg.runs[0].run_at == "20260604T000000Z"  # newest first
    assert reg.runs[0].mean_latency_ms == 500.0
    assert reg.catalogue_cases == 10
    assert set(reg.models) == {"llama3.2:3b", "mistral:7b"}


def test_compare_models_verdicts(tmp_path: Path) -> None:
    # best local, a priced frontier, a weak local, plus an older run of the best.
    _write_run(tmp_path, "best.json", _run("llama3.3:70b", "20260604T000000Z", passed=9))
    _write_run(tmp_path, "best_old.json", _run("llama3.3:70b", "20260601T000000Z", passed=5))
    _write_run(tmp_path, "front.json", _run("gpt-5.5", "20260605T000000Z", passed=6, cost=0.2))
    _write_run(tmp_path, "weak.json", _run("mistral:7b", "20260604T000000Z", passed=3))
    stats = compare_models(load_runs(tmp_path).runs)
    by_model = {s.model: s for s in stats}
    assert by_model["llama3.3:70b"].verdict == "best"
    assert by_model["llama3.3:70b"].n_runs == 2  # both runs counted
    assert by_model["llama3.3:70b"].pass_rate == 0.9  # latest, not the old 0.5
    assert by_model["gpt-5.5"].verdict == "balanced"  # priced, not best, >=50%
    assert by_model["gpt-5.5"].est_cost_eur == 0.2
    assert by_model["mistral:7b"].verdict == "avoid"  # < 50%
    # Sorted best pass-rate first.
    assert stats[0].model == "llama3.3:70b"


def test_real_archive_loads() -> None:
    reg = load_runs()
    assert reg.n >= 1
    assert "gpt-5.5" in reg.models
    stats = compare_models(reg.runs)
    assert any(s.verdict == "best" for s in stats)
