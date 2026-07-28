"""Cross-worker coordination via Postgres advisory locks (ADR 0044).

When the agent runs as N uvicorn worker processes (``TESSERA_API__WORKERS>1``) two
boot concerns stop being free:

* **The lifespan background loops** — the Hica seal cycle, the canary turns, the GDPR
  retention purge, the full ledger re-verification, and the one-time convergence sweeps
  (gating archive, ledger drain/backfill) — must run **once**, not once per worker. N
  concurrent sealers or N purge loops are not a scaling win, they are a correctness bug.
* **Schema bootstrap** — ``CREATE TABLE/INDEX IF NOT EXISTS`` races to a catalogue
  duplicate-key error when several fresh workers run it at the same instant (the same race
  ``_isolate_environment`` already guards for ``CREATE SCHEMA``).

Both are solved the same way the store already solves the schema-creation race: a Postgres
advisory lock. This module is the single place that owns those locks.

* :func:`try_become_leader` takes a **session-scoped** lock on a *dedicated* connection and
  hands it back to exactly one worker. The winner keeps the connection open for its whole
  life (the loops run under it); the losers get ``None`` and serve request traffic only. If
  the leader dies its connection drops, Postgres releases the lock, and a respawned worker
  re-acquires it on its next boot — leadership self-heals.
* :func:`bootstrap_lock` takes a **blocking** lock for the duration of the schema-ensure
  block, so concurrent workers serialise their ``CREATE ... IF NOT EXISTS`` instead of
  racing. It is released the instant the block finishes.

Both locks are keyed by ``hashtext(<env schema>)`` so two environments sharing one Postgres
never contend, mirroring the schema isolation of ADR 0014. In the single-worker default
(``workers=1``) the lone process trivially wins leadership and the bootstrap lock is
uncontended — behaviour is identical to the pre-ADR single-process model.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

import psycopg

from tessera.observability import logging as obs_logging
from tessera.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

__all__ = ["bootstrap_lock", "try_become_leader"]

# Advisory-lock ``objid``s (int4). The ``classid`` is always ``hashtext(schema)`` so the
# pair is unique per (environment, purpose). Values are arbitrary; only their stability and
# mutual distinctness matter.
_LEADER_PURPOSE = 0x1EAD  # "lead" — the singleton background-loop leader
_BOOT_PURPOSE = 0x0B07  # "boot" — serialises the schema-ensure block


async def try_become_leader() -> psycopg.AsyncConnection[Any] | None:
    """Try to acquire the singleton background-loop leadership for this worker.

    Opens a **dedicated** connection — never the shared pool, whose connections must cycle —
    and takes a session-scoped ``pg_try_advisory_lock`` keyed by the env schema. Exactly one
    worker across the process group wins.

    Returns:
        The held connection when this worker is the leader (the caller MUST keep it open for
        the process lifetime and close it to abdicate), or ``None`` when another worker
        already leads. Best-effort: a DB hiccup logs and returns ``None`` (no leader this
        cycle) rather than crashing boot — a respawned worker retries.
    """
    settings = get_settings()
    log = obs_logging.get_logger("tessera.leader")
    try:
        conn = await psycopg.AsyncConnection.connect(str(settings.postgres.dsn), autocommit=True)
    except Exception as exc:  # a leaderless boot is honest; a crashed boot is not
        log.warning("leader.connect_failed", error=str(exc))
        return None
    try:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT pg_try_advisory_lock(hashtext(%s), %s)",
                (settings.pg_schema, _LEADER_PURPOSE),
            )
            row = await cur.fetchone()
        won = bool(row and row[0])
    except Exception as exc:
        await conn.close()
        log.warning("leader.acquire_failed", error=str(exc))
        return None
    if not won:
        await conn.close()
        return None
    return conn


@asynccontextmanager
async def bootstrap_lock() -> AsyncIterator[None]:
    """Serialise the schema-ensure block across workers (blocking session lock).

    Holds a blocking ``pg_advisory_lock`` on a dedicated connection for the duration of the
    ``with`` body, so concurrent workers run their ``CREATE ... IF NOT EXISTS`` one at a
    time. Released and closed on exit. Best-effort acquisition: if the dedicated connection
    cannot be opened the block still runs (unsynchronised) rather than blocking boot — the
    IF-NOT-EXISTS guards remain correct in the common (already-created) case, and the lock
    only removes the rare cold-start race.
    """
    settings = get_settings()
    log = obs_logging.get_logger("tessera.leader")
    try:
        conn = await psycopg.AsyncConnection.connect(str(settings.postgres.dsn), autocommit=True)
    except Exception as exc:
        log.warning("bootstrap.lock_unavailable", error=str(exc))
        yield  # run the ensures anyway; IF NOT EXISTS is still correct, just unsynchronised
        return
    try:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT pg_advisory_lock(hashtext(%s), %s)",
                (settings.pg_schema, _BOOT_PURPOSE),
            )
        yield
    finally:
        try:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT pg_advisory_unlock(hashtext(%s), %s)",
                    (settings.pg_schema, _BOOT_PURPOSE),
                )
        finally:
            await conn.close()
