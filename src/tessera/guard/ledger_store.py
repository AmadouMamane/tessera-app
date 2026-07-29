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

from tessera.guard.audit import (
    HANDOFF_TYPE,
    LEDGER_ATTESTATION_TYPE,
    ChainStatus,
    _event_identity,
    _hash_core,
    verify_audit_chain,
)
from tessera.observability.store_spans import store_read
from tessera.sql import safe_identifier

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
    "audit_target_call_counts",
    "audit_type_min_occurred_and_count",
    "backfill_ledger_from_file",
    "drain_spool",
    "dual_write_enabled",
    "enqueue_ledger_entry",
    "ensure_audit_ledger_schema",
    "handoff_conversations",
    "handoff_counts",
    "latest_entries_of_type_by_agent",
    "latest_entry_of_type_for_agent",
    "ledger_available",
    "ledger_head_hash",
    "ledger_head_seq",
    "ledger_source",
    "load_ledger_payloads_of_type",
    "load_ledger_payloads_sync",
    "read_agent_journal_entries",
    "read_ledger_entries",
    "read_ledger_entries_by_target_prefix",
    "shadow_verify_ledger",
    "verify_active_ledger",
    "verify_active_ledger_checkpointed",
    "verify_ledger_rows",
    "verify_ledger_tree",
]

# Validated at definition (audit P0.3 `sql-fstring`). This is the table the whole opposable
# audit chain lives in — the one name in the codebase where a silently different table would
# be worst — so it goes through the same gate as every other identifier, literal or not.
LEDGER_TABLE: Final = safe_identifier("audit_ledger")
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
    # The incremental verifier asks, per new row: "which rows already claim this parent?" —
    # that is fork detection. Without this index the question is a sequential scan and the fork
    # delta degrades from 0.09 ms to 38 ms, i.e. back to O(ledger), which is the whole thing we
    # are killing. (Measured after ANALYZE: a fresh index with stale statistics still gets the
    # slow plan — the index alone is not the fix, the statistics are part of it.)
    f"CREATE INDEX IF NOT EXISTS audit_ledger_prev ON {LEDGER_TABLE} (prev_hash)",
    # "What was this agent's last canary verdict?" — one row. The fleet answered it by loading
    # all 29 600 payloads and scanning them in Python, once PER AGENT. This index is what lets
    # the question be asked the way it is shaped: a ``WHERE type=… AND agent_id=…`` on a
    # ``seq DESC`` tail. ``seq DESC`` is in the index so the LIMIT 1 is a single index fetch and
    # never a sort. It also serves the handoff/lifecycle counts (same leading column).
    f"CREATE INDEX IF NOT EXISTS audit_ledger_type_agent_seq ON {LEDGER_TABLE} "
    f"((payload->>'type'), (payload->>'agent_id'), seq DESC)",
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
                # skip a non-ISO stamp and try the next key; falls back to now() below —
                # best-effort as-of INDEX only, the payload keeps the canonical truth (0015)
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
        # Refresh planner statistics so a FRESH deploy uses audit_ledger_type_agent_seq for
        # selective per-agent counts from the first read — the index alone is not the fix, the
        # statistics are part of it (see CREATE_LEDGER_INDEXES). Best effort: a stats refresh is
        # advisory (autovacuum catches up regardless) and must never fail schema init / boot.
        try:
            await cur.execute(f"ANALYZE {LEDGER_TABLE}")
        except Exception as exc:  # a stats refresh must never block schema init
            sys.stderr.write(f"tessera.ledger: ANALYZE {LEDGER_TABLE} skipped: {exc}\n")
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
    conn.execute(f"SET search_path TO {safe_identifier(settings.pg_schema)}, public")
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
                # Drop a corrupt line (a partial write on crash) but make it VISIBLE — a
                # silently skipped ledger line is a lost record; the chain verifier still
                # catches any real break later. Best-effort read, non-gating (0015).
                sys.stderr.write(f"tessera.ledger: skipped an unparseable line in {path}\n")
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
    with store_read("file", "audit_log.entries", target=path.name) as read:
        with path.open("r", encoding="utf-8") as fp:
            for raw in fp:
                stripped = raw.strip()
                if not stripped:
                    continue
                try:
                    obj = json.loads(stripped)
                except json.JSONDecodeError:
                    # Drop a corrupt line (a partial write on crash) but make it VISIBLE — a
                    # silently skipped ledger line is a lost record; the chain verifier still
                    # catches any real break later. Best-effort read, non-gating (0015).
                    sys.stderr.write(f"tessera.ledger: skipped an unparseable line in {path}\n")
                    continue
                if isinstance(obj, dict):
                    entries.append(obj)
        read.rows_read(len(entries))
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


