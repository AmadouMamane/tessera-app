"""Unit tests for traces → SFT data (ADR 0010, #122)."""

from __future__ import annotations

from tessera.observability.sft_export import build_sft_dataset


def test_empty() -> None:
    ds = build_sft_dataset([])
    assert ds.n_total == 0
    assert ds.n_eligible == 0
    assert ds.samples == []


def test_only_high_scoring_eligible() -> None:
    turns = [
        ("q1", "ctx", "good answer", "fr", 0.9),  # eligible
        ("q2", "ctx", "weak answer", "de", 0.4),  # below min_score
        ("q3", "ctx", "great answer", "en", 0.85),  # eligible
    ]
    ds = build_sft_dataset(turns, min_score=0.8)
    assert ds.n_total == 3
    assert ds.n_eligible == 2
    assert ds.by_language == {"fr": 1, "en": 1}


def test_empty_answer_excluded() -> None:
    ds = build_sft_dataset([("q", "ctx", "   ", "fr", 0.95)], min_score=0.8)
    assert ds.n_eligible == 0


def test_record_shape() -> None:
    ds = build_sft_dataset([("question", "context", "answer", "fr", 0.9)])
    rec = ds.samples[0]
    assert rec.output == "answer"
    assert "QUESTION:" in rec.input
    assert "CONTEXT:" in rec.input
    assert rec.language == "fr"


def test_sample_limit() -> None:
    turns = [(f"q{i}", "ctx", "answer", "fr", 0.95) for i in range(30)]
    ds = build_sft_dataset(turns, sample_limit=5)
    assert ds.n_eligible == 30
    assert len(ds.samples) == 5
