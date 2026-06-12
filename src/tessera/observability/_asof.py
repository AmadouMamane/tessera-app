"""Shared as-of-T helper (ADR 0011).

A single, robust timestamp comparison used wherever an observability signal is
filtered to "events at or before instant T". Timestamps are stored with a
``+00:00`` offset while the cockpit sends ``Z``-suffixed instants; comparing
them as strings is unreliable at the boundary, so we always parse to ``datetime``
(``datetime.fromisoformat`` accepts both forms on Python 3.12).
"""

from __future__ import annotations

from datetime import datetime

__all__ = ["occurred_before"]


def occurred_before(ts: object, at: str | None) -> bool:
    """Return whether event timestamp ``ts`` is at or before cutoff ``at``.

    ``at`` of ``None`` means "live" — every event qualifies. A malformed ``ts``
    or ``at`` fails open (the event is kept) so a bad timestamp never silently
    drops real data.
    """
    if at is None:
        return True
    if not isinstance(ts, str):
        return True
    try:
        return datetime.fromisoformat(ts) <= datetime.fromisoformat(at)
    except ValueError:
        return True
