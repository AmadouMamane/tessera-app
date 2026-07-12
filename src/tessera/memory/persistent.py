"""Tier 2 — cross-session long-term memory over pgvector (ADR 0007).

Durable memory keyed by *subject* (the customer proxy), holding semantic facts
and episodic incident summaries that survive across conversations. It reuses
Tessera's own embedding + pgvector layer (the same one behind document
retrieval) rather than LangGraph's ``BaseStore`` vector index: that keeps the
whole embedding path under one roof, avoids version-specific index wiring, and
lets us own the governance columns (TTL, importance) directly. This is a
deliberate refinement of the ADR's "BaseStore" wording, recorded in the ADR's
Tier 2 note.

Writes are de-duplicated by cosine similarity (an upsert, not an append) so the
store does not accumulate near-identical rows — the classic failure mode of
naive memory layers. Every row carries an ``expires_at`` so retention is
enforced by construction, and reads go through :mod:`tessera.memory.governance`
so a poisoned or PII-laden memory is screened before it reaches the prompt.
"""

from __future__ import annotations

import sys
from collections import Counter
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Final

from psycopg import sql
from psycopg.rows import dict_row

from tessera.authz import Actor
from tessera.guard.redaction import mask_pan
from tessera.memory import governance
from tessera.memory.entities import ledger_from_json, ledger_to_json, mask_ledger_pans
from tessera.memory.protocol import EntityLedger, MemoryContext, MemoryItem
from tessera.memory.summary import SummaryBackend
from tessera.retrieval import embeddings
from tessera.retrieval.store import get_pool
from tessera.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tessera.agent.state import ConversationMessage
    from tessera.memory.protocol import MemoryScope, TurnRecord

__all__ = [
    "PersistentBackend",
    "StoredMemory",
    "delete_memory",
    "delete_subject",
    "ensure_longterm_schema",
    "list_inventory",
    "list_subject_memories",
    "purge_expired",
    "rank_memories",
    "search_memory",
    "update_memory_text",
    "upsert_memory",
]

#: Recall during a turn: the agent read the subject's own memories to answer them. Nobody
#: ordered it — the graph did, on every turn.
_TURN_ACTOR: Final = Actor.system("agent-turn")

#: The retention scheduler (``api/main.py``), deleting personal data because its TTL elapsed —
#: GDPR Art. 5(1)(e), storage limitation. It is a *deletion of a person's data*, so it belongs
#: in the trail exactly as much as an operator's erasure does, and it now names itself rather
#: than leaving an unexplained gap where rows used to be.
_RETENTION_ACTOR: Final = Actor.system("retention-purge")

#: The backend protocol's own ``forget`` (``MemoryBackend.forget``). Named separately from the
#: operator erasure on purpose: if this ever *did* serve a human request, attributing it to the
#: system would be a lie, and the distinct name is what makes that lie visible in the trail
#: instead of hiding it under a shared "system".
_BACKEND_FORGET_ACTOR: Final = Actor.system("memory-backend-forget")

_TABLE: Final[sql.Identifier] = sql.Identifier("long_term_memory")
# Above this cosine similarity, a new candidate is treated as the same memory
# and updated in place rather than inserted as a duplicate.
_DEDUP_THRESHOLD: Final[float] = 0.95
# Recency half-life (days) used when blending relevance, recency, and importance.
_RECALL_HALF_LIFE_DAYS: Final[float] = 30.0
# How many cosine candidates to fetch per requested item before re-ranking.
_CANDIDATE_MULTIPLIER: Final[int] = 4


async def ensure_longterm_schema() -> None:
    """Create the long-term memory table and its indexes idempotently."""
    dim = embeddings.embedding_dimension()
    pool = get_pool()
    if pool.closed:
        await pool.open()
    create = sql.SQL(
        """
        CREATE TABLE IF NOT EXISTS {table} (
            id          bigserial   PRIMARY KEY,
            subject_id  text        NOT NULL,
            kind        text        NOT NULL,
            text        text        NOT NULL,
            entities    jsonb       NOT NULL DEFAULT '{{}}'::jsonb,
            embedding   vector({dim}) NOT NULL,
            importance  real        NOT NULL DEFAULT 0.5,
            created_at  timestamptz NOT NULL DEFAULT now(),
            expires_at  timestamptz NOT NULL,
            metadata    jsonb       NOT NULL DEFAULT '{{}}'::jsonb
        );
        """
    ).format(table=_TABLE, dim=sql.Literal(dim))
    index = sql.SQL(
        "CREATE INDEX IF NOT EXISTS {idx} ON {table} USING hnsw (embedding vector_cosine_ops);"
    ).format(idx=sql.Identifier("long_term_memory_embedding_hnsw"), table=_TABLE)
    subject_index = sql.SQL(
        "CREATE INDEX IF NOT EXISTS {idx} ON {table} (subject_id, kind);"
    ).format(idx=sql.Identifier("long_term_memory_subject"), table=_TABLE)
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        await cur.execute(create)
        await cur.execute(index)
        await cur.execute(subject_index)
        await conn.commit()


