r"""SQL identifier validation — the one gate every interpolated name goes through.

**An identifier cannot be parameterised; it must be validated before interpolation.**
That is the whole doctrine of this module, and it is why the codebase's SQL is not simply
"use bound parameters everywhere". A driver binds *values* — `WHERE id = %s` — and refuses
to bind *names*: `FROM %s` is not a query. So a table, schema, column or database name that
comes from configuration has to be spliced into the query text, and the only defence left is
to prove, before splicing, that the string cannot be anything but a name.

Audit 2026-07-10, **P0.3 `sql-fstring`**. None of the interpolated names came from user input
— they are settings, module constants and enum-derived values — so the finding was a *class*
risk, not a live exploit. It was closed as a class:

* every name that reaches an f-string is passed through :func:`safe_identifier` **at the point
  of interpolation**, every time, with no exceptions;
* and the two settings that feed most of them (`postgres.vector_table`, and the ClickHouse
  database) are validated **at ingestion**, so an unsafe value cannot even exist in the
  process.

Belt and braces, deliberately. The boundary check means a bad value never gets in; the
per-site check means a future refactor that changes where a name comes from cannot silently
un-validate it. Neither alone survives a careless edit.

What was actually there before, and why one shared gate:

* **Two divergent private validators.** `observability/agent_scope.py` allowed
  `^[a-z_][a-z0-9_]*$`; `spine/adapters/clickhouse.py` allowed `^[A-Za-z_][A-Za-z0-9_]*$`.
  Two spellings of the same idea, neither reused, and the second admitted names the first
  rejected.
* **Both used `re.match`, not `re.fullmatch`.** With a `$` anchor that is *almost* the same
  thing — except `$` also matches immediately before a trailing newline, so `"documents\n"`
  passed both. Narrow, but it is exactly the hole the check exists to close.
* **Most sites had no validation at all**, including `retrieval/store.py`, which splices
  `postgres.vector_table` into `CREATE TABLE` / `INSERT` / `SELECT` and which **ruff never
  flagged** — S608's heuristic misses indented multi-line f-strings. Counting `# noqa: S608`
  comments undercounts the class; that is why this module exists rather than a longer list of
  suppressions.

**The `# noqa: S608` comments stay, and they are not a smell.** S608 is a *syntactic* rule: it
fires on any f-string that looks like SQL and has no way to see that the interpolated value was
validated one line above. Deleting the suppressions would simply turn the gate red. What
changed is that each one is now *earned* — the identifier really is validated — and the class
ratchet in `tests/unit/test_sql_identifier_class.py` fails if a new f-string SQL site appears
in a module that does not import this helper.

The strictly better tool for the Postgres sites is `psycopg.sql.SQL(...).format(table=
psycopg.sql.Identifier(...))`, which quotes the name in the driver and needs no suppression at
all. It is already the idiom in `memory/` and `api/settings_store.py`. Migrating the ~30
f-string Postgres queries to it is the real end state and a separate slice — it rewrites live
queries, and the integration tier that would prove them is outside the gate.
"""

from __future__ import annotations

import re
from typing import Final

__all__ = ["MAX_IDENTIFIER_LENGTH", "safe_identifier", "safe_qualified_identifier"]

#: A bare SQL identifier: a letter or underscore, then letters, digits and underscores.
#: Deliberately narrower than either engine allows — no quoting, no dots, no dollars, no
#: unicode. Everything this codebase names fits, and anything that does not is a bug, not a
#: table.
_IDENTIFIER: Final = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

#: PostgreSQL truncates identifiers at `NAMEDATALEN - 1` = 63 bytes. ClickHouse is far more
#: permissive, so the tighter bound governs: a name Postgres would silently truncate is a name
#: we refuse, because a *silently different* table is worse than a loud failure.
MAX_IDENTIFIER_LENGTH: Final = 63


def safe_identifier(name: str) -> str:
    r"""Return ``name`` if it is a plain SQL identifier; raise ``ValueError`` otherwise.

    Call this on **every** name spliced into a query — table, schema, column, database —
    at the point of interpolation. It is cheap (one regex) and it is the only thing standing
    between a configuration string and the query text.

    Uses ``fullmatch``, not ``match``: with a ``$``-anchored pattern the two differ on exactly
    one input, a trailing newline (``"documents\n"``), and that input is precisely the kind of
    thing a validator exists to reject.

    Args:
        name: The candidate identifier, typically from settings or a module constant.

    Returns:
        The same string, unchanged, once proven safe.

    Raises:
        ValueError: If ``name`` is empty, over :data:`MAX_IDENTIFIER_LENGTH`, or contains
            anything but ``[A-Za-z0-9_]`` (starting with a letter or underscore) — which is
            what an injection attempt necessarily does.

    Examples:
        >>> safe_identifier("documents")
        'documents'
        >>> safe_identifier("x; DROP TABLE audit_ledger")
        Traceback (most recent call last):
            ...
        ValueError: unsafe SQL identifier: 'x; DROP TABLE audit_ledger'
    """
    if not name or len(name) > MAX_IDENTIFIER_LENGTH:
        msg = (
            f"unsafe SQL identifier: {name!r} "
            f"(must be 1..{MAX_IDENTIFIER_LENGTH} characters, got {len(name)})"
        )
        raise ValueError(msg)
    if not _IDENTIFIER.fullmatch(name):
        msg = f"unsafe SQL identifier: {name!r}"
        raise ValueError(msg)
    return name


def safe_qualified_identifier(name: str) -> str:
    """Validate a dotted name (``database.table``), part by part.

    ClickHouse addresses its tables as ``<database>.<table>``, so the string that reaches the
    query is not a bare identifier. Splitting and validating each half is not the same as
    loosening :func:`safe_identifier` to allow a dot: ``"db.tbl; DROP"`` fails here, and
    ``"a.b.c.d"`` — which is not a name this codebase ever builds — fails too.

    Args:
        name: A ``part`` or ``part.part`` name.

    Returns:
        The same string, unchanged, once every part is proven safe.

    Raises:
        ValueError: If the name has more than two parts, or any part is not a safe identifier.
    """
    parts = name.split(".")
    max_parts = 2
    if len(parts) > max_parts:
        msg = f"unsafe qualified SQL identifier: {name!r} (expected at most database.table)"
        raise ValueError(msg)
    for part in parts:
        safe_identifier(part)
    return name
