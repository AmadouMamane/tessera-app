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
from threading import Lock
from typing import TYPE_CHECKING, Any, Final

from tessera.fsutil import atomic_write_text
from tessera.observability.logging import get_logger
from tessera.settings import get_settings

if TYPE_CHECKING:
    from pathlib import Path

_LOG = get_logger("tessera.snapshot")

__all__ = [
    "SNAPSHOT_INTERVAL_S",
    "SNAPSHOT_REFRESH_CEILING_S",
    "SNAPSHOT_TTL_S",
    "audit_overview_snapshot_key",
    "audit_page_snapshot_key",
    "batch_snapshot_key",
    "chrome_snapshot_key",
    "compute_snapshot_entries",
    "fleet_snapshot_key",
    "inbox_snapshot_key",
    "incidents_snapshot_key",
    "read_snapshot",
    "reset_read_snapshot",
    "snapshot_fingerprint",
    "snapshot_needs_recompute",
    "write_snapshot",
]

#: How often the leader recomputes and republishes the snapshot.
SNAPSHOT_INTERVAL_S: Final = 3.0
#: How old a snapshot entry a reader will still serve before falling through to compute. A small
#: multiple of the interval, so one slow/missed leader cycle does not blank the cards.
SNAPSHOT_TTL_S: Final = 10.0
#: The leader recomputes the (expensive ~2.8 s) snapshot content only when its cheap fingerprint
#: moves — the ledger head advanced or this ceiling elapsed — never on the blind interval alone. The
#: content is derived from an append-only chain, so an unchanged head proves it byte-identical
#: (``ledger_store.ledger_head_seq``: an unchanged ``max(seq)`` guarantees an unchanged result);
#: recomputing it every interval was pure waste that pinned the leader at ~100 % CPU on a STABLE
#: ledger and produced an intermittent flash on the client fleet card. This ceiling is the backstop
#: for the two things the head does NOT witness — wall-clock windows (fleet ``d7``, incidents
#: ``until=now``) and any non-ledger mutation (business_events, operator items) — forcing a periodic
#: recompute so neither can drift unbounded. Between recomputes the leader RE-STAMPS the last
#: snapshot every interval, so readers' :data:`SNAPSHOT_TTL_S` never expires and they never fall
#: through to a per-worker compute.
SNAPSHOT_REFRESH_CEILING_S: Final = 60.0

_SNAPSHOT_NAME: Final = "read_snapshot.json"
_DEFAULT_LOCALE: Final = "fr"
_SNAPSHOT_LOCALES: Final = ("fr", "de", "en")
#: Fleet periods precomputed for the default locale (the vue-ensemble default is 7 days; ``None``
#: is the all-history directory contract). Other locale/period combos fall through to compute.
_SNAPSHOT_FLEET_PERIODS: Final[tuple[str | None, ...]] = (None, "d7")


def _snapshot_path() -> Path:
    """The shared snapshot file under the per-env state dir (a bind mount all workers see)."""
    return get_settings().state_dir / _SNAPSHOT_NAME


# A cockpit page fires ~14 reads at once, each its own `read_snapshot` call, and the file is one
# ~300 KB JSON document — so parsing it per read meant ~14 full parses for a single page. Parse it
# once per file VERSION and share the parsed document across those reads. The version key is
# (path, mtime_ns, size): the leader publishes via an atomic rename every cycle, which bumps mtime,
# so a new snapshot is always re-parsed; the path guards against an isolated test's tmp file reusing
# a stale entry. Freshness stays PER ENTRY — each entry carries its own `ts`, checked against the
# wall clock below — so a cached parse never serves a stale entry as fresh. Process-local: every
# worker parses once per version; the writer (write_snapshot) invalidates its own copy.
_PARSE_CACHE_LOCK = Lock()
_PARSE_CACHE: tuple[tuple[str, int, int], dict[str, Any]] | None = None  # (version, doc)


def _reset_parse_cache() -> None:
    """Drop the parsed-document memo (writer invalidation + test isolation)."""
    global _PARSE_CACHE
    with _PARSE_CACHE_LOCK:
        _PARSE_CACHE = None


def _load_snapshot_doc() -> dict[str, Any] | None:
    """Parse the snapshot file once per version, shared across a page's reads.

    Returns the parsed top-level document, or ``None`` on any miss — absent file, unreadable,
    corrupt, or not a dict. A version-key collision (coarse mtime resolution) could only ever serve
    a document a few seconds older, which the caller's per-entry TTL check still bounds.
    """
    path = _snapshot_path()
    try:
        st = path.stat()
    except OSError:
        return None
    version = (str(path), st.st_mtime_ns, st.st_size)
    global _PARSE_CACHE
    with _PARSE_CACHE_LOCK:
        cached = _PARSE_CACHE
        if cached is not None and cached[0] == version:
            return cached[1]
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(doc, dict):
        return None
    with _PARSE_CACHE_LOCK:
        _PARSE_CACHE = (version, doc)
    return doc


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


def incidents_snapshot_key(lang: str) -> str:
    """Snapshot key for the live (at=None) incidents & playbooks overview of one locale."""
    return f"incidents:{lang}"


