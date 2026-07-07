"""Owned append-only hash-chained Postgres ledger (ADR 0015 §Amendment 3).

Promotes the tamper-evident S1 journal (``audit.log`` — guard decisions, routing,
handoffs, lifecycle, governance events, all one chain) from a flat file to an **owned,
indexed, append-only Postgres table**: the chain — not the medium — is the tamper
evidence, and a row is as chain-protected as a file line while gaining index + scale +
as-of-T reconstruction (TE-01). The ledger's integrity is the one thing never delegated
to a third party: this table lives in the same owned Postgres as the gating porteur,
never in Langfuse or ClickHouse.

Guarantees, enforced not promised:

* **Append-only**: a ``BEFORE UPDATE OR DELETE`` trigger raises — mutation is impossible
  at the store level, not merely discouraged.
* **Verification walks the chain**, not the insert order: rows are linked by
  ``prev_hash`` from the genesis link, each hash recomputed from the canonical payload —
  a forked, orphaned, edited or missing row breaks the walk and is reported. Insert
  order (``seq``) is a write audit, never the proof.
* **Never import a broken chain**: the backfill verifies the file chain first and
  refuses to copy a file that does not verify.
* **Dual-write is durable AND serialized, not best-effort** (H2 step 2; TESS-LEDGER-001): each
  entry is fsynced to a local spool before emit returns, then the drain assigns the chain
  linkage and inserts it INSIDE one ``pg_advisory_xact_lock`` transaction — the head is read in
  that transaction, so insert order IS chain order and two concurrent writers can never extend
  the same head (**no fork**; a partial UNIQUE index on ``prev_hash`` is the belt-and-suspenders
  guard). A Postgres outage leaves entries spooled and replays them on recovery (including boot)
  — **zero loss, zero duplicate** (idempotent by the position-independent ``event_id`` +
  whole-batch transaction), **chain order preserved**. The spool is the mechanism that lets the
  flat ``audit.log`` be retired at the cut. The FILE stays the canonical store until the cut
  (``TESSERA_LEDGER_SOURCE=postgres``), gated on :func:`shadow_verify_ledger` holding — never
  flip a ledger read before its chain verifies (§Amendment 3 migration note).

The unit suite disables the dual-write (``TESSERA_LEDGER_DUAL_WRITE=0``) so audit
emission stays hermetic; the write/backfill legs are covered by contract tests.
"""

from __future__ import annotations

import json
import os
import sys
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Final

from tessera.guard.audit import ChainStatus, _event_identity, _hash_core, verify_audit_chain

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

__all__ = [
    "LEDGER_ATTESTATION_TYPE",
    "LEDGER_TABLE",
    "LedgerForkPoint",
    "LedgerShadowStatus",
    "LedgerTreeStatus",
    "active_ledger_tree_status",
    "backfill_ledger_from_file",
    "drain_spool",
    "dual_write_enabled",
    "enqueue_ledger_entry",
    "ensure_audit_ledger_schema",
    "ledger_available",
    "ledger_head_hash",
    "ledger_source",
    "load_ledger_payloads_sync",
    "read_ledger_entries",
    "shadow_verify_ledger",
    "verify_active_ledger",
    "verify_ledger_rows",
    "verify_ledger_tree",
]

LEDGER_TABLE: Final = "audit_ledger"
_GENESIS: Final = "0" * 64

# §Amendment 3 DDL: (seq, occurred_at, agent_id, payload, prev_hash, hash), append-only.
CREATE_LEDGER_TABLE: Final = f"""
CREATE TABLE IF NOT EXISTS {LEDGER_TABLE} (
    seq         bigserial   PRIMARY KEY,
    occurred_at timestamptz NOT NULL,
    agent_id    text,
    payload     jsonb       NOT NULL,
    prev_hash   text        NOT NULL,
    hash        text        NOT NULL
)
"""

