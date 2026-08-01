"""Erasure clears its own schema, and PROVES it cannot silently clear another's.

Two claims, and they are opposite in direction. Both matter, and only one was ever tested.

**Totality.** `erase_subject` must remove every trace in the environment it runs in. Tested
before, and still tested here — with the difference that a second schema now exists in the
fixture, so a delete that fell through would show up as a survivor rather than as nothing.

**Confinement.** It must NOT reach another environment's schema. That is what ADR 0014 is for,
and it was structurally untestable until the erasure statements were schema-qualified: with a
bare table name and ``search_path = <schema>, public``, a table missing from this environment's
schema sends the ``DELETE`` to ``public`` — the PRODUCTION schema in the deployed stack — with
nothing raised. One skipped ``CREATE TABLE`` in a migration is all it takes.

**And the gap between them.** Confinement means rows in the other schema SURVIVE, which is
correct and is also the finding: on 2026-08-01 ``public`` held 138 subjects and 1 236
conversations, last written 2026-06-24, that no erasure path could see, while `DELETE /memory`
returned success and the ledger recorded a total erasure. Correct behaviour, uncounted. The
last test here asserts that the gap is *measured* — because an invariant nobody can see the
cost of is one somebody eventually trades away.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql

from tessera.memory.erasure_reach import assess_erasure_reach
from tessera.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = pytest.mark.integration

#: A disposable schema standing in for "another environment" — never `public`, which holds
#: real data on a developer machine and IS production in the deployed stack.
_FOREIGN = "tessera_erasure_probe"


@pytest.fixture
async def foreign_schema() -> AsyncIterator[str]:
    """Create a second schema carrying the same memory tables, and drop it after."""
    dsn = str(get_settings().postgres.dsn)
    async with await psycopg.AsyncConnection.connect(dsn, autocommit=True) as conn:
        await conn.execute(
            sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(_FOREIGN))
        )
        await conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(_FOREIGN)))
        await conn.execute(
            sql.SQL("""
            CREATE TABLE {}.long_term_memory (
                id uuid PRIMARY KEY,
                subject_id text NOT NULL,
                content text NOT NULL,
                created_at timestamptz NOT NULL DEFAULT now()
            )
            """).format(sql.Identifier(_FOREIGN))
        )
    try:
        yield _FOREIGN
    finally:
        async with await psycopg.AsyncConnection.connect(dsn, autocommit=True) as conn:
            await conn.execute(
                sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(_FOREIGN))
            )


async def _embedding_dimension(conn: psycopg.AsyncConnection[object], schema: str) -> int:
    """Read the column's declared width rather than assuming one.

    `long_term_memory.embedding` is `vector(N)` and N follows the configured embedder, so a
    literal here would pass on one machine and fail on the next — the kind of environment
    coupling this whole ADR-0014 story is about.
    """
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT a.atttypmod
            FROM pg_attribute a
            JOIN pg_class c ON c.oid = a.attrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = %s AND c.relname = 'long_term_memory' AND a.attname = 'embedding'
            """,
            (schema,),
        )
        row = await cur.fetchone()
        return int(row[0]) if row and row[0] and row[0] > 0 else 8


async def _insert_real(subject_id: str) -> None:
    """Insert into the ACTIVE schema's real table, honouring its actual shape."""
    settings = get_settings()
    async with await psycopg.AsyncConnection.connect(
        str(settings.postgres.dsn), autocommit=True
    ) as conn:
        dim = await _embedding_dimension(conn, settings.pg_schema)
        await conn.execute(
            sql.SQL("""
            INSERT INTO {}.long_term_memory
                (subject_id, kind, text, embedding, expires_at)
            VALUES (%s, 'fact', %s, %s, now() + interval '1 day')
            """).format(sql.Identifier(settings.pg_schema)),
            (subject_id, "a memory that must not survive its erasure", str([0.0] * dim)),
        )


