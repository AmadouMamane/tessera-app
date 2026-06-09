"""GDPR erasure across telemetry (ADR 0010, idea #180; ADR 0007).

A right-to-erasure (GDPR Art. 17) request that only deletes the long-term memory
rows is incomplete: the customer's turns also live in *telemetry* — captured
replay bundles and online-eval scores keyed by conversation. If those survive,
the deletion is a fiction. This module makes erasure reach the telemetry layer
too, so ``DELETE /memory/{id}`` purges the subject everywhere.

It exposes a read-only :func:`footprint` (what telemetry references a subject —
a pre-deletion preview), the :func:`purge_telemetry` action wired into the
delete path, and an aggregate :func:`coverage` of the whole erasure surface for
the dashboard. The counting helpers are pure over the buffer snapshots; the
purge calls the buffers' own erasure primitives.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from tessera.observability import replay as replay_mod
from tessera.observability.eval import scores as scores_mod

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tessera.observability.replay import ReplayBundle

__all__ = [
    "ErasureCoverage",
    "ErasureFootprint",
    "coverage",
    "footprint",
    "purge_telemetry",
]


@dataclass(frozen=True, slots=True)
class ErasureFootprint:
    """Telemetry artefacts referencing one subject/conversation."""

    conversation_id: str
    n_bundles: int
    n_scores: int
    total: int


@dataclass(frozen=True, slots=True)
class ErasureCoverage:
    """The whole telemetry-erasure surface across all tracked conversations."""

    n_conversations: int
    n_bundles: int
    n_scores: int


def footprint(
    conversation_id: str,
    *,
    bundles: Sequence[ReplayBundle],
    scores: Sequence[dict[str, object]],
) -> ErasureFootprint:
    """Count the telemetry artefacts that reference ``conversation_id`` (preview)."""
    n_bundles = sum(1 for b in bundles if b.conversation_id == conversation_id)
    n_scores = sum(1 for s in scores if s.get("conversation_id") == conversation_id)
    return ErasureFootprint(
        conversation_id=conversation_id,
        n_bundles=n_bundles,
        n_scores=n_scores,
        total=n_bundles + n_scores,
    )


def coverage(
    bundles: Sequence[ReplayBundle],
    scores: Sequence[dict[str, object]],
) -> ErasureCoverage:
    """Aggregate the telemetry-erasure surface across all conversations."""
    conversations: set[str] = set()
    for bundle in bundles:
        if bundle.conversation_id is not None:
            conversations.add(bundle.conversation_id)
    for score in scores:
        conv = score.get("conversation_id")
        if isinstance(conv, str):
            conversations.add(conv)
    return ErasureCoverage(
        n_conversations=len(conversations),
        n_bundles=len(bundles),
        n_scores=len(scores),
    )


def purge_telemetry(conversation_id: str) -> ErasureFootprint:
    """Erase a conversation's replay bundles and eval scores; return what was purged."""
    n_bundles = replay_mod.purge_conversation(conversation_id)
    n_scores = scores_mod.purge_conversation(conversation_id)
    return ErasureFootprint(
        conversation_id=conversation_id,
        n_bundles=n_bundles,
        n_scores=n_scores,
        total=n_bundles + n_scores,
    )
