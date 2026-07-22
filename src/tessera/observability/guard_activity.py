"""Public-safe guard-activity rollup for the launcher band (ADR 0009).

Two aggregate counters, each read from its own witness (ADR 0026 — a witness
interrogates the thing):

* ``checked_today`` — user turns recorded in the durable transcript since local
  midnight (ADR 0040: the transcript is the single witness of turns, and every
  persisted user turn entered through the input guard). Test turns (canaries,
  operator trials) are **included**: the guard checks each of them for real, and
  this counter measures the guard's activity, not business traffic. The
  launcher's info popover states that scope in its own words.
* ``blocked_today`` — input-guard denials since local midnight, read from the
  tamper-evident audit trail. The guard only writes an entry when it actually
  decides, so a recorded denial is its own witness.

The ledger scan is TTL-cached: the public launcher polls this read, and one walk
per window is enough — an anonymous visitor must never be able to trigger a
fresh ledger scan per request.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final

from tessera.guard.ledger_store import read_ledger_entries
from tessera.memory.transcript import count_user_turns_since

if TYPE_CHECKING:
    from pathlib import Path

_CACHE_TTL_SECONDS: Final[float] = 60.0

_cache_lock = threading.Lock()
_blocked_cache: tuple[float, str, int] | None = None


def local_midnight(now: datetime | None = None) -> datetime:
    """Start of "today" in the server's local timezone, as an aware datetime.

    Args:
        now: Optional aware instant to anchor on (defaults to the current time).

    Returns:
        Local midnight of the day containing ``now``.
    """
    local = (now or datetime.now(UTC)).astimezone()
    return local.replace(hour=0, minute=0, second=0, microsecond=0)


def _parse_dt(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def blocked_since(since: datetime, *, path: Path | None = None) -> int:
    """Count input-guard denials recorded at or after ``since``.

    One refused message counts once, however many decision records the entry
    carries; tool-level denials (``target != "user_input"``) are out of scope —
    the launcher line speaks about *messages*.

    Args:
        since: Aware lower bound (inclusive) on the decision timestamp.
        path: Optional ledger path override (tests inject a temp chain here).

    Returns:
        The number of refused messages since ``since``.
    """
    count = 0
    for entry in read_ledger_entries(path, since=since):
        if entry.get("type") != "tessera.guard.audit" or entry.get("outcome") != "denied":
            continue
        decisions = entry.get("decisions")
        if not isinstance(decisions, list):
            continue
        for decision in decisions:
            if not isinstance(decision, dict):
                continue
            if decision.get("target") != "user_input" or decision.get("decision") != "deny":
                continue
            when = _parse_dt(decision.get("occurred_at"))
            if when is not None and when >= since:
                count += 1
                break
    return count


@dataclass(frozen=True, slots=True)
class GuardExchangeCounts:
    """Real user exchanges controlled by the guard in a journal window."""

    controlled: int
    blocked: int


def exchange_counts_since(since: datetime, *, path: Path | None = None) -> GuardExchangeCounts:
    """Count real input-guard exchanges from the S1 journal.

    One ``tessera.guard.audit`` entry targeting ``user_input`` is one controlled exchange. A
    refusal increments the blocked bucket once, regardless of how many decision records explain
    it. Entries stamped ``synthetic`` are excluded at this read seam (ADR 0019 section 4); old
    entries without the field predate the stamp and remain real by default.

    Args:
        since: Inclusive aware lower bound.
        path: Optional ledger path override for tests.

    Returns:
        Controlled and blocked counts over real traffic only.
    """
    controlled_turns: set[str] = set()
    blocked_turns: set[str] = set()
    for entry in read_ledger_entries(path, since=since):
        if (
            entry.get("type") != "tessera.guard.audit"
            or entry.get("target") != "user_input"
            or entry.get("synthetic") is True
        ):
            continue
        when = _parse_dt(entry.get("occurred_at"))
        if when is None or when < since:
            continue
        turn_id = entry.get("turn_id")
        if not isinstance(turn_id, str) or not turn_id:
            # Direct guard probes are audit evidence, but they are not business exchanges. A
            # chat turn carries its server-issued identity at emit time; without it the reader
            # cannot honestly classify the entry as real traffic.
            continue
        controlled_turns.add(turn_id)
        if entry.get("outcome") == "denied":
            blocked_turns.add(turn_id)
    return GuardExchangeCounts(controlled=len(controlled_turns), blocked=len(blocked_turns))


def _blocked_today_cached(since: datetime) -> int:
    """``blocked_since`` behind a short TTL cache keyed on the day window."""
    global _blocked_cache
    key = since.isoformat()
    with _cache_lock:
        if (
            _blocked_cache is not None
            and _blocked_cache[1] == key
            and time.monotonic() - _blocked_cache[0] < _CACHE_TTL_SECONDS
        ):
            return _blocked_cache[2]
    count = blocked_since(since)
    with _cache_lock:
        _blocked_cache = (time.monotonic(), key, count)
    return count


async def build_guard_activity() -> dict[str, object]:
    """The launcher's guard-activity aggregate.

    Returns:
        ``{"checked_today", "blocked_today", "since"}`` — counts a public
        visitor may see (ADR 0009: aggregates only, never per-case detail).
    """
    since = local_midnight()
    checked = await count_user_turns_since(since)
    blocked = _blocked_today_cached(since)
    return {"checked_today": checked, "blocked_today": blocked, "since": since.isoformat()}


__all__ = [
    "GuardExchangeCounts",
    "blocked_since",
    "build_guard_activity",
    "exchange_counts_since",
    "local_midnight",
]
