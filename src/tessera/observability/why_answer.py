"""User-facing "Why this answer?" (ADR 0010, idea #133; provenance is #11).

Trust in a banking answer comes from being able to see *why* it was said. The
provenance graph (#11) already attributes each claim in the answer to its
best-supporting retrieved chunk; this module turns that machine artefact into a
user-facing explanation: for each claim, the source snippet that backs it and how
strongly, an overall confidence, and an honest flag on any claim the grounding
does not actually support.

It reuses :func:`tessera.observability.provenance.attribute`, so the explanation
is exactly the provenance the rest of the stack computes — no second, divergent
story. The builder is async (it embeds, via provenance) and per-turn; the
endpoint drives it from a captured turn's answer and chunks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from tessera.observability.provenance import attribute

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["ClaimExplanation", "WhyExplanation", "build_explanation"]

_SNIPPET = 160


@dataclass(frozen=True, slots=True)
class ClaimExplanation:
    """One claim and the source that backs it, for a user."""

    claim: str
    supported: bool
    support: float
    source: str  # snippet of the supporting chunk, or "" if unsupported


@dataclass(frozen=True, slots=True)
class WhyExplanation:
    """A user-facing explanation of why an answer was given."""

    n_claims: int
    grounded_fraction: float
    confidence: float  # mean support across claims
    fully_grounded: bool
    claims: list[ClaimExplanation] = field(default_factory=list)


async def build_explanation(
    *,
    answer: str,
    chunks: Sequence[str],
) -> WhyExplanation:
    """Build a "why this answer" explanation from the provenance graph.

    Args:
        answer: The agent's answer.
        chunks: The retrieved context chunks the answer should rest on.

    Returns:
        A :class:`WhyExplanation` pairing each claim with its supporting source.
    """
    report = await attribute(answer, chunks)

    claims: list[ClaimExplanation] = []
    supports: list[float] = []
    for claim in report.claims:
        supports.append(claim.support)
        source = ""
        if claim.supported and 0 <= claim.best_chunk < len(chunks):
            source = chunks[claim.best_chunk][:_SNIPPET]
        claims.append(
            ClaimExplanation(
                claim=claim.text,
                supported=claim.supported,
                support=claim.support,
                source=source,
            )
        )

    confidence = sum(supports) / len(supports) if supports else 1.0
    return WhyExplanation(
        n_claims=report.n_claims,
        grounded_fraction=report.grounded_fraction,
        confidence=confidence,
        fully_grounded=report.grounded_fraction >= 1.0,
        claims=claims,
    )
