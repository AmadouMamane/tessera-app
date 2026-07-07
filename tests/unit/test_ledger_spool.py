"""Durable dual-write spool (ADR 0015 H2, step 2) — the zero-loss failure path, now
serialized + fork-free (TESS-LEDGER-001).

Acceptance criterion #1 for retiring the flat audit.log: a Postgres blip during audit
emission must NEVER drop an event. Drives the spool directly (Postgres simulated by an
in-memory table, ``FakeLedgerConn``), cutting Postgres mid-stream, then restoring — and
proves the chain that lands is complete, in order, and verifies. Post-fix the drain assigns
the chain linkage itself under the advisory lock (the head is read in-transaction), so the
LANDED ``prev_hash``/``hash`` are the drain's, not the emitter's; idempotence is by the
position-independent ``event_id``. Hermetic: no real Postgres, no background thread.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tessera.guard import ledger_store
from tessera.guard.ledger_store import drain_spool, verify_ledger_rows
from tests.unit._ledger_fake import FakeLedgerConn

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _entries(ns: list[int]) -> list[dict[str, Any]]:
    """Raw (unlinked) audit entries with distinct content — the drain links them."""
    return [
        {"type": "tessera.guard.audit", "occurred_at": f"2026-07-07T00:00:0{n}+00:00", "n": n}
        for n in ns
    ]


def _install_fake_postgres(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> tuple[FakeLedgerConn, dict[str, bool]]:
    """Point the spool at tmp, simulate Postgres with a persistent in-memory table + cut switch."""
    from tessera.settings import get_settings

    monkeypatch.setattr(get_settings().guard, "audit_file", tmp_path / "audit.log")
    monkeypatch.setenv("TESSERA_LEDGER_DUAL_WRITE", "1")
    conn = FakeLedgerConn()
    cut = {"on": False}

    def fake_connect() -> FakeLedgerConn:
        if cut["on"]:
            msg = "postgres unreachable"
            raise RuntimeError(msg)
        return conn

    monkeypatch.setattr(ledger_store, "_connect_sync", fake_connect)
    return conn, cut


def test_spool_survives_a_postgres_outage_with_no_loss_no_dup_order_kept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    conn, cut = _install_fake_postgres(monkeypatch, tmp_path)
    entries = _entries([0, 1, 2, 3])

    # 1) Postgres up: the first two entries land (drain-linked from genesis) and the spool clears.
    ledger_store._spool_append(entries[0])
    ledger_store._spool_append(entries[1])
    assert drain_spool() is True
    assert [p["n"] for p in conn.payloads()] == [0, 1]  # landed, in order
    assert ledger_store._read_spool_locked() == []

    # 2) Postgres CUT mid-stream: two more audits are emitted → they SPOOL, nothing lands.
    cut["on"] = True
    ledger_store._spool_append(entries[2])
    ledger_store._spool_append(entries[3])
    assert drain_spool() is False  # unreachable → deferred, not dropped
    assert len(conn.rows) == 2  # nothing new landed
    assert len(ledger_store._read_spool_locked()) == 2  # the two are safe in the spool

    # 3) Postgres restored: the spool REPLAYS in chain order — zero loss.
    cut["on"] = False
    assert drain_spool() is True
    assert [p["n"] for p in conn.payloads()] == [0, 1, 2, 3]  # all 4, in order
    assert ledger_store._read_spool_locked() == []

    # 4) Re-draining is a no-op — zero duplicate (idempotent by event_id).
    ledger_store._spool_append(entries[1])  # re-emit an already-durable entry
    assert drain_spool() is True
    assert len(conn.rows) == 4  # not re-inserted

    # 5) The chain that landed is complete and verifies end-to-end (through the outage).
    status = verify_ledger_rows(conn.payloads())
    assert status.verified is True and status.length == 4

    # 6) The drain assigned the linkage: genesis → e0 → e1 → e2 → e3 (no fork).
    assert conn.payloads()[0]["prev_hash"] == "0" * 64
    prev_hashes = [p["prev_hash"] for p in conn.payloads()]
    hashes = [p["hash"] for p in conn.payloads()]
    assert prev_hashes[1:] == hashes[:-1]  # each links to its immediate predecessor


def test_partial_batch_never_half_commits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A drain that fails leaves the WHOLE batch spooled (one transaction, no partial)."""
    conn, cut = _install_fake_postgres(monkeypatch, tmp_path)
    for e in _entries([0, 1, 2]):
        ledger_store._spool_append(e)
    cut["on"] = True
    assert drain_spool() is False
    # All three remain — a failed drain never drops or partially applies.
    assert len(ledger_store._read_spool_locked()) == 3
    assert len(conn.rows) == 0


def test_enqueue_durably_spools_before_returning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The real emit entry point fsyncs to the spool before returning (crash-safe)."""
    _conn, cut = _install_fake_postgres(monkeypatch, tmp_path)
    cut["on"] = True  # any drain fails, so the spooled entry is preserved for the assertion
    monkeypatch.setattr(ledger_store, "_writer_started", True)  # do not spawn the bg thread
    entry = _entries([0])[0]
    ledger_store.enqueue_ledger_entry(entry)
    spooled = ledger_store._read_spool_locked()
    assert len(spooled) == 1 and spooled[0]["n"] == 0


def test_dual_write_disabled_spools_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TESSERA_LEDGER_DUAL_WRITE=0 keeps the unit suite hermetic — no spool, no Postgres."""
    _install_fake_postgres(monkeypatch, tmp_path)
    monkeypatch.setenv("TESSERA_LEDGER_DUAL_WRITE", "0")
    ledger_store.enqueue_ledger_entry(_entries([0])[0])
    assert ledger_store._read_spool_locked() == []
