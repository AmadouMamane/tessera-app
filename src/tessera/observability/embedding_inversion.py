"""Embedding-inversion privacy risk (ADR 0010, idea #73; memory is ADR 0007).

A pgvector store keeps *embeddings* of memories, and it is tempting to treat a
vector as anonymous — it is just numbers. It is not. Embeddings are
approximately invertible: an attacker who can query the same embedder can match a
stored vector back to its source meaning by searching candidate phrases for the
nearest one. So a vector of "the customer holds a Crédit Aurore mortgage in
arrears" leaks that fact to anyone who can read the column.

This module *demonstrates and measures* the risk. Given stored memory texts and a
set of attacker candidate phrases ("probes"), it embeds both and, for each
memory, finds the nearest probe; a memory whose nearest probe clears the
similarity threshold is **recoverable** — its gist can be reconstructed from the
vector alone. The recovery rate is the privacy-risk signal. Mitigation
(documented for the operator): do not persist raw vectors of highly sensitive
text, mask before embedding (the governance layer already masks card/IBAN), or
store memories that have themselves been minimised.

The assessment is pure with an injectable embedder; the endpoint runs it over a
small built-in demonstration corpus with the live embedder so the dashboard
always shows a concrete number.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

__all__ = [
    "DEMO_MEMORIES",
    "DEMO_PROBES",
    "InversionMatch",
    "InversionReport",
    "assess_inversion_risk",
]

# Above this cosine, a probe is treated as recovering the memory's gist.
_DEFAULT_THRESHOLD = 0.60
_PREVIEW = 80

# A built-in demonstration corpus: sensitive "memories" and the kind of candidate
# phrases an attacker would try. Used by the endpoint so the risk is always
# visible; the maths is identical over the real store.
DEMO_MEMORIES: tuple[str, ...] = (
    "The customer holds a Crédit Aurore mortgage and is two months in arrears.",
    "The customer requested a card block after a fraud on their account.",
    "The customer prefers communication in German and lives in Munich.",
)
DEMO_PROBES: tuple[str, ...] = (
    "mortgage in arrears at Crédit Aurore",
    "blocked card following account fraud",
    "German-speaking customer based in Munich",
    "opened a new savings account last week",
    "requested a mortgage simulation",
)


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


@dataclass(frozen=True, slots=True)
class InversionMatch:
    """The nearest attacker probe for one stored memory."""

    memory: str
    probe: str
    cosine: float
    recoverable: bool


@dataclass(frozen=True, slots=True)
class InversionReport:
    """How recoverable stored memory vectors are from candidate probes."""

    n_memories: int
    n_recoverable: int
    recovery_rate: float
    threshold: float
    matches: list[InversionMatch] = field(default_factory=list)


async def assess_inversion_risk(
    memories: Sequence[str],
    probes: Sequence[str],
    *,
    embedder: Callable[[Sequence[str]], Awaitable[list[list[float]]]],
    threshold: float = _DEFAULT_THRESHOLD,
) -> InversionReport:
    """Measure how recoverable ``memories`` are from attacker ``probes``.

    Args:
        memories: Stored memory texts whose vectors are at risk.
        probes: Attacker candidate phrases.
        embedder: Async embedding function (the same embedder the store uses).
        threshold: Cosine at or above which a memory counts as recoverable.

    Returns:
        An :class:`InversionReport`. With no memories or probes, the rate is 0.
    """
    if not memories or not probes:
        return InversionReport(
            n_memories=len(memories),
            n_recoverable=0,
            recovery_rate=0.0,
            threshold=threshold,
        )

    vectors = await embedder([*memories, *probes])
    memory_vecs = vectors[: len(memories)]
    probe_vecs = vectors[len(memories) :]

    matches: list[InversionMatch] = []
    n_recoverable = 0
    for memory, mvec in zip(memories, memory_vecs, strict=True):
        best_probe = ""
        best_cosine = -1.0
        for probe, pvec in zip(probes, probe_vecs, strict=True):
            sim = _cosine(mvec, pvec)
            if sim > best_cosine:
                best_cosine = sim
                best_probe = probe
        recoverable = best_cosine >= threshold
        if recoverable:
            n_recoverable += 1
        matches.append(
            InversionMatch(
                memory=memory[:_PREVIEW],
                probe=best_probe[:_PREVIEW],
                cosine=best_cosine,
                recoverable=recoverable,
            )
        )

    return InversionReport(
        n_memories=len(memories),
        n_recoverable=n_recoverable,
        recovery_rate=n_recoverable / len(memories),
        threshold=threshold,
        matches=matches,
    )
