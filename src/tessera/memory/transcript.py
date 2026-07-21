"""Durable, server-side conversation transcript — Mechanism A of ADR 0007.

This is the fix for Tessera's real memory gap: before this, conversation
continuity lived entirely in the client (the dashboard re-sent the full history
on every request). The transcript makes the **server** the source of truth, so
continuity survives client bugs and a second client, and every conversation is
replayable for the audit trail.

Why a dedicated table rather than re-keying the LangGraph checkpointer by
conversation id: ``AgentState`` carries per-turn accumulator channels
(``retrieved_documents``, ``tool_calls``, ``citations``, ``guard_decisions``,
``errors``) whose reducers *concatenate*. Persisting the whole graph state
across turns on one thread would bleed one turn's retrievals and citations into
the next. So the checkpointer stays keyed per turn (it only powers the
intra-turn streaming pause), and the cross-turn conversation record lives here —
explicit, minimal, and auditable.

The table name is composed with :class:`psycopg.sql.Identifier` and every user
value is bound as a query parameter, so the layer is injection-safe by
construction. It reuses the retrieval connection pool and manages its own
commits (it never assumes autocommit).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from psycopg import sql
from psycopg.rows import dict_row

from tessera.agent.identity import DEFAULT_AGENT_ID
from tessera.agent.state import ConversationMessage
from tessera.guard.redaction import mask_pan
from tessera.retrieval.store import get_pool

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime
    from uuid import UUID

__all__ = [
    "ConversationSummary",
    "append_messages",
    "delete_transcript",
    "ensure_transcript_schema",
    "last_agent_for",
    "list_conversations",
    "load_transcript",
    "turn_agent_and_synthetic",
]


@dataclass(frozen=True, slots=True)
class ConversationSummary:
    """A row in an agent's conversation list (the console "Récents" + Historique).

    ``title`` is the conversation's opening user message — empty when a
    conversation has no user turn yet. Counts cover the persisted conversational
    record (``user``/``assistant`` messages), keyed by ``conversation_id``.
    """

    conversation_id: str
    title: str
    started_at: datetime
    last_at: datetime
    message_count: int
    turn_count: int


_TABLE: Final[sql.Identifier] = sql.Identifier("conversation_messages")
_PERSISTED_ROLES: Final[frozenset[str]] = frozenset({"user", "assistant"})


async def ensure_transcript_schema() -> None:
    """Create the transcript table and its lookup index idempotently."""
    pool = get_pool()
    if pool.closed:
        await pool.open()
    create_table = sql.SQL(
        """
        CREATE TABLE IF NOT EXISTS {table} (
            id              bigserial   PRIMARY KEY,
            conversation_id uuid        NOT NULL,
            turn_id         uuid        NOT NULL,
            seq             int         NOT NULL,
            agent_id        text        NOT NULL DEFAULT {default_agent},
            subject_id      text,
            role            text        NOT NULL,
            content         text        NOT NULL,
            name            text,
            synthetic       boolean     NOT NULL DEFAULT false,
            created_at      timestamptz NOT NULL DEFAULT now()
        );
        """
    ).format(table=_TABLE, default_agent=sql.Literal(DEFAULT_AGENT_ID))
    # Per-turn agent attribution: stamp each message with the acting agent so a
    # conversation can span agents (handoff, Phase 2) and metrics partition by
    # agent. Added idempotently for tables created before the multi-agent work.
    add_agent_col = sql.SQL(
        "ALTER TABLE {table} ADD COLUMN IF NOT EXISTS agent_id text "
        "NOT NULL DEFAULT {default_agent};"
    ).format(table=_TABLE, default_agent=sql.Literal(DEFAULT_AGENT_ID))
    # Per-turn latency (ms), so the Synthèse latency KPI can be derived per agent
    # from real traffic instead of a shared eval run. Nullable: rows without a
    # measured latency render an honest "-".
    add_latency_col = sql.SQL(
        "ALTER TABLE {table} ADD COLUMN IF NOT EXISTS latency_ms double precision;"
    ).format(table=_TABLE)
    # Test-turn marker (ADR 0040): a turn entering on an operator TEST surface
    # (Console, COCKPIT_EMBEDDED) is still written — the transcript stays the single
    # witness of every turn — but marked so every "real traffic" read (Synthèse,
    # Flotte) can exclude it. Default false backfills existing rows as real: the
    # honest prior behaviour, since pre-marker rows cannot be re-distinguished.
    add_synthetic_col = sql.SQL(
        "ALTER TABLE {table} ADD COLUMN IF NOT EXISTS synthetic boolean " "NOT NULL DEFAULT false;"
    ).format(table=_TABLE)
    # The client/subject the turn served, so "Utilisateurs servis" can count
    # distinct clients per agent from real traffic. Nullable: an anonymous session
    # carries no subject, and an honest "-" is better than a fabricated one.
    add_subject_col = sql.SQL(
        "ALTER TABLE {table} ADD COLUMN IF NOT EXISTS subject_id text;"
    ).format(table=_TABLE)
    create_index = sql.SQL(
        "CREATE INDEX IF NOT EXISTS {idx} ON {table} (conversation_id, id);"
    ).format(idx=sql.Identifier("conversation_messages_conversation"), table=_TABLE)
    create_agent_index = sql.SQL(
        "CREATE INDEX IF NOT EXISTS {idx} ON {table} (agent_id, created_at);"
    ).format(idx=sql.Identifier("conversation_messages_agent"), table=_TABLE)
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(create_table)
        await cur.execute(add_agent_col)
        await cur.execute(add_latency_col)
        await cur.execute(add_synthetic_col)
        await cur.execute(add_subject_col)
        await cur.execute(create_index)
        await cur.execute(create_agent_index)
        await conn.commit()


async def load_transcript(
    conversation_id: UUID,
    *,
    limit: int | None = None,
) -> list[ConversationMessage]:
    """Return the persisted messages for ``conversation_id`` in chronological order.

    Args:
        conversation_id: The conversation whose transcript to load.
        limit: When set, return only the most recent ``limit`` messages (still
            in chronological order). ``None`` returns the whole transcript.
    """
    if limit is not None:
        query = sql.SQL(
            """
            SELECT role, content, name, created_at FROM (
                SELECT role, content, name, created_at, id
                FROM {table}
                WHERE conversation_id = %s
                ORDER BY id DESC
                LIMIT %s
            ) recent
            ORDER BY id ASC;
            """
        ).format(table=_TABLE)
        params: tuple[object, ...] = (conversation_id, limit)
    else:
        query = sql.SQL(
            """
            SELECT role, content, name, created_at
            FROM {table}
            WHERE conversation_id = %s
            ORDER BY id ASC;
            """
        ).format(table=_TABLE)
        params = (conversation_id,)

    pool = get_pool()
    if pool.closed:
        await pool.open()
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, params)
        rows = await cur.fetchall()
    return [
        ConversationMessage(
            role=row["role"],
            content=str(row["content"]),
            timestamp=row["created_at"],
            name=row["name"],
        )
        for row in rows
    ]


async def list_conversations(
    agent_id: str,
    *,
    limit: int = 30,
) -> list[ConversationSummary]:
    """Return ``agent_id``'s recent conversations, most-recently-active first.

    Powers the business console's "Récents" list and the agent's cockpit
    Historique. A conversation belongs to ``agent_id`` when its persisted messages
    are stamped with it (per-turn attribution). ``title`` is the first user
    message; the counts cover persisted ``user``/``assistant`` messages. This is
    a real-traffic read: synthetic turns (operator/canary trials, ADR 0040) are
    excluded, so a trial never shows up as a customer conversation.

    Args:
        agent_id: The acting agent whose conversations to list.
        limit: Maximum number of conversations to return.
    """
    query = sql.SQL(
        """
        SELECT
            m.conversation_id,
            MIN(m.created_at)                                       AS started_at,
            MAX(m.created_at)                                       AS last_at,
            COUNT(*) FILTER (WHERE m.role IN ('user', 'assistant')) AS message_count,
            COUNT(DISTINCT m.turn_id)                               AS turn_count,
            (
                SELECT u.content FROM {table} u
                WHERE u.conversation_id = m.conversation_id AND u.role = 'user'
                      AND NOT u.synthetic
                ORDER BY u.id ASC
                LIMIT 1
            )                                                       AS title
        FROM {table} m
        WHERE m.agent_id = %s AND NOT m.synthetic
        GROUP BY m.conversation_id
        ORDER BY last_at DESC
        LIMIT %s;
        """
    ).format(table=_TABLE)
    pool = get_pool()
    if pool.closed:
        await pool.open()
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, (agent_id, limit))
        rows = await cur.fetchall()
    return [
        ConversationSummary(
            conversation_id=str(row["conversation_id"]),
            title=str(row["title"] or ""),
            started_at=row["started_at"],
            last_at=row["last_at"],
            message_count=int(row["message_count"] or 0),
            turn_count=int(row["turn_count"] or 0),
        )
        for row in rows
    ]


async def append_messages(
    conversation_id: UUID,
    turn_id: UUID,
    messages: Sequence[ConversationMessage],
    *,
    agent_id: str = DEFAULT_AGENT_ID,
    latency_ms: float | None = None,
    subject_id: str | None = None,
    synthetic: bool = False,
) -> None:
    """Append a finished turn's user/assistant messages to the transcript.

    Only ``user`` and ``assistant`` roles are persisted; transient ``system``
    and ``tool`` messages are not part of the conversational record. Ordering
    within the turn is captured by ``seq``.

    ``agent_id`` attributes the turn to an agent (per-turn attribution); it
    defaults to the single agent until the supervisor (Phase 2) routes.
    ``latency_ms`` is the measured end-to-end turn latency; it is stored on the
    assistant row so the Synthèse latency KPI can be derived per agent.
    ``subject_id`` is the client the turn served (``None`` for anonymous), so the
    "Utilisateurs servis" KPI can count distinct clients per agent.
    ``synthetic`` marks an operator TEST turn (ADR 0040): the turn is still
    written — the transcript is the single witness — but every "real traffic"
    read excludes it, so operator tests never inflate an agent's Synthèse.

    Defence-in-depth backstop (docs/design/pii-input-redaction.md §4.2): the
    durable transcript structurally never holds a Luhn-valid card number.
    Callers mask upstream; if a clear PAN still reaches this seam it is masked
    here and the missed seam is logged — fail-safe (store masked), never
    fail-closed (the write always proceeds).
    """
    persisted = [m for m in messages if m.role in _PERSISTED_ROLES]
    if not persisted:
        return
    contents: list[str] = []
    for message in persisted:
        masked = mask_pan(message.content)
        if masked.changed:
            sys.stderr.write(
                "tessera.memory.transcript: missed seam — PAN masked at persistence "
                f"(conversation {conversation_id}, role {message.role})\n"
            )
        contents.append(masked.text)
    insert = sql.SQL(
        """
        INSERT INTO {table}
            (conversation_id, turn_id, seq, agent_id, subject_id, role, content,
             name, latency_ms, synthetic)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """
    ).format(table=_TABLE)
    rows = [
        (
            conversation_id,
            turn_id,
            seq,
            agent_id,
            subject_id,
            m.role,
            content,
            m.name,
            latency_ms if m.role == "assistant" else None,
            synthetic,
        )
        for seq, (m, content) in enumerate(zip(persisted, contents, strict=True))
    ]
    pool = get_pool()
    if pool.closed:
        await pool.open()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.executemany(insert, rows)
        await conn.commit()


async def last_agent_for(conversation_id: UUID) -> str | None:
    """Return the agent that handled the most recent turn of a conversation.

    The supervisor uses this as the routing default (the conversation's
    *parcours*): a new turn stays with the agent already on the conversation
    unless a handoff is warranted. ``None`` when the conversation is new.
    """
    query = sql.SQL(
        "SELECT agent_id FROM {table} WHERE conversation_id = %s ORDER BY id DESC LIMIT 1;"
    ).format(table=_TABLE)
    pool = get_pool()
    if pool.closed:
        await pool.open()
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, (conversation_id,))
        row = await cur.fetchone()
    return str(row["agent_id"]) if row else None


async def turn_agent_and_synthetic(turn_id: UUID) -> tuple[str, bool] | None:
    """Return the ``(agent_id, synthetic)`` of a persisted turn, or ``None`` if unknown.

    Used to attribute a customer's feedback to the agent that actually handled the turn
    and to inherit the turn's test-marker (ADR 0040/0041): you can only rate a turn the
    transcript has really recorded, and a vote on a test turn is itself a test.
    """
    query = sql.SQL("SELECT agent_id, synthetic FROM {table} WHERE turn_id = %s LIMIT 1;").format(
        table=_TABLE
    )
    pool = get_pool()
    if pool.closed:
        await pool.open()
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, (turn_id,))
        row = await cur.fetchone()
    if row is None:
        return None
    return str(row["agent_id"]), bool(row["synthetic"])


async def count_user_turns_since(since: datetime) -> int:
    """Count user turns recorded at or after ``since`` — test turns included.

    The transcript is the single witness of turns (ADR 0040), and every persisted
    user turn entered through the input guard, so this is the honest numerator for
    the launcher's "messages checked" counter. Synthetic turns are deliberately
    **included**: the guard checks a canary or an operator trial exactly like a
    customer message, and the counter measures the guard's activity, not business
    traffic. The read that displays it states that scope in its own words.
    """
    query = sql.SQL(
        "SELECT count(DISTINCT turn_id) AS turns FROM {table} "
        "WHERE role = 'user' AND created_at >= %s;"
    ).format(table=_TABLE)
    pool = get_pool()
    if pool.closed:
        await pool.open()
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, (since,))
        row = await cur.fetchone()
    return int(row["turns"]) if row is not None else 0


async def delete_transcript(conversation_id: UUID) -> None:
    """Delete the entire transcript for a conversation (GDPR Art. 17)."""
    query = sql.SQL("DELETE FROM {table} WHERE conversation_id = %s;").format(table=_TABLE)
    pool = get_pool()
    if pool.closed:
        await pool.open()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(query, (conversation_id,))
        await conn.commit()
