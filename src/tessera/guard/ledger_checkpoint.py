"""Incremental ledger verification — a verified prefix stays verified, and says since when.

The integrity badge sits in the header of every cockpit page. It used to re-walk the ENTIRE
chain on every request: 25 634 rows, SHA-256 recomputed for each, in Python. Measured p50 was
1 093 ms, and 1 828 ms on the ``?at=`` branch the overview dashboard polls every 15 seconds.
The ledger is append-only, so that cost could only ever grow.

The fix rests on a property the database ENFORCES, not on one we assume:

    audit_ledger carries a BEFORE UPDATE OR DELETE trigger that raises. A row, once written,
    cannot change. Therefore a prefix, once verified, STAYS verified — and re-walking it is
    pure waste.

Every part of the verdict is therefore computed over the NEW rows only:

  * ``content_integrity`` — only rows above the checkpoint are re-hashed.
  * ``forks`` — a new row can fork an OLD parent, so the checkpoint carries the fork list and
    a delta query re-groups only the parents the new rows touch (authoritative for those,
    untouched ones cannot have changed). 0.09 ms for one new row.
  * ``orphans`` — a new row can BE an orphan, and can also RESOLVE one (by being the parent
    that was missing). Both are decided from the new rows alone.
  * ``length`` — counted exactly in SQL, and used as a CROSS-CHECK: if the count disagrees with
    ``checkpoint.verified_count + new rows``, something appeared below the anchor and the whole
    chain is re-walked.

And the checkpoint is never simply believed:

  * Its ANCHOR (the seq and hash it stopped at) is re-read from the ledger on EVERY request —
    one indexed row, 0.03 ms. The append-only trigger guards ROWS, not the TABLE: a restore or
    a truncate replaces history wholesale (the restore drill does exactly that). If the anchor
    row is gone, or its hash differs, this is not a stale checkpoint — it is a checkpoint about
    a DIFFERENT chain, and it is discarded.
  * The badge publishes when the full chain was last walked and how many entries have been
    verified incrementally since. A checkpoint trusted in silence would be an assumption wearing
    the clothes of a proof. This one states its own age and lets the reader judge it.

A periodic full verification (boot + off-chrono, like the Hica seal) re-walks everything and
resets that clock. That is what keeps the incremental claim honest.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final

from tessera.guard.audit import LEDGER_ATTESTATION_TYPE, _hash_core
from tessera.guard.ledger_store import (
    _GENESIS,
    LEDGER_TABLE,
    LedgerForkPoint,
    LedgerTreeStatus,
    _connect_sync,
)
from tessera.observability.store_spans import store_read
from tessera.sql import safe_identifier

CHECKPOINT_TABLE: Final = safe_identifier("audit_ledger_checkpoint")

#: One row. It is a CACHE of a proof, never the proof itself — the ledger is the truth, and the
#: anchor is re-checked against it on every read.
CREATE_CHECKPOINT_TABLE: Final = f"""
CREATE TABLE IF NOT EXISTS {CHECKPOINT_TABLE} (
    id                smallint    PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    verified_seq      bigint      NOT NULL,
    verified_hash     text        NOT NULL,
    verified_count    bigint      NOT NULL,
    content_ok        boolean     NOT NULL,
    broken_at         bigint,
    attested          boolean     NOT NULL DEFAULT false,
    forks             jsonb       NOT NULL DEFAULT '[]'::jsonb,
    orphans           jsonb       NOT NULL DEFAULT '[]'::jsonb,
    full_verified_at  timestamptz NOT NULL,
    full_verified_seq bigint      NOT NULL,
    updated_at        timestamptz NOT NULL
)
"""


@dataclass(frozen=True, slots=True)
class _Orphan:
    """A row whose declared parent is not present.

    ``parent`` is kept so a later row that turns out to BE that parent can resolve the orphan
    without re-scanning the table.
    """

    child: str
    parent: str


@dataclass(frozen=True, slots=True)
class Checkpoint:
    """The last verified point of the chain, and when the whole chain was last walked."""

    verified_seq: int
    verified_hash: str
    verified_count: int
    content_ok: bool
    broken_at: int | None
    attested: bool
    forks: tuple[LedgerForkPoint, ...]
    orphans: tuple[_Orphan, ...]
    full_verified_at: datetime
    full_verified_seq: int


@dataclass(frozen=True, slots=True)
class LedgerVerdict:
    """A tree status, plus the provenance of the claim: how fresh, and how much was re-read."""

    tree: LedgerTreeStatus
    full_verified_at: datetime | None
    entries_since_full: int
    entries_verified_now: int
    checkpoint_used: bool


@dataclass(frozen=True, slots=True)
class _Row:
    seq: int
    payload: dict[str, Any]
    hash: str
    prev_hash: str


def ensure_checkpoint_schema(conn: Any) -> None:
    """Create the checkpoint table if absent (called at boot, beside the ledger schema)."""
    conn.execute(CREATE_CHECKPOINT_TABLE)


# ── Reads ───────────────────────────────────────────────────────────────────────


def _rows_above(conn: Any, seq: int) -> list[_Row]:
    """Every row above ``seq``, oldest first — an index range scan on the primary key.

    The one read here that can be O(ledger): on a full walk ``seq`` is 0 and this materialises
    the whole chain. It is instrumented for exactly that reason — when the badge does re-read
    29 600 rows, the trace must say so out loud instead of hiding it inside a fast average.
    """
    with store_read("postgres", "audit_ledger.rows_above", target=LEDGER_TABLE) as read:
        rows = conn.execute(
            f"SELECT seq, payload, hash, prev_hash FROM {LEDGER_TABLE} "  # noqa: S608 — fixed ident
            f"WHERE seq > %s ORDER BY seq",
            (seq,),
        ).fetchall()
        read.rows_read(len(rows))
    return [_Row(int(r[0]), r[1], str(r[2]), str(r[3])) for r in rows if isinstance(r[1], dict)]


def _length(conn: Any) -> int:
    with store_read("postgres", "audit_ledger.length", target=LEDGER_TABLE) as read:
        row = conn.execute(f"SELECT count(*) FROM {LEDGER_TABLE}").fetchone()  # noqa: S608
        read.rows_read(1 if row else 0)
    return int(row[0]) if row else 0


def _max_seq(conn: Any) -> int:
    with store_read("postgres", "audit_ledger.max_seq", target=LEDGER_TABLE) as read:
        row = conn.execute(
            f"SELECT COALESCE(max(seq), 0) FROM {LEDGER_TABLE}"  # noqa: S608
        ).fetchone()
        read.rows_read(1 if row else 0)
    return int(row[0]) if row else 0


def _all_forks(conn: Any) -> tuple[LedgerForkPoint, ...]:
    """Every fork point in the whole table — the FULL walk only.

    Groups 29 600 rows in the database and returns the 29 that fork. The row count on the span is
    29, not 29 600, and that is correct: what costs is what is materialised in Python.
    """
    with store_read("postgres", "audit_ledger.forks_all", target=LEDGER_TABLE) as read:
        rows = conn.execute(
            f"SELECT prev_hash, array_agg(hash ORDER BY seq) FROM {LEDGER_TABLE} "  # noqa: S608
            f"GROUP BY prev_hash HAVING count(*) > 1"
        ).fetchall()
        read.rows_read(len(rows))
    return tuple(LedgerForkPoint(str(r[0]), tuple(str(h) for h in r[1])) for r in rows)


def _forks_touching(conn: Any, seq: int) -> tuple[LedgerForkPoint, ...]:
    """Fork points among the parents the rows above ``seq`` point at — authoritative for those.

    A parent no new row points at cannot have gained a child (append-only), so its state in the
    checkpoint still holds. This is what makes fork detection O(new) instead of O(ledger).
    """
    with store_read("postgres", "audit_ledger.forks_touching", target=LEDGER_TABLE) as read:
        rows = conn.execute(
            f"SELECT a.prev_hash, array_agg(a.hash ORDER BY a.seq) FROM {LEDGER_TABLE} a "  # noqa: S608
            f"WHERE a.prev_hash IN (SELECT prev_hash FROM {LEDGER_TABLE} WHERE seq > %s) "
            f"GROUP BY a.prev_hash HAVING count(*) > 1",
            (seq,),
        ).fetchall()
        read.rows_read(len(rows))
    return tuple(LedgerForkPoint(str(r[0]), tuple(str(h) for h in r[1])) for r in rows)


def _all_orphans(conn: Any) -> tuple[_Orphan, ...]:
    """Every row whose declared parent is absent — the FULL walk only."""
    with store_read("postgres", "audit_ledger.orphans_all", target=LEDGER_TABLE) as read:
        rows = conn.execute(
            f"SELECT a.hash, a.prev_hash FROM {LEDGER_TABLE} a "  # noqa: S608 — fixed identifier
            f"WHERE a.prev_hash <> %s "
            f"AND NOT EXISTS (SELECT 1 FROM {LEDGER_TABLE} b WHERE b.hash = a.prev_hash)",
            (_GENESIS,),
        ).fetchall()
        read.rows_read(len(rows))
    return tuple(_Orphan(str(r[0]), str(r[1])) for r in rows)


def _orphans_above(conn: Any, seq: int) -> tuple[_Orphan, ...]:
    """Rows above ``seq`` whose declared parent is absent — O(new), on the hash unique index."""
    with store_read("postgres", "audit_ledger.orphans_above", target=LEDGER_TABLE) as read:
        rows = conn.execute(
            f"SELECT a.hash, a.prev_hash FROM {LEDGER_TABLE} a "  # noqa: S608 — fixed identifier
            f"WHERE a.seq > %s AND a.prev_hash <> %s "
            f"AND NOT EXISTS (SELECT 1 FROM {LEDGER_TABLE} b WHERE b.hash = a.prev_hash)",
            (seq, _GENESIS),
        ).fetchall()
        read.rows_read(len(rows))
    return tuple(_Orphan(str(r[0]), str(r[1])) for r in rows)


def _load_checkpoint(conn: Any) -> Checkpoint | None:
    row = conn.execute(
        f"SELECT verified_seq, verified_hash, verified_count, content_ok, broken_at, attested, "  # noqa: S608
        f"forks, orphans, full_verified_at, full_verified_seq "
        f"FROM {CHECKPOINT_TABLE} WHERE id = 1"
    ).fetchone()
    if row is None:
        return None
    return Checkpoint(
        verified_seq=int(row[0]),
        verified_hash=str(row[1]),
        verified_count=int(row[2]),
        content_ok=bool(row[3]),
        broken_at=int(row[4]) if row[4] is not None else None,
        attested=bool(row[5]),
        forks=tuple(LedgerForkPoint(f["prev_hash"], tuple(f["children"])) for f in row[6]),
        orphans=tuple(_Orphan(o["child"], o["parent"]) for o in row[7]),
        full_verified_at=row[8],
        full_verified_seq=int(row[9]),
    )


def _anchor_holds(conn: Any, checkpoint: Checkpoint) -> bool:
    """Is the checkpoint still anchored in the ledger it claims to have verified?"""
    row = conn.execute(
        f"SELECT hash FROM {LEDGER_TABLE} WHERE seq = %s",  # noqa: S608 — fixed identifier
        (checkpoint.verified_seq,),
    ).fetchone()
    return row is not None and str(row[0]) == checkpoint.verified_hash


def _save(conn: Any, cp: Checkpoint) -> None:
    conn.execute(
        f"INSERT INTO {CHECKPOINT_TABLE} (id, verified_seq, verified_hash, verified_count, "  # noqa: S608
        f"content_ok, broken_at, attested, forks, orphans, full_verified_at, full_verified_seq, "
        f"updated_at) VALUES (1, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
        f"ON CONFLICT (id) DO UPDATE SET verified_seq = EXCLUDED.verified_seq, "
        f"verified_hash = EXCLUDED.verified_hash, verified_count = EXCLUDED.verified_count, "
        f"content_ok = EXCLUDED.content_ok, broken_at = EXCLUDED.broken_at, "
        f"attested = EXCLUDED.attested, forks = EXCLUDED.forks, orphans = EXCLUDED.orphans, "
        f"full_verified_at = EXCLUDED.full_verified_at, "
        f"full_verified_seq = EXCLUDED.full_verified_seq, updated_at = EXCLUDED.updated_at",
        (
            cp.verified_seq,
            cp.verified_hash,
            cp.verified_count,
            cp.content_ok,
            cp.broken_at,
            cp.attested,
            json.dumps(
                [{"prev_hash": f.prev_hash, "children": list(f.children)} for f in cp.forks]
            ),
            json.dumps([{"child": o.child, "parent": o.parent} for o in cp.orphans]),
            cp.full_verified_at,
            cp.full_verified_seq,
            datetime.now(UTC),
        ),
    )
    conn.commit()


# ── Verification ────────────────────────────────────────────────────────────────


def _hash_rows(rows: list[_Row], position: int) -> tuple[bool, int | None, bool]:
    """Recompute each row's hash. Returns (content_ok, broken_at position, saw_attestation)."""
    content_ok = True
    broken_at: int | None = None
    attested = False
    for offset, row in enumerate(rows):
        if row.payload.get("type") == LEDGER_ATTESTATION_TYPE:
            attested = True
        stored = row.payload.get("hash")
        recomputed = _hash_core({k: v for k, v in row.payload.items() if k != "hash"})
        if not isinstance(stored, str) or stored != recomputed:
            content_ok = False
            if broken_at is None:
                broken_at = position + offset
    return content_ok, broken_at, attested