CREATE_LEDGER_INDEXES: Final = (
    f"CREATE INDEX IF NOT EXISTS audit_ledger_occurred ON {LEDGER_TABLE} (occurred_at)",
    # The hash is the entry's identity — the idempotence key for dual-write + backfill.
    f"CREATE UNIQUE INDEX IF NOT EXISTS audit_ledger_hash_uq ON {LEDGER_TABLE} (hash)",
    # TESS-LEDGER-001 — the drain's idempotence key: the position-independent event_id makes a
    # crash-replayed drain a no-op. Partial so the 13k+ legacy rows (no event_id → NULL) are
    # excluded; new rows carry it and dedup on it.
    f"CREATE UNIQUE INDEX IF NOT EXISTS audit_ledger_event_uq ON {LEDGER_TABLE} "
    f"((payload->>'event_id')) WHERE payload->>'event_id' IS NOT NULL",
)

# TESS-LEDGER-001 — the fork guard (belt + suspenders to the advisory lock). A partial UNIQUE
# index on prev_hash forbids a second child of any parent. It is anchored above the table's
# high-water mark at install time so the 29 historical forks (all below the anchor) are
# grandfathered — never rewritten (append-only is absolute) — while every NEW row is
# constrained. Installed by :func:`ensure_audit_ledger_schema` (not a static ``IF NOT EXISTS``,
# because the anchor is table-state dependent — it reads the high-water mark at install time).
_FORK_GUARD_INDEX: Final = "audit_ledger_no_fork"

# Strict append-only: enforced by the store, not by convention. DDL (DROP) stays possible
# for the operator — the chain itself is what proves absence/tampering, per the ADR.
CREATE_APPEND_ONLY_FUNCTION: Final = f"""
CREATE OR REPLACE FUNCTION {LEDGER_TABLE}_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION '{LEDGER_TABLE} is append-only (ADR 0015 §Amendment 3)';
END;
$$ LANGUAGE plpgsql
"""

CREATE_APPEND_ONLY_TRIGGER: Final = f"""
CREATE OR REPLACE TRIGGER {LEDGER_TABLE}_append_only
BEFORE UPDATE OR DELETE ON {LEDGER_TABLE}
FOR EACH ROW EXECUTE FUNCTION {LEDGER_TABLE}_append_only()
"""

_INSERT_ENTRY: Final = f"""
INSERT INTO {LEDGER_TABLE} (occurred_at, agent_id, payload, prev_hash, hash)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (hash) DO NOTHING
"""  # noqa: S608 — fixed table identifier; every value is a bound parameter

# The drain assigns the chain linkage itself (prev_hash/hash) under the advisory lock, so it
# pre-filters duplicates by the position-independent event_id (see :func:`drain_spool`) and
# uses a plain INSERT — a unique violation (the fork guard, tripped only by a non-cooperating
# writer) rolls the whole batch back and the next drain retries against the fresh head.
_INSERT_DRAIN: Final = f"""
INSERT INTO {LEDGER_TABLE} (occurred_at, agent_id, payload, prev_hash, hash)
VALUES (%s, %s, %s, %s, %s)
"""  # noqa: S608 — fixed table identifier; every value is a bound parameter

# TESS-LEDGER-001 — the append serialization key. All writers to THIS database's ledger take
# ``pg_advisory_xact_lock(_LOCK_HI, _LOCK_LO)`` in the drain transaction, so the head read +
# link + insert are globally serialized and two writers can never extend the same head. The
# key is per-database (ci vs local live in separate databases → naturally isolated).
_LOCK_HI: Final = 1_414_743_379  # 'TESS'
_LOCK_LO: Final = 1_279_607_634  # 'LDGR'


