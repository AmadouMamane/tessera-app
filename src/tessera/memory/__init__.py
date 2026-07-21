"""Agent memory — durable thread state plus a pluggable memory backend.

See ADR 0007 for the full design. The public surface is intentionally tiny:

* the contract types in :mod:`tessera.memory.protocol`;
* :func:`get_memory_backend`, which resolves the configured backend.

Everything else (tiers, adapters, governance, the checkpointer) is an
implementation detail behind that contract.
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import lru_cache
from typing import TYPE_CHECKING

from tessera.memory.protocol import (
    EntityLedger,
    MemoryBackend,
    MemoryContext,
    MemoryItem,
    MemoryScope,
    TurnRecord,
)
from tessera.settings import get_settings

if TYPE_CHECKING:
    from uuid import UUID

    from tessera.settings import LanguageCode

__all__ = [
    "EntityLedger",
    "MemoryBackend",
    "MemoryContext",
    "MemoryItem",
    "MemoryScope",
    "TurnRecord",
    "get_memory_backend",
    "memory_backend_for",
    "memory_backend_for_state",
    "scope_for",
]

#: The first-party tiers a per-agent knob may select (ADR 0036). The external
#: adapters are deliberately absent: they are optional extras that may not be
#: installed, and a knob that can select an uninstalled backend would be a lie.
_FIRST_PARTY_TIERS = ("window", "summary", "persistent")


def scope_for(
    conversation_id: UUID,
    language: LanguageCode,
    *,
    subject_id: str | None = None,
) -> MemoryScope:
    """Build a :class:`MemoryScope`.

    ``subject_id`` is the long-term identity key. When the caller supplies a
    stable identifier (e.g. a client-persisted id, or a real authenticated
    customer once auth exists), cross-session memory is keyed by it. Absent one,
    it falls back to the conversation id — per-thread memory only (ADR 0007,
    "Identity").
    """
    return MemoryScope(
        conversation_id=conversation_id,
        subject_id=subject_id or str(conversation_id),
        language=language,
    )


@lru_cache(maxsize=1)
def get_memory_backend() -> MemoryBackend:
    """Return the process-wide memory backend selected by settings.

    Backends are imported lazily so the default install needs none of the
    optional external engines. Tests that flip ``TESSERA_MEMORY__BACKEND`` must
    call ``get_memory_backend.cache_clear()`` after mutating the environment.
    """
    backend = get_settings().memory.backend
    if backend == "window":
        from tessera.memory.window import WindowBackend

        return WindowBackend()
    if backend == "summary":
        from tessera.memory.summary import SummaryBackend

        return SummaryBackend()
    if backend == "persistent":
        from tessera.memory.persistent import PersistentBackend

        return PersistentBackend()
    if backend == "langmem":
        from tessera.memory.adapters.langmem import LangMemBackend

        return LangMemBackend()
    if backend == "mem0":
        from tessera.memory.adapters.mem0 import Mem0Backend

        return Mem0Backend()
    from tessera.memory.adapters.zep import ZepBackend

    return ZepBackend()


@lru_cache(maxsize=16)
def _tier_backend(tier: str, history_window: int | None) -> MemoryBackend:
    """One cached instance per (first-party tier, window) pair (ADR 0036)."""
    if tier == "window":
        from tessera.memory.window import WindowBackend

        return WindowBackend(history_window=history_window)
    if tier == "summary":
        from tessera.memory.summary import SummaryBackend

        return SummaryBackend(history_window=history_window)
    from tessera.memory.persistent import PersistentBackend

    return PersistentBackend(history_window=history_window)


def memory_backend_for(tier: str | None = None, history_window: int | None = None) -> MemoryBackend:
    """The backend serving one agent's turn (ADR 0036) — org singleton by default.

    ``tier`` names a first-party tier (``window`` / ``summary`` /
    ``persistent``); ``history_window`` overrides the verbatim recency window.
    Both unset → the process-wide singleton, exactly the historical behaviour.
    A window override with no tier applies to the ORG tier — unless the org
    runs an external adapter, whose constructor takes no window: the singleton
    serves and the gap is logged, never silently absorbed.
    """
    if tier is None and history_window is None:
        return get_memory_backend()
    if tier is None:
        org_tier = get_settings().memory.backend
        if org_tier not in _FIRST_PARTY_TIERS:
            import sys

            sys.stderr.write(
                f"tessera.memory: per-agent window ignored — org backend {org_tier!r} "
                "is an external adapter (ADR 0036)\n"
            )
            return get_memory_backend()
        tier = org_tier
    if tier not in _FIRST_PARTY_TIERS:
        return get_memory_backend()
    return _tier_backend(tier, history_window)


def memory_backend_for_state(state: Mapping[str, object]) -> MemoryBackend:
    """Resolve one turn's backend from its seam-stamped state.

    Loading context before generation and recording the completed turn must
    call this same resolver.  Otherwise a per-agent tier can read from one
    store and write into the organisation default, making memory appear to
    vanish on the next turn.
    """
    raw = state.get("memory")
    memory = raw if isinstance(raw, Mapping) else {}
    raw_tier = memory.get("tier")
    raw_window = memory.get("window")
    tier = raw_tier if isinstance(raw_tier, str) else None
    window = (
        int(raw_window)
        if isinstance(raw_window, int | float) and not isinstance(raw_window, bool)
        else None
    )
    return memory_backend_for(tier, window)
