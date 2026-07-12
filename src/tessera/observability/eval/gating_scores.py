"""Owned Postgres home of the GATING eval scores (ADR 0015 §Amendment 2, Nature 1).

The release socle — the offline harness verdicts archived under ``eval/reports/*.json``
that **gate a release** — is the opposable, load-bearing eval fact. Its volume is bounded
(cases x languages x metrics x runs; it grows per *release*, not per *traffic*), so it
lives in a plain indexed, transactional Postgres table with **no partition/retention
machinery**. The online monitoring firehose lives elsewhere (owned ClickHouse,
§Correction 2b) and Prometheus keeps the aggregates — this table is never summed on the
hot path.

Schema bootstrap follows the repo's idempotent ``ensure_*_schema`` pattern (not Alembic).
The pool pins ``search_path`` to the active environment's schema (ADR 0014), so the table
materialises per environment at boot and a read never falls through to another
environment's state. The unique ``(run_id, case_id, language, metric)`` key is what makes
re-ingest and backfill idempotent (``ON CONFLICT DO NOTHING``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final

from tessera.retrieval.store import get_pool
from tessera.sql import safe_identifier

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

__all__ = [
    "GATING_METRIC",
    "GATING_TABLE",
    "GatingScoreRow",
    "ensure_eval_gating_schema",
    "gating_row_dict",
    "gating_rows_from_report",
    "ingest_gating_reports",
    "record_gating_report",
    "record_gating_rows",
]

# Validated at definition (audit P0.3 `sql-fstring`). Found by the class ratchet, not by the
# audit and not by ruff: this module's `INSERT INTO {GATING_TABLE}` sits in an indented
# multi-line f-string, the shape S608's heuristic does not see.
GATING_TABLE: Final = safe_identifier("eval_gating_scores")

# The harness produces one deterministic verdict per case x language — the socle's single
# metric today. A numeric judge metric added to the harness later becomes another metric
# name under the same unique key; nothing here changes.
GATING_METRIC: Final = "case_pass"

# Nature-1 DDL (ADR 0015 §Amendment 2) — the release-gating socle: bounded, opposable.
CREATE_GATING_TABLE: Final = f"""
CREATE TABLE IF NOT EXISTS {GATING_TABLE} (
    id                bigserial PRIMARY KEY,
    run_id            text        NOT NULL,
    case_id           text        NOT NULL,
    agent_id          text        NOT NULL,
    language          text        NOT NULL,
    model             text        NOT NULL,
    metric            text        NOT NULL,
    score             double precision NOT NULL,
    passed            boolean     NOT NULL,
    catalogue_version text,
    judge_model       text,
    scored_at         timestamptz NOT NULL
)
"""

CREATE_GATING_INDEXES: Final = (
    f"CREATE INDEX IF NOT EXISTS eval_gating_run ON {GATING_TABLE} (run_id)",
    f"CREATE INDEX IF NOT EXISTS eval_gating_agent ON {GATING_TABLE} (agent_id, scored_at)",
    # Idempotent re-ingest / backfill: a run + case + language + metric is unique.
    "CREATE UNIQUE INDEX IF NOT EXISTS eval_gating_uq "
    f"ON {GATING_TABLE} (run_id, case_id, language, metric)",
)


async def ensure_eval_gating_schema() -> None:
    """Create the gating-scores table and its indexes idempotently."""
    pool = get_pool()
    if pool.closed:
        await pool.open()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(CREATE_GATING_TABLE)
        for statement in CREATE_GATING_INDEXES:
            await cur.execute(statement)
        await conn.commit()


@dataclass(frozen=True, slots=True)
class GatingScoreRow:
    """One per-case gating verdict, shaped exactly like the owned table's row."""

    run_id: str
    case_id: str
    agent_id: str
    language: str
    model: str
    metric: str
    score: float
    passed: bool
    catalogue_version: str | None
    judge_model: str | None
    scored_at: datetime


def gating_row_dict(row: GatingScoreRow) -> dict[str, object]:
    """One gating row as the plain dict shape the spine readers serve.

    Both sides of the G4 parity comparison (report files vs the owned Postgres table)
    serialize through this one function, so the shapes cannot drift apart.
    """
    return {
        "run_id": row.run_id,
        "case_id": row.case_id,
        "agent_id": row.agent_id,
        "language": row.language,
        "model": row.model,
        "metric": row.metric,
        "score": row.score,
        "passed": row.passed,
        "catalogue_version": row.catalogue_version,
        "judge_model": row.judge_model,
        "scored_at": row.scored_at.isoformat(),
    }