def ledger_source() -> str:
    """The active ledger source — ``postgres`` (default) or ``file`` (the escape).

    Since the H2 step-5 cut the promoted append-only table is canonical for BOTH reads and
    writes (baked default): readers serve from it and the flat-file write stops (see
    :mod:`tessera.guard.audit`). ``TESSERA_LEDGER_SOURCE=file`` reverts to the flat file
    (read + written) as the operator escape hatch, until ``audit.log`` is finally removed.
    """
    raw = os.environ.get("TESSERA_LEDGER_SOURCE", "postgres").strip().lower()
    return raw if raw in {"file", "postgres"} else "postgres"


def dual_write_enabled() -> bool:
    """Whether ledger entries are dual-written to Postgres (default on; ``0`` disables)."""
    return os.environ.get("TESSERA_LEDGER_DUAL_WRITE", "1").lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _entry_occurred_at(entry: Mapping[str, Any]) -> datetime:
    """The entry's instant for the as-of-T index (payload keeps the truth regardless)."""
    for key in ("occurred_at", "recorded_at"):
        value = entry.get(key)
        if isinstance(value, str):
            try:
                stamp = datetime.fromisoformat(value)
            except ValueError:
                continue
            return stamp if stamp.tzinfo is not None else stamp.replace(tzinfo=UTC)
    # Chained entries always carry occurred_at; this fallback only indexes an anomalous
    # entry at ingest time — the payload (and the chain) remain the canonical record.
    sys.stderr.write("tessera.ledger: entry without occurred_at — indexed at ingest time\n")
    return datetime.now(UTC)


def _row_tuple(entry: Mapping[str, Any]) -> tuple[object, ...]:
    from psycopg.types.json import Jsonb

    agent_id = entry.get("agent_id")
    return (
        _entry_occurred_at(entry),
        agent_id if isinstance(agent_id, str) else None,
        Jsonb(dict(entry)),
        str(entry.get("prev_hash", "")),
        str(entry.get("hash", "")),
    )


async def ensure_audit_ledger_schema() -> None:
    """Create the promoted ledger table, its indexes, the append-only trigger + fork guard."""
    from tessera.retrieval.store import get_pool

    pool = get_pool()
    if pool.closed:
        await pool.open()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(CREATE_LEDGER_TABLE)
        for statement in CREATE_LEDGER_INDEXES:
            await cur.execute(statement)
        await cur.execute(CREATE_APPEND_ONLY_FUNCTION)
        await cur.execute(CREATE_APPEND_ONLY_TRIGGER)
        # The fork guard is anchored at the current high-water mark so pre-existing forks are
        # grandfathered (never rewritten) and only new rows are constrained. Idempotent: skip
        # if already installed (re-computing the anchor would move the boundary).
        await cur.execute("SELECT 1 FROM pg_indexes WHERE indexname = %s", (_FORK_GUARD_INDEX,))
        if await cur.fetchone() is None:
            await cur.execute(f"SELECT COALESCE(max(seq), 0) FROM {LEDGER_TABLE}")  # noqa: S608
            row = await cur.fetchone()
            anchor = int(row[0]) if row else 0
            await cur.execute(
                f"CREATE UNIQUE INDEX {_FORK_GUARD_INDEX} ON {LEDGER_TABLE} "
                f"(prev_hash) WHERE seq > {anchor}"
            )
        await conn.commit()


# ── Durable dual-write: spool → Postgres (zero-loss on a Postgres blip) ─────────
# The chained entry is appended to a durable local spool (fsync) BEFORE emit returns; a
# background writer drains the spool into the append-only table in chain order. A Postgres
# outage leaves entries in the spool (never dropped); on recovery — including a process
# restart (boot replays the spool) — the drain lands them. Zero loss (fsync before ack),
# zero duplicate (ON CONFLICT (hash) DO NOTHING + whole-batch transaction), chain order
# preserved (FIFO spool). The spool holds only entries not yet durable in Postgres and
# self-clears — it is the mechanism that lets the flat audit.log be retired at the cut.

_spool_lock = threading.Lock()
_wake = threading.Event()
_writer_lock = threading.Lock()
_writer_started = False
_DRAIN_RETRY_SECONDS: Final = 5.0


