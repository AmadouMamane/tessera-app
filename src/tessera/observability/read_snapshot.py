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
from tessera.settings import get_settings

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "SNAPSHOT_INTERVAL_S",
    "SNAPSHOT_TTL_S",
    "chrome_snapshot_key",
    "compute_snapshot_entries",
    "fleet_snapshot_key",
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

    chrome for every locale (it is cheap now that its incident sub-read is memoised), and the fleet
    rollup for the default locale over the precomputed periods. A single compute that raises omits
    only its own entry — the worker then computes that one itself, exactly as before.
    """
    import asyncio

    from tessera.api.routes.observability.fleet import _compute_fleet
    from tessera.observability.chrome import _compute_chrome_uncached

    entries: dict[str, dict[str, Any]] = {}
    for lang in _SNAPSHOT_LOCALES:
        try:
            entries[chrome_snapshot_key(lang)] = await asyncio.to_thread(
                _compute_chrome_uncached, lang
            )
        except Exception:  # noqa: S112 — best-effort: omit this entry; the leader loop logs health
            continue
    for period in _SNAPSHOT_FLEET_PERIODS:
        try:
            payload = await _compute_fleet(_DEFAULT_LOCALE, period, None)
            entries[fleet_snapshot_key(_DEFAULT_LOCALE, period)] = payload.model_dump(mode="json")
        except Exception:  # noqa: S112 — best-effort: omit this entry; the worker computes it
            continue
    return entries
