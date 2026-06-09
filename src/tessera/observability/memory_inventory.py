"""Memory inventory — what the agent remembers (ADR 0010, #135; ADR 0007).

GDPR Art. 15 (access) and Art. 16 (rectification) require that a customer can
*see* and *correct* what is held about them. The rectification primitives live on
the ``/memory`` route; this module is the read-side aggregate that makes the
store legible on the dashboard: how many memories exist, for how many subjects,
of which kind, and how many are about to expire under the retention TTL.

The summariser is pure over inventory rows so it is trivially testable; the
endpoint feeds it rows from the persistent store (degrading to an empty report
when the store is unavailable, so the dashboard never errors).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = ["InventoryItem", "InventoryReport", "summarize_inventory"]

_SOON_DAYS = 30
_SAMPLE_LIMIT = 8
_TEXT_PREVIEW = 80


@dataclass(frozen=True, slots=True)
class InventoryItem:
    """One stored long-term memory, as surfaced for access/rectification."""

    memory_id: int
    subject_id: str
    kind: str
    text: str
    created_at: datetime
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class InventorySample:
    """A redacted preview row for the dashboard."""

    memory_id: int
    subject: str
    kind: str
    preview: str
    expires_in_days: int


@dataclass(frozen=True, slots=True)
class InventoryReport:
    """Aggregate view of the long-term memory store."""

    n_memories: int
    n_subjects: int
    by_kind: dict[str, int]
    n_expiring_soon: int
    samples: list[InventorySample] = field(default_factory=list)


def summarize_inventory(
    items: Iterable[InventoryItem],
    *,
    now: datetime | None = None,
    soon_days: int = _SOON_DAYS,
) -> InventoryReport:
    """Summarise stored memories into a dashboard-ready inventory.

    Args:
        items: Stored long-term memories.
        now: Reference time (defaults to current UTC).
        soon_days: A memory expiring within this many days counts as "soon".

    Returns:
        An :class:`InventoryReport` with counts and a redacted sample.
    """
    reference = now or datetime.now(UTC)
    soon_cutoff = reference + timedelta(days=soon_days)

    rows = list(items)
    by_kind: dict[str, int] = {}
    subjects: set[str] = set()
    n_soon = 0
    samples: list[InventorySample] = []
    for item in rows:
        by_kind[item.kind] = by_kind.get(item.kind, 0) + 1
        subjects.add(item.subject_id)
        if item.expires_at <= soon_cutoff:
            n_soon += 1
        if len(samples) < _SAMPLE_LIMIT:
            expires_in = max(0, (item.expires_at - reference).days)
            samples.append(
                InventorySample(
                    memory_id=item.memory_id,
                    subject=item.subject_id[:12],
                    kind=item.kind,
                    preview=item.text[:_TEXT_PREVIEW],
                    expires_in_days=expires_in,
                )
            )

    return InventoryReport(
        n_memories=len(rows),
        n_subjects=len(subjects),
        by_kind=by_kind,
        n_expiring_soon=n_soon,
        samples=samples,
    )