# ── Live-payloads cache (incremental, head-invalidated) ─────────────────────────────────────────
# `load_ledger_payloads_sync()` was a per-request O(ledger) scan — ~62 000 rows / 38 MB
# materialised into Python and filtered, on every SURVEILLER page (compliance, reliability,
# proofs and timeline each drive one). Measured 1.7-2.6 s each.
#
# The ledger is STRICTLY append-only: a BEFORE UPDATE OR DELETE trigger RAISES on any mutation
# (CREATE_APPEND_ONLY_TRIGGER) and `seq` is a monotonic bigserial. So the head (`max(seq)`) is a
# COMPLETE cache key — an unchanged head proves every row and payload is byte-identical; an
# advanced head means only `seq > head` rows were appended. That makes an incremental cache
# provably correct: the full scan happens ONCE, then each request pays only a `max(seq)` probe on
# the primary key plus the few new rows, serving the rest from memory. This AMORTISES the read; it
# does NOT make it bounded — the whole chain still lives in RAM and grows with the ledger, so the
# per-path aggregation this stops short of (the OWED debt named in test_ledger_read_budget.py) is
# still worth paying. As-of-T reads bypass the cache: rare (seal / État-à-date) and each is bounded.
_PAYLOADS_CACHE_LOCK: Final = threading.Lock()
_payloads_cache_seq: int = 0
_payloads_cache_rows: list[dict[str, Any]] = []


def reset_ledger_payloads_cache() -> None:
    """Drop the live-payloads cache. Tests reset it per-test so cached rows never leak forward."""
    global _payloads_cache_seq, _payloads_cache_rows
    with _PAYLOADS_CACHE_LOCK:
        _payloads_cache_seq = 0
        _payloads_cache_rows = []


def load_ledger_payloads_sync(at: str | None = None) -> list[dict[str, Any]]:
    """Every promoted-ledger payload (oldest→newest by seq), optionally as of instant T.

    Synchronous (the spine readers are sync) over a short-lived bounded connection —
    mirrors the gating adapter's posture. Raises into the caller's honest-empty handling
    when Postgres is unreachable.

    The live read (``at is None``) is served from an incremental, head-invalidated cache
    (see the module note above): correct because the ledger is append-only and immutable, so
    an unchanged ``max(seq)`` guarantees an unchanged result. As-of-T reads (``at`` set) bypass
    the cache — they are rare and each already carries its own ``occurred_at`` upper bound.
    """
    if at is not None:
        return _load_ledger_payloads_at(at)
    return _load_ledger_payloads_live()


def _load_ledger_payloads_at(at: str) -> list[dict[str, Any]]:
    """The as-of-T whole-ledger read (``occurred_at <= at``), uncached."""
    query = f"SELECT payload FROM {LEDGER_TABLE}"  # noqa: S608 — fixed identifier
    params: list[object] = []
    try:
        cutoff = datetime.fromisoformat(at)
    except ValueError:
        # Defensive only: the sole caller (guard/seal.py) passes datetime.isoformat(), which
        # always parses. A malformed `at` falls through to the unfiltered query — safe today;
        # re-check if a raw request string ever reaches here (it over-returns, never under).
        cutoff = None
    if cutoff is not None:
        if cutoff.tzinfo is None:
            cutoff = cutoff.replace(tzinfo=UTC)
        query += " WHERE occurred_at <= %s"
        params.append(cutoff)
    query += " ORDER BY seq"
    with (
        store_read("postgres", "audit_ledger.payloads_all", target=LEDGER_TABLE) as read,
        _connect_sync() as conn,
        conn.cursor() as cur,
    ):
        cur.execute(query, params)
        rows = cur.fetchall()
        read.rows_read(len(rows))
    return [row[0] for row in rows if isinstance(row[0], dict)]


