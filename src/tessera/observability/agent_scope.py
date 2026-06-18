"""Shared multi-agent scope helpers for GOUVERNER / PLATEFORME surfaces.

GOUVERNER (Surveiller / Agir / Prouver) and PLATEFORME (Configurer / Admin) are
**global, filterable by agent** via a URL filter (``?agent=all|<id>``) that is
*distinct* from the AGENT switcher (which only scopes ``AGENT/*``). Org totals on
these surfaces count **DISTINCT entities**: a conversation that spanned two agents
through a handoff counts **once** for the org — never the naive per-agent sum.

This module centralises the deduplicated-org-total computation that the fleet view
(:mod:`tessera.observability.fleet`) pioneered, so every global surface reconciles
the same way. The reusable bit is the dedup arithmetic over an ``(entity, agent)``
table; pages layer their own observable per-agent KPIs on top.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from psycopg import AsyncCursor

__all__ = ["OrgRollup", "dedup_org_total"]

# SQL identifiers are interpolated (table / column names cannot be bound params),
# so we constrain them to a strict allowlist shape before they touch a query.
_IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")


def _ident(name: str) -> str:
    """Return ``name`` if it is a safe SQL identifier, else raise ``ValueError``."""
    if not _IDENT.match(name):
        msg = f"unsafe SQL identifier: {name!r}"
        raise ValueError(msg)
    return name


def _as_int(value: object) -> int:
    """Coerce a SQL count cell (int / Decimal / None) to ``int``, defaulting to 0."""
    return int(value) if isinstance(value, int | float) else 0


@dataclass(frozen=True, slots=True)
class OrgRollup:
    """Deduplicated org rollup over an ``(entity, agent)`` table.

    Attributes:
        org: distinct entities across the whole org (a handoff conversation = 1).
        naive_sum: the misleading sum of per-agent distinct counts — kept so the UI
            can *show* what dedup saved, never as the headline total.
        shared: entities touching more than one agent (the dedup population).
        dedup_saved: ``naive_sum - org`` (double-counting removed).
        by_agent: distinct entity count per agent id (its own slice).
    """

    org: int
    naive_sum: int
    shared: int
    dedup_saved: int
    by_agent: dict[str, int]


async def dedup_org_total(
    cur: AsyncCursor[dict[str, object]],
    *,
    table: str,
    entity_col: str,
    agent_col: str = "agent_id",
    where: str = "",
) -> OrgRollup:
    """Compute the deduplicated org rollup for an ``(entity, agent)`` table.

    The org total is ``count(DISTINCT entity_col)`` over the whole table — never
    the sum of the per-agent slices, so a conversation spanning two agents counts
    once. ``by_agent`` gives each agent its own distinct count (used for the
    breakdown); their sum is the *naive* total whose gap from ``org`` is the
    dedup saving.

    Args:
        cur: an async cursor whose ``row_factory`` yields ``dict`` rows.
        table: the entity table (validated identifier).
        entity_col: the distinct entity column, e.g. ``conversation_id`` (validated).
        agent_col: the agent column, default ``agent_id`` (validated).
        where: optional raw SQL predicate (no leading ``WHERE``); the caller owns
            its safety — pass constants only, never user input.

    Returns:
        An :class:`OrgRollup`.
    """
    table_id = _ident(table)
    entity_id = _ident(entity_col)
    agent_id = _ident(agent_col)
    clause = f" WHERE {where}" if where else ""

    # Identifiers are validated above; the predicate is caller-owned constant SQL.
    per_agent_sql = (
        f"SELECT {agent_id} AS agent, count(DISTINCT {entity_id}) AS n "  # noqa: S608
        f"FROM {table_id}{clause} GROUP BY {agent_id}"
    )
    org_sql = f"SELECT count(DISTINCT {entity_id}) AS n FROM {table_id}{clause}"  # noqa: S608
    shared_sql = (
        f"SELECT count(*) AS n FROM ("  # noqa: S608
        f"  SELECT {entity_id} FROM {table_id}{clause} "
        f"  GROUP BY {entity_id} HAVING count(DISTINCT {agent_id}) > 1"
        f") s"
    )

    await cur.execute(per_agent_sql)
    by_agent = {str(r["agent"]): _as_int(r["n"]) for r in await cur.fetchall()}
    naive_sum = sum(by_agent.values())

    await cur.execute(org_sql)
    org = _as_int((await cur.fetchone() or {}).get("n"))

    await cur.execute(shared_sql)
    shared = _as_int((await cur.fetchone() or {}).get("n"))

    return OrgRollup(
        org=org,
        naive_sum=naive_sum,
        shared=shared,
        dedup_saved=naive_sum - org,
        by_agent=by_agent,
    )
