"""Unit tests for retrieval chunk-utilization (ADR 0010, #26)."""

from __future__ import annotations

from tessera.observability.provenance import ProvenanceClaim, ProvenanceReport
from tessera.observability.retrieval_quality import utilization


def test_utilization_counts_only_supporting_chunks() -> None:
    claims = [
        ProvenanceClaim(text="a", support=0.9, supported=True, best_chunk=0),
        ProvenanceClaim(text="b", support=0.8, supported=True, best_chunk=0),
        ProvenanceClaim(text="c", support=0.1, supported=False, best_chunk=2),
    ]
    report = ProvenanceReport(n_claims=3, grounded_fraction=2 / 3, claims=claims)

    util = utilization(report, n_chunks=4)
    assert util.used_chunks == 1  # only chunk 0 supported a claim
    assert util.dead_chunks == 3
    assert util.utilization == 0.25
    assert util.used_indices == [0]


def test_utilization_no_chunks() -> None:
    report = ProvenanceReport(n_claims=0, grounded_fraction=1.0, claims=[])
    util = utilization(report, n_chunks=0)
    assert util.utilization == 0.0
    assert util.dead_chunks == 0