def merge_verdict(
    checkpoint: Checkpoint,
    *,
    new_hashes: set[str],
    new_content_ok: bool,
    new_broken_at: int | None,
    new_attested: bool,
    touched_forks: tuple[LedgerForkPoint, ...],
    new_orphans: tuple[_Orphan, ...],
) -> tuple[bool, int | None, bool, tuple[LedgerForkPoint, ...], tuple[_Orphan, ...]]:
    """Fold what the new rows say into what the checkpoint already knew. PURE — no database.

    This is where an incremental verifier gets things wrong, so it is a function you can test
    without a Postgres:

    * content integrity is a conjunction, and ``broken_at`` keeps the FIRST break, not the latest;
    * ``attested`` is a disjunction — an attestation, once seen, is not un-seen;
    * a fork verdict is authoritative for the parents the new rows point at, and untouched parents
      keep the checkpoint's verdict (append-only means they cannot have gained a child);
    * an orphan is RESOLVED when a new row turns out to be the parent it was missing — which is
      why the checkpoint stores each orphan's parent hash, not just the orphan.
    """
    content_ok = checkpoint.content_ok and new_content_ok
    broken_at = checkpoint.broken_at if checkpoint.broken_at is not None else new_broken_at
    attested = checkpoint.attested or new_attested

    merged = {f.prev_hash: f for f in checkpoint.forks}
    merged.update({f.prev_hash: f for f in touched_forks})
    forks = tuple(merged.values())

    survivors = tuple(o for o in checkpoint.orphans if o.parent not in new_hashes)
    orphans = survivors + new_orphans
    return content_ok, broken_at, attested, forks, orphans


