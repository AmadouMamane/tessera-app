"""Persisted runtime application settings (a tiny key/value on Postgres).

Some toggles must outlive a process and be shared across instances — unlike the
frozen :mod:`tessera.settings` (env-derived, immutable per deploy). The first
such toggle is whether the superadmin has granted the ``admin`` role visibility
of the failure synthesis, which is superadmin-only by default.

The table is created idempotently on first use (same pattern as the memory
transcript), so there is no separate migration step. Values are booleans; the
key space is a closed set of named flags defined here.
"""

from __future__ import annotations

from typing import Final

from psycopg import sql
from psycopg.rows import dict_row

from tessera.retrieval.store import get_pool

__all__ = ["get_synthesis_admin", "set_synthesis_admin"]

_TABLE: Final[sql.Identifier] = sql.Identifier("app_settings")
_SYNTHESIS_ADMIN_KEY: Final[str] = "synthesis_visible_to_admin"


async def _ensure_schema() -> None:
    """Create the settings table idempotently."""
    pool = get_pool()
    if pool.closed:
        await pool.open()
    create_table = sql.SQL(
        """
        CREATE TABLE IF NOT EXISTS {table} (
            key        text        PRIMARY KEY,
            value      boolean     NOT NULL,
            updated_at timestamptz NOT NULL DEFAULT now()
        );
        """
    ).format(table=_TABLE)
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(create_table)
        await conn.commit()


async def _get_flag(key: str, *, default: bool = False) -> bool:
    """Return a boolean flag, or ``default`` when it has never been set."""
    await _ensure_schema()
    pool = get_pool()
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            sql.SQL("SELECT value FROM {table} WHERE key = %s;").format(table=_TABLE),
            (key,),
        )
        row = await cur.fetchone()
    return bool(row["value"]) if row is not None else default


async def _set_flag(key: str, *, enabled: bool) -> bool:
    """Upsert a boolean flag and return the stored value."""
    await _ensure_schema()
    pool = get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            sql.SQL(
                """
                INSERT INTO {table} (key, value, updated_at)
                VALUES (%s, %s, now())
                ON CONFLICT (key) DO UPDATE
                  SET value = EXCLUDED.value, updated_at = now();
                """
            ).format(table=_TABLE),
            (key, enabled),
        )
        await conn.commit()
    return enabled


async def get_synthesis_admin() -> bool:
    """Whether the ``admin`` role may currently view the failure synthesis."""
    return await _get_flag(_SYNTHESIS_ADMIN_KEY)


async def set_synthesis_admin(*, enabled: bool) -> bool:
    """Grant or revoke ``admin`` visibility of the failure synthesis."""
    return await _set_flag(_SYNTHESIS_ADMIN_KEY, enabled=enabled)
