"""GDPR erasure across telemetry (ADR 0010, idea #180; ADR 0007; ADR 0015 §Migration D).

A right-to-erasure (GDPR Art. 17) request that only deletes the long-term memory
rows is incomplete: the customer's turns also live in *telemetry* — captured
replay bundles and online-eval scores keyed by conversation, **and in the spine**
(Langfuse traces). If those survive, the deletion is a fiction. This module makes
erasure reach the telemetry layer too, so ``DELETE /memory/{id}`` purges the
subject everywhere.

Erasure reaches three places (ADR 0015 §Migration D): the local convenience
stores (still the system of record until parity bakes), the **spine** (Langfuse
traces — the PII-bearing rows), and the **read-through cache** (evicted so an
in-flight snapshot cannot resurrect an erased row). Prometheus aggregates carry
**no** ``conversation_id`` label (cardinality is bounded to agent/language/model),
so there is no per-conversation metric series to drop — aggregate PII exposure is
nil by construction, not by deletion. The tamper-evident ledgers (``audit.log`` +
S1) are the ADR carve-out and are **kept**: they record *that* an erasure happened
(the legal proof), not the subject's content.

It exposes a read-only :func:`footprint` (what telemetry references a subject —
a pre-deletion preview), the :func:`purge_telemetry` action wired into the
delete path, and an aggregate :func:`coverage` of the whole erasure surface for
the dashboard. The counting helpers are pure over the buffer snapshots; the
purge calls the buffers' own erasure primitives plus the spine deletion.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from tessera.observability import replay as replay_mod
from tessera.observability.eval import scores as scores_mod
from tessera.observability.logging import get_logger
from tessera.observability.spine.adapters.base import SpineUnavailableError
from tessera.observability.spine.snapshot import reset_snapshot_cache

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tessera.observability.replay import ReplayBundle

__all__ = [
    "ErasureCoverage",
    "ErasureFootprint",
    "coverage",
    "footprint",
    "purge_owned_scores",
    "purge_spine",
    "purge_telemetry",
]

_LOG = get_logger("tessera.observability.erasure")


@dataclass(frozen=True, slots=True)
class ErasureFootprint:
    """Telemetry artefacts referencing one subject/conversation.

    ``n_spine`` is the number of spine (Langfuse) traces deleted; it is 0 on the pre-deletion
    :func:`footprint` preview (which counts only the local stores) and set by
    :func:`purge_telemetry`. ``spine_reached`` records whether the spine deletion actually ran
    (``False`` when Langfuse was unreachable — the erasure is then locally complete but the
    spine leg needs a retry, and that honesty is preserved rather than hidden).
    """

    conversation_id: str
    n_bundles: int
    n_scores: int
    total: int
    n_spine: int = 0
    spine_reached: bool = True
    # The OWNED online-score store (ClickHouse, §Correction 2b): erasure must reach the
    # durable home of the score rows, not only the local jsonl + the Langfuse traces.
    # The gating porteur carries no conversation_id (release runs are not subject-linked),
    # so it has no erasure surface by construction.
    n_owned_scores: int = 0
    owned_reached: bool = True


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


def _spine_delete(conversation_id: str) -> int:
    """Delete the conversation's traces in Langfuse (the spine deletion seam).

    A thin indirection so the delete path is patchable: unit tests stub this to stay offline,
    while the live wiring constructs the adapter against the self-hosted Langfuse.
    """
    from tessera.observability.spine.adapters.langfuse import LangfuseAdapter

    return LangfuseAdapter().delete_conversation(conversation_id)


def _owned_scores_delete(conversation_id: str) -> int:
    """Delete the conversation's rows in the owned ClickHouse score store (the seam)."""
    from tessera.observability.spine.adapters.clickhouse import ClickHouseAdapter

    return ClickHouseAdapter().delete_conversation(conversation_id)


def purge_owned_scores(conversation_id: str) -> tuple[int, bool]:
    """Erase a conversation's rows in the owned online-score store (§Correction 2b).

    Same honesty contract as :func:`purge_spine`: best-effort, ``(n_deleted, reached)``,
    an unreachable store is logged and reported — deferred, never faked.
    """
    deleted = 0
    reached = True
    try:
        deleted = _owned_scores_delete(conversation_id)
    except SpineUnavailableError as exc:
        reached = False
        _LOG.warning(
            "owned-score erasure deferred (clickhouse unreachable): %s",
            exc,
            extra={"conversation_id": conversation_id},
        )
    return deleted, reached


def purge_spine(conversation_id: str) -> tuple[int, bool]:
    """Erase a conversation in the spine (Langfuse traces) + evict the read-through cache.

    Returns ``(n_deleted, reached)``. Best-effort by design: an unreachable Langfuse is logged
    and reported as ``reached=False`` (the local system-of-record purge still completes — the
    erasure is not lost, only its spine leg is deferred to a retry), never raised into the delete
    path. The cache is evicted **unconditionally** so a cached snapshot cannot re-serve an erased
    row even if the spine deletion itself has to be retried.
    """
    deleted = 0
    reached = True
    try:
        deleted = _spine_delete(conversation_id)
    except SpineUnavailableError as exc:
        reached = False
        _LOG.warning(
            "spine erasure deferred (langfuse unreachable): %s",
            exc,
            extra={"conversation_id": conversation_id},
        )
    reset_snapshot_cache()
    return deleted, reached


def purge_telemetry(conversation_id: str) -> ErasureFootprint:
    """Erase a conversation across the local stores **and** the spine; return what was purged.

    Order: local stores first (the current system of record), then the spine (Langfuse traces),
    then evict the read-through cache (inside :func:`purge_spine`). The ledgers are intentionally
    untouched (the carve-out). See the module docstring for why Prometheus needs no per-series
    deletion.
    """
    n_bundles = replay_mod.purge_conversation(conversation_id)
    n_scores = scores_mod.purge_conversation(conversation_id)
    n_owned, owned_reached = purge_owned_scores(conversation_id)
    n_spine, spine_reached = purge_spine(conversation_id)
    return ErasureFootprint(
        conversation_id=conversation_id,
        n_bundles=n_bundles,
        n_scores=n_scores,
        total=n_bundles + n_scores,
        n_spine=n_spine,
        spine_reached=spine_reached,
        n_owned_scores=n_owned,
        owned_reached=owned_reached,
    )
