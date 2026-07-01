"""Ledger read filter — the tamper-evident ``audit.log`` / S1 journal (ADR 0015 carve-out).

These hash-chained ledgers **stay local**: their sequential chain *is* the security
property (DORA / BaFin evidence). Exporting them to Langfuse would break tamper-evidence,
so "no jsonl" explicitly does not apply to them. They already carry ``agent_id`` and
``occurred_at``, so reading them directly, filtered by scope, is correct — they are not the
"two parallel paths" smell, they are the compliance ledger.

This module holds the *filtering* helpers over already-read entries; the physical read is
:meth:`~tessera.observability.spine.adapters.current.CurrentStoresReader.audit_entries`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tessera.observability._asof import occurred_before

if TYPE_CHECKING:
    from tessera.observability.spine.scope import Scope

__all__ = ["events_for_scope"]


def events_for_scope(entries: list[dict[str, object]], scope: Scope) -> list[dict[str, object]]:
    """Ledger entries at/before the scope's instant, optionally one agent's.

    A per-agent scope keeps only entries stamped with that ``agent_id``; the org view keeps
    all. As-of-T keeps entries whose ``occurred_at`` is ≤ the instant (ADR 0011).
    """
    kept = [e for e in entries if occurred_before(e.get("occurred_at"), scope.at)]
    if scope.agent_id is not None:
        kept = [e for e in kept if e.get("agent_id") == scope.agent_id]
    return kept
