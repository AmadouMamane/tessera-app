"""Direct-insert write path for ONLINE monitoring scores (ADR 0015 §Correction 2b).

Every online-eval verdict lands as one row in the **owned** ClickHouse table
``tessera.eval_online_scores`` by **direct insert** — never via Langfuse's public Scores
ingestion (proven fragile 2026-07-02: 201-accepted, never materialised). Langfuse keeps
**no score object** for online rows: the turn's *trace* already lives in Langfuse/Phoenix
and the row carries ``trace_id``, so drill-down follows the id — mirroring the score would
duplicate a fact the spine no longer reads from Langfuse (§Amendment 1).

Safety: strictly best-effort and non-blocking. The caller (``emit_score``) already runs
off the hot path (ADR 0010 ``_spawn_background``); the insert still runs on its own
short-lived daemon thread so a slow ClickHouse never stalls even the cold path. A down
ClickHouse is logged and skipped — the jsonl event log remains the system of record until
the G4 parity flip, and a dropped insert surfaces as shadow divergence there, never as a
silently wrong number. Set ``TESSERA_CLICKHOUSE_SCORES=0`` to disable (the unit suite
does, staying hermetic).
"""

from __future__ import annotations

import json
import os
import sys
import threading
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from tessera.observability.spine.adapters.clickhouse import ClickHouseAdapter

__all__ = ["online_score_line", "record_online_score"]

_STRING_COLUMNS = ("agent_id", "language", "model", "conversation_id", "trace_id", "judge_model")

_adapter_lock = threading.Lock()
_adapter: ClickHouseAdapter | None = None
_schema_ensured = False


def _enabled() -> bool:
    """Whether the direct insert is on. Defaults on; ``0``/``false``/``no``/``off`` disable."""
    return os.environ.get("TESSERA_CLICKHOUSE_SCORES", "1").lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _clickhouse_datetime(value: object) -> str | None:
    """Normalise an ISO ``scored_at`` to ClickHouse's ``DateTime64(3)`` literal (UTC).

    Returns ``None`` when the value is missing or unparsable — the row is then skipped
    (a telemetry row without its instant is dropped, never given a fabricated one).
    """
    if not isinstance(value, str) or not value:
        return None
    try:
        stamp = datetime.fromisoformat(value)
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    utc = stamp.astimezone(UTC)
    return utc.strftime("%Y-%m-%d %H:%M:%S.") + f"{utc.microsecond // 1000:03d}"


def online_score_line(row: Mapping[str, object]) -> bytes | None:
    """One jsonl score row → one ``JSONEachRow`` line for the owned table (pure).

    Dimension ``None``s become ``""`` (the table's "unattributed" marker, mapped back to
    ``None`` at read); ``sampled`` becomes 0/1 per the §Correction 2b DDL. Returns ``None``
    for a row with no parsable ``scored_at`` or ``score`` — skipped, never fabricated.
    """
    scored_at = _clickhouse_datetime(row.get("scored_at"))
    metric = row.get("metric")
    score = row.get("score")
    if scored_at is None or not isinstance(metric, str) or not isinstance(score, int | float):
        return None
    payload: dict[str, object] = {
        "scored_at": scored_at,
        "metric": metric,
        "score": float(score),
        "sampled": 1 if row.get("sampled") else 0,
    }
    for column in _STRING_COLUMNS:
        value = row.get(column)
        payload[column] = value if isinstance(value, str) else ""
    return json.dumps(payload).encode("utf-8")


def _get_adapter() -> ClickHouseAdapter:
    """The process-wide adapter, schema ensured once (lazy — boot may have deferred it).

    The adapter import is deferred too: ``eval.scores`` imports this module, and the
    spine adapters package imports ``eval.scores`` back (the jsonl reader) — a module-
    level import here would be that cycle.
    """
    from tessera.observability.spine.adapters.clickhouse import ClickHouseAdapter

    global _adapter, _schema_ensured
    with _adapter_lock:
        if _adapter is None:
            _adapter = ClickHouseAdapter()
        if not _schema_ensured:
            _adapter.ensure_schema()
            _schema_ensured = True
        return _adapter


def _insert(line: bytes) -> None:
    from tessera.observability.spine.adapters.base import SpineUnavailableError

    try:
        adapter = _get_adapter()
        adapter.execute(f"INSERT INTO {adapter.table} FORMAT JSONEachRow", data=line)
    except SpineUnavailableError as exc:
        # Best-effort: jsonl stays the system of record until the G4 parity flip; the
        # shadow-divergence gate is what catches a lagging store — never a silent number.
        sys.stderr.write(f"tessera.clickhouse_scores: insert skipped: {exc}\n")


def record_online_score(row: Mapping[str, object]) -> None:
    """Insert one online score row into the owned store (best-effort, non-blocking)."""
    if not _enabled():
        return
    line = online_score_line(row)
    if line is None:
        sys.stderr.write("tessera.clickhouse_scores: row without instant/metric skipped\n")
        return
    threading.Thread(target=_insert, args=(line,), daemon=True).start()