async def _insert(schema: str, subject_id: str) -> None:
    """Insert into the disposable foreign schema's minimal table."""
    dsn = str(get_settings().postgres.dsn)
    async with await psycopg.AsyncConnection.connect(dsn, autocommit=True) as conn:
        await conn.execute(
            sql.SQL(
                "INSERT INTO {}.long_term_memory (id, subject_id, content) VALUES (%s, %s, %s)"
            ).format(sql.Identifier(schema)),
            (uuid4(), subject_id, "a memory that must not survive its erasure"),
        )


async def _count(schema: str, subject_id: str) -> int:
    dsn = str(get_settings().postgres.dsn)
    async with await psycopg.AsyncConnection.connect(dsn) as conn, conn.cursor() as cur:
        await cur.execute(
            sql.SQL("SELECT count(*) FROM {}.long_term_memory WHERE subject_id = %s").format(
                sql.Identifier(schema)
            ),
            (subject_id,),
        )
        row = await cur.fetchone()
        return int(row[0]) if row else 0


async def test_erasure_clears_its_own_schema_and_leaves_the_other(
    foreign_schema: str,
) -> None:
    """One subject, two schemas. Erasure clears one and provably not the other."""
    from tessera.memory.persistent import delete_subject

    settings = get_settings()
    subject = f"probe-{uuid4()}"

    await _insert_real(subject)
    await _insert(foreign_schema, subject)
    assert await _count(settings.pg_schema, subject) == 1
    assert await _count(foreign_schema, subject) == 1

    await delete_subject(subject)

    assert (
        await _count(settings.pg_schema, subject) == 0
    ), "erasure did not clear its own schema — this is the totality GDPR Art. 17 requires"
    assert await _count(foreign_schema, subject) == 1, (
        "erasure reached ANOTHER environment's schema. In the deployed stack that schema is "
        "`public`, i.e. production, and a bare table name plus `search_path` fall-through is "
        "exactly how a local process would silently delete from it (ADR 0014)."
    )


async def test_the_unreachable_rows_are_counted_rather_than_ignored(
    foreign_schema: str,
) -> None:
    """Confinement is correct AND costly. The cost must be a number somebody can read.

    Leaving another schema alone is right. Leaving it alone *silently* is how 138 subjects came
    to sit outside the right to erasure for months while the endpoint reported success.
    """
    settings = get_settings()
    subject = f"probe-{uuid4()}"
    await _insert(foreign_schema, subject)

    async with await psycopg.AsyncConnection.connect(str(settings.postgres.dsn)) as conn:
        reach = await assess_erasure_reach(conn, settings.pg_schema)

    assert foreign_schema in reach.unreachable_schemas, (
        "a schema holding subject rows that erasure cannot reach must be NAMED. A gap nobody "
        "can see the size of is one somebody eventually trades away."
    )
    assert reach.unreachable_subjects >= 1
    by_schema = {s.schema: s for s in reach.schemas}
    assert by_schema[settings.pg_schema].reachable is True
    assert by_schema[foreign_schema].reachable is False


async def test_subjects_and_conversations_are_never_one_number(
    foreign_schema: str,
) -> None:
    """Two units, two fields. The first version of the probe conflated them and was wrong.

    It reported "1 236 subjects out of reach" by taking the largest per-table count, which was
    `conversation_messages.conversation_id` — a count of CONVERSATIONS. The subject count was
    138. On a compliance surface the number IS the finding, so a figure that means neither unit
    is worse than no figure.
    """
    settings = get_settings()
    await _insert(foreign_schema, f"probe-{uuid4()}")

    async with await psycopg.AsyncConnection.connect(str(settings.postgres.dsn)) as conn:
        reach = await assess_erasure_reach(conn, settings.pg_schema)

    # The probe schema carries ONLY `long_term_memory`, a subject-keyed table. Its contribution
    # must land in the subject count and nowhere near the conversation one.
    probe = next(s for s in reach.schemas if s.schema == foreign_schema)
    assert probe.n_subjects >= 1
    assert probe.n_conversations == 0
