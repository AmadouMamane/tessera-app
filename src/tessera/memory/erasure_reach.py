"""How far GDPR erasure actually reaches, and what it leaves behind.

ADR 0014 gives each environment its own Postgres schema and sets
``search_path = <schema>, public``. Erasure writes bare table names —
``DELETE FROM long_term_memory`` — which resolve to the environment's own table. Correct, and
incomplete in a way nothing measured: **rows that predate the isolation are still in
``public``, and no erasure path can see them.**

Measured on 2026-08-01, on the live local Postgres::

    public.long_term_memory        1 357 rows,  138 distinct subjects
    public.conversation_messages   2 920 rows,  last written 2026-06-24
    public.documents                 238 rows
    tessera_local.long_term_memory 1 258 rows,   64 distinct subjects
    tessera_local.conversation_messages          last written 2026-08-01

ADR 0014 said the schema "starts empty". It never said the old one stops holding personal data.
`DELETE /memory` returns success, the audit ledger records a total erasure, and 138 subjects'
memories sit one schema over — a right to erasure honoured against the wrong half of the store.

**This module does not delete anything.** Purging another environment's schema from inside this
one is precisely what ADR 0014 forbids, and doing it silently would trade one violation for a
worse one. It MEASURES: which schemas hold subject-bearing Tessera tables, how many subjects
each holds, and which of them this environment's erasure can reach. A number an operator must
act on beats a deletion nobody authorised — and beats, by a long way, the silence there was.

`scripts/purge_orphan_schema.py` performs the purge, dry-run by default, as an operator act.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from psycopg import sql

if TYPE_CHECKING:
    from typing import Any

    from psycopg import AsyncConnection

__all__ = ["ErasureReach", "SchemaSubjects", "SUBJECT_TABLES", "assess_erasure_reach"]

#: Tables erasure must clear, each with its identifying column and WHAT that column counts.
#:
#: The unit matters and it took a wrong number to notice. A first version reported "1 236
#: subjects out of reach" by taking the largest per-table count — which was
#: `conversation_messages.conversation_id`, a count of CONVERSATIONS. The real subject count was
#: 138. A conversation belongs to a subject, so mixing the two produces a figure that means
#: neither, on exactly the surface where the number is the whole point.
#:
#: `documents` is a corpus table with no subject column and is deliberately absent: it holds no
#: personal data by design, and counting it would inflate the finding with rows erasure was
#: never meant to touch.
SUBJECT_TABLES: tuple[tuple[str, str, str], ...] = (
    ("long_term_memory", "subject_id", "subject"),
    ("memory_consent", "subject_id", "subject"),
    ("conversation_messages", "conversation_id", "conversation"),
    ("conversation_memory", "conversation_id", "conversation"),
)


#: table -> what its identifying column counts. Derived, never re-typed.
_UNIT: dict[str, str] = {table: unit for table, _column, unit in SUBJECT_TABLES}


@dataclass(frozen=True, slots=True)
class SchemaSubjects:
    """Subject-bearing rows found in one schema."""

    schema: str
    #: Distinct identifiers per table, e.g. ``{"long_term_memory": 138}``.
    subjects: dict[str, int] = field(default_factory=dict)
    #: True when this environment's erasure resolves to this schema.
    reachable: bool = False

    @property
    def n_subjects(self) -> int:
        """A floor on the PEOPLE involved: the largest count over subject-keyed tables."""
        return max(
            (n for t, n in self.subjects.items() if _UNIT[t] == "subject"),
            default=0,
        )

    @property
    def n_conversations(self) -> int:
        """A floor on the CONVERSATIONS involved. A different unit, reported separately."""
        return max(
            (n for t, n in self.subjects.items() if _UNIT[t] == "conversation"),
            default=0,
        )


@dataclass(frozen=True, slots=True)
class ErasureReach:
    """Where subject data lives, and how much of it erasure can reach."""

    active_schema: str
    schemas: list[SchemaSubjects] = field(default_factory=list)
    #: PEOPLE whose data sits in a schema this environment's erasure cannot reach.
    unreachable_subjects: int = 0
    #: CONVERSATIONS in the same position. A different unit — never folded into the one above.
    unreachable_conversations: int = 0
    unreachable_schemas: list[str] = field(default_factory=list)


async def assess_erasure_reach(conn: AsyncConnection[Any], active_schema: str) -> ErasureReach:
    """Count subject-bearing rows per schema, and say which erasure reaches.

    Args:
        conn: An open connection. The caller owns it; nothing here commits or writes.
        active_schema: The schema this environment's erasure resolves to
            (:attr:`tessera.settings.Settings.pg_schema`).

    Returns:
        An :class:`ErasureReach`. ``unreachable_subjects > 0`` means personal data exists that
        `DELETE /memory` cannot touch, whatever the endpoint reports.
    """
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_type = 'BASE TABLE'
              AND table_schema NOT IN ('pg_catalog', 'information_schema')
              AND table_name = ANY(%s)
            """,
            ([name for name, _column, _unit in SUBJECT_TABLES],),
        )
        present = [(str(row[0]), str(row[1])) for row in await cur.fetchall()]

        column_of = {table: column for table, column, _unit in SUBJECT_TABLES}
        per_schema: dict[str, dict[str, int]] = {}
        for schema, table in present:
            # Identifiers are composed, never interpolated: they come from
            # information_schema, but `sql.Identifier` is what makes that a fact rather than
            # a habit — a habit is what a future refactor breaks.
            count_query = sql.SQL("SELECT count(DISTINCT {col}) FROM {schema}.{table}").format(
                col=sql.Identifier(column_of[table]),
                schema=sql.Identifier(schema),
                table=sql.Identifier(table),
            )
            await cur.execute(count_query)
            row = await cur.fetchone()
            n = int(row[0]) if row and row[0] is not None else 0
            if n:
                per_schema.setdefault(schema, {})[table] = n

    schemas = [
        SchemaSubjects(schema=schema, subjects=tables, reachable=schema == active_schema)
        for schema, tables in sorted(per_schema.items())
    ]
    unreachable = [s for s in schemas if not s.reachable]
    return ErasureReach(
        active_schema=active_schema,
        schemas=schemas,
        unreachable_subjects=sum(s.n_subjects for s in unreachable),
        unreachable_conversations=sum(s.n_conversations for s in unreachable),
        unreachable_schemas=[s.schema for s in unreachable],
    )
