"""Cross-tenant leakage detection (ADR 0010, idea #74).

In a multi-tenant banking deployment the cardinal sin is tenant A's data
surfacing for tenant B — a document or a memory keyed to one customer appearing
in another's context. Tessera has no formal tenant boundary yet (ADR 0007,
"Identity"), so the *subject/conversation id* is the tenant proxy: a turn's
delivered context should only ever reference its **own** subject.

This module detects the breach: it scans each turn's context for identifiers
(UUID-shaped subject/conversation ids) that differ from the turn's own, and flags
any foreign id as a cross-tenant leak. The detector is pure over
``(conversation_id, context)`` pairs; the endpoint feeds it captured turns. It is
the observability half of a control — the fix is per-tenant filtering at
retrieval and memory recall — but surfacing the leak rate is what proves the
boundary holds.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = ["CrossTenantLeak", "CrossTenantReport", "detect_cross_tenant"]

# UUID v4-shaped identifiers (the conversation/subject key format).
_ID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.IGNORECASE
)


@dataclass(frozen=True, slots=True)
class CrossTenantLeak:
    """A turn whose context referenced a foreign subject."""

    conversation_id: str
    foreign_ids: list[str]


@dataclass(frozen=True, slots=True)
class CrossTenantReport:
    """Cross-tenant leakage over the scanned turns."""

    n_turns: int
    n_leaks: int
    leak_rate: float
    leaks: list[CrossTenantLeak] = field(default_factory=list)


def detect_cross_tenant(turns: Iterable[tuple[str, str]]) -> CrossTenantReport:
    """Detect foreign-subject identifiers in each turn's context.

    Args:
        turns: ``(conversation_id, context)`` pairs.

    Returns:
        A :class:`CrossTenantReport`; a turn leaks when its context contains a
        UUID-shaped identifier other than its own conversation id.
    """
    n_turns = 0
    leaks: list[CrossTenantLeak] = []
    for conversation_id, context in turns:
        n_turns += 1
        own = conversation_id.lower()
        found = {m.group(0).lower() for m in _ID_RE.finditer(context)}
        foreign = sorted(fid for fid in found if fid != own)
        if foreign:
            leaks.append(CrossTenantLeak(conversation_id=conversation_id, foreign_ids=foreign))

    return CrossTenantReport(
        n_turns=n_turns,
        n_leaks=len(leaks),
        leak_rate=len(leaks) / n_turns if n_turns else 0.0,
        leaks=leaks,
    )