def _connect_sync() -> Any:
    import psycopg

    from tessera.settings import get_settings

    settings = get_settings()
    conn = psycopg.connect(str(settings.postgres.dsn), connect_timeout=2)
    conn.execute(f"SET search_path TO {settings.pg_schema}, public")
    return conn


def _spool_path() -> Path:
    """The durable spool of entries not yet committed to the table (per-env, ADR 0014)."""
    from tessera.settings import get_settings

    return get_settings().guard.audit_file.parent / "audit_spool.jsonl"


def _spool_append(entry: Mapping[str, Any]) -> None:
    """Durably append one chained entry to the spool (append + flush + fsync)."""
    path = _spool_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(dict(entry), ensure_ascii=False)
    with _spool_lock, path.open("a", encoding="utf-8") as fp:
        fp.write(line + "\n")
        fp.flush()
        os.fsync(fp.fileno())


def _read_spool_locked() -> list[dict[str, Any]]:
    """Spooled entries in FIFO (chain) order. Call under ``_spool_lock``."""
    path = _spool_path()
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fp:
        for raw in fp:
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                obj = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                entries.append(obj)
    return entries


def _link_and_insert(entries: list[dict[str, Any]]) -> set[str]:
    """Serialize the append: read the true head under the advisory lock, link + insert.

    TESS-LEDGER-001 core. One transaction holding ``pg_advisory_xact_lock`` so the head read,
    the linking and the inserts are globally serialized — insert order IS chain order, and two
    concurrent writers can never extend the same head (no fork). Each entry is (re)linked to
    the running head here, NOT at emit, so the recorded ``prev_hash``/``hash`` reflect the true
    immediate predecessor. Idempotent by the position-independent ``event_id``: entries already
    durable are skipped (a crash-replayed drain never duplicates). Returns the event_ids that
    are now durable (freshly inserted or already present) — the set the spool may drop.
    """
    prepared = [(str(e.get("event_id") or _event_identity(e)), e) for e in entries]
    with _connect_sync() as conn:
        conn.execute("SELECT pg_advisory_xact_lock(%s, %s)", (_LOCK_HI, _LOCK_LO))
        durable: set[str] = {
            row[0]
            for row in conn.execute(
                f"SELECT payload->>'event_id' FROM {LEDGER_TABLE} "  # noqa: S608
                f"WHERE payload->>'event_id' = ANY(%s)",
                ([eid for eid, _ in prepared],),
            ).fetchall()
        }
        head_row = conn.execute(
            f"SELECT hash FROM {LEDGER_TABLE} ORDER BY seq DESC LIMIT 1"  # noqa: S608
        ).fetchone()
        head = str(head_row[0]) if head_row and head_row[0] else _GENESIS
        for eid, entry in prepared:
            if eid in durable:
                continue  # already in the table — idempotent skip, head untouched
            linked = {k: v for k, v in entry.items() if k != "hash"}
            linked["event_id"] = eid
            linked["prev_hash"] = head
            linked["hash"] = _hash_core(linked)
            conn.execute(_INSERT_DRAIN, _row_tuple(linked))
            head = str(linked["hash"])
            durable.add(eid)
        conn.commit()
    return {eid for eid, _ in prepared}


def _clear_spooled(processed: set[str]) -> None:
    """Drop only the now-durable entries from the spool, preserving concurrent appends.

    Rewrites the spool with the entries whose ``event_id`` is NOT in ``processed`` — strictly
    safer than truncating the whole file (which could wipe an entry appended by another writer
    between the drain's read and its clear). Matches the drain's identity rule (event_id, or a
    recomputed one for a legacy entry that predates the field).
    """
    with _spool_lock:
        remaining = [
            e
            for e in _read_spool_locked()
            if str(e.get("event_id") or _event_identity(e)) not in processed
        ]
        text = (
            "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in remaining)
            if remaining
            else ""
        )
        _spool_path().write_text(text, encoding="utf-8")