async def upsert_memory(
    *,
    subject_id: str,
    kind: str,
    text: str,
    entities: EntityLedger,
    importance: float = 0.5,
) -> None:
    """Insert a memory, or update the nearest existing one if highly similar.

    De-duplication keeps the store from filling with paraphrases of the same
    fact: if the most similar existing memory of the same kind is within
    :data:`_DEDUP_THRESHOLD`, that row is refreshed instead of a new one added.

    Defence-in-depth backstop (docs/design/pii-input-redaction.md §4.2):
    ``long_term_memory`` structurally never holds a Luhn-valid card number.
    ``governance.screen_memory`` already minimises reflector candidates
    upstream (its broader, non-Luhn card mask); this seam holds the invariant
    for every other caller, and masks *before* embedding so the stored vector
    matches the stored text. Fail-safe: the write always proceeds.
    """
    masked_text = mask_pan(text)
    if masked_text.changed:
        sys.stderr.write(
            f"tessera.memory.persistent: missed seam — PAN masked at persistence "
            f"(subject {subject_id}, kind {kind})\n"
        )
        text = masked_text.text
    entities = mask_ledger_pans(entities)
    embedding = (await embeddings.embed([text]))[0]
    expires_at = datetime.now(UTC) + governance.ttl_for(kind)
    nearest = sql.SQL(
        """
        SELECT id, 1 - (embedding <=> %s::vector) AS sim
        FROM {table}
        WHERE subject_id = %s AND kind = %s
        ORDER BY embedding <=> %s::vector
        LIMIT 1;
        """
    ).format(table=_TABLE)
    insert = sql.SQL(
        """
        INSERT INTO {table} (subject_id, kind, text, entities, embedding, importance, expires_at)
        VALUES (%s, %s, %s, %s::jsonb, %s::vector, %s, %s);
        """
    ).format(table=_TABLE)
    update = sql.SQL(
        """
        UPDATE {table}
        SET text = %s, entities = %s::jsonb, embedding = %s::vector,
            importance = %s, created_at = now(), expires_at = %s
        WHERE id = %s;
        """
    ).format(table=_TABLE)

    pool = get_pool()
    if pool.closed:
        await pool.open()
    entities_json = ledger_to_json(entities)
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(nearest, (embedding, subject_id, kind, embedding))
        row = await cur.fetchone()
        if row is not None and float(row["sim"]) >= _DEDUP_THRESHOLD:
            await cur.execute(
                update, (text, entities_json, embedding, importance, expires_at, row["id"])
            )
        else:
            await cur.execute(
                insert,
                (subject_id, kind, text, entities_json, embedding, importance, expires_at),
            )
        await conn.commit()


def rank_memories(
    items: list[MemoryItem],
    *,
    top_k: int,
    now: datetime | None = None,
) -> list[MemoryItem]:
    """Re-rank candidates by relevance, recency, and importance (ADR 0007).

    This is the Generative-Agents memory-stream idea: vector similarity alone
    over-weights stale-but-similar memories. We blend the retrieval relevance
    with an exponential recency decay (half-life :data:`_RECALL_HALF_LIFE_DAYS`)
    and the memory's stored importance, then keep the best ``top_k``.
    """
    reference = now or datetime.now(UTC)

    def _combined(item: MemoryItem) -> float:
        age_days = max((reference - item.created_at).total_seconds() / 86_400.0, 0.0)
        recency: float = 0.5 ** (age_days / _RECALL_HALF_LIFE_DAYS)
        return item.score * recency * (0.5 + item.importance)

    return sorted(items, key=_combined, reverse=True)[:top_k]


