"""Postgres read adapter — the owned GATING-score porteur (ADR 0015 §Amendment 2 + 3).

Reads the release socle from the owned, transactional ``eval_gating_scores`` table: the
per-case verdicts that gate an agent's release, as-of-T by ``scored_at``, filterable by
agent / language / model — the load-bearing eval fact whose durability and read path never
depend on a third party (Langfuse ceased to be a spine source, §Amendment 1).

The spine readers are synchronous, so this adapter opens its own short-lived **sync**
psycopg connection per read (the process pool is async), pinned to the active
environment's schema (ADR 0014) with a bounded ``statement_timeout`` — a slow or absent
Postgres raises :class:`SpineUnavailableError` → honest-empty, never a fabricated zero.
Every value is bound as a query parameter; the fixed table name is the only identifier.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from tessera.observability.spine.adapters.base import SpineUnavailableError
from tessera.sql import safe_identifier

if TYPE_CHECKING:
    from tessera.observability.spine.scope import Scope


def _cutoff(at: str) -> datetime | None:
    """``scope.at`` as an aware datetime; unparsable → no time bound (jsonl parity)."""
    try:
        stamp = datetime.fromisoformat(at)
    except ValueError:
        return None
    return stamp if stamp.tzinfo is not None else stamp.replace(tzinfo=UTC)


__all__ = ["GATING_TOTAL_ORDER", "PostgresGatingAdapter"]

# Bounded like the other spine adapters (0.8 s reads): the snapshot must degrade to an
# honest-empty signal rather than stall on a slow store.
_STATEMENT_TIMEOUT_MS = 800
_CONNECT_TIMEOUT_S = 1

# A TOTAL order: `id` (insert order) breaks scored_at ties so the same (scope, T) always
# returns the same rows in the same order — the SR-01 as-of-T reproducibility contract.
GATING_TOTAL_ORDER = " ORDER BY scored_at, id"


class PostgresGatingAdapter:
    """Query client for the owned gating-score table (as-of-T, dimension-filtered)."""

    def gating_scores(self, scope: Scope) -> list[dict[str, object]]:
        """Gating rows for ``scope`` (oldest→newest), shaped like ``gating_row_dict``."""
        import psycopg
        from psycopg.rows import dict_row

        from tessera.observability.eval.gating_scores import GATING_TABLE
        from tessera.settings import get_settings

        settings = get_settings()
        conditions: list[str] = []
        params: list[object] = []
        cutoff = _cutoff(scope.at) if scope.at else None
        if cutoff is not None:
            conditions.append("scored_at <= %s")
            params.append(cutoff)
        if scope.agent_id is not None:
            conditions.append("agent_id = %s")
            params.append(scope.agent_id)
        if scope.language is not None:
            conditions.append("language = %s")
            params.append(scope.language)
        if scope.model is not None:
            conditions.append("model = %s")
            params.append(scope.model)
        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        # S608 cannot be removed: it is a syntactic rule and cannot see the validation below.
        # It is earned, though — the table is validated by `safe_identifier` and every value
        # is a bound parameter, so nothing but a proven identifier enters the SQL text.
        query = (
            "SELECT run_id, case_id, agent_id, language, model, metric, score, passed,"  # noqa: S608
            f" catalogue_version, judge_model, scored_at FROM {safe_identifier(GATING_TABLE)}"
            f"{where}{GATING_TOTAL_ORDER}"
        )
        try:
            with psycopg.connect(
                str(settings.postgres.dsn),
                connect_timeout=_CONNECT_TIMEOUT_S,
                options=f"-c statement_timeout={_STATEMENT_TIMEOUT_MS}",
            ) as conn:
                # `pg_schema` is derived from the Environment enum, so it was never reachable
                # by an attacker — but it was spliced into SQL with NO check of any kind, and
                # "safe because of where it comes from" is exactly the reasoning the audit
                # asked us to stop relying on. Validated like every other identifier.
                schema = safe_identifier(settings.pg_schema)
                conn.execute(f"SET search_path TO {schema}, public")
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(query, params)
                    records = cur.fetchall()
        except psycopg.Error as exc:
            msg = f"postgres gating store unreachable: {exc}"
            raise SpineUnavailableError(msg) from exc
        rows: list[dict[str, object]] = []
        for record in records:
            scored_at = record.get("scored_at")
            rows.append(
                {
                    **record,
                    "scored_at": (
                        scored_at.isoformat() if isinstance(scored_at, datetime) else None
                    ),
                }
            )
        return rows