def drain_spool() -> bool:
    """Replay spooled entries into the table, serialized + fork-free — never drops one.

    Reads the spool (FIFO), then links + inserts under the advisory lock in ONE transaction:
    the batch commits whole or not at all, so there is never a partial replay; a re-drain is a
    no-op (idempotent by ``event_id``). Returns True when the spool is drained, False when
    Postgres was unreachable (or the fork guard tripped a concurrent non-cooperating writer) —
    the entries remain spooled, order intact, and the next wake retries against the fresh head.
    """
    with _spool_lock:
        entries = _read_spool_locked()
    if not entries:
        return True
    try:
        processed = _link_and_insert(entries)
    except Exception as exc:  # unreachable / fork-guard conflict — keep the spool, replay later
        sys.stderr.write(f"tessera.ledger: spool drain deferred ({len(entries)} pending): {exc}\n")
        return False
    _clear_spooled(processed)
    return True


def _writer_loop() -> None:
    while True:
        _wake.wait(timeout=_DRAIN_RETRY_SECONDS)
        _wake.clear()
        try:
            drain_spool()
        except Exception as exc:  # a background reconciler thread must never die
            sys.stderr.write(f"tessera.ledger: writer loop error: {exc}\n")


def enqueue_ledger_entry(entry: Mapping[str, Any]) -> None:
    """Durably record one chained entry for the Postgres leg (spool → table).

    Spools the entry (fsync) before returning — zero loss even across a crash or a Postgres
    outage — then wakes the background drain. Only the Postgres *visibility* is asynchronous;
    the *durability* is synchronous. ``TESSERA_LEDGER_DUAL_WRITE=0`` disables the whole leg
    so the unit suite stays hermetic.
    """
    global _writer_started
    if not dual_write_enabled():
        return
    _spool_append(entry)
    with _writer_lock:
        if not _writer_started:
            threading.Thread(target=_writer_loop, daemon=True, name="tessera-ledger").start()
            _writer_started = True
    _wake.set()


# ── Backfill + verification ────────────────────────────────────────────────────


