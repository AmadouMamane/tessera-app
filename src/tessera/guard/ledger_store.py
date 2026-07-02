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
* **Dual-write is best-effort and self-healing**: entries enqueue to a single FIFO
  writer thread (chain order preserved); a missed insert is reconciled by the idempotent
  boot backfill (``ON CONFLICT (hash) DO NOTHING``). The FILE stays the canonical store
  until the cut (``TESSERA_LEDGER_SOURCE=postgres``), which is gated on
  :func:`shadow_verify_ledger` holding — never flip a ledger read before its chain
  verifies (§Amendment 3 migration note).

The unit suite disables the dual-write (``TESSERA_LEDGER_DUAL_WRITE=0``) so audit
emission stays hermetic; the write/backfill legs are covered by contract tests.
"""

from __future__ import annotations

import json
import os
import queue
import sys
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Final

from tessera.guard.audit import ChainStatus, _hash_core, verify_audit_chain

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

__all__ = [
    "LEDGER_TABLE",
    "LedgerShadowStatus",
    "backfill_ledger_from_file",
    "dual_write_enabled",
    "enqueue_ledger_entry",
    "ensure_audit_ledger_schema",
    "ledger_source",
    "load_ledger_payloads_sync",
    "shadow_verify_ledger",
    "verify_active_ledger",
    "verify_ledger_rows",
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
)

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


def ledger_source() -> str:
    """The active ledger read source: ``file`` (default) | ``postgres`` (the cut)."""
    raw = os.environ.get("TESSERA_LEDGER_SOURCE", "file").strip().lower()
    return raw if raw in {"file", "postgres"} else "file"


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
    """Create the promoted ledger table, its indexes and the append-only trigger."""
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
        await conn.commit()


# ── Dual-write (one FIFO writer thread — chain order preserved) ────────────────

_queue: queue.Queue[dict[str, Any]] = queue.Queue()
_writer_lock = threading.Lock()
_writer_started = False


def _connect_sync() -> Any:
    import psycopg

    from tessera.settings import get_settings

    settings = get_settings()
    conn = psycopg.connect(str(settings.postgres.dsn), connect_timeout=2)
    conn.execute(f"SET search_path TO {settings.pg_schema}, public")
    return conn


def _insert_sync(entry: Mapping[str, Any]) -> None:
    with _connect_sync() as conn:
        conn.execute(_INSERT_ENTRY, _row_tuple(entry))
        conn.commit()


def _writer_loop() -> None:
    while True:
        entry = _queue.get()
        try:
            _insert_sync(entry)
        except Exception as exc:  # the boot reconcile self-heals a missed insert
            sys.stderr.write(f"tessera.ledger: dual-write deferred: {exc}\n")
        finally:
            _queue.task_done()


def enqueue_ledger_entry(entry: Mapping[str, Any]) -> None:
    """Queue one chained entry for the Postgres leg (best-effort, order-preserving)."""
    global _writer_started
    if not dual_write_enabled():
        return
    with _writer_lock:
        if not _writer_started:
            threading.Thread(target=_writer_loop, daemon=True, name="tessera-ledger").start()
            _writer_started = True
    _queue.put(dict(entry))


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


def verify_active_ledger() -> ChainStatus:
    """Chain integrity of the ACTIVE ledger source (file today, Postgres after the cut)."""
    from tessera.settings import get_settings

    if ledger_source() == "postgres":
        return verify_ledger_rows(load_ledger_payloads_sync())
    return verify_audit_chain(get_settings().guard.audit_file)