def _load_ledger_payloads_live() -> list[dict[str, Any]]:
    """The live (``at is None``) whole-ledger read, from the incremental head-keyed cache."""
    global _payloads_cache_seq, _payloads_cache_rows
    with (
        store_read("postgres", "audit_ledger.payloads_all", target=LEDGER_TABLE) as read,
        _connect_sync() as conn,
        conn.cursor() as cur,
    ):
        cur.execute(f"SELECT max(seq) FROM {LEDGER_TABLE}")  # noqa: S608 — fixed identifier
        head_row = cur.fetchone()
        if head_row is None:
            # A connection double that does not model max(seq): read the whole table, uncached,
            # so a fake sees the historical behaviour (the read-budget ratchet counts it).
            cur.execute(f"SELECT payload FROM {LEDGER_TABLE} ORDER BY seq")  # noqa: S608
            rows = cur.fetchall()
            read.rows_read(len(rows))
            return [row[0] for row in rows if isinstance(row[0], dict)]
        head = int(head_row[0]) if head_row[0] is not None else 0
        with _PAYLOADS_CACHE_LOCK:
            if head == _payloads_cache_seq and _payloads_cache_rows:
                read.rows_read(0)  # served from memory — a real, honest zero-row read
                return list(_payloads_cache_rows)
            # Reuse the cached prefix only when it is a strict prefix of the current head (an
            # append). A smaller head (a test truncation/reset) discards it and re-reads from 0.
            reuse = 0 < _payloads_cache_seq <= head
            base = _payloads_cache_rows if reuse else []
            anchor = _payloads_cache_seq if reuse else 0
            cur.execute(
                f"SELECT payload FROM {LEDGER_TABLE} WHERE seq > %s ORDER BY seq",  # noqa: S608
                [anchor],
            )
            delta = [row[0] for row in cur.fetchall() if isinstance(row[0], dict)]
            read.rows_read(len(delta))
            rows = base + delta
            _payloads_cache_rows = rows
            _payloads_cache_seq = head
            return list(rows)


# ── Read seam (every direct ledger consumer routes here — ADR 0015 H2) ──────────
# The flat-file parse and the promoted-table read return byte-identical payload dicts,
# so a consumer's downstream ``type``/agent/as-of filtering is unchanged across the cut.
# Consumers keep their own filters and call one of these instead of opening the file.


def read_ledger_entries(
    path: Path | None = None,
    *,
    since: datetime | None = None,
    until: datetime | None = None,
) -> list[dict[str, Any]]:
    """Every ledger entry (oldest→newest) from the ACTIVE source — the single read seam.

    ``file`` (default) parses the flat journal at ``path`` — or the settings audit file
    when ``path`` is omitted; tests inject a temp chain here. ``postgres`` reads the
    promoted append-only table in ``seq`` order (``path`` ignored — the cut). Both mediums
    yield the same dicts, so a caller's filtering is identical before and after the cut.
    In postgres mode an unreachable store raises ``psycopg.Error`` — the caller maps that
    to honest-empty (never a fabricated zero), exactly as the spine adapter does.

    ``since``/``until`` bound the read IN SQL, on the ``occurred_at`` index. Without them a
    single request materialises the whole 38 MB table before filtering a page out of it in
    Python — the unbounded read that made ``GET /audit`` a DoS surface. Both default to None,
    so the 21 existing callers are byte-for-byte unchanged.

    NOT pushed down, and deliberately so: the eight payload-shape filters (target, outcome,
    event_type, actor_role, scope, policy_rule, free-text q, agent) still run in Python over the
    windowed rows, and therefore ``LIMIT`` cannot be pushed either — a SQL ``LIMIT 50`` applied
    before those filters would return the wrong page, silently. Closing that needs the filters
    expressed over the jsonb payload (a GIN index); it is written up as an owed item rather than
    faked with a cap that reads like completeness.
    """
    if ledger_source() == "postgres":
        # No window → the historical seam, unchanged, so the 21 existing callers (and the test
        # that pins this seam) keep the exact call they had.
        if since is None and until is None:
            return load_ledger_payloads_sync()
        return load_ledger_payloads_window(since=since, until=until)
    from tessera.settings import get_settings

    target = path if path is not None else get_settings().guard.audit_file
    if not target.exists():
        return []
    return _file_entries(target)


def load_ledger_payloads_window(
    *, since: datetime | None = None, until: datetime | None = None
) -> list[dict[str, Any]]:
    """Payloads inside a time window (oldest→newest), bounded in SQL on the occurred_at index."""
    query = f"SELECT payload FROM {LEDGER_TABLE}"  # noqa: S608 — fixed identifier
    clauses: list[str] = []
    params: list[object] = []
    if since is not None:
        clauses.append("occurred_at >= %s")
        params.append(since)
    if until is not None:
        clauses.append("occurred_at <= %s")
        params.append(until)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY seq"
    with (
        store_read("postgres", "audit_ledger.payloads_window", target=LEDGER_TABLE) as read,
        _connect_sync() as conn,
        conn.cursor() as cur,
    ):
        cur.execute(query, params)
        rows = cur.fetchall()
        read.rows_read(len(rows))
    return [row[0] for row in rows if isinstance(row[0], dict)]


