"""Observability routes — memory surface. AGGREGATES ONLY.

The two subject-scoped reads that lived here moved to :mod:`.pii` behind
``require_subject_reader`` (audit 2026-07-12, **P1 F-4**): ``/observability/memory-inventory``
(whose "redacted" samples are the first 80 characters of a stored memory) and
``/observability/erasure/{conversation_id}`` (which answers *"how much do you hold about this
person?"* for a caller-named subject).

What remains are counts: memory-layer activity, and the erasure surface's totals. Both touch
subject records to compute them and neither carries one out — ``ErasureCoverage`` is three
integers.
"""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter

from tessera.api.routes.observability._common import (
    _read_audit_entries,
)
from tessera.observability import (
    erasure as erasure_mod,
    memory_obs as memory_obs_mod,
    replay as replay_mod,
)
from tessera.observability.spine.adapters import read_scores

router = APIRouter()


@router.get("/observability/memory")
def observability_memory() -> dict[str, object]:
    """Memory-layer activity: writes, recall hit/miss, stored-injection caught (#23)."""
    return asdict(memory_obs_mod.aggregate_memory_audit(_read_audit_entries()))


@router.get("/observability/erasure-coverage")
def observability_erasure_coverage() -> dict[str, object]:
    """The telemetry-erasure surface: conversations, bundles, scores in scope (#180).

    Aggregate: ``ErasureCoverage`` is ``(n_conversations, n_bundles, n_scores)``. The
    conversation ids are counted into a set and discarded — they never reach the wire.
    """
    return asdict(erasure_mod.coverage(replay_mod.recent_bundles(), read_scores()))
