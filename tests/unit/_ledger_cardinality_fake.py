"""A ledger that answers by CARDINALITY — the double the read-budget ratchet drives.

Not collected (``python_files = ["test_*.py"]``).

The ratchet asks one question of the request paths: *how many rows did you pull into memory?*
Answering it hermetically needs a fake ``audit_ledger`` — and the temptation is to write a small
SQL engine, which would be fragile and would encode this author's guesses about Postgres.

This is not that. It is a **cardinality oracle**: it does not evaluate the predicates, it reads
the SHAPE of the query and hands back as many rows as a real database would. The rule it encodes
is the exact rule under test:

    a query with no bounding construct returns the whole table.

``LIMIT`` bounds. A bare ``count(*)``/``max()`` bounds to one row. ``GROUP BY`` and ``DISTINCT
ON`` bound to the number of groups — note the order: a ``count(*)`` *with* a ``GROUP BY`` returns
one row **per group**, not one row, and getting that backwards is how a fake starts lying on
behalf of the code it is meant to police. Everything else — ``SELECT payload FROM audit_ledger
ORDER BY seq`` — hands back all :data:`LEDGER_ROWS`, and the ratchet fails.

That conservatism runs the right way. A *new* unbounded read is caught, because the oracle gives
it the whole table. A *bounded* read is never falsely accused, because the oracle honours its
bound. And a read that is bounded in name only — ``load_ledger_payloads_of_type
("tessera.guard.audit")``, which matches 94 % of the real chain — is still caught, because what
is counted is rows, never the name of the function that asked for them.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

#: How many entries the fake chain holds. Large enough that a full read is unmistakable.
LEDGER_ROWS = 5_000

#: The agents the fake ledger carries canary / handoff entries for.
AGENTS = ("recouvrement", "support-client", "onboarding")

_LEDGER = "audit_ledger"
_CHECKPOINT = "audit_ledger_checkpoint"

_DISTINCT_ON = re.compile(r"\bdistinct\s+on\b")
_GROUP_BY = re.compile(r"\bgroup\s+by\b")
_LIMIT = re.compile(r"\blimit\s+(\d+)\b")
_AGGREGATE = re.compile(r"\b(count|max)\s*\(")


def _normalise(sql: str) -> str:
    return " ".join(sql.split()).lower()


def _anchor(params: object) -> int | None:
    """The ``seq`` a ``WHERE seq > %s`` is anchored at — the first bound integer parameter.

    The oracle must read the BOUND VALUE, not just the query text: ``WHERE seq > %s`` is a full
    read at 0 (a cold verifier re-walking the chain) and reads nothing at the tail (the steady
    incremental delta). The same SQL, two cardinalities — as in the real database. A fake that
    judged the text alone would call the cold full walk "bounded" and hide the one read this
    design genuinely depends on.
    """
    if isinstance(params, tuple | list):
        for value in params:
            if isinstance(value, int) and not isinstance(value, bool):
                return value
    return None


def cardinality(sql: str, params: object = None) -> int:  # noqa: PLR0911
    """How many rows a real Postgres would hand back for this query — its SHAPE, not its meaning.

    The order is the substance: ``LIMIT`` is the hardest bound; a GROUPED aggregate returns one
    row per group; only a BARE aggregate collapses to one row; and what has none of those reads
    the table.
    """
    s = _normalise(sql)
    if not s.startswith("select"):
        return 0  # INSERT / CREATE / SET — a write materialises nothing
    limit = _LIMIT.search(s)
    if limit:
        return min(int(limit.group(1)), LEDGER_ROWS)
    if _DISTINCT_ON.search(s) or _GROUP_BY.search(s):
        return len(AGENTS)  # one row per group — including a GROUPED count(*)
    if _AGGREGATE.search(s):
        return 1  # a bare aggregate over the whole table still returns ONE row
    if "where seq > " in s or "where a.seq > " in s:
        anchor = _anchor(params)
        return LEDGER_ROWS if anchor == 0 else 0  # cold walk vs the steady delta
    if "where seq = " in s or "where hash = " in s or "where id = 1" in s:
        return 1  # a single indexed row
    return LEDGER_ROWS  # an unbounded read of the chain — the offence this ratchet exists for


def _payload(index: int) -> dict[str, Any]:
    return {
        "type": "tessera.agent.canary",
        "agent_id": AGENTS[index % len(AGENTS)],
        "verdict": "green",
        "occurred_at": "2026-07-13T00:00:00+00:00",
        "hash": f"h{index}",
        "prev_hash": f"h{index - 1}" if index else "0" * 64,
    }


def _checkpoint_row() -> tuple[Any, ...]:
    """A checkpoint anchored at the tail — the STEADY state a request path actually meets.

    (verified_seq, verified_hash, verified_count, content_ok, broken_at, attested, forks,
    orphans, full_verified_at, full_verified_seq)
    """
    return (
        LEDGER_ROWS,
        f"h{LEDGER_ROWS - 1}",
        LEDGER_ROWS,
        True,
        None,
        False,
        [],
        [],
        datetime.now(UTC),
        LEDGER_ROWS,
    )


def _ledger_rows(sql: str, params: object = None) -> list[tuple[Any, ...]]:  # noqa: PLR0911
    """Rows of the arity the caller unpacks — only the shape and the COUNT matter."""
    s = _normalise(sql)
    n = cardinality(sql, params)
    if _AGGREGATE.search(s) and not (_GROUP_BY.search(s) or _DISTINCT_ON.search(s)):
        return [(LEDGER_ROWS,)]  # count(*)/max(seq): reports the TABLE's size, reads one row
    if "select hash from" in s and "where seq = " in s:
        return [(f"h{LEDGER_ROWS - 1}",)]  # the checkpoint's anchor still holds
    if "to_agent" in s and "from_agent" in s:
        return [(AGENTS[i], AGENTS[(i + 1) % len(AGENTS)], 1) for i in range(n)]
    if _DISTINCT_ON.search(s):
        return [(AGENTS[i], _payload(i)) for i in range(n)]
    if "select seq, payload, hash, prev_hash" in s:
        return [(i + 1, _payload(i), f"h{i}", f"h{i - 1}" if i else "0" * 64) for i in range(n)]
    if "array_agg" in s or "select a.hash, a.prev_hash" in s:
        return [(f"h{i}", f"h{i - 1}") for i in range(n)]
    return [(_payload(i),) for i in range(n)]


class _Result:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self._rows = rows

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._rows[0] if self._rows else None

    def fetchall(self) -> list[tuple[Any, ...]]:
        return list(self._rows)


class _Cursor:
    def __init__(self, conn: CardinalityLedgerConn) -> None:
        self._conn = conn
        self._result = _Result([])

    def __enter__(self) -> _Cursor:
        return self

    def __exit__(self, *_: object) -> bool:
        return False

    def execute(self, sql: str, params: object = None) -> _Result:
        self._result = self._conn._answer(sql, params)
        return self._result

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._result.fetchone()

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self._result.fetchall()


class CardinalityLedgerConn:
    """A ``_connect_sync`` double answering by shape. Context-managed, exactly like the real one.

    Args:
        checkpoint: whether a verification checkpoint already exists. ``True`` is the STEADY
            state — the one a request path meets, and the one the budget polices. ``False`` is a
            cold process, where the verifier re-walks the whole chain **on purpose, once**; the
            ratchet asserts that too, so the exception stays visible instead of quietly becoming
            the rule.
    """

    def __init__(self, *, checkpoint: bool = True) -> None:
        self.checkpoint = checkpoint

    def __enter__(self) -> CardinalityLedgerConn:
        return self

    def __exit__(self, *_: object) -> bool:
        return False

    def _answer(self, sql: str, params: object = None) -> _Result:
        s = _normalise(sql)
        if _CHECKPOINT in s:
            if not s.startswith("select"):
                return _Result([])  # CREATE TABLE / INSERT … ON CONFLICT — a write
            return _Result([_checkpoint_row()] if self.checkpoint else [])
        if _LEDGER not in s:
            return _Result([])
        return _Result(_ledger_rows(sql, params))

    def execute(self, sql: str, params: object = None) -> _Result:
        return self._answer(sql, params)

    def cursor(self) -> _Cursor:
        return _Cursor(self)

    def commit(self) -> None:
        pass
