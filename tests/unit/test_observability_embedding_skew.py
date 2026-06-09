"""Unit tests for embedding-version skew (ADR 0010, #64)."""

from __future__ import annotations

from tessera.observability.embedding_skew import EmbeddingFingerprint, detect_skew


def test_matching_fingerprints_no_skew() -> None:
    fp = EmbeddingFingerprint(model="bge-m3", dimension=1024)
    report = detect_skew(fp, fp)
    assert report.skew is False
    assert report.severity == "none"
    assert report.dimension_mismatch is False
    assert report.model_mismatch is False


def test_dimension_mismatch_is_hard_skew() -> None:
    report = detect_skew(
        EmbeddingFingerprint(model="text-multilingual-embedding-002", dimension=768),
        EmbeddingFingerprint(model="bge-m3", dimension=1024),
    )
    assert report.skew is True
    assert report.dimension_mismatch is True
    assert report.severity == "hard"
    assert "not comparable" in report.reason


def test_model_mismatch_same_dimension_is_soft_skew() -> None:
    report = detect_skew(
        EmbeddingFingerprint(model="bge-m3", dimension=1024),
        EmbeddingFingerprint(model="mxbai-embed-large", dimension=1024),
    )
    assert report.skew is True
    assert report.dimension_mismatch is False
    assert report.model_mismatch is True
    assert report.severity == "soft"


def test_severity_priority_dimension_over_model() -> None:
    # Both model and dimension differ → reported as hard (the worse one).
    report = detect_skew(
        EmbeddingFingerprint(model="a", dimension=512),
        EmbeddingFingerprint(model="b", dimension=1024),
    )
    assert report.severity == "hard"