def verify_ledger_incremental(*, force_full: bool = False) -> LedgerVerdict:
    """The badge's verdict: verified against a checkpoint that is itself re-verified.

    Args:
        force_full: Re-walk and re-hash the ENTIRE chain, ignoring any checkpoint, and reset the
            freshness clock. This is what the periodic verifier calls.

    Returns:
        The tree status, plus how old the full-chain walk is and how much was read this time.
    """
    with _connect_sync() as conn:
        ensure_checkpoint_schema(conn)
        length = _length(conn)
        if length == 0:
            return LedgerVerdict(
                tree=LedgerTreeStatus(True, True, (), (), 0, None),
                full_verified_at=None,
                entries_since_full=0,
                entries_verified_now=0,
                checkpoint_used=False,
            )

        checkpoint = None if force_full else _load_checkpoint(conn)
        if checkpoint is not None and not _anchor_holds(conn, checkpoint):
            checkpoint = None  # a different chain — the history was replaced

        rows = _rows_above(conn, checkpoint.verified_seq if checkpoint else 0)

        # The count cross-check: a checkpoint whose arithmetic does not reconcile with the table
        # is a checkpoint about a table that grew somewhere it should not have. Free, and it
        # catches what the single-row anchor cannot.
        if checkpoint is not None and length != checkpoint.verified_count + len(rows):
            checkpoint = None
            rows = _rows_above(conn, 0)

        base_count = checkpoint.verified_count if checkpoint else 0
        new_ok, new_broken, new_attested = _hash_rows(rows, base_count)

        if checkpoint is None:
            content_ok, broken_at, attested = new_ok, new_broken, new_attested
            forks = _all_forks(conn)
            orphans = _all_orphans(conn)
        else:
            content_ok, broken_at, attested, forks, orphans = merge_verdict(
                checkpoint,
                new_hashes={r.hash for r in rows},
                new_content_ok=new_ok,
                new_broken_at=new_broken,
                new_attested=new_attested,
                touched_forks=_forks_touching(conn, checkpoint.verified_seq),
                new_orphans=_orphans_above(conn, checkpoint.verified_seq),
            )

        now = datetime.now(UTC)
        was_full = checkpoint is None
        if checkpoint is None:
            full_at, full_seq = now, _max_seq(conn)
        else:
            full_at, full_seq = checkpoint.full_verified_at, checkpoint.full_verified_seq

        tail = rows[-1] if rows else None
        if tail is not None:
            anchor_seq, anchor_hash = tail.seq, tail.hash
        elif checkpoint is not None:
            anchor_seq, anchor_hash = checkpoint.verified_seq, checkpoint.verified_hash
        else:
            row = conn.execute(
                f"SELECT seq, hash FROM {LEDGER_TABLE} ORDER BY seq DESC LIMIT 1"  # noqa: S608
            ).fetchone()
            anchor_seq, anchor_hash = (int(row[0]), str(row[1])) if row else (0, "")

        if rows or was_full:
            _save(
                conn,
                Checkpoint(
                    verified_seq=anchor_seq,
                    verified_hash=anchor_hash,
                    verified_count=length,
                    content_ok=content_ok,
                    broken_at=broken_at,
                    attested=attested,
                    forks=forks,
                    orphans=orphans,
                    full_verified_at=full_at,
                    full_verified_seq=full_seq,
                ),
            )

        since = conn.execute(
            f"SELECT count(*) FROM {LEDGER_TABLE} WHERE seq > %s",  # noqa: S608 — fixed ident
            (full_seq,),
        ).fetchone()

    return LedgerVerdict(
        tree=LedgerTreeStatus(
            content_integrity=content_ok,
            linear=content_ok and not forks and not orphans,
            forks=forks,
            orphans=tuple(o.child for o in orphans),
            length=length,
            broken_at=broken_at,
            attested=attested,
        ),
        full_verified_at=full_at,
        entries_since_full=int(since[0]) if since else 0,
        entries_verified_now=len(rows),
        checkpoint_used=not was_full,
    )