def load_ledger_payloads_of_type(entry_type: str, at: str | None = None) -> list[dict[str, Any]]:
    """Only the payloads of one ``type`` (oldest→newest) — a targeted read, not a full scan.

    The seal facet needs the latest ``tessera.ledger.seal`` entry: a handful of rows. It was
    getting them by loading all 25 634 payloads and filtering in Python, on every badge request.
    """
    query = f"SELECT payload FROM {LEDGER_TABLE} WHERE payload->>'type' = %s"  # noqa: S608
    params: list[object] = [entry_type]
    if at:
        try:
            cutoff = datetime.fromisoformat(at)
        except ValueError:
            cutoff = None
        if cutoff is not None:
            if cutoff.tzinfo is None:
                cutoff = cutoff.replace(tzinfo=UTC)
            query += " AND occurred_at <= %s"
            params.append(cutoff)
    query += " ORDER BY seq"
    with (
        store_read("postgres", "audit_ledger.payloads_of_type", target=LEDGER_TABLE) as read,
        _connect_sync() as conn,
        conn.cursor() as cur,
    ):
        cur.execute(query, params)
        rows = cur.fetchall()
        read.rows_read(len(rows))
    return [row[0] for row in rows if isinstance(row[0], dict)]


def count_ledger_entries_of_type(entry_type: str, agent_id: str | None = None) -> int:
    """COUNT of ledger entries of one ``type`` (optionally one agent) — a bounded aggregate.

    The database answers the count; nothing is materialised. This is the bounded twin of
    :func:`load_ledger_payloads_of_type` for callers that only need ``len(...)``: the
    guard-audit type is 94 % of the chain, so materialising it just to take its length cost
    the fleet snapshot ~1.6 s per agent (six per request). A ``count(*)`` costs one row.

    The scope filter reproduces :func:`events_for_scope`'s LIVE semantics exactly — the
    ``type`` predicate matches ``_read_audit_ledger``'s postgres filter, and ``agent_id`` is
    the same ``payload->>'agent_id'`` equality :func:`latest_entry_of_type_for_agent` uses.
    It carries NO as-of bound on purpose: ``occurred_before(_, None)`` keeps every entry, so
    this is byte-identical for a live read; an as-of caller needing ``occurred_before``'s
    fail-open-on-malformed-timestamp semantics must stay on the Python path.
    """
    query = f"SELECT count(*) FROM {LEDGER_TABLE} WHERE payload->>'type' = %s"  # noqa: S608
    params: list[object] = [entry_type]
    if agent_id is not None:
        query += " AND payload->>'agent_id' = %s"
        params.append(agent_id)
    with (
        store_read("postgres", "audit_ledger.count_of_type", target=LEDGER_TABLE) as read,
        _connect_sync() as conn,
        conn.cursor() as cur,
    ):
        cur.execute(query, params)
        row = cur.fetchone()
        read.rows_read(1)
    return int(row[0]) if row and row[0] is not None else 0


def count_ledger_entries() -> int:
    """COUNT of every ledger entry — the whole chain's length as one bounded aggregate.

    The bounded twin of ``len(read_ledger_entries())`` for a caller that needs only the row count.
    ``system_profile`` shows ``audit_lines`` (the chain length) in its runtime panel and used to
    take it by materialising the entire 38 MB chain to call ``len``. ``count(*)`` is byte-identical
    — ``read_ledger_entries()`` returns every row, so its length IS the row count — and costs one
    row. File mode has no index: it stays on the materialise-then-``len`` path, identical both ways.
    """
    if ledger_source() != "postgres":
        return len(read_ledger_entries())
    with (
        store_read("postgres", "audit_ledger.count_all", target=LEDGER_TABLE) as read,
        _connect_sync() as conn,
        conn.cursor() as cur,
    ):
        cur.execute(f"SELECT count(*) FROM {LEDGER_TABLE}")  # noqa: S608 — fixed identifier
        row = cur.fetchone()
        read.rows_read(1)
    return int(row[0]) if row and row[0] is not None else 0