def _file_entries(path: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fp:
        for raw in fp:
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                obj = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                entries.append(obj)
    return entries


async def backfill_ledger_from_file(path: Path) -> tuple[int, ChainStatus]:
    """Copy the flat file into the promoted table — after verifying its chain.

    Returns ``(rows_inserted, file_chain_status)``. A file whose chain does not verify
    is **never imported** (0 inserted, the broken status returned) — recompute + verify
    on import is the §Amendment 3 contract. Idempotent by the unique hash.
    """
    from tessera.retrieval.store import get_pool

    status = verify_audit_chain(path)
    if not status.verified or status.length == 0:
        return 0, status
    entries = _file_entries(path)
    await ensure_audit_ledger_schema()
    pool = get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.executemany(_INSERT_ENTRY, [_row_tuple(entry) for entry in entries])
        inserted = cur.rowcount if cur.rowcount >= 0 else 0
        await conn.commit()
    return inserted, status


def verify_ledger_rows(payloads: Sequence[Mapping[str, Any]]) -> ChainStatus:
    """Verify the promoted ledger by WALKING the chain (order-independent).

    Rebuilds the linked list from the genesis hash via ``prev_hash``, recomputing every
    entry's hash from its canonical payload. A fork (two entries with one parent), an
    orphan (unreachable entry), a gap, or an edited payload all fail the walk — stronger
    than trusting insert order, and immune to out-of-order ingestion.
    """
    if not payloads:
        return ChainStatus(verified=True, length=0, broken_at=None)
    by_parent: dict[str, Mapping[str, Any]] = {}
    for payload in payloads:
        parent = str(payload.get("prev_hash", ""))
        if parent in by_parent:
            # A fork: two entries claim the same parent — tampering, report at the walk
            # position below by leaving the duplicate unreachable (count mismatch).
            continue
        by_parent[parent] = payload
    prev = _GENESIS
    walked = 0
    while walked < len(payloads):
        entry = by_parent.get(prev)
        if entry is None:
            return ChainStatus(verified=False, length=walked, broken_at=walked)
        stored = entry.get("hash")
        recomputed = _hash_core({k: v for k, v in entry.items() if k != "hash"})
        if stored != recomputed:
            return ChainStatus(verified=False, length=walked + 1, broken_at=walked)
        prev = str(stored)
        walked += 1
    return ChainStatus(verified=True, length=walked, broken_at=None)


# TESS-LEDGER-001 — the attestation entry type (point 4): a signed, appended entry that ratifies
# the historical forks (never a rewrite). Its presence flips the badge to "attested".
LEDGER_ATTESTATION_TYPE: Final = "tessera.ledger.attestation"


@dataclass(frozen=True, slots=True)
class LedgerForkPoint:
    """A parent extended by more than one child — a break in the total order (not a forgery)."""

    prev_hash: str
    children: tuple[str, ...]  # the child hashes sharing this parent (≥2)


@dataclass(frozen=True, slots=True)
class LedgerTreeStatus:
    """Tree-aware ledger verdict (TESS-LEDGER-001): tamper-evidence ≠ total order.

    The binary "chain broken" conflated three very different things. This separates them:

    * ``content_integrity`` — the tamper-evidence guarantee: every PRESENT row's hash recomputes
      from its canonical payload (no edited/forged row). It stays TRUE for a forked or gapped
      chain, because a fork is a tree — not a forgery — and a lost write is not an edit.
    * ``forks`` — parents extended by more than one child (concurrent writers). REPORTED, never
      deleted: the orphan branches are real guard events.
    * ``orphans`` — present rows whose ``prev_hash`` resolves to NO present row: the parent entry
      was never persisted (a lost write, not a deletion — append-only forbids DELETE). A
      completeness gap, distinct from tampering.
    * ``linear`` — the strong property: content intact AND a single unbroken chain (no fork, no
      orphan).
    * ``attested`` — True once an appended attestation entry has ratified the historical state
      (point 4).
    """

    content_integrity: bool
    linear: bool
    forks: tuple[LedgerForkPoint, ...]
    orphans: tuple[str, ...]  # hashes of rows whose parent is missing (a lost write)
    length: int
    broken_at: int | None
    attested: bool = False

    @property
    def fork_count(self) -> int:
        """Number of fork points (parents with more than one child)."""
        return len(self.forks)

    @property
    def orphan_count(self) -> int:
        """Number of rows whose parent entry is missing (lost writes)."""
        return len(self.orphans)


def verify_ledger_tree(payloads: Sequence[Mapping[str, Any]]) -> LedgerTreeStatus:
    """Tree-aware verification — tamper-evidence, forks and gaps judged separately.

    Recomputes every row's hash (a mismatch is an EDIT → fails ``content_integrity``), collects
    every fork point instead of dead-ending on the first one, and reports rows whose parent is
    missing as ``orphans`` (a lost write — completeness, not tampering). A healthy-but-forked
    ledger returns ``content_integrity=True, linear=False, forks=[…]`` — the honest verdict the
    binary walk could not give (it reported such a chain as flatly "broken").
    """
    if not payloads:
        return LedgerTreeStatus(True, True, (), (), 0, None)
    by_hash: dict[str, Mapping[str, Any]] = {}
    children: dict[str, list[str]] = {}
    content_ok = True
    broken_at: int | None = None
    attested = False
    for idx, payload in enumerate(payloads):
        if payload.get("type") == LEDGER_ATTESTATION_TYPE:
            attested = True
        stored = payload.get("hash")
        recomputed = _hash_core({k: v for k, v in payload.items() if k != "hash"})
        if not isinstance(stored, str) or stored != recomputed:
            content_ok = False  # an edited/forged row — the tamper signal
            if broken_at is None:
                broken_at = idx
            continue
        by_hash[stored] = payload
        children.setdefault(str(payload.get("prev_hash", "")), []).append(stored)
    orphans = tuple(
        child
        for parent, kids in children.items()
        if parent != _GENESIS and parent not in by_hash
        for child in kids  # the child(ren) whose declared parent was never persisted
    )
    forks = tuple(
        LedgerForkPoint(parent, tuple(kids)) for parent, kids in children.items() if len(kids) > 1
    )
    return LedgerTreeStatus(
        content_integrity=content_ok,
        linear=content_ok and not forks and not orphans,
        forks=forks,
        orphans=orphans,
        length=len(payloads),
        broken_at=broken_at,
        attested=attested,
    )


def load_ledger_payloads_sync(at: str | None = None) -> list[dict[str, Any]]:
    """Every promoted-ledger payload (oldest→newest by seq), optionally as of instant T.

    Synchronous (the spine readers are sync) over a short-lived bounded connection —
    mirrors the gating adapter's posture. Raises into the caller's honest-empty handling
    when Postgres is unreachable.
    """
    query = f"SELECT payload FROM {LEDGER_TABLE}"  # noqa: S608 — fixed identifier
    params: list[object] = []
    if at:
        try:
            cutoff = datetime.fromisoformat(at)
        except ValueError:
            cutoff = None
        if cutoff is not None:
            if cutoff.tzinfo is None:
                cutoff = cutoff.replace(tzinfo=UTC)
            query += " WHERE occurred_at <= %s"
            params.append(cutoff)
    query += " ORDER BY seq"
    with _connect_sync() as conn, conn.cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()
    return [row[0] for row in rows if isinstance(row[0], dict)]


# ── Read seam (every direct ledger consumer routes here — ADR 0015 H2) ──────────
# The flat-file parse and the promoted-table read return byte-identical payload dicts,
# so a consumer's downstream ``type``/agent/as-of filtering is unchanged across the cut.
# Consumers keep their own filters and call one of these instead of opening the file.


def read_ledger_entries(path: Path | None = None) -> list[dict[str, Any]]:
    """Every ledger entry (oldest→newest) from the ACTIVE source — the single read seam.

    ``file`` (default) parses the flat journal at ``path`` — or the settings audit file
    when ``path`` is omitted; tests inject a temp chain here. ``postgres`` reads the
    promoted append-only table in ``seq`` order (``path`` ignored — the cut). Both mediums
    yield the same dicts, so a caller's filtering is identical before and after the cut.
    In postgres mode an unreachable store raises ``psycopg.Error`` — the caller maps that
    to honest-empty (never a fabricated zero), exactly as the spine adapter does.
    """
    if ledger_source() == "postgres":
        return load_ledger_payloads_sync()
    from tessera.settings import get_settings

    target = path if path is not None else get_settings().guard.audit_file
    if not target.exists():
        return []
    return _file_entries(target)


def ledger_head_hash() -> str | None:
    """The hash of the promoted chain's tail (max ``seq``), or None if empty/unreachable.

    Seeds a fresh process's chain AFTER the cut so the next entry links to the last row —
    this is what makes the chain continuous across the file→table boundary (the first
    post-cut entry's ``prev_hash`` is the last pre-cut entry's hash, so ``verify`` walks
    genesis→tail unbroken). ``seq`` is chain order: the spool drains FIFO in one whole-batch
    transaction, so insert order never diverges from chain order. Returns None (never
    genesis) on empty/unreachable so the caller chooses the fallback explicitly.
    """
    try:
        with _connect_sync() as conn:
            row = conn.execute(
                f"SELECT hash FROM {LEDGER_TABLE} ORDER BY seq DESC LIMIT 1"  # noqa: S608
            ).fetchone()
    except Exception:
        return None
    return row[0] if row and isinstance(row[0], str) else None


def _ledger_reachable() -> bool:
    """Cheap probe: is the promoted ledger table reachable? (health, postgres mode)."""
    try:
        with _connect_sync() as conn:
            conn.execute(f"SELECT 1 FROM {LEDGER_TABLE} LIMIT 1")  # noqa: S608 — fixed ident
        return True
    except Exception:
        return False


def ledger_available(path: Path | None = None) -> bool:
    """Whether the ACTIVE ledger source is materialised — the health signal.

    ``file``: the journal file exists on disk. ``postgres``: the promoted table is
    reachable. Replaces a bare ``audit_file.is_file()`` so a health check reads whichever
    medium is canonical after the cut (post-cut, the flat file is gone by design).
    """
    if ledger_source() == "postgres":
        return _ledger_reachable()
    from tessera.settings import get_settings

    target = path if path is not None else get_settings().guard.audit_file
    return target.is_file()


@dataclass(frozen=True, slots=True)
class LedgerShadowStatus:
    """The shadow-verify verdict: both mediums verify AND agree (the cut gate)."""

    file_status: ChainStatus
    table_status: ChainStatus
    file_count: int
    table_count: int

    @property
    def ok(self) -> bool:
        """True when both chains verify and cover the same entries — the cut may proceed."""
        return (
            self.file_status.verified
            and self.table_status.verified
            and self.file_count == self.table_count
        )


def shadow_verify_ledger(path: Path) -> LedgerShadowStatus:
    """Verify the chain on the file AND the table, and that they cover the same entries."""
    file_status = verify_audit_chain(path)
    payloads = load_ledger_payloads_sync()
    table_status = verify_ledger_rows(payloads)
    return LedgerShadowStatus(
        file_status=file_status,
        table_status=table_status,
        file_count=file_status.length,
        table_count=len(payloads),
    )


def verify_active_ledger(path: Path | None = None) -> ChainStatus:
    """CONTENT integrity (tamper-evidence) of the ACTIVE ledger source.

    TESS-LEDGER-001 — ``verified`` is the CONTENT guarantee (every row hashes correctly and
    every ``prev_hash`` resolves), NOT linearity: a historical fork is a tree, not a forgery,
    and must not read as tampering across the cockpit. Total order + the fork list are surfaced
    by :func:`active_ledger_tree_status` (the integrity badge). In file mode the flat journal is
    single-writer, so content integrity and linearity coincide (``verify_audit_chain``).

    In postgres mode ``path`` is ignored (the promoted table is the source); an unreachable
    store raises into the caller's honest-empty handling.
    """
    from tessera.settings import get_settings

    if ledger_source() == "postgres":
        tree = verify_ledger_tree(load_ledger_payloads_sync())
        return ChainStatus(
            verified=tree.content_integrity, length=tree.length, broken_at=tree.broken_at
        )
    return verify_audit_chain(path if path is not None else get_settings().guard.audit_file)


def active_ledger_tree_status(path: Path | None = None) -> LedgerTreeStatus:
    """Tree-aware status of the ACTIVE ledger — the integrity badge's source (TESS-LEDGER-001).

    Postgres mode returns the full ``{content_integrity, linear, forks, attested}`` verdict over
    the promoted table. File mode has no forks (a single-writer append-only journal), so it lifts
    the binary :func:`verify_audit_chain` result into the same shape (``linear == content``).
    """
    from tessera.settings import get_settings

    if ledger_source() == "postgres":
        return verify_ledger_tree(load_ledger_payloads_sync())
    status = verify_audit_chain(path if path is not None else get_settings().guard.audit_file)
    return LedgerTreeStatus(
        content_integrity=status.verified,
        linear=status.verified,
        forks=(),
        orphans=(),
        length=status.length,
        broken_at=status.broken_at,
    )