def audit_overview_snapshot_key() -> str:
    """Snapshot key for the unfiltered, full-window audit overview (org-wide, locale-neutral)."""
    return "audit:overview"


def audit_page_snapshot_key() -> str:
    """Snapshot key for the newest default page of the audit log (no filters, cursor 0)."""
    return "audit:page"


def read_snapshot(key: str, ttl_s: float) -> dict[str, Any] | None:
    """Return the payload published for ``key`` if it is at most ``ttl_s`` old, else ``None``.

    ``None`` on every miss — no file, no such key, a stale entry, or an unreadable/corrupt file —
    is the signal for the caller to compute. Never raises into the request path.
    """
    doc = _load_snapshot_doc()
    if doc is None:
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
    # The writer invalidates its OWN parsed-document memo: on some filesystems mtime resolution is
    # coarse enough that two writes within the same tick share a version key, so clearing here is
    # what guarantees this process re-parses the content it just published.
    _reset_parse_cache()


def reset_read_snapshot() -> None:
    """Remove the snapshot file (test isolation; a no-op when it does not exist)."""
    _snapshot_path().unlink(missing_ok=True)
    _reset_parse_cache()


def snapshot_fingerprint() -> tuple[int, int] | None:
    """A cheap witness of whether the snapshot content could have changed since the last compute.

    Returns ``(ledger_head_seq, ceiling_bucket)`` in postgres mode. Every governed act appends to
    the append-only ledger, so the head (``max(seq)``, one indexed row, sub-millisecond) moves
    whenever the ledger-derived cards could change, and an unchanged head proves them unchanged.
    The ``ceiling_bucket`` is ``int(time.time() // SNAPSHOT_REFRESH_CEILING_S)``: it rolls over
    every ceiling and forces a recompute so wall-clock windows and non-ledger mutations cannot
    drift unbounded.

    Returns ``None`` when there is no cheap head — a file ledger source has none, and a probe
    failure is treated the same — which signals the caller to recompute this cycle (the exact
    pre-head-key behavior). Never raises: the leader loop must not die on a transient head-probe
    error.
    """
    from tessera.guard.ledger_store import ledger_head_seq, ledger_source

    try:
        if ledger_source() != "postgres":
            return None
        head = ledger_head_seq()
    except Exception:
        # Any probe failure degrades to "recompute" (fingerprint None), never crashes the loop.
        return None
    return head, int(time.time() // SNAPSHOT_REFRESH_CEILING_S)


def snapshot_needs_recompute(
    last_fingerprint: tuple[int, int] | None,
    current_fingerprint: tuple[int, int] | None,
    have_snapshot: bool,
) -> bool:
    """Whether the leader must run the expensive recompute this cycle, rather than only re-stamp.

    Recompute when nothing has been published yet (``not have_snapshot``), when there is no reliable
    fingerprint (``current_fingerprint is None`` — a file source or a probe failure, so we cannot
    prove the content unchanged and must fall back to the pre-head-key behavior), or when the
    fingerprint moved (the ledger head advanced or the refresh ceiling elapsed). Otherwise the last
    snapshot is still valid and the leader only re-stamps it — the win that unpins the CPU.
    """
    return (
        not have_snapshot or current_fingerprint is None or current_fingerprint != last_fingerprint
    )


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
    # The AGIR incidents & playbooks overview per locale (live, at=None): clustering the deny
    # ledger is ~2.9 s cold and ~180 ms even warm, and its per-worker 30 s memo expires between
    # the operator's page visits — so a fresh visit recurrently lands on a cold worker and waits
    # seconds. The leader clusters it once per cycle and publishes the whole payload; workers read
    # the file. Only the default (at=None) is snapshotted — an as-of-T read computes fresh.
    from tessera.observability.incidents import compute_incidents_overview

    for lang in _SNAPSHOT_LOCALES:
        incidents_key = incidents_snapshot_key(lang)
        try:
            overview = await asyncio.to_thread(compute_incidents_overview, lang, None)
            entries[incidents_key] = {"available": True, **overview}
        except Exception as exc:
            _LOG.warning("read_snapshot.entry_omitted", entry=incidents_key, error=str(exc))
    # The audit cockpit's org-wide default overview + newest page (locale-independent): both walk
    # the whole 126 k-row chain, so the leader precomputes them once instead of every worker
    # re-validating the chain under the operator's page load.
    from tessera.api.routes.audit import compute_default_overview, compute_default_page

    audit_overview_key = audit_overview_snapshot_key()
    try:
        entries[audit_overview_key] = await asyncio.to_thread(compute_default_overview)
    except Exception as exc:
        _LOG.warning("read_snapshot.entry_omitted", entry=audit_overview_key, error=str(exc))
    audit_page_key = audit_page_snapshot_key()
    try:
        entries[audit_page_key] = await asyncio.to_thread(compute_default_page)
    except Exception as exc:
        _LOG.warning("read_snapshot.entry_omitted", entry=audit_page_key, error=str(exc))
    return entries