def guard_explain_scan() -> tuple[int, list[tuple[str, str, int, int]]]:
    """Guard-explain rollup as bounded SQL: ``(n_entries, [(rule, kind, count, first_seen)])``.

    ``compute_guard_explain`` materialised every ``tessera.guard.audit`` entry (94 % of the chain)
    and rolled up ``Counter[(policy_rule, decision)]`` in Python. This asks the database instead:
    ``jsonb_array_elements(payload->'decisions')`` unnests each entry's decisions and a ``GROUP BY``
    returns ONE row per distinct ``(rule, kind)`` pair (a few dozen), never the chain.

    Byte-identical to the Python path (verified against the live ledger):

    * ``rule``/``kind`` reproduce ``str(decision.get(k, 'unknown'))`` — a ``CASE`` distinguishes an
      absent key ('unknown') from a JSON ``null`` value ('None'); a present string/number yields its
      text, exactly as ``str()`` does. (policy_rule/decision are always strings in real data.)
    * ``first_seen`` = ``min(seq * 1_000_000 + ordinality)`` per pair, i.e. the smallest
      (entry seq, array index) at which the pair appears. ``Counter.most_common`` breaks count ties
      by first-insertion order = first-encountered = this value, so the caller's
      ``sorted(key=(-count, first_seen))[:N]`` matches ``most_common(N)``.

    ``n_entries`` counts audit entries carrying a ``decisions`` ARRAY (empty arrays included,
    matching ``isinstance(decisions, list)``); non-object array elements are dropped
    (``jsonb_typeof = 'object'`` mirrors ``isinstance(decision, dict)``). Postgres only; a
    file-source caller keeps the Python loop.
    """
    entries_q = (
        f"SELECT count(*) FROM {LEDGER_TABLE} "  # noqa: S608 — fixed identifier
        "WHERE payload->>'type' = 'tessera.guard.audit' "
        "AND jsonb_typeof(payload->'decisions') = 'array'"
    )
    groups_q = (
        "SELECT rule, kind, count(*), min(ord_key) FROM ("  # noqa: S608 — fixed identifier
        "  SELECT"
        "    CASE WHEN d ? 'policy_rule' THEN COALESCE(d->>'policy_rule', 'None')"
        "         ELSE 'unknown' END AS rule,"
        "    CASE WHEN d ? 'decision' THEN COALESCE(d->>'decision', 'None')"
        "         ELSE 'unknown' END AS kind,"
        "    a.seq * 1000000 + t.ord AS ord_key"
        f"  FROM {LEDGER_TABLE} a,"
        "       LATERAL jsonb_array_elements(a.payload->'decisions') WITH ORDINALITY AS t(d, ord)"
        "  WHERE a.payload->>'type' = 'tessera.guard.audit'"
        "    AND jsonb_typeof(a.payload->'decisions') = 'array'"
        "    AND jsonb_typeof(t.d) = 'object'"
        ") s GROUP BY rule, kind"
    )
    with (
        store_read("postgres", "audit_ledger.guard_explain_scan", target=LEDGER_TABLE) as read,
        _connect_sync() as conn,
        conn.cursor() as cur,
    ):
        cur.execute(entries_q)
        head = cur.fetchone()
        n_entries = int(head[0]) if head and head[0] is not None else 0
        cur.execute(groups_q)
        rows = cur.fetchall()
        read.rows_read(len(rows))
    groups = [(str(r[0]), str(r[1]), int(r[2]), int(r[3])) for r in rows]
    return n_entries, groups


def ledger_head_seq() -> int:
    """The active ledger's high-water ``seq`` (0 when empty) — one indexed row.

    A complete cache key for any read over the whole append-only chain: the ledger is strictly
    append-only (a BEFORE UPDATE OR DELETE trigger + a monotone ``seq``), so an unchanged head
    proves every row and payload is byte-identical. Callers that memoise a full-chain fold key it
    on this. Postgres only; a file-source caller has no cheap head and must not cache on it.
    """
    with (
        store_read("postgres", "audit_ledger.head_seq", target=LEDGER_TABLE) as read,
        _connect_sync() as conn,
        conn.cursor() as cur,
    ):
        cur.execute(f"SELECT max(seq) FROM {LEDGER_TABLE}")  # noqa: S608 — fixed identifier
        row = cur.fetchone()
        read.rows_read(1)
    return int(row[0]) if row and row[0] is not None else 0


def audit_type_min_occurred_and_count(entry_type: str) -> tuple[str | None, int]:
    """(earliest non-blank payload ``occurred_at``, total count) of one ``type`` — bounded SQL.

    ``data-range`` needs only the minimum instant and the row count of the guard-audit type
    (94 % of the chain), yet materialised every payload to take a ``min`` and a ``len``. The
    lexicographic ``min`` over the JSON ``occurred_at`` string reproduces
    ``_data_availability_start`` exactly — ISO-8601 sorts lexicographically, blanks excluded — and
    ``count(*)`` is the same ``len``. One aggregate row instead of 64 k dicts. Postgres only; a
    file-source caller stays on the materialise path.
    """
    query = (
        f"SELECT min(payload->>'occurred_at') "  # noqa: S608 — fixed identifier
        f"FILTER (WHERE coalesce(payload->>'occurred_at', '') <> ''), count(*) "
        f"FROM {LEDGER_TABLE} WHERE payload->>'type' = %s"
    )
    with (
        store_read("postgres", "audit_ledger.min_and_count_of_type", target=LEDGER_TABLE) as read,
        _connect_sync() as conn,
        conn.cursor() as cur,
    ):
        cur.execute(query, [entry_type])
        row = cur.fetchone()
        read.rows_read(1)
    start = row[0] if row and isinstance(row[0], str) else None
    count = int(row[1]) if row and row[1] is not None else 0
    return start, count


