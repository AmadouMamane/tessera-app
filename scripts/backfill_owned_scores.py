"""Backfill the owned score stores from the legacy files (ADR 0015 G4, idempotent).

Two legs, both safe to re-run:

* **Online** — every ``scores.jsonl`` row absent from the owned ClickHouse table
  (``tessera.eval_online_scores``) is inserted by **difference**: the dedup key is
  ``(scored_at@ms, metric, conversation_id, trace_id)``, computable identically on both
  sides, so a second run inserts zero rows. This fills the history the live write path
  (G2) could not have seen.
* **Gating** — the env's report-file archive is swept into the Postgres porteur via
  ``ingest_gating_reports()`` (unique-key idempotent; agent-less catalogue probes
  contribute nothing). Newly recorded runs are mirrored to Langfuse (session-anchored)
  and the SDK batch is flushed before exit.

Run from the repo root:

    PYTHONPATH=src:. uv run python scripts/backfill_owned_scores.py
"""

from __future__ import annotations

import asyncio
import sys

from tessera.observability.clickhouse_scores import online_row_key, online_score_line
from tessera.observability.eval.gating_scores import ingest_gating_reports
from tessera.observability.eval.scores import persisted_scores
from tessera.observability.langfuse_scores import flush_mirror
from tessera.observability.spine.adapters.base import SpineUnavailableError
from tessera.observability.spine.adapters.clickhouse import ClickHouseAdapter


def existing_online_keys(adapter: ClickHouseAdapter) -> set[tuple[str, str, str, str]]:
    """The dedup keys already present in the owned table."""
    raw = adapter.execute(
        "SELECT toString(scored_at) AS scored_at, metric, conversation_id, trace_id"  # noqa: S608 — fixed identifiers
        f" FROM {adapter.table} FORMAT JSONEachRow"
    )
    import json

    keys: set[tuple[str, str, str, str]] = set()
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        row = json.loads(stripped)
        keys.add(
            (
                str(row.get("scored_at", "")),
                str(row.get("metric", "")),
                str(row.get("conversation_id", "")),
                str(row.get("trace_id", "")),
            )
        )
    return keys


def backfill_online(adapter: ClickHouseAdapter) -> tuple[int, int, int]:
    """Insert the jsonl rows missing from the owned table; return (total, missing, skipped)."""
    adapter.ensure_schema()
    existing = existing_online_keys(adapter)
    rows = persisted_scores()
    lines: list[bytes] = []
    skipped = 0
    for row in rows:
        key = online_row_key(row)
        line = online_score_line(row)
        if key is None or line is None:
            skipped += 1  # a row without an instant/metric is dropped, never invented
            continue
        if key in existing:
            continue
        existing.add(key)  # jsonl-internal duplicates collapse too
        lines.append(line)
    if lines:
        adapter.execute(
            f"INSERT INTO {adapter.table} FORMAT JSONEachRow",
            data=b"\n".join(lines),
        )
    return len(rows), len(lines), skipped


async def main() -> int:
    adapter = ClickHouseAdapter(timeout_s=10.0)
    try:
        total, inserted, skipped = backfill_online(adapter)
    except SpineUnavailableError as exc:
        print(f"online backfill skipped (clickhouse unreachable): {exc}", file=sys.stderr)
        return 1
    print(f"online: {total} jsonl rows → {inserted} inserted ({skipped} skipped, rest present)")
    reports, gating_rows = await ingest_gating_reports()
    print(f"gating: {reports} release reports swept → {gating_rows} rows inserted")
    flush_mirror()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
