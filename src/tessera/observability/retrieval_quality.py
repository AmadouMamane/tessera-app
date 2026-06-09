"""Retrieval chunk-utilization / dead context (ADR 0010, idea #26).

Retrieval can be expensive and still wasteful: chunks are fetched, stuffed into
the prompt, and never actually used. Reusing the claim-level provenance
attribution, a chunk is "used" when it is the best support for at least one
*supported* claim. Utilization is the share of retrieved chunks that were used;
the rest is dead context — paid for, never grounding anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tessera.observability.provenance import ProvenanceReport

__all__ = ["UtilizationReport", "utilization"]


@dataclass(frozen=True, slots=True)
class UtilizationReport:
    """How many retrieved chunks actually grounded the answer."""

    n_chunks: int
    used_chunks: int
    dead_chunks: int
    utilization: float  # used / total, 0..1
    used_indices: list[int]


def utilization(report: ProvenanceReport, n_chunks: int) -> UtilizationReport:
    """Derive chunk utilization from a provenance report.

    Args:
        report: The provenance attribution for the answer.
        n_chunks: The number of retrieved chunks offered to the model.

    Returns:
        A :class:`UtilizationReport`.
    """
    used = sorted({c.best_chunk for c in report.claims if c.supported and c.best_chunk >= 0})
    used_n = len(used)
    return UtilizationReport(
        n_chunks=n_chunks,
        used_chunks=used_n,
        dead_chunks=max(0, n_chunks - used_n),
        utilization=(used_n / n_chunks if n_chunks else 0.0),
        used_indices=used,
    )
