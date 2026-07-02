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

if TYPE_CHECKING:
    from tessera.observability.spine.scope import Scope


def _cutoff(at: str) -> datetime | None:
    """``scope.at`` as an aware datetime; unparsable → no time bound (jsonl parity)."""
    try:
        stamp = datetime.fromisoformat(at)
    except ValueError:
        return None
    return stamp if stamp.tzinfo is not None else stamp.replace(tzinfo=UTC)


__all__ = ["PostgresGatingAdapter"]

# Bounded like the other spine adapters (0.8 s reads): the snapshot must degrade to an
# honest-empty signal rather than stall on a slow store.
_STATEMENT_TIMEOUT_MS = 800
_CONNECT_TIMEOUT_S = 1


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
        # S608: the table name is a fixed module constant and every value is a bound
        # parameter — nothing user-controlled enters the SQL text.
        query = (
            "SELECT run_id, case_id, agent_id, language, model, metric, score, passed,"  # noqa: S608
            f" catalogue_version, judge_model, scored_at FROM {GATING_TABLE}{where}"
            " ORDER BY scored_at"
        )
        try:
            with psycopg.connect(
                str(settings.postgres.dsn),
                connect_timeout=_CONNECT_TIMEOUT_S,
                options=f"-c statement_timeout={_STATEMENT_TIMEOUT_MS}",
            ) as conn:
                conn.execute(f"SET search_path TO {settings.pg_schema}, public")
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
