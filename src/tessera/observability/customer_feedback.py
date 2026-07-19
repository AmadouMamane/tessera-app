"""Durable customer-satisfaction store — the 👍/👎 a customer leaves on a reply (ADR 0041).

Unlike the operator console feedback (a per-conversation JSON toggle, operator-sourced),
this is a real, agent-attributed, windowable signal: one row per rated assistant turn,
carrying the agent that handled the turn and whether the turn was a test (``synthetic``),
so the Synthèse can compute a real per-agent CSAT over a trailing window and exclude
operator tests — the same real-traffic rule as the transcript (ADR 0040).

Customer telemetry, never a governed operator act: it names no author (the customer is
anonymous; the write is bound to a conversation by the signed resume capability at the
route, ADR 0008/F-4), and it is never written to the governance ledger.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from psycopg import sql

from tessera.agent.identity import DEFAULT_AGENT_ID
from tessera.retrieval.store import get_pool

if TYPE_CHECKING:
    from uuid import UUID

__all__ = ["RATINGS", "ensure_customer_feedback_schema", "record_customer_feedback"]

#: The only ratings a customer may leave — a thumbs up or down.
RATINGS: Final[frozenset[str]] = frozenset({"up", "down"})

_TABLE: Final[sql.Identifier] = sql.Identifier("customer_feedback")


async def ensure_customer_feedback_schema() -> None:
    """Create the customer-feedback table and its indexes idempotently."""
    pool = get_pool()
    if pool.closed:
        await pool.open()
    create_table = sql.SQL(
        """
        CREATE TABLE IF NOT EXISTS {table} (
            id              bigserial   PRIMARY KEY,
            conversation_id uuid        NOT NULL,
            turn_id         uuid        NOT NULL,
            agent_id        text        NOT NULL DEFAULT {default_agent},
            rating          text        NOT NULL,
            synthetic       boolean     NOT NULL DEFAULT false,
            created_at      timestamptz NOT NULL DEFAULT now()
        );
        """
    ).format(table=_TABLE, default_agent=sql.Literal(DEFAULT_AGENT_ID))
    # One vote per rated turn: a re-vote UPDATEs the row rather than piling clicks, so the
    # CSAT rate counts distinct rated turns. The UNIQUE index is also the ON CONFLICT target.
    unique_turn = sql.SQL(
        "CREATE UNIQUE INDEX IF NOT EXISTS {idx} ON {table} (conversation_id, turn_id);"
    ).format(idx=sql.Identifier("customer_feedback_turn"), table=_TABLE)
    # Mirrors ``conversation_messages_agent`` — the per-agent windowed read is the whole point.
    agent_index = sql.SQL(
        "CREATE INDEX IF NOT EXISTS {idx} ON {table} (agent_id, created_at);"
    ).format(idx=sql.Identifier("customer_feedback_agent"), table=_TABLE)
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(create_table)
        await cur.execute(unique_turn)
        await cur.execute(agent_index)
        await conn.commit()


async def record_customer_feedback(
    conversation_id: UUID,
    turn_id: UUID,
    *,
    agent_id: str,
    rating: str,
    synthetic: bool,
) -> None:
    """Persist (or update) the customer's vote on one assistant turn.

    ``agent_id`` and ``synthetic`` are inherited from the rated turn (resolved from the
    transcript by the caller), so the vote is attributed to the agent that actually
    handled it and a vote on a test turn is itself excluded from the real CSAT.

    Args:
        conversation_id: The conversation the rated turn belongs to.
        turn_id: The assistant turn being rated.
        agent_id: The agent that handled the turn (from the transcript).
        rating: ``"up"`` or ``"down"``.
        synthetic: Whether the rated turn was an operator test.

    Raises:
        ValueError: If ``rating`` is not a known rating (defence in depth; the route
            validates first).
    """
    if rating not in RATINGS:
        raise ValueError(f"unknown rating: {rating!r}")
    insert = sql.SQL(
        """
        INSERT INTO {table} (conversation_id, turn_id, agent_id, rating, synthetic)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (conversation_id, turn_id)
        DO UPDATE SET rating = EXCLUDED.rating,
                      agent_id = EXCLUDED.agent_id,
                      synthetic = EXCLUDED.synthetic,
                      created_at = now();
        """
    ).format(table=_TABLE)
    pool = get_pool()
    if pool.closed:
        await pool.open()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(insert, (conversation_id, turn_id, agent_id, rating, synthetic))
        await conn.commit()
