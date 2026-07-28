"""Integration tests for the advisory-lock leader (ADR 0044) against a LIVE Postgres.

Proves the property the unit tests can only mock: across independent sessions, exactly one
``try_become_leader`` holds the session-scoped advisory lock at a time, and closing the holder
releases it so a later attempt can win. Tagged ``integration``; skips cleanly with no database.
"""

from __future__ import annotations

import psycopg
import pytest

from tessera.api import leader

pytestmark = pytest.mark.integration


@pytest.fixture
async def _pg() -> None:
    """Skip unless Postgres is reachable at the configured DSN."""
    from tessera.settings import get_settings

    dsn = str(get_settings().postgres.dsn)
    try:
        conn = await psycopg.AsyncConnection.connect(dsn, connect_timeout=2)
        await conn.close()
    except (psycopg.OperationalError, OSError) as exc:
        pytest.skip(f"Postgres unavailable: {exc}")


@pytest.mark.usefixtures("_pg")
async def test_exactly_one_of_two_concurrent_attempts_wins() -> None:
    first = await leader.try_become_leader()
    second = await leader.try_become_leader()
    try:
        # Two independent sessions, one lock: exactly one holds it.
        assert (first is None) != (second is None)
    finally:
        for conn in (first, second):
            if conn is not None:
                await conn.close()


@pytest.mark.usefixtures("_pg")
async def test_leadership_transfers_after_the_holder_abdicates() -> None:
    first = await leader.try_become_leader()
    assert first is not None  # uncontended → wins
    await first.close()  # abdicate: closing the connection releases the session lock

    second = await leader.try_become_leader()
    try:
        assert second is not None  # the freed lock can be re-acquired
    finally:
        if second is not None:
            await second.close()


@pytest.mark.usefixtures("_pg")
async def test_bootstrap_lock_is_uncontended_after_release() -> None:
    # Two sequential bootstrap blocks must each acquire and release cleanly — a leaked lock
    # from the first would deadlock the second (it is a BLOCKING acquire).
    async with leader.bootstrap_lock():
        pass
    async with leader.bootstrap_lock():
        pass
