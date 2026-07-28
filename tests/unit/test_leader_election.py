"""Unit tests for the advisory-lock coordination (ADR 0044), hermetic — no real Postgres.

The real mutual-exclusion property (exactly one holder across processes) is a Postgres fact,
covered by ``tests/integration/test_leader_election.py``. Here we pin the *contract* around the
lock with a fake connection: the winner keeps its connection, a loser closes it, and both
helpers fail OPEN (no leader / run-anyway) when the DB is unreachable rather than crashing boot.
"""

from __future__ import annotations

from typing import Any
from unittest import mock

from tessera.api import leader


class _FakeCursor:
    def __init__(self, conn: _FakeConn) -> None:
        self._conn = conn

    async def __aenter__(self) -> _FakeCursor:
        return self

    async def __aexit__(self, *_exc: object) -> bool:
        return False

    async def execute(self, sql: str, params: tuple[Any, ...] | None = None) -> None:
        if self._conn.execute_raises:
            raise RuntimeError("query blew up")
        self._conn.executed.append((sql, params))

    async def fetchone(self) -> tuple[Any, ...] | None:
        return self._conn.row


class _FakeConn:
    def __init__(self, row: tuple[Any, ...] | None, *, execute_raises: bool = False) -> None:
        self.row = row
        self.execute_raises = execute_raises
        self.closed = False
        self.executed: list[tuple[str, tuple[Any, ...] | None]] = []

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(self)

    async def close(self) -> None:
        self.closed = True


def _patch_connect(conn: _FakeConn | None) -> mock._patch:
    async def _connect(*_a: object, **_k: object) -> _FakeConn:
        if conn is None:
            raise RuntimeError("could not connect")
        return conn

    return mock.patch("tessera.api.leader.psycopg.AsyncConnection.connect", new=_connect)


# ── try_become_leader ────────────────────────────────────────────────────────────────────


async def test_leader_wins_and_keeps_connection() -> None:
    conn = _FakeConn(row=(True,))
    with _patch_connect(conn):
        held = await leader.try_become_leader()
    assert held is conn
    assert conn.closed is False  # the leader must keep the lock alive
    # It asked for the session lock keyed by the env schema + the leader purpose.
    sql, params = conn.executed[-1]
    assert "pg_try_advisory_lock" in sql
    assert params == ("tessera_ci", leader._LEADER_PURPOSE)


async def test_loser_gets_none_and_closes_connection() -> None:
    conn = _FakeConn(row=(False,))
    with _patch_connect(conn):
        held = await leader.try_become_leader()
    assert held is None
    assert conn.closed is True  # a non-leader must not leak the dedicated connection


async def test_leader_fails_open_when_db_unreachable() -> None:
    with _patch_connect(None):
        held = await leader.try_become_leader()
    assert held is None  # a leaderless boot is honest; a crashed boot is not


async def test_leader_closes_connection_on_query_error() -> None:
    conn = _FakeConn(row=None, execute_raises=True)
    with _patch_connect(conn):
        held = await leader.try_become_leader()
    assert held is None
    assert conn.closed is True


# ── bootstrap_lock ───────────────────────────────────────────────────────────────────────


async def test_bootstrap_lock_acquires_and_releases() -> None:
    conn = _FakeConn(row=None)
    with _patch_connect(conn):
        async with leader.bootstrap_lock():
            pass
    assert conn.closed is True
    statements = [sql for sql, _ in conn.executed]
    assert any("pg_advisory_lock" in s for s in statements)
    assert any("pg_advisory_unlock" in s for s in statements)


async def test_bootstrap_lock_runs_body_even_without_db() -> None:
    ran = False
    with _patch_connect(None):
        async with leader.bootstrap_lock():
            ran = True
    # IF NOT EXISTS is still correct unsynchronised; the block must run, not block boot.
    assert ran is True


async def test_bootstrap_lock_releases_on_body_exception() -> None:
    conn = _FakeConn(row=None)
    with _patch_connect(conn):
        try:
            async with leader.bootstrap_lock():
                raise ValueError("boom")
        except ValueError:
            pass
    assert conn.closed is True  # released + closed even when the body raised
