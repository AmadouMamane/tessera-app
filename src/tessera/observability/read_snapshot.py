"""Leader-computed shared read-snapshot for the hottest cockpit reads (ADR 0046).

ADR 0044 runs the agent as N workers, each with its own in-process read memo. A cockpit page fires
~14 reads at once, they scatter across the workers, and the heaviest (chrome, fleet) recompute
independently on N workers under that concurrent burst — contending on each worker's GIL. This
module lets the LEADER compute those reads once, off the request path, and publish them to a single
JSON file in the shared state dir; every worker reads the file instead of recomputing.

The snapshot is a CACHE, never a source of truth: it is derived, best-effort, and every reader
degrades to its own compute when the file is absent (leader not up yet), stale (leader fell behind),
unreadable, or lacks the requested argument combination (a non-default locale/period, an as-of-T
read). It carries only public-aggregate reads — never subject-scoped or PII surfaces.

Freshness: the leader refreshes every :data:`SNAPSHOT_INTERVAL_S`; readers accept an entry up to
:data:`SNAPSHOT_TTL_S` old, so a single missed cycle serves the last snapshot rather than blanking
the cards, then falls through to compute. The stored timestamp is wall-clock (:func:`time.time`)
because readers and the writer are different processes — a monotonic clock is not comparable across
them; the same machine's wall clock is.
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any, Final

from tessera.fsutil import atomic_write_text
from tessera.observability.logging import get_logger
from tessera.settings import get_settings

if TYPE_CHECKING:
    from pathlib import Path

_LOG = get_logger("tessera.snapshot")

__all__ = [
    "SNAPSHOT_INTERVAL_S",
    "SNAPSHOT_TTL_S",
    "batch_snapshot_key",
    "chrome_snapshot_key",
    "compute_snapshot_entries",
    "fleet_snapshot_key",
    "inbox_snapshot_key",
    "read_snapshot",
    "reset_read_snapshot",
    "write_snapshot",
]

#: How often the leader recomputes and republishes the snapshot.
SNAPSHOT_INTERVAL_S: Final = 3.0
#: How old a snapshot entry a reader will still serve before falling through to compute. A small
#: multiple of the interval, so one slow/missed leader cycle does not blank the cards.
SNAPSHOT_TTL_S: Final = 10.0

_SNAPSHOT_NAME: Final = "read_snapshot.json"
_DEFAULT_LOCALE: Final = "fr"
_SNAPSHOT_LOCALES: Final = ("fr", "de", "en")
#: Fleet periods precomputed for the default locale (the vue-ensemble default is 7 days; ``None``
#: is the all-history directory contract). Other locale/period combos fall through to compute.
_SNAPSHOT_FLEET_PERIODS: Final[tuple[str | None, ...]] = (None, "d7")


def _snapshot_path() -> Path:
    """The shared snapshot file under the per-env state dir (a bind mount all workers see)."""
    return get_settings().state_dir / _SNAPSHOT_NAME


def chrome_snapshot_key(lang: str) -> str:
    """Snapshot key for the chrome badges/notifications of one locale."""
    return f"chrome:{lang}"


def fleet_snapshot_key(lang: str, period: str | None) -> str:
    """Snapshot key for one locale + period fleet rollup (``None`` = the all-history read)."""
    return f"fleet:{lang}:{period or 'all'}"


def batch_snapshot_key(lang: str) -> str:
    """Snapshot key for the whole batch panel set of one locale (default scope, agent all)."""
    return f"batch:{lang}"


def inbox_snapshot_key(lang: str, agent: str) -> str:
    """Snapshot key for the inbox overview of one locale + agent scope (default agent = ``all``)."""
    return f"inbox:{lang}:{agent}"


def read_snapshot(key: str, ttl_s: float) -> dict[str, Any] | None:
    """Return the payload published for ``key`` if it is at most ``ttl_s`` old, else ``None``.

    ``None`` on every miss — no file, no such key, a stale entry, or an unreadable/corrupt file —
    is the signal for the caller to compute. Never raises into the request path.
    """
    try:
        doc = json.loads(_snapshot_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(doc, dict):
        return None
    entry = doc.get(key)
    if not isinstance(entry, dict):
        return None
    ts = entry.get("ts")
    if not isinstance(ts, int | float) or time.time() - ts >= ttl_s:
        return None
    payload = entry.get("payload")
    return payload if isinstance(payload, dict) else None


def write_snapshot(entries: dict[str, dict[str, Any]]) -> None:
    """Atomically publish ``{key: payload}`` as one stamped document. Leader-only."""
    now = time.time()
    doc = {key: {"ts": now, "payload": payload} for key, payload in entries.items()}
    atomic_write_text(_snapshot_path(), json.dumps(doc, ensure_ascii=False))


def reset_read_snapshot() -> None:
    """Remove the snapshot file (test isolation; a no-op when it does not exist)."""
    _snapshot_path().unlink(missing_ok=True)


async def compute_snapshot_entries() -> dict[str, dict[str, Any]]:
    """Compute the default-locale hot reads for the leader to publish (best-effort per entry).

    chrome for every locale (cheap now its incident sub-read is memoised); the fleet rollup for the
    default locale over the precomputed periods; the WHOLE batch panel set for the default locale
    (default scope agent=all, at=None — computing it here also keeps the underlying ledger/score
    caches warm on the leader, which is what stops a cold request-path fan-out from stampeding); and
    the default inbox overview. A compute that raises omits only its OWN entry — the worker then
    computes that one itself, exactly as before — and it is LOGGED (``read_snapshot.entry_omitted``,
    with the error) so a panel that fails persistently is loud, not a silent hole in the snapshot.
    """
    import asyncio

    from tessera.api.routes.observability.batch import compute_all_panels
    from tessera.api.routes.observability.fleet import _compute_fleet
    from tessera.observability import inbox as inbox_mod
    from tessera.observability.chrome import _compute_chrome_uncached

    entries: dict[str, dict[str, Any]] = {}
    for lang in _SNAPSHOT_LOCALES:
        chrome_key = chrome_snapshot_key(lang)
        try:
            entries[chrome_key] = await asyncio.to_thread(_compute_chrome_uncached, lang)
        except Exception as exc:
            _LOG.warning("read_snapshot.entry_omitted", entry=chrome_key, error=str(exc))
    for period in _SNAPSHOT_FLEET_PERIODS:
        fleet_key = fleet_snapshot_key(_DEFAULT_LOCALE, period)
        try:
            payload = await _compute_fleet(_DEFAULT_LOCALE, period, None)
            entries[fleet_key] = payload.model_dump(mode="json")
        except Exception as exc:
            _LOG.warning("read_snapshot.entry_omitted", entry=fleet_key, error=str(exc))
    batch_key = batch_snapshot_key(_DEFAULT_LOCALE)
    try:
        entries[batch_key] = await compute_all_panels(_DEFAULT_LOCALE)
    except Exception as exc:
        _LOG.warning("read_snapshot.entry_omitted", entry=batch_key, error=str(exc))
    inbox_key = inbox_snapshot_key(_DEFAULT_LOCALE, "all")
    try:
        overview = await asyncio.to_thread(
            inbox_mod.compute_inbox_overview, lang=_DEFAULT_LOCALE, agent_id=None
        )
        entries[inbox_key] = {"available": True, "agent": "all", **overview}
    except Exception as exc:
        _LOG.warning("read_snapshot.entry_omitted", entry=inbox_key, error=str(exc))
    return entries
