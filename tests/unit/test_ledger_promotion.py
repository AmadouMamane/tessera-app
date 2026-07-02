"""H — the promoted append-only hash-chained ledger (ADR 0015 §Amendment 3), offline.

Locks the pure verification (a chain WALK from genesis — order-independent, so a fork,
orphan, edit or gap fails regardless of insert order), the source switch and its honest
degradation, the hermetic dual-write off-switch, and the occurred_at indexing rule. The
live legs (append-only trigger enforcement, verified backfill, shadow-verify) are covered
by the integration contract tests.
"""

from __future__ import annotations

import pytest

from tessera.guard.audit import _hash_core
from tessera.guard.ledger_store import (
    _entry_occurred_at,
    dual_write_enabled,
    ledger_source,
    verify_ledger_rows,
)

_GENESIS = "0" * 64


def _chained(cores: list[dict[str, object]]) -> list[dict[str, object]]:
    """Link entries into a valid chain exactly like ``_append_to_chain`` does."""
    prev = _GENESIS
    out: list[dict[str, object]] = []
    for core in cores:
        entry = {**core, "prev_hash": prev}
        entry["hash"] = _hash_core(entry)
        out.append(entry)
        prev = str(entry["hash"])
    return out


def _three() -> list[dict[str, object]]:
    return _chained(
        [
            {"type": "tessera.guard.audit", "occurred_at": "2026-01-01T00:00:00+00:00", "n": 1},
            {"type": "tessera.agent.routing", "occurred_at": "2026-01-01T00:00:01+00:00", "n": 2},
            {"type": "tessera.guard.audit", "occurred_at": "2026-01-01T00:00:02+00:00", "n": 3},
        ]
    )


class TestChainWalkVerification:
    def test_valid_chain_verifies(self) -> None:
        status = verify_ledger_rows(_three())
        assert status.verified is True and status.length == 3

    def test_verification_is_order_independent(self) -> None:
        # The walk rebuilds the linked list from genesis: rows may arrive in any insert
        # order (a healed dual-write gap lands late) without weakening the proof.
        rows = _three()
        shuffled = [rows[2], rows[0], rows[1]]
        assert verify_ledger_rows(shuffled).verified is True

    def test_edited_payload_breaks_the_walk(self) -> None:
        rows = _three()
        tampered = dict(rows[1])
        tampered["n"] = 999  # the stored hash no longer matches the canonical payload
        assert verify_ledger_rows([rows[0], tampered, rows[2]]).verified is False

    def test_missing_link_breaks_the_walk(self) -> None:
        rows = _three()
        status = verify_ledger_rows([rows[0], rows[2]])  # gap: rows[2]'s parent absent
        assert status.verified is False
        assert status.broken_at == 1

    def test_fork_is_detected(self) -> None:
        rows = _three()
        fork = {**rows[1], "n": 42}
        fork["hash"] = _hash_core({k: v for k, v in fork.items() if k != "hash"})
        # Two entries claim the same parent: the second branch is unreachable → broken.
        assert verify_ledger_rows([*rows, fork]).verified is False

    def test_empty_ledger_is_trivially_verified(self) -> None:
        assert verify_ledger_rows([]).verified is True


class TestSourceSwitch:
    def test_default_is_the_flat_file(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.delenv("TESSERA_LEDGER_SOURCE", raising=False)
        assert ledger_source() == "file"

    def test_cut_selects_postgres(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setenv("TESSERA_LEDGER_SOURCE", "postgres")
        assert ledger_source() == "postgres"

    def test_unknown_value_falls_back_to_file(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setenv("TESSERA_LEDGER_SOURCE", "langfuse")  # never a third party
        assert ledger_source() == "file"

    def test_suite_disables_the_dual_write(self) -> None:
        # conftest hermeticity: audit emission in tests must never reach Postgres.
        assert dual_write_enabled() is False

    def test_promoted_read_degrades_honestly_when_unreachable(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        import psycopg

        from tessera.observability.spine.adapters import current
        from tessera.observability.spine.adapters.base import SpineUnavailableError

        monkeypatch.setenv("TESSERA_LEDGER_SOURCE", "postgres")

        def _down() -> list[dict[str, object]]:
            raise psycopg.OperationalError("down")

        monkeypatch.setattr("tessera.guard.ledger_store.load_ledger_payloads_sync", _down)
        with pytest.raises(SpineUnavailableError, match="promoted ledger"):
            current._read_audit_ledger()


class TestOccurredAtIndexing:
    def test_occurred_at_is_parsed_aware(self) -> None:
        stamp = _entry_occurred_at({"occurred_at": "2026-01-01T00:00:00+00:00"})
        assert stamp.tzinfo is not None
        assert stamp.year == 2026

    def test_recorded_at_is_the_fallback(self) -> None:
        stamp = _entry_occurred_at({"recorded_at": "2026-02-02T00:00:00+00:00"})
        assert stamp.month == 2


class TestActiveLedgerIntegritySignal:
    async def test_signal_reports_the_active_medium(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        from tessera.observability.spine.scope import Scope
        from tessera.observability.spine.signals import _read_audit_integrity

        monkeypatch.delenv("TESSERA_LEDGER_SOURCE", raising=False)
        data = await _read_audit_integrity(Scope())
        assert data["medium"] == "file"  # the H cut is visible in the signal payload
        assert isinstance(data["chain_valid"], bool)  # the shared ci file's verdict, honest