async def search_memory(*, subject_id: str, query: str, top_k: int) -> list[MemoryItem]:
    """Return the best ``top_k`` non-expired memories for a subject.

    Over-fetches by cosine similarity, then re-ranks the candidate pool with
    :func:`rank_memories` so recency and importance shape the final selection.
    """
    if top_k <= 0:
        return []
    query_embedding = (await embeddings.embed([query]))[0]
    candidate_pool = top_k * _CANDIDATE_MULTIPLIER
    search = sql.SQL(
        """
        SELECT kind, text, entities, importance, created_at,
               1 - (embedding <=> %s::vector) AS score
        FROM {table}
        WHERE subject_id = %s AND expires_at > now()
        ORDER BY embedding <=> %s::vector
        LIMIT %s;
        """
    ).format(table=_TABLE)
    pool = get_pool()
    if pool.closed:
        await pool.open()
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(search, (query_embedding, subject_id, query_embedding, candidate_pool))
        rows = await cur.fetchall()
    candidates = [
        MemoryItem(
            kind="semantic" if row["kind"] == "semantic" else "episodic",
            text=str(row["text"]),
            entities=ledger_from_json(row["entities"]),
            score=float(row["score"]),
            created_at=row["created_at"],
            importance=float(row["importance"]),
        )
        for row in rows
    ]
    return rank_memories(candidates, top_k=top_k)


@dataclass(frozen=True, slots=True)
class StoredMemory:
    """A long-term memory row, surfaced for GDPR access and rectification."""

    memory_id: int
    subject_id: str
    kind: str
    text: str
    created_at: datetime
    expires_at: datetime


def _row_to_stored(row: dict[str, Any]) -> StoredMemory:
    return StoredMemory(
        memory_id=int(row["id"]),
        subject_id=str(row["subject_id"]),
        kind=str(row["kind"]),
        text=str(row["text"]),
        created_at=row["created_at"],
        expires_at=row["expires_at"],
    )


async def list_subject_memories(subject_id: str) -> list[StoredMemory]:
    """Return all non-expired memories held for ``subject_id`` (GDPR Art. 15)."""
    query = sql.SQL(
        """
        SELECT id, subject_id, kind, text, created_at, expires_at
        FROM {table}
        WHERE subject_id = %s AND expires_at > now()
        ORDER BY created_at DESC;
        """
    ).format(table=_TABLE)
    pool = get_pool()
    if pool.closed:
        await pool.open()
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, (subject_id,))
        rows = await cur.fetchall()
    return [_row_to_stored(row) for row in rows]


async def list_inventory(limit: int = 200) -> list[StoredMemory]:
    """Return non-expired memories across all subjects, newest first."""
    query = sql.SQL(
        """
        SELECT id, subject_id, kind, text, created_at, expires_at
        FROM {table}
        WHERE expires_at > now()
        ORDER BY created_at DESC
        LIMIT %s;
        """
    ).format(table=_TABLE)
    pool = get_pool()
    if pool.closed:
        await pool.open()
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, (limit,))
        rows = await cur.fetchall()
    return [_row_to_stored(row) for row in rows]


async def update_memory_text(memory_id: int, *, subject_id: str, text: str) -> bool:
    """Rewrite one memory's text and re-embed it (GDPR Art. 16 rectification).

    Scoped by ``subject_id`` so a subject can only rectify their own memory.
    Returns ``True`` when a row was updated.
    """
    embedding = (await embeddings.embed([text]))[0]
    query = sql.SQL(
        """
        UPDATE {table}
        SET text = %s, embedding = %s::vector
        WHERE id = %s AND subject_id = %s;
        """
    ).format(table=_TABLE)
    pool = get_pool()
    if pool.closed:
        await pool.open()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(query, (text, embedding, memory_id, subject_id))
        updated = (cur.rowcount or 0) > 0
        await conn.commit()
    return updated


async def delete_memory(memory_id: int, *, subject_id: str) -> bool:
    """Delete one memory of a subject; returns ``True`` when a row was removed."""
    query = sql.SQL("DELETE FROM {table} WHERE id = %s AND subject_id = %s;").format(table=_TABLE)
    pool = get_pool()
    if pool.closed:
        await pool.open()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(query, (memory_id, subject_id))
        deleted = (cur.rowcount or 0) > 0
        await conn.commit()
    return deleted


async def delete_subject(subject_id: str) -> int:
    """Delete every long-term memory for ``subject_id``; return the row count."""
    query = sql.SQL("DELETE FROM {table} WHERE subject_id = %s;").format(table=_TABLE)
    pool = get_pool()
    if pool.closed:
        await pool.open()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(query, (subject_id,))
        deleted = cur.rowcount or 0
        await conn.commit()
    return deleted


