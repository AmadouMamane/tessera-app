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

import sys
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


@router.get("/observability/erasure-reach")
async def observability_erasure_reach() -> dict[str, object]:
    """Whether GDPR erasure can reach every schema holding subject data (ADR 0014).

    `/observability/erasure-coverage` answers "how much telemetry is IN SCOPE for an erasure".
    This answers the question underneath it, which nothing asked: **is the scope the whole
    store?** Erasure writes bare table names resolved through ``search_path``, so it clears
    this environment's schema and no other. Rows that predate the ADR-0014 isolation sit in
    ``public``, and `DELETE /memory` reports success over every one of them.

    Measured 2026-08-01 on the live local Postgres: **138 subjects and 1 236 conversations in
    ``public``, last written 2026-06-24, outside every erasure path.**

    ``unreachable_subjects > 0`` is a compliance finding, not a metric. It degrades to
    ``available: false`` on a connection failure — unlike the count itself, which must never
    read as zero when it could not be taken.
    """
    import psycopg

    from tessera.memory.erasure_reach import assess_erasure_reach
    from tessera.settings import get_settings

    settings = get_settings()
    try:
        async with await psycopg.AsyncConnection.connect(str(settings.postgres.dsn)) as conn:
            reach = await assess_erasure_reach(conn, settings.pg_schema)
    except Exception as exc:  # never break the page — but never claim zero either
        sys.stderr.write(f"tessera.observability.erasure_reach: failed: {exc}\n")
        return {"available": False}
    return {"available": True, **asdict(reach)}
