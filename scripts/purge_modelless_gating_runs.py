#!/usr/bin/env python
"""Purge gating runs that carry a ``model`` witness no token evidence backs — by interrogation.

Four runs entered ``eval_gating_scores`` on 2026-07-12: full per-agent sweeps completing
in under 4 seconds, ``model`` filled with the *configured* name, and not one report file
in the archive publishing them — the null control filed as a model verdict. The table does
not store tokens, so it cannot defend itself; this tool interrogates on its behalf:

* **The archive is the only place tokens live.** For every run of the requested date, the
  tool looks for the report that published it. Found → :func:`eval.ratchet.model_spoke`
  (the one rule) decides on the report's own tokens. Not found → the run is *table-only*:
  no witness anywhere that a model spoke, and its own rows (a full sweep spread over
  seconds) say nothing could have. Both are ghosts; the evidence column names which.
* **Nothing is identified by a hard-coded id.** The date scopes the interrogation; the
  verdicts come out of the archive and the rows.
* **The door must exist before the cleanup.** This script imports the ingestion guard's
  refusal type, so it cannot run in a tree where the entry it purges behind is still open
  — purge-then-guard would erase the only proof the hole existed while leaving it open.

Dry-run by default; ``--apply`` deletes and prints before/after counts. Exit codes:
``0`` interrogated (including "nothing to purge"), ``2`` the store cannot be seen — a
tool that cannot look never reports "ok" (ADR 0026).

Usage:
    uv run python scripts/purge_modelless_gating_runs.py --date 2026-07-12
    uv run python scripts/purge_modelless_gating_runs.py --date 2026-07-12 --apply
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import date, datetime

import psycopg

from eval.ratchet import model_spoke
from tessera.observability.eval.gating_scores import GATING_TABLE, ModellessRunRefusedError
from tessera.observability.eval.report_paths import iter_report_files
from tessera.settings import get_settings
from tessera.sql import safe_identifier


@dataclass(frozen=True, slots=True)
class RunEvidence:
    """One run of the requested date, with everything the interrogation could see."""

    run_id: str
    agent_id: str
    model: str
    rows: int
    spread_seconds: float
    published_by: str | None
    output_tokens: int | None
    # The archive's own verdict via eval.ratchet.model_spoke — never recomputed here. A
    # False over a published run means 0 tokens; over a table-only run it means the one
    # artefact that stores tokens holds no witness at all. Both read "ghost" below.
    spoke: bool

    def verdict_line(self) -> str:
        """One evidence line: what was asked, what answered, what it means."""
        if self.published_by is not None and self.spoke:
            witness = (
                f"KEEP   published by {self.published_by} — {self.output_tokens} output tokens"
            )
        elif self.published_by is not None:
            witness = f"GHOST  published by {self.published_by} — 0 output tokens, model field lies"
        else:
            witness = (
                f"GHOST  table-only: no report in the archive publishes this run, and its own "
                f"rows say a full {self.rows}-row sweep completed in {self.spread_seconds:.1f}s "
                f"— no model could have spoken"
            )
        return (
            f"  {self.run_id}  agent={self.agent_id} model={self.model} rows={self.rows}\n"
            f"    {witness}"
        )


def published_runs() -> dict[str, tuple[str, int, bool]]:
    """``run_id -> (report file, output tokens, model spoke)`` per run the archive publishes.

    A timestamped archive beats its ``latest_<agent>.json`` copy for naming, but both
    carry the same content — the tokens are identical whichever file answers. The
    "spoke" bit is :func:`eval.ratchet.model_spoke` on the report itself — the one
    rule, asked of the one artefact that stores tokens.
    """
    published: dict[str, tuple[str, int, bool]] = {}
    for path in iter_report_files():
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(report, dict) or not report.get("agent_id"):
            continue
        run_id = f"{report.get('run_at')}_{report.get('agent_id')}"
        tokens = int((report.get("cost") or {}).get("output_tokens", 0) or 0)
        if run_id not in published or "latest" not in path.name:
            published[run_id] = (path.name, tokens, model_spoke(report))
    return published


# S608 on the three statements below is earned the same way the spine adapter earns it:
# the table name is validated by `safe_identifier` at its definition and every value is a
# bound parameter — nothing but a proven identifier enters the SQL text.


def _counts(conn: psycopg.Connection) -> tuple[int, int]:
    row = conn.execute(
        f"SELECT count(*), count(DISTINCT run_id) FROM {GATING_TABLE}"  # noqa: S608
    ).fetchone()
    if row is None:  # pragma: no cover — count(*) always returns one row
        msg = "count(*) returned no row"
        raise RuntimeError(msg)
    return int(row[0]), int(row[1])


def main() -> int:
    """Interrogate the runs of one date; delete the ghosts only under ``--apply``."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--date", required=True, type=date.fromisoformat, help="UTC day to interrogate"
    )
    parser.add_argument(
        "--apply", action="store_true", help="delete the ghost runs (default: dry-run)"
    )
    args = parser.parse_args()

    settings = get_settings()
    sys.stdout.write(
        f"door at ingestion: {ModellessRunRefusedError.__name__} is in this tree — "
        f"the entry is closed before the cleanup\n"
    )

    archive = published_runs()
    prefix = f"{args.date:%Y%m%d}T"
    try:
        with psycopg.connect(str(settings.postgres.dsn), connect_timeout=10) as conn:
            schema = safe_identifier(settings.pg_schema)
            conn.execute(f"SET search_path TO {schema}, public")
            before_rows, before_runs = _counts(conn)
            sys.stdout.write(
                f"BEFORE  schema={settings.pg_schema} rows={before_rows} runs={before_runs}\n\n"
            )
            candidates = [
                RunEvidence(
                    run_id=str(run_id),
                    agent_id=str(agent_id),
                    model=str(model),
                    rows=int(rows),
                    spread_seconds=float(spread),
                    published_by=archive[str(run_id)][0] if str(run_id) in archive else None,
                    output_tokens=archive[str(run_id)][1] if str(run_id) in archive else None,
                    spoke=archive[str(run_id)][2] if str(run_id) in archive else False,
                )
                for run_id, agent_id, model, rows, spread in conn.execute(
                    "SELECT run_id, agent_id, model, count(*),"  # noqa: S608
                    " EXTRACT(EPOCH FROM max(scored_at) - min(scored_at))"
                    f" FROM {GATING_TABLE} WHERE run_id LIKE %s"
                    " GROUP BY run_id, agent_id, model ORDER BY run_id",
                    (f"{prefix}%",),
                )
            ]
            sys.stdout.write(f"runs on {args.date}: {len(candidates)}\n")
            for run in candidates:
                sys.stdout.write(run.verdict_line() + "\n")
            ghosts = [run for run in candidates if not run.spoke]
            ghost_rows = sum(run.rows for run in ghosts)
            sys.stdout.write(f"\nghosts: {len(ghosts)} run(s), {ghost_rows} row(s) to purge\n")
            if not ghosts:
                sys.stdout.write("nothing to purge\n")
                return 0
            if not args.apply:
                sys.stdout.write("DRY RUN — nothing deleted (pass --apply to purge)\n")
                return 0
            deleted = conn.execute(
                f"DELETE FROM {GATING_TABLE} WHERE run_id = ANY(%s)",  # noqa: S608
                ([run.run_id for run in ghosts],),
            ).rowcount
            conn.commit()
            after_rows, after_runs = _counts(conn)
    except psycopg.Error as exc:
        sys.stderr.write(f"CANNOT SAY — the gating store cannot be seen: {exc}\n")
        return 2
    sys.stdout.write(
        f"deleted {deleted} row(s) across {len(ghosts)} run(s) "
        f"at {datetime.now().astimezone().isoformat(timespec='seconds')}\n"
        f"AFTER   rows={after_rows} runs={after_runs} "
        f"(expected rows={before_rows - ghost_rows}, runs={before_runs - len(ghosts)})\n"
    )
    if (after_rows, after_runs) != (before_rows - ghost_rows, before_runs - len(ghosts)):
        sys.stderr.write("the AFTER counts do not match what was deleted — investigate\n")
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover  thin CLI shim
    raise SystemExit(main())