def run_full_verification() -> LedgerVerdict:
    """Re-walk the ENTIRE chain and reset the freshness clock — the off-chrono verifier.

    This is the claim the incremental path leans on. Without it the badge would say "verified" on
    the strength of a checkpoint nobody had re-earned; with it, the badge can say WHEN the whole
    chain was last read, and the reader can decide whether that is recent enough.
    """
    return verify_ledger_incremental(force_full=True)


def active_ledger_verdict(path: Any = None) -> LedgerVerdict:
    """The ACTIVE ledger's live verdict — incremental on the table, a full walk on a flat file.

    The seam for every caller that needs to know *whether the chain is intact right now* and does
    not need to prove it to a third party: the fleet's health dots, the header's integrity bell.
    They ask a weaker question than :func:`tessera.guard.seal.active_ledger_opposability` — "is
    there a proven break?", not "can I oppose this chain to a regulator?" — and they may pay a
    weaker price for it.

    The verdict always carries **the provenance of its own claim**: when the chain was last walked
    end to end, and how many entries have been verified against the checkpoint since. A caller may
    then show a green dot AND say what that green rests on. A checkpoint trusted in silence would
    be an assumption wearing the clothes of a proof; this one hands you its age unasked.

    File mode has no checkpoint — the walk IS full, every time — so the provenance says exactly
    that: walked now, nothing outstanding.
    """
    from tessera.guard.ledger_store import active_ledger_tree_status, ledger_source

    if ledger_source() == "postgres":
        return verify_ledger_incremental()
    tree = active_ledger_tree_status(path)
    return LedgerVerdict(
        tree=tree,
        full_verified_at=datetime.now(UTC),
        entries_since_full=0,
        entries_verified_now=tree.length,
        checkpoint_used=False,
    )