def _parse_run_at(run_at: str) -> datetime | None:
    """The runner's ``run_at`` stamp (``YYYYMMDDTHHMMSSZ``) as an aware datetime."""
    try:
        return datetime.strptime(run_at, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
    except ValueError:
        return None


def _scored_at(result: Mapping[str, object], run_stamp: datetime) -> datetime:
    """A case's instant: its own ``ended_at`` when present, else the run's stamp."""
    ended_at = result.get("ended_at")
    if isinstance(ended_at, str):
        try:
            stamp = datetime.fromisoformat(ended_at)
        except ValueError:
            return run_stamp
        return stamp if stamp.tzinfo is not None else stamp.replace(tzinfo=UTC)
    return run_stamp


def gating_rows_from_report(report: Mapping[str, object]) -> list[GatingScoreRow]:
    """Per-case gating rows from one harness report (pure — unit-testable).

    Only *release* runs qualify: a report without an ``agent_id`` is a catalogue-wide
    probe, not the socle that gates an agent's release (§Amendment 2 Nature 1) — it stays
    in the file archive and produces no rows here, never a fabricated attribution. The
    ``run_id`` is derived from the report *content* (``run_at`` + agent), so the
    timestamped archive and its ``latest_<agent>.json`` copy dedup to the same run.
    """
    agent_id = report.get("agent_id")
    run_at = report.get("run_at")
    model = report.get("model")
    if not isinstance(agent_id, str) or not agent_id:
        return []
    if not isinstance(run_at, str) or not isinstance(model, str) or not model:
        return []
    run_stamp = _parse_run_at(run_at)
    if run_stamp is None:
        return []
    catalogue_version = report.get("catalogue_version")
    results = report.get("results")
    rows: list[GatingScoreRow] = []
    for result in results if isinstance(results, list) else []:
        if not isinstance(result, dict):
            continue
        case_id = result.get("case_id")
        language = result.get("language")
        passed = result.get("passed")
        if not isinstance(case_id, str) or not isinstance(language, str):
            continue
        if not isinstance(passed, bool):
            continue
        rows.append(
            GatingScoreRow(
                run_id=f"{run_at}_{agent_id}",
                case_id=case_id,
                agent_id=agent_id,
                language=language,
                model=model,
                metric=GATING_METRIC,
                score=1.0 if passed else 0.0,
                passed=passed,
                catalogue_version=(
                    catalogue_version if isinstance(catalogue_version, str) else None
                ),
                judge_model=None,  # deterministic harness graders — no LLM judge
                scored_at=_scored_at(result, run_stamp),
            )
        )
    return rows


_INSERT_ROW: Final = f"""
INSERT INTO {GATING_TABLE}
    (run_id, case_id, agent_id, language, model, metric, score, passed,
     catalogue_version, judge_model, scored_at)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (run_id, case_id, language, metric) DO NOTHING
"""


async def record_gating_rows(rows: Sequence[GatingScoreRow]) -> int:
    """Insert gating rows durably; the unique key makes re-recording free.

    Returns the number of rows actually inserted (0 on a full re-ingest) — the
    idempotence the backfill and the boot-time sweep rely on.
    """
    if not rows:
        return 0
    await ensure_eval_gating_schema()
    pool = get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.executemany(
            _INSERT_ROW,
            [
                (
                    row.run_id,
                    row.case_id,
                    row.agent_id,
                    row.language,
                    row.model,
                    row.metric,
                    row.score,
                    row.passed,
                    row.catalogue_version,
                    row.judge_model,
                    row.scored_at,
                )
                for row in rows
            ],
        )
        inserted = cur.rowcount if cur.rowcount >= 0 else 0
        await conn.commit()
    return inserted


async def record_gating_report(report: Mapping[str, object], *, flush_mirror: bool = False) -> int:
    """Record one harness report durably + hand its rows to the best-effort mirror.

    The Postgres insert is the load-bearing leg (the porteur). The Langfuse mirror is
    drill-down enrichment via the SDK (§Amendment 1 "voie 1"), session-anchored on the
    run id and idempotent by stable score id — mirrored only for *newly* inserted runs,
    so a boot-time re-sweep never re-sends the whole archive. ``flush_mirror`` drains
    the SDK batch before returning (for CLI exits — the eval runner). Returns the
    number of newly inserted rows.
    """
    rows = gating_rows_from_report(report)
    inserted = await record_gating_rows(rows)
    if inserted:
        from tessera.observability import langfuse_scores

        langfuse_scores.mirror_gating_rows(rows, flush=flush_mirror)
    return inserted


async def ingest_gating_reports() -> tuple[int, int]:
    """Reconcile the env's report-file archive into the porteur (idempotent sweep).

    Parses every report the environment can read (ADR 0014 path resolution), records the
    release runs, and returns ``(reports_with_rows, rows_inserted)``. The unique key makes
    a re-sweep free, so this runs at every boot **and** serves as the G4 historical
    backfill — the file archive and the owned table converge without a separate tool.
    Non-release (agent-less) reports contribute nothing, by design.
    """
    import json

    from tessera.observability.eval.report_paths import iter_report_files

    reports_with_rows = 0
    inserted_total = 0
    seen_runs: set[str] = set()
    for path in sorted(iter_report_files()):
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # best-effort: skip an unreadable/corrupt gating report — non-gating read (0015)
            continue
        if not isinstance(report, dict):
            continue
        rows = gating_rows_from_report(report)
        if not rows:
            continue
        run_id = rows[0].run_id
        if run_id in seen_runs:  # latest_<agent>.json duplicates its timestamped archive
            continue
        seen_runs.add(run_id)
        reports_with_rows += 1
        inserted_total += await record_gating_report(report)
    return reports_with_rows, inserted_total
