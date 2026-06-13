"""Unit tests for the per-model judge cache loader."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from tessera.observability.eval.model_judge import load_model_judge

if TYPE_CHECKING:
    from pathlib import Path


def test_absent_cache_is_empty(tmp_path: Path) -> None:
    report = load_model_judge(tmp_path / "missing.json")
    assert report.models == {}
    assert report.judge_model is None


def test_loads_per_model_means(tmp_path: Path) -> None:
    cache = tmp_path / "_model_judge.json"
    cache.write_text(
        json.dumps(
            {
                "judge_model": "llama3.2:3b",
                "context_basis": "expected_behavior",
                "models": {
                    "gpt-5.5": {
                        "faithfulness": 0.71,
                        "grounding": 0.6,
                        "hallucination": 0.8,
                        "n": 60,
                    },
                    "mistral:7b": {
                        "faithfulness": 0.4,
                        "grounding": None,
                        "hallucination": 0.5,
                        "n": 59,
                    },
                },
                "_detail": {"gpt-5.5|01|faithfulness": 0.71},
            }
        ),
        encoding="utf-8",
    )
    report = load_model_judge(cache)
    assert report.judge_model == "llama3.2:3b"
    assert report.context_basis == "expected_behavior"
    assert report.models["gpt-5.5"].faithfulness == 0.71
    assert report.models["gpt-5.5"].n == 60
    # A null metric stays None, never coerced to 0.
    assert report.models["mistral:7b"].grounding is None


def test_malformed_cache_is_empty(tmp_path: Path) -> None:
    cache = tmp_path / "_model_judge.json"
    cache.write_text("not json", encoding="utf-8")
    assert load_model_judge(cache).models == {}
