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

from dataclasses import dataclass
from typing import TYPE_CHECKING

from tessera.sql import safe_identifier

if TYPE_CHECKING:
    from collections.abc import Collection

    from psycopg import AsyncCursor

__all__ = ["OrgRollup", "dedup_org_total", "shared_entities_among"]

# This module used to carry its own `_ident` — `^[a-z_][a-z0-9_]*$` with `re.match` — while
# the ClickHouse adapter carried a second, differently-spelled one. Two private validators for
# one rule, neither reused, and `re.match` let a trailing newline through both. There is now
# one gate: `tessera.sql.safe_identifier` (audit P0.3 `sql-fstring`).


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

    Returns:
        An :class:`OrgRollup`.
    """
    table_id = safe_identifier(table)
    entity_id = safe_identifier(entity_col)
    agent_id = safe_identifier(agent_col)

    # Every interpolation is an identifier validated above. The unused, injection-prone `where`
    # predicate parameter was removed (P0.3 class closure): no raw SQL text is accepted here,
    # so these f-strings are safe by construction, not by caller convention.
    per_agent_sql = (
        f"SELECT {agent_id} AS agent, count(DISTINCT {entity_id}) AS n "  # noqa: S608
        f"FROM {table_id} GROUP BY {agent_id}"
    )
    org_sql = f"SELECT count(DISTINCT {entity_id}) AS n FROM {table_id}"  # noqa: S608
    shared_sql = (
        f"SELECT count(*) AS n FROM ("  # noqa: S608
        f"  SELECT {entity_id} FROM {table_id} "
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


async def shared_entities_among(
    cur: AsyncCursor[dict[str, object]],
    *,
    table: str,
    entity_col: str,
    entities: Collection[str],
    agent_col: str = "agent_id",
) -> int:
    """How many of ``entities`` this table has seen under MORE THAN ONE agent.

    This is the reconciliation half of the dedup story. ``OrgRollup.shared`` answers a
    question about the table's own neighbourhood — "which of MY entities touch two
    agents?" — and it reads 0 with total composure when the handed-off journeys the S1
    journal attests never share an id in this table at all. So the caller passes the
    exact entities the journal claims crossed agents, and this asks the table about
    *those*: every one it cannot find under two agents is a journey the dedup silently
    double-counts. The two numbers travel together to the UI, which states the gap —
    never "0 dédoublonnées" dressed as a completed reconciliation.

    Args:
        cur: an async cursor whose ``row_factory`` yields ``dict`` rows.
        table: the entity table (validated identifier).
        entity_col: the distinct entity column (validated).
        entities: the entity ids the journal attests; empty ⇒ 0 without a query.
        agent_col: the agent column, default ``agent_id`` (validated).

    Returns:
        The count of ``entities`` present in ``table`` under >1 distinct agent.
    """
    if not entities:
        return 0
    table_id = safe_identifier(table)
    entity_id = safe_identifier(entity_col)
    agent_id = safe_identifier(agent_col)
    # Identifiers validated above; the id list travels as a bound parameter, never as text.
    sql = (
        f"SELECT count(*) AS n FROM ("  # noqa: S608
        f"  SELECT {entity_id} FROM {table_id} "
        f"  WHERE {entity_id} = ANY(%s) "
        f"  GROUP BY {entity_id} HAVING count(DISTINCT {agent_id}) > 1"
        f") s"
    )
    await cur.execute(sql, (sorted(entities),))
    return _as_int((await cur.fetchone() or {}).get("n"))