def audit_target_call_counts(entry_type: str) -> dict[str, int]:
    """Per-``target`` occurrence counts for one ``type`` — a bounded SQL ``GROUP BY``.

    ``least-privilege`` counts how often each tool ``target`` appears in the guard-audit trail; it
    materialised 64 k payloads to do ``usage[target] += 1``. The ``GROUP BY`` returns one row per
    distinct target (a handful), byte-identical counts. NULL targets are dropped (they are not
    ``isinstance(str)`` in the Python path); the caller applies the ``user_input`` / ``memory.*``
    exclusions on the small result, exactly as the loop did. Postgres only; file mode stays Python.
    """
    query = (
        f"SELECT payload->>'target', count(*) FROM {LEDGER_TABLE} "  # noqa: S608 — fixed identifier
        f"WHERE payload->>'type' = %s AND payload->>'target' IS NOT NULL "
        f"GROUP BY payload->>'target'"
    )
    with (
        store_read("postgres", "audit_ledger.target_counts_of_type", target=LEDGER_TABLE) as read,
        _connect_sync() as conn,
        conn.cursor() as cur,
    ):
        cur.execute(query, [entry_type])
        rows = cur.fetchall()
        read.rows_read(len(rows))
    return {str(target): int(count) for target, count in rows}


def read_ledger_entries_by_target_prefix(
    prefix: str, *, until: datetime | None = None
) -> list[dict[str, Any]]:
    """Ledger payloads whose ``target`` starts with ``prefix`` (oldest→newest), bounded in SQL.

    ``source_state_traces`` keeps only the per-source knowledge acts (``target`` =
    ``knowledge_source.<cat>``) out of the whole chain. It was finding them by materialising
    every payload and testing the prefix in Python, on every Connaissances load. This pushes the
    prefix (and the ``until`` bound) into SQL so only the handful of matching rows come back. The
    ``LIKE`` may over-match (``_`` is a wildcard), but the caller's identical ``startswith`` belt
    filter narrows it exactly, so the result is byte-identical. File mode has no SQL: it returns
    the full (optionally ``until``-bounded) read and the same belt holds — identical both ways.
    """
    if ledger_source() != "postgres":
        return read_ledger_entries(until=until)
    query = f"SELECT payload FROM {LEDGER_TABLE} WHERE payload->>'target' LIKE %s"  # noqa: S608
    params: list[object] = [prefix + "%"]
    if until is not None:
        query += " AND occurred_at <= %s"
        params.append(until)
    query += " ORDER BY seq"
    with (
        store_read("postgres", "audit_ledger.payloads_by_target", target=LEDGER_TABLE) as read,
        _connect_sync() as conn,
        conn.cursor() as cur,
    ):
        cur.execute(query, params)
        rows = cur.fetchall()
        read.rows_read(len(rows))
    return [row[0] for row in rows if isinstance(row[0], dict)]


def read_agent_journal_entries(
    agent_id: str,
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    guard_tail: int,
) -> list[dict[str, Any]]:
    """The three journal slices ``_journal_scan`` keeps for one agent (oldest→newest), bounded.

    ``agent-synthese``'s activity scan walked the WHOLE window and kept only: handoffs the agent
    is a party to (``to_agent``/``from_agent``), the agent's routing events, and the agent's
    guard-audit entries — of which only the most-recent ``guard_tail`` reach a capped deque. This
    fetches exactly those rows in SQL: handoffs + routing in full, guard-audit as a ``seq DESC
    LIMIT guard_tail`` tail, all merged in ``seq`` order. The ``deque(maxlen)`` and the caller's
    belt filters make the result byte-identical to the full-window read — for the heavy agent
    (whose guard-audit is 94 % of the chain) as much as the sparse ones. File mode returns the
    full window; the belt holds there too.
    """
    if ledger_source() != "postgres":
        return read_ledger_entries(since=since, until=until)
    window = ""
    wparams: list[object] = []
    if since is not None:
        window += " AND occurred_at >= %s"
        wparams.append(since)
    if until is not None:
        window += " AND occurred_at <= %s"
        wparams.append(until)
    handoff_sql = (
        f"SELECT seq, payload FROM {LEDGER_TABLE} WHERE "  # noqa: S608 — fixed identifier
        f"payload->>'type' = 'tessera.agent.handoff' "
        f"AND (payload->>'to_agent' = %s OR payload->>'from_agent' = %s){window}"
    )
    routing_sql = (
        f"SELECT seq, payload FROM {LEDGER_TABLE} WHERE "  # noqa: S608
        f"payload->>'type' = 'tessera.agent.routing' AND payload->>'agent_id' = %s{window}"
    )
    guard_sql = (
        f"SELECT seq, payload FROM {LEDGER_TABLE} WHERE "  # noqa: S608
        f"payload->>'type' = 'tessera.guard.audit' AND payload->>'agent_id' = %s{window} "
        f"ORDER BY seq DESC LIMIT %s"
    )
    merged: list[tuple[int, dict[str, Any]]] = []
    with (
        store_read("postgres", "audit_ledger.agent_journal", target=LEDGER_TABLE) as read,
        _connect_sync() as conn,
        conn.cursor() as cur,
    ):
        cur.execute(handoff_sql, [agent_id, agent_id, *wparams])
        merged.extend((s, p) for s, p in cur.fetchall() if isinstance(p, dict))
        cur.execute(routing_sql, [agent_id, *wparams])
        merged.extend((s, p) for s, p in cur.fetchall() if isinstance(p, dict))
        cur.execute(guard_sql, [agent_id, *wparams, guard_tail])
        merged.extend((s, p) for s, p in cur.fetchall() if isinstance(p, dict))
        read.rows_read(len(merged))
    merged.sort(key=lambda r: r[0])
    return [payload for _, payload in merged]


