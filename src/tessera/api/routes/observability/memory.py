"""Observability routes — memory surface."""

from __future__ import annotations

import sys
from dataclasses import asdict

from fastapi import APIRouter

from tessera.api.routes.observability._common import (
    _read_audit_entries,
)
from tessera.observability import (
    erasure as erasure_mod,
    memory_inventory as memory_inventory_mod,
    memory_obs as memory_obs_mod,
    replay as replay_mod,
)
from tessera.observability.spine.adapters import read_scores

router = APIRouter()


@router.get("/observability/memory")
async def observability_memory() -> dict[str, object]:
    """Memory-layer activity: writes, recall hit/miss, stored-injection caught (#23)."""
    return asdict(memory_obs_mod.aggregate_memory_audit(_read_audit_entries()))


@router.get("/observability/erasure-coverage")
async def observability_erasure_coverage() -> dict[str, object]:
    """The telemetry-erasure surface: conversations, bundles, scores in scope (#180)."""
    return asdict(erasure_mod.coverage(replay_mod.recent_bundles(), read_scores()))


@router.get("/observability/erasure/{conversation_id}")
async def observability_erasure_preview(conversation_id: str) -> dict[str, object]:
    """Preview the telemetry that a GDPR erasure of this subject would purge (#180)."""
    return asdict(
        erasure_mod.footprint(
            conversation_id,
            bundles=replay_mod.recent_bundles(),
            scores=read_scores(),
        )
    )


@router.get("/observability/memory-inventory")
async def observability_memory_inventory() -> dict[str, object]:
    """What the agent remembers: long-term store inventory (GDPR access, #135)."""
    from tessera.memory.persistent import list_inventory
    from tessera.observability.memory_inventory import InventoryItem

    try:
        rows = await list_inventory()
    except Exception as exc:  # store may be offline / empty — never break the dashboard
        sys.stderr.write(f"tessera.observability.memory_inventory: failed: {exc}\n")
        return asdict(memory_inventory_mod.summarize_inventory([]))
    items = [
        InventoryItem(
            memory_id=row.memory_id,
            subject_id=row.subject_id,
            kind=row.kind,
            text=row.text,
            created_at=row.created_at,
            expires_at=row.expires_at,
        )
        for row in rows
    ]
    return asdict(memory_inventory_mod.summarize_inventory(items))