async def purge_expired() -> int:
    """Delete all memories past their retention window; return the row count.

    **The purge is a governed act, and it now leaves one.** This deletes a person's data —
    GDPR Art. 5(1)(e), storage limitation — on a background scheduler (``api/main.py``), and
    until now it wrote *nothing* to the audit trail: rows vanished, and no entry said whose,
    how many, or why. An erasure the controller cannot account for is the same defect whether
    a human ordered it or a cron did; the only difference is that nobody was even looking for
    this one.

    ``RETURNING subject_id`` is what makes the record per-*person* rather than a bare count.
    Art. 30 asks for records of processing, and "417 rows deleted" is not a record of
    processing anybody: it names no subject, so it cannot answer a subject's own access
    request about their own deletion. One entry per subject, with what they lost.
    """
    query = sql.SQL("DELETE FROM {table} WHERE expires_at <= now() RETURNING subject_id;").format(
        table=_TABLE
    )
    pool = get_pool()
    if pool.closed:
        await pool.open()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(query)
        rows = await cur.fetchall()
        await conn.commit()

    purged = Counter(str(row[0]) for row in rows)
    for subject_id, count in purged.items():
        governance.audit_memory(
            action="memory.forget",
            subject_id=subject_id,
            decision="allow",
            rationale=(
                f"retention window elapsed: {count} "
                f"{'memory' if count == 1 else 'memories'} purged (GDPR Art. 5(1)(e))"
            ),
            actor=_RETENTION_ACTOR,
        )
    return sum(purged.values())


class PersistentBackend(SummaryBackend):
    """Tier 2 backend — window + summary + entity ledger + long-term recall."""

    def __init__(self, *, history_window: int | None = None, top_k: int | None = None) -> None:
        """Initialise the persistent backend.

        Args:
            history_window: Forwarded to the window/summary layers.
            top_k: Number of long-term items to recall per turn; defaults to
                ``settings.memory.long_term_top_k``.
        """
        super().__init__(history_window=history_window)
        self._top_k = top_k if top_k is not None else get_settings().memory.long_term_top_k

    async def load(
        self,
        *,
        scope: MemoryScope,
        messages: Sequence[ConversationMessage],
        query: str,
    ) -> MemoryContext:
        """Return the summary context plus screened long-term recall."""
        base = await super().load(scope=scope, messages=messages, query=query)
        long_term = await self._recall(scope, query)
        return MemoryContext(
            recent_verbatim=base.recent_verbatim,
            summary=base.summary,
            entities=base.entities,
            long_term=long_term,
        )

    async def _recall(self, scope: MemoryScope, query: str) -> list[MemoryItem]:
        try:
            items = await search_memory(subject_id=scope.subject_id, query=query, top_k=self._top_k)
        except Exception as exc:  # recall must never break a turn (e.g. embed offline)
            sys.stderr.write(f"tessera.memory.persistent: recall failed: {exc}\n")
            return []
        # Memory is untrusted data: screen on read too, dropping poisoned items
        # and masking residual PII (ADR 0007, anti-poisoning).
        screened: list[MemoryItem] = []
        for item in items:
            result = governance.screen_memory(item.text)
            if result.allowed:
                screened.append(replace(item, text=result.text))
        governance.audit_memory(
            action="memory.read",
            subject_id=scope.subject_id,
            decision="allow",
            rationale=f"recalled {len(screened)}/{len(items)} item(s) after screening",
            actor=_TURN_ACTOR,
        )
        return screened

    async def record(self, *, scope: MemoryScope, turn: TurnRecord) -> None:
        """Update the summary, then form long-term memories (both cold-path)."""
        await super().record(scope=scope, turn=turn)
        try:
            from tessera.memory.reflector import form_memories

            await form_memories(scope, turn)
        except Exception as exc:
            sys.stderr.write(f"tessera.memory.persistent: reflection failed: {exc}\n")

    async def forget(self, *, scope: MemoryScope) -> None:
        """Erase every trace of the subject (GDPR Art. 17), on the backend's own protocol path.

        Distinct from the operator's ``DELETE /memory/{id}``, which threads the *human* who
        ordered it. Nothing in ``src/`` currently calls this — the HTTP erasure goes straight to
        :func:`~tessera.memory.governance.erase_subject` — so the honest actor here is the
        backend itself. If a future caller routes a human's erasure through this method, the
        actor must be threaded from that caller's verified session, not left as this one:
        ``system:memory-backend-forget`` appearing in the trail for an act a person ordered is
        precisely the mis-attribution this whole lane exists to make impossible.
        """
        await governance.erase_subject(scope.conversation_id, actor=_BACKEND_FORGET_ACTOR)
