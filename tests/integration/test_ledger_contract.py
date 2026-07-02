"""Contract tests: the promoted ledger against LIVE Postgres (ADR 0015 §Amendment 3).

Integration-tagged. Proves the properties that only a real store can prove: the
append-only trigger actually raises on UPDATE/DELETE, the backfill verifies-then-copies
(idempotent; refuses a broken file), and shadow-verify holds when — and only when — both
mediums cover the same intact chain. The test env's table is dropped first so every run
verifies a deterministic chain (test-env DDL only; the trigger blocks DML, not DDL — the
chain, not the medium, is the tamper evidence).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from tessera.guard.audit import _hash_core
from tessera.guard.ledger_store import (
    LEDGER_TABLE,
    backfill_ledger_from_file,
    ensure_audit_ledger_schema,
    load_ledger_payloads_sync,
    shadow_verify_ledger,
)

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

_GENESIS = "0" * 64


def _write_chain(path: Path, count: int) -> None:
    prev = _GENESIS
    lines = []
    for n in range(count):
        entry: dict[str, object] = {
            "type": "tessera.guard.audit",
            "occurred_at": f"2026-01-01T00:00:0{n}+00:00",
            "agent_id": "contract-probe",
            "n": n,
            "prev_hash": prev,
        }
        entry["hash"] = _hash_core(entry)
        prev = str(entry["hash"])
        lines.append(json.dumps(entry, ensure_ascii=False))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def _fresh_ledger() -> None:
    """Drop + recreate the TEST env's ledger so each run verifies a deterministic chain."""
    from tessera.retrieval.store import get_pool

    try:
        pool = get_pool()
        if pool.closed:
            await pool.open()
        async with pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(f"DROP TABLE IF EXISTS {LEDGER_TABLE}")
            await conn.commit()
    except Exception:  # any connection failure means "no local Postgres"
        pytest.skip("postgres not up (docker compose up)")
    await ensure_audit_ledger_schema()


class TestAppendOnlyEnforcement:
    async def test_update_and_delete_raise_insert_succeeds(self, tmp_path: Path) -> None:
        import psycopg

        from tessera.retrieval.store import get_pool

        await _fresh_ledger()
        chain_file = tmp_path / "audit.log"
        _write_chain(chain_file, 2)
        inserted, status = await backfill_ledger_from_file(chain_file)
        assert inserted == 2 and status.verified
        pool = get_pool()
        async with pool.connection() as conn, conn.cursor() as cur:
            with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
                await cur.execute(f"UPDATE {LEDGER_TABLE} SET agent_id = 'tampered'")  # noqa: S608
            await conn.rollback()
            with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
                await cur.execute(f"DELETE FROM {LEDGER_TABLE}")  # noqa: S608
            await conn.rollback()


class TestVerifiedBackfill:
    async def test_backfill_is_idempotent_and_walk_verifies(self, tmp_path: Path) -> None:
        await _fresh_ledger()
        chain_file = tmp_path / "audit.log"
        _write_chain(chain_file, 3)
        first, status = await backfill_ledger_from_file(chain_file)
        assert (first, status.verified, status.length) == (3, True, 3)
        again, _ = await backfill_ledger_from_file(chain_file)
        assert again == 0  # unique hash → re-run is free
        shadow = shadow_verify_ledger(chain_file)
        assert shadow.ok
        assert shadow.table_status.length == 3 == shadow.file_count

    async def test_backfill_refuses_a_broken_file_chain(self, tmp_path: Path) -> None:
        await _fresh_ledger()
        chain_file = tmp_path / "audit.log"
        _write_chain(chain_file, 3)
        lines = chain_file.read_text(encoding="utf-8").splitlines()
        tampered = json.loads(lines[1])
        tampered["n"] = 999  # edit without re-hashing → the file chain breaks
        lines[1] = json.dumps(tampered, ensure_ascii=False)
        chain_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        inserted, status = await backfill_ledger_from_file(chain_file)
        assert inserted == 0  # never import a broken chain
        assert status.verified is False and status.broken_at == 1
        assert load_ledger_payloads_sync() == []  # nothing leaked into the table

    async def test_shadow_verify_fails_on_divergent_mediums(self, tmp_path: Path) -> None:
        await _fresh_ledger()
        chain_file = tmp_path / "audit.log"
        _write_chain(chain_file, 2)
        await backfill_ledger_from_file(chain_file)
        _write_chain(chain_file, 3)  # the file moved on; the table did not
        shadow = shadow_verify_ledger(chain_file)
        assert shadow.file_status.verified and shadow.table_status.verified
        assert not shadow.ok  # both intact but NOT covering the same entries → no cut
