"""Durable dual-write spool (ADR 0015 H2, step 2) — the zero-loss failure path.

Acceptance criterion #1 for retiring the flat audit.log: a Postgres blip during audit
emission must NEVER drop an event. This drives the spool directly (Postgres simulated by
monkeypatching the sync connection), cutting Postgres mid-stream, then restoring — and
proves the chain that lands is complete, in order, with no duplicate. Hermetic: no real
Postgres, no background thread (the drain is exercised synchronously).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tessera.guard import ledger_store
from tessera.guard.audit import _hash_core
from tessera.guard.ledger_store import drain_spool, verify_ledger_rows

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

_GENESIS = "0" * 64


def _chain(payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build a valid hash chain (genesis → …) from ``payloads``."""
    prev = _GENESIS
    out: list[dict[str, Any]] = []
    for p in payloads:
        entry = {"type": "tessera.guard.audit", **p, "prev_hash": prev}
        entry["hash"] = _hash_core(entry)
        prev = str(entry["hash"])
        out.append(entry)
    return out


class _FakeConn:
    def __init__(self, sink: list[tuple[object, ...]]) -> None:
        self._sink = sink

    def __enter__(self) -> _FakeConn:
        return self

    def __exit__(self, *_: object) -> bool:
        return False

    def execute(self, _sql: str, params: tuple[object, ...]) -> None:
        self._sink.append(params)

    def commit(self) -> None:
        pass


def _install_fake_postgres(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> tuple[list[tuple[object, ...]], dict[str, bool]]:
    """Point the spool at tmp, simulate Postgres with an in-memory sink + a cut switch."""
    from tessera.settings import get_settings

    monkeypatch.setattr(get_settings().guard, "audit_file", tmp_path / "audit.log")
    monkeypatch.setenv("TESSERA_LEDGER_DUAL_WRITE", "1")
    inserted: list[tuple[object, ...]] = []
    cut = {"on": False}

    def fake_connect() -> _FakeConn:
        if cut["on"]:
            msg = "postgres unreachable"
            raise RuntimeError(msg)
        return _FakeConn(inserted)

    monkeypatch.setattr(ledger_store, "_connect_sync", fake_connect)
    return inserted, cut


def test_spool_survives_a_postgres_outage_with_no_loss_no_dup_order_kept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inserted, cut = _install_fake_postgres(monkeypatch, tmp_path)
    entries = _chain([{"n": 0}, {"n": 1}, {"n": 2}, {"n": 3}])

    # 1) Postgres up: the first two entries land and the spool clears.
    ledger_store._spool_append(entries[0])
    ledger_store._spool_append(entries[1])
    assert drain_spool() is True
    assert [row[4] for row in inserted] == [entries[0]["hash"], entries[1]["hash"]]
    assert ledger_store._read_spool_locked() == []

    # 2) Postgres CUT mid-stream: two more audits are emitted → they SPOOL, nothing lands.
    cut["on"] = True
    ledger_store._spool_append(entries[2])
    ledger_store._spool_append(entries[3])
    assert drain_spool() is False  # unreachable → deferred, not dropped
    assert len(inserted) == 2  # nothing new landed
    assert len(ledger_store._read_spool_locked()) == 2  # the two are safe in the spool

    # 3) Postgres restored: the spool REPLAYS in chain order — zero loss.
    cut["on"] = False
    assert drain_spool() is True
    assert [row[4] for row in inserted] == [e["hash"] for e in entries]  # all 4, in order
    assert ledger_store._read_spool_locked() == []

    # 4) Re-draining is a no-op — zero duplicate (spool empty; ON CONFLICT would guard anyway).
    assert drain_spool() is True
    assert len(inserted) == 4

    # 5) The chain that landed is complete and verifies end-to-end (through the outage).
    status = verify_ledger_rows(entries)
    assert status.verified is True and status.length == 4


def test_partial_batch_never_half_commits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A drain that fails leaves the WHOLE batch spooled (one transaction, no partial)."""
    _inserted, cut = _install_fake_postgres(monkeypatch, tmp_path)
    entries = _chain([{"n": 0}, {"n": 1}, {"n": 2}])
    for e in entries:
        ledger_store._spool_append(e)
    cut["on"] = True
    assert drain_spool() is False
    # All three remain — a failed drain never drops or partially applies.
    assert len(ledger_store._read_spool_locked()) == 3


def test_enqueue_durably_spools_before_returning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The real emit entry point fsyncs to the spool before returning (crash-safe)."""
    _inserted, cut = _install_fake_postgres(monkeypatch, tmp_path)
    cut["on"] = True  # any drain fails, so the spooled entry is preserved for the assertion
    monkeypatch.setattr(ledger_store, "_writer_started", True)  # do not spawn the bg thread
    entry = _chain([{"n": 0}])[0]
    ledger_store.enqueue_ledger_entry(entry)
    spooled = ledger_store._read_spool_locked()
    assert len(spooled) == 1 and spooled[0]["hash"] == entry["hash"]


def test_dual_write_disabled_spools_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TESSERA_LEDGER_DUAL_WRITE=0 keeps the unit suite hermetic — no spool, no Postgres."""
    _install_fake_postgres(monkeypatch, tmp_path)
    monkeypatch.setenv("TESSERA_LEDGER_DUAL_WRITE", "0")
    ledger_store.enqueue_ledger_entry(_chain([{"n": 0}])[0])
    assert ledger_store._read_spool_locked() == []