def latest_entry_of_type_for_agent(entry_type: str, agent_id: str) -> dict[str, Any] | None:
    """The most recent entry of ``entry_type`` for one agent — ONE indexed row, ~1 ms.

    The question the fleet's health dot and the cockpit's bell both ask: *what was this agent's
    last canary verdict?* It used to be answered by loading all 29 600 payloads into memory and
    scanning them in Python — once per agent, six times per fleet request, and again per page
    for the header. A one-row question, costing a full table read.

    Ordered by ``seq DESC``: the chain's insert order IS its order, so the tail of the filtered
    set is the most recent run — the same entry the Python scan selected by keeping the LAST
    match of an oldest→newest walk.
    """
    query = (
        f"SELECT payload FROM {LEDGER_TABLE} "  # noqa: S608 — fixed identifier, bound params
        f"WHERE payload->>'type' = %s AND payload->>'agent_id' = %s "
        f"ORDER BY seq DESC LIMIT 1"
    )
    with (
        store_read(
            "postgres", "audit_ledger.latest_of_type_for_agent", target=LEDGER_TABLE
        ) as read,
        _connect_sync() as conn,
        conn.cursor() as cur,
    ):
        cur.execute(query, (entry_type, agent_id))
        rows = cur.fetchall()
        read.rows_read(len(rows))
    if not rows or not isinstance(rows[0][0], dict):
        return None
    return dict(rows[0][0])


def latest_entries_of_type_by_agent(entry_type: str) -> dict[str, dict[str, Any]]:
    """The most recent entry of ``entry_type`` for EVERY agent — one query, one row per agent.

    The fleet asks the canary question about all its agents at once, so it should ask once.
    ``DISTINCT ON`` walks the ``(type, agent_id, seq DESC)`` index and takes the first row of
    each agent's group: N rows, one round trip, instead of N full table reads.
    """
    query = (
        f"SELECT DISTINCT ON (payload->>'agent_id') payload->>'agent_id', payload "  # noqa: S608
        f"FROM {LEDGER_TABLE} "
        f"WHERE payload->>'type' = %s AND payload->>'agent_id' IS NOT NULL "
        f"ORDER BY payload->>'agent_id', seq DESC"
    )
    with (
        store_read("postgres", "audit_ledger.latest_of_type_by_agent", target=LEDGER_TABLE) as read,
        _connect_sync() as conn,
        conn.cursor() as cur,
    ):
        cur.execute(query, (entry_type,))
        rows = cur.fetchall()
        read.rows_read(len(rows))
    return {
        str(row[0]): dict(row[1])
        for row in rows
        if isinstance(row[0], str) and isinstance(row[1], dict)
    }


def handoff_counts() -> tuple[dict[str, int], dict[str, int]]:
    """Handoffs per agent — ``(incoming by to_agent, outgoing by from_agent)`` — counted in SQL.

    The fleet used to read every ledger entry to count a handful of handoff events. The count is
    an aggregate, and an aggregate belongs in the database: this returns one row per
    ``(to_agent, from_agent)`` pair that actually occurred, on the ``(type, …)`` index.
    """
    query = (
        f"SELECT payload->>'to_agent', payload->>'from_agent', count(*) "  # noqa: S608
        f"FROM {LEDGER_TABLE} WHERE payload->>'type' = %s GROUP BY 1, 2"
    )
    with (
        store_read("postgres", "audit_ledger.handoff_counts", target=LEDGER_TABLE) as read,
        _connect_sync() as conn,
        conn.cursor() as cur,
    ):
        cur.execute(query, (HANDOFF_TYPE,))
        rows = cur.fetchall()
        read.rows_read(len(rows))
    incoming: dict[str, int] = {}
    outgoing: dict[str, int] = {}
    for to_agent, from_agent, count in rows:
        if isinstance(to_agent, str) and to_agent:
            incoming[to_agent] = incoming.get(to_agent, 0) + int(count)
        if isinstance(from_agent, str) and from_agent:
            outgoing[from_agent] = outgoing.get(from_agent, 0) + int(count)
    return incoming, outgoing


