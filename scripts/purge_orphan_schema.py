"""Purge subject data from a schema this environment's erasure cannot reach.

**Dry-run by default. Nothing is deleted without `--apply`, and `--apply` requires naming the
schema explicitly.** This deletes personal data permanently; that is the point, and it is why
it is a script an operator runs rather than a branch of a route.

## Why this exists

ADR 0014 gave each environment its own Postgres schema. The rows that predated it stayed in
``public``, and every erasure path resolves through ``search_path`` to the environment's own
schema — so `DELETE /memory` returns success, the audit ledger records a total erasure, and the
old rows are untouched. Measured 2026-08-01 on the live local Postgres::

    public.long_term_memory        1 357 rows over 138 distinct subjects
    public.conversation_messages   2 920 rows, last written 2026-06-24
    public.conversation_memory        13 rows

138 people's memories, outside the reach of the right to erasure, with the endpoint reporting
that it had honoured it.

## Why a script and not a fix

``public`` is the PRODUCTION schema in the deployed stack (`Settings.pg_schema`). Code inside
`tessera_local` reaching across to delete from it is exactly the cross-environment write ADR
0014 exists to prevent — a violation traded for a worse one. So the code MEASURES
(:mod:`tessera.memory.erasure_reach`, surfaced at `/observability/erasure-reach`) and an operator
who can see both environments DECIDES.

## Usage

    uv run python scripts/purge_orphan_schema.py                  # report only
    uv run python scripts/purge_orphan_schema.py --schema public  # what would be deleted
    uv run python scripts/purge_orphan_schema.py --schema public --apply

Exit codes: ``0`` nothing to do · ``1`` unreachable subjects exist (report mode) · ``2`` the
target schema is the ACTIVE one and was refused.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

import psycopg
from psycopg import sql

from tessera.memory.erasure_reach import SUBJECT_TABLES, assess_erasure_reach
from tessera.settings import get_settings


async def _run(target: str | None, apply: bool) -> int:
    settings = get_settings()
    active = settings.pg_schema

    async with await psycopg.AsyncConnection.connect(str(settings.postgres.dsn)) as conn:
        reach = await assess_erasure_reach(conn, active)

        print(f"active schema (erasure reaches this one): {active}")
        for entry in reach.schemas:
            mark = "reachable" if entry.reachable else "OUT OF REACH"
            detail = ", ".join(f"{t}={n}" for t, n in sorted(entry.subjects.items()))
            print(f"  {entry.schema:20s} {mark:12s} {detail}")

        if not reach.unreachable_schemas:
            print("\nno subject data outside the active schema.")
            return 0

        # Two units, reported separately. A first version printed "1 236 subjects" by taking
        # the largest per-table count — which was a count of CONVERSATIONS. 138 is the number
        # of people.
        print(
            f"\n{reach.unreachable_subjects} subject(s) and "
            f"{reach.unreachable_conversations} conversation(s) in "
            f"{', '.join(reach.unreachable_schemas)} cannot be reached by GDPR erasure."
        )

        if target is None:
            print("re-run with --schema <name> to see what would be deleted.")
            return 1

        if target == active:
            # Refused, loudly. The active schema is erased through the ORDINARY path, one
            # subject at a time, with an audit entry naming its author (ADR 0024). A bulk
            # truncation here would destroy live data and leave no attributable record.
            print(f"\nREFUSED: {target} is the active schema. Use DELETE /memory per subject.")
            return 2

        if target not in reach.unreachable_schemas:
            print(f"\nnothing to purge in {target}.")
            return 0

        for table, _column, _unit in SUBJECT_TABLES:
            statement = sql.SQL("DELETE FROM {schema}.{table}").format(
                schema=sql.Identifier(target), table=sql.Identifier(table)
            )
            if not apply:
                print(f"  [dry-run] {statement.as_string(conn)}")
                continue
            async with conn.cursor() as cur:
                try:
                    await cur.execute(statement)
                except psycopg.errors.UndefinedTable:
                    # A table the other schema never had. Reported, not swallowed: a purge
                    # that silently skips is a purge nobody can audit.
                    print(f"  {target}.{table}: absent")
                    await conn.rollback()
                    continue
                print(f"  {target}.{table}: {cur.rowcount} row(s) deleted")
        if apply:
            await conn.commit()
            print("\ncommitted.")
        else:
            print("\nnothing was deleted. Re-run with --apply.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", help="the orphaned schema to purge (never the active one)")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="actually delete. Without it every statement is only printed.",
    )
    args = parser.parse_args()
    return asyncio.run(_run(args.schema, args.apply))


if __name__ == "__main__":
    sys.exit(main())
