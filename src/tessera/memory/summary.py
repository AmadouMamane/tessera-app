"""Tier 1 — summary buffer with a literal entity ledger (ADR 0007).

Keeps the recent window verbatim (inherited from :class:`WindowBackend`) and
compacts everything older than the window into a running summary, while
preserving the literal entities of the older turns *separately and verbatim* via
:mod:`tessera.memory.entities`. The summary is produced by a cheap model on the
**cold path** (``record``, called as a background task after the turn) so the
next turn pays no latency.

The summary and the entity ledger are persisted in a small ``conversation_memory``
table (one row per conversation), distinct from the pgvector long-term Store of
Tier 2. The table name is composed with :class:`psycopg.sql.Identifier` and all
user values are bound as parameters.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Final

from psycopg import sql
from psycopg.rows import dict_row

from tessera.guard.redaction import mask_pan
from tessera.memory.entities import (
    extract_from_messages,
    ledger_from_json,
    ledger_to_json,
    mask_ledger_pans,
)
from tessera.memory.protocol import EntityLedger, MemoryContext
from tessera.memory.window import WindowBackend
from tessera.retrieval.store import get_pool
from tessera.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from tessera.agent.state import ConversationMessage
    from tessera.memory.protocol import MemoryScope, TurnRecord
    from tessera.settings import LanguageCode

__all__ = [
    "SummaryBackend",
    "delete_summary",
    "ensure_summary_schema",
    "load_summary",
    "save_summary",
]

_TABLE: Final[sql.Identifier] = sql.Identifier("conversation_memory")


def _memory_table(table: sql.Identifier) -> sql.Composed:
    """Schema-qualify a memory table (ADR 0014), so no statement can fall through to `public`.

    The connection carries ``search_path = <schema>, public``, so a bare table name resolves to
    this environment's table *when it exists* and to ``public`` when it does not — silently, in
    both directions:

    * a **read** that falls through returns ANOTHER environment's rows, and in the deployed
      stack ``public`` IS production;
    * a **delete** that falls through erases them.

    One ``CREATE TABLE`` skipped in a migration is all it takes, and nothing raises.

    Naming the schema also makes the converse legible, which is the finding that produced this
    function: erasure reaches exactly this environment's rows and NO others. On 2026-08-01
    ``public`` held 1 357 memory rows over **138 distinct subjects**, last written 2026-06-24,
    outside every erasure path — while `DELETE /memory` returned success and the ledger recorded
    a total erasure. :mod:`tessera.memory.erasure_reach` measures that gap;
    ``scripts/purge_orphan_schema.py`` closes it as an operator act, because purging another
    environment's schema from inside this one is exactly what ADR 0014 forbids.
    """
    from tessera.settings import get_settings

    return sql.SQL("{schema}.{table}").format(
        schema=sql.Identifier(get_settings().pg_schema), table=table
    )


_DEFAULT_SUMMARY_INSTRUCTION: Final[str] = (
    "Summarise the earlier conversation turns below concisely for context. "
    "Preserve meaning and intent. Do NOT restate amounts, IBANs, dates, ticket "
    "numbers or regulatory citations verbatim — those are tracked separately; "
    "refer to them generically. Answer in the conversation's language."
)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


async def ensure_summary_schema() -> None:
    """Create the per-conversation summary table idempotently."""
    pool = get_pool()
    if pool.closed:
        await pool.open()
    create = sql.SQL(
        """
        CREATE TABLE IF NOT EXISTS {table} (
            conversation_id uuid        PRIMARY KEY,
            summary         text,
            entities        jsonb       NOT NULL DEFAULT '{{}}'::jsonb,
            updated_at      timestamptz NOT NULL DEFAULT now()
        );
        """
    ).format(table=_memory_table(_TABLE))
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(create)
        await conn.commit()


async def load_summary(conversation_id: UUID) -> tuple[str | None, EntityLedger]:
    """Return the persisted ``(summary, entity_ledger)`` for a conversation."""
    query = sql.SQL("SELECT summary, entities FROM {table} WHERE conversation_id = %s;").format(
        table=_memory_table(_TABLE)
    )
    pool = get_pool()
    if pool.closed:
        await pool.open()
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, (conversation_id,))
        row = await cur.fetchone()
    if row is None:
        return None, EntityLedger()
    summary = row["summary"]
    return (str(summary) if summary is not None else None), ledger_from_json(row["entities"])


async def save_summary(conversation_id: UUID, summary: str | None, entities: EntityLedger) -> None:
    """Upsert the summary and entity ledger for a conversation.

    Defence-in-depth backstop (docs/design/pii-input-redaction.md §4.2): the
    ``conversation_memory`` table structurally never holds a Luhn-valid card
    number. The summariser already receives masked text, so a changed summary
    here means a missed seam and is logged; the entity-ledger screening is the
    *designed* seam (extract raw, store masked) and stays silent. Fail-safe:
    the write always proceeds, with the masked text.
    """
    if summary is not None:
        masked_summary = mask_pan(summary)
        if masked_summary.changed:
            sys.stderr.write(
                "tessera.memory.summary: missed seam — PAN masked in summary at persistence "
                f"(conversation {conversation_id})\n"
            )
            summary = masked_summary.text
    entities = mask_ledger_pans(entities)
    query = sql.SQL(
        """
        INSERT INTO {table} (conversation_id, summary, entities, updated_at)
        VALUES (%s, %s, %s::jsonb, now())
        ON CONFLICT (conversation_id)
        DO UPDATE SET summary = EXCLUDED.summary,
                      entities = EXCLUDED.entities,
                      updated_at = now();
        """
    ).format(table=_memory_table(_TABLE))
    pool = get_pool()
    if pool.closed:
        await pool.open()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(query, (conversation_id, summary, ledger_to_json(entities)))
        await conn.commit()


async def delete_summary(conversation_id: UUID) -> int:
    """Delete the summary row for a conversation (used by GDPR erasure); return the row count."""
    query = sql.SQL("DELETE FROM {table} WHERE conversation_id = %s;").format(
        table=_memory_table(_TABLE)
    )
    pool = get_pool()
    if pool.closed:
        await pool.open()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(query, (conversation_id,))
        deleted = cur.rowcount or 0
        await conn.commit()
    return deleted


# ---------------------------------------------------------------------------
# Backend
# ---------------------------------------------------------------------------


class SummaryBackend(WindowBackend):
    """Tier 1 backend — recent window verbatim plus a compacted summary."""

    async def load(
        self,
        *,
        scope: MemoryScope,
        messages: Sequence[ConversationMessage],
        query: str,
    ) -> MemoryContext:
        """Return the recent window plus the persisted summary and entity ledger."""
        window_ctx = await super().load(scope=scope, messages=messages, query=query)
        try:
            summary, entities = await load_summary(scope.conversation_id)
        except Exception as exc:  # never let memory recall break a turn
            sys.stderr.write(f"tessera.memory.summary: load failed: {exc}\n")
            summary, entities = None, EntityLedger()
        return MemoryContext(
            recent_verbatim=window_ctx.recent_verbatim,
            summary=summary,
            entities=entities,
        )

    async def record(self, *, scope: MemoryScope, turn: TurnRecord) -> None:
        """Compact turns older than the window into a summary + entity ledger.

        Runs on the cold path; all failures are swallowed so a memory-formation
        error can never surface to the user.
        """
        try:
            await self._form(scope, turn)
        except Exception as exc:
            sys.stderr.write(f"tessera.memory.summary: record failed: {exc}\n")

    async def _form(self, scope: MemoryScope, turn: TurnRecord) -> None:
        prior = [m for m in turn.messages if m.role in ("user", "assistant")]
        if len(prior) <= self._window:
            return  # nothing older than the window to compact yet
        older = prior[: len(prior) - self._window]
        entities = extract_from_messages(older)

        budget = get_settings().memory.token_budget
        older_text = "\n".join(f"{m.role}: {m.content}" for m in older)
        # Bound the model input by the configured budget (cheap guard).
        if budget and len(older_text) > budget:
            older_text = older_text[-budget:]
        # Input-leg PAN mask (pii-input-redaction, cold-path model call): the
        # entity extraction above ran on the raw text — the summariser LLM
        # only ever sees the masked form.
        older_text = mask_pan(older_text).text
        summary = await self._summarise(older_text, scope.language)
        await save_summary(scope.conversation_id, summary, entities)

    async def _summarise(self, older_text: str, language: LanguageCode) -> str:
        # Local imports avoid any import-time coupling with the reporter, which
        # itself imports the memory package.
        from tessera.agent.reporter import load_prompts
        from tessera.llm.router import ChatMessage, get_summary_backend

        prompts = load_prompts(language)
        system = prompts.get("summary", _DEFAULT_SUMMARY_INSTRUCTION)
        backend = get_summary_backend()
        response = await backend.chat(
            [
                ChatMessage(role="system", content=system),
                ChatMessage(role="user", content=older_text),
            ],
            temperature=0.1,
        )
        return response.content.strip()