def handoff_conversations() -> tuple[int, set[str]]:
    """``(total S1 handoff events, distinct conversation ids they attest)`` — one aggregate.

    The ids come back alongside the count because the fleet's dedup reconciliation has to
    ask the conversation store about *these exact journeys* — which of them it can actually
    see under two agents. A bare count could only be compared to another bare count, and two
    totals agreeing says nothing about whether they describe the same conversations.
    """
    query = (
        f"SELECT payload->>'conversation_id' AS cid, count(*) AS n "  # noqa: S608
        f"FROM {LEDGER_TABLE} WHERE payload->>'type' = %s GROUP BY 1"
    )
    with (
        store_read("postgres", "audit_ledger.handoff_conversations", target=LEDGER_TABLE) as read,
        _connect_sync() as conn,
        conn.cursor() as cur,
    ):
        cur.execute(query, (HANDOFF_TYPE,))
        rows = cur.fetchall()
        read.rows_read(len(rows))
    events = sum(int(n) for _cid, n in rows)
    ids = {cid for cid, _n in rows if isinstance(cid, str) and cid}
    return events, ids


def ledger_length_as_of(at: datetime) -> int:
    """How many entries existed at instant T — counted in SQL, on the ``occurred_at`` index.

    Was: load every payload, Pydantic-validate every row into an ``AuditEntry``, then count the
    ones inside the window. 3.3 ms in SQL against a full materialisation of 38 MB.
    """
    with (
        store_read("postgres", "audit_ledger.length_as_of", target=LEDGER_TABLE) as read,
        _connect_sync() as conn,
    ):
        row = conn.execute(
            f"SELECT count(*) FROM {LEDGER_TABLE} WHERE occurred_at <= %s",  # noqa: S608
            (at,),
        ).fetchone()
        read.rows_read(1 if row else 0)
    return int(row[0]) if row else 0


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
        # A transient DB error → None; the caller reseeds from genesis (documented). Broad
        # by design (any connect/query failure means "head unknown"), not a swallowed bug.
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


def verify_active_ledger_checkpointed(path: Path | None = None) -> ChainStatus:
    """CONTENT integrity of the active ledger for a HEALTH BADGE — checkpoint-incremental.

    Same ``ChainStatus`` shape and same verdict as :func:`verify_active_ledger`, but served by the
    checkpointed incremental verifier (:func:`ledger_checkpoint.verify_ledger_incremental`, which
    re-hashes only the rows above a stored, already-verified anchor) instead of re-walking the
    whole chain. A dashboard health dot needs "no proven break", not an opposability re-read —
    measured ~15 ms vs ~2 s on the 65k-row chain — so the Synthèse and Garde-fous badges ask this
    (the intent already stated in :func:`active_ledger_tree_status`'s docstring). The full walk
    :func:`verify_active_ledger` stays for the callers that CLAIM to a regulator (État à date,
    audit-integrity). File mode has no checkpoint, so it falls back to the SAME
    :func:`verify_audit_chain` the full path uses — byte-identical there.
    """
    from tessera.settings import get_settings

    if ledger_source() == "postgres":
        from tessera.guard.ledger_checkpoint import verify_ledger_incremental

        tree = verify_ledger_incremental().tree
        return ChainStatus(
            verified=tree.content_integrity, length=tree.length, broken_at=tree.broken_at
        )
    return verify_audit_chain(path if path is not None else get_settings().guard.audit_file)


def active_ledger_tree_status(path: Path | None = None) -> LedgerTreeStatus:
    """Tree-aware status of the ACTIVE ledger — the STRONG verdict: a full walk, every time.

    Postgres mode re-reads and re-hashes every row. That cost is deliberate and it is not the one
    this lot removed: the callers of this function are the ones that *claim* something — the État
    à date page asserts opposability to a regulator, and an assertion of that weight re-reads the
    chain end to end rather than trusting a cached proof.

    What a health dot needs is weaker and cheaper — "no proven break" — and it asks
    :func:`tessera.guard.ledger_checkpoint.active_ledger_verdict`, which is incremental and which
    *publishes when the chain was last walked in full*. The two questions are different, and this
    is the one that pays.

    File mode has no forks (a single-writer append-only journal), so it lifts the binary
    :func:`verify_audit_chain` result into the same shape (``linear == content``).
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
