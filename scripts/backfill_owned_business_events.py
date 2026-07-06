"""Backfill the owned business-event store from the durable substrate (ADR 0017 §5 / G4).

Idempotent by construction: every business-event row present in the durable replay bundles
(``bundles.jsonl``, which embed each turn's ``business_events``) or the in-process store,
and absent from the owned ClickHouse table ``tessera.business_events``, is inserted by
**difference**. The dedup key ``(occurred_at@ms, agent_id, event_name, conversation_id,
turn_id, artifact_id)`` is computable identically on both sides (the store keeps
millisecond stamps), so a second run inserts zero rows. This fills the history the live
dual-write (Phase D) could not have seen, the leg the flip's shadow parity checks against.

Run from the repo root:

    PYTHONPATH=src:. uv run python scripts/backfill_owned_business_events.py
"""

from __future__ import annotations

import json
import sys

from tessera.observability import replay as replay_mod
from tessera.observability.business_events import get_business_event_store
from tessera.observability.clickhouse_business_events import (
    business_event_line,
    business_event_row_key,
)
from tessera.observability.spine.adapters.base import SpineUnavailableError
from tessera.observability.spine.adapters.clickhouse import ClickHouseAdapter

_KEY_COLUMNS = (
    "occurred_at",
    "agent_id",
    "event_name",
    "conversation_id",
    "turn_id",
    "artifact_id",
)


def existing_business_event_keys(
    adapter: ClickHouseAdapter,
) -> set[tuple[str, str, str, str, str, str]]:
    """The dedup keys already present in the owned table (millisecond precision)."""
    raw = adapter.execute(
        "SELECT toString(occurred_at) AS occurred_at, agent_id, event_name,"  # noqa: S608 — fixed identifiers
        " conversation_id, turn_id, artifact_id"
        f" FROM {adapter.business_events_table} FORMAT JSONEachRow"
    )
    keys: set[tuple[str, str, str, str, str, str]] = set()
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        row = json.loads(stripped)
        keys.add(tuple(str(row.get(column, "")) for column in _KEY_COLUMNS))  # type: ignore[arg-type]
    return keys


def _source_rows() -> list[dict[str, object]]:
    """Business-event rows from the durable replay bundles + the in-process seed."""
    rows: list[dict[str, object]] = []
    for bundle in replay_mod.persisted_bundles():
        rows.extend(bundle.business_events)
    rows.extend(event.to_row() for event in get_business_event_store().list())
    return rows


def backfill_business_events(adapter: ClickHouseAdapter) -> tuple[int, int, int]:
    """Insert the source rows missing from the owned table; return (total, inserted, skipped)."""
    adapter.ensure_business_events_schema()
    existing = existing_business_event_keys(adapter)
    rows = _source_rows()
    lines: list[bytes] = []
    skipped = 0
    for row in rows:
        key = business_event_row_key(row)
        line = business_event_line(row)
        if key is None or line is None:
            skipped += 1  # a row without an instant/event_name is dropped, never invented
            continue
        if key in existing:
            continue
        existing.add(key)  # collapse duplicates across bundles + the seed too
        lines.append(line)
    if lines:
        adapter.execute(
            f"INSERT INTO {adapter.business_events_table} FORMAT JSONEachRow",
            data=b"\n".join(lines),
        )
    return len(rows), len(lines), skipped


def main() -> int:
    adapter = ClickHouseAdapter(timeout_s=10.0)
    try:
        total, inserted, skipped = backfill_business_events(adapter)
    except SpineUnavailableError as exc:
        print(f"business-event backfill skipped (clickhouse unreachable): {exc}", file=sys.stderr)
        return 1
    print(
        f"business_events: {total} source rows → {inserted} inserted "
        f"({skipped} skipped, rest present)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
