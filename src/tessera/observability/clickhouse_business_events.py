"""Direct-insert write path for business events (ADR 0017 §5 / Phase D).

Every business event fans out to its ADR 0016 sinks (OTel, Prometheus, the audit ledger
when opposable, the in-process read model) and, since Phase D, **also** dual-writes one row
to the **owned** ClickHouse table ``tessera.business_events`` by **direct insert** — the
durable, traffic-driven read model the multi-agent cockpit needs (the volatile
``InMemoryBusinessEventStore`` is bounded and lost on restart). The opposable facet still
lives in the Postgres ledger; ClickHouse is never a home for a fact that gates or proves.

Safety mirrors ``clickhouse_scores``: strictly best-effort and non-blocking. The insert
runs on its own short-lived daemon thread so a slow/down ClickHouse never stalls a turn; a
failure is logged and skipped — the in-process store + the replay bundles remain the read
substrate until the read flip bakes, and a dropped insert surfaces as shadow divergence,
never as a silently wrong number. Set ``TESSERA_CLICKHOUSE_BUSINESS_EVENTS=0`` to disable
(the unit suite does, staying hermetic).
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

__all__ = ["business_event_line", "business_event_row_key", "record_business_event_row"]

# String columns of the §5 table, filled from the ``to_row`` dict; a missing/None value
# becomes ``""`` (the "unattributed" marker, mapped back to None at read). Pre-stamp
# business events without ``capability_id`` keep that honest-empty marker.
_STRING_COLUMNS = (
    "agent_id",
    "workflow_id",
    "capability_id",
    "node_name",
    "conversation_id",
    "turn_id",
    "case_id",
    "artifact_id",
    "artifact_type",
    "artifact_status",
    "decision",
    "actor",
    "surface",
    "language",
    "model",
    "environment",
    "schema_version",
    "grammar_version",
)

_adapter_lock = threading.Lock()
_adapter: ClickHouseAdapter | None = None
_schema_ensured = False


def _enabled() -> bool:
    """Whether the direct insert is on. Defaults on; ``0``/``false``/``no``/``off`` disable."""
    return os.environ.get("TESSERA_CLICKHOUSE_BUSINESS_EVENTS", "1").lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _clickhouse_datetime(value: object) -> str | None:
    """Normalise an ISO ``timestamp`` to ClickHouse's ``DateTime64(3)`` literal (UTC).

    Returns ``None`` when missing/unparsable — the row is then skipped (a telemetry row
    without its instant is dropped, never given a fabricated one).
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


def business_event_line(row: Mapping[str, object]) -> bytes | None:
    """One ``BusinessEvent.to_row`` dict → one ``JSONEachRow`` line for the owned table (pure).

    Dimension ``None``s become ``""``; ``reason_codes`` becomes a JSON array; ``payload``
    becomes a JSON string (the ``String`` column — strict-schema, PII-free by construction,
    §2); ``synthetic`` becomes ``UInt8`` (ADR 0019 §4). Returns ``None`` for a row with no
    parsable ``timestamp`` or ``event_name`` — skipped, never fabricated.
    """
    occurred_at = _clickhouse_datetime(row.get("timestamp"))
    event_name = row.get("event_name")
    if occurred_at is None or not isinstance(event_name, str) or not event_name:
        return None
    reason_codes = row.get("reason_codes")
    payload = row.get("payload")
    raw_version = row.get("event_version", row.get("version"))
    line: dict[str, object] = {
        "occurred_at": occurred_at,
        "event_name": event_name,
        "reason_codes": [str(code) for code in reason_codes]
        if isinstance(reason_codes, list)
        else [],
        "payload": json.dumps(payload, ensure_ascii=False) if isinstance(payload, dict) else "",
        "event_version": int(raw_version) if isinstance(raw_version, int) else 1,
        # ADR 0019 §4 — the canary/test mark must cross the medium. Dropping it here is what
        # made a synthetic row read back as a real one once `business_events` flipped to spine.
        "synthetic": 1 if row.get("synthetic") else 0,
    }
    for column in _STRING_COLUMNS:
        value = row.get(column)
        line[column] = value if isinstance(value, str) else ""
    if not line["actor"]:
        line["actor"] = "system"
    return json.dumps(line, ensure_ascii=False).encode("utf-8")


def business_event_row_key(row: Mapping[str, object]) -> tuple[str, str, str, str, str, str] | None:
    """A row's identity at the owned store's precision — the backfill's dedup key (pure).

    ``(occurred_at@ms, agent_id, event_name, conversation_id, turn_id, artifact_id)``:
    what both the ``to_row`` dict and the stored ClickHouse row compute identically (the
    store keeps millisecond stamps), so the idempotent backfill inserts exactly the
    difference — twice-run = zero new rows.
    """
    occurred_at = _clickhouse_datetime(row.get("timestamp"))
    event_name = row.get("event_name")
    if occurred_at is None or not isinstance(event_name, str):
        return None

    def _s(key: str) -> str:
        value = row.get(key)
        return value if isinstance(value, str) else ""

    return (
        occurred_at,
        _s("agent_id"),
        event_name,
        _s("conversation_id"),
        _s("turn_id"),
        _s("artifact_id"),
    )


def _get_adapter() -> ClickHouseAdapter:
    """The process-wide adapter, business-event schema ensured once (lazy — boot deferred it).

    The adapter import is deferred to avoid the ``observability`` ↔ spine-adapters cycle.
    """
    from tessera.observability.spine.adapters.clickhouse import ClickHouseAdapter

    global _adapter, _schema_ensured
    with _adapter_lock:
        if _adapter is None:
            _adapter = ClickHouseAdapter()
        if not _schema_ensured:
            _adapter.ensure_business_events_schema()
            _schema_ensured = True
        return _adapter


def _insert(line: bytes) -> None:
    from tessera.observability.spine.adapters.base import SpineUnavailableError

    try:
        adapter = _get_adapter()
        adapter.execute(
            f"INSERT INTO {adapter.business_events_table} FORMAT JSONEachRow", data=line
        )
    except SpineUnavailableError as exc:
        # Best-effort: the in-process store + replay bundles stay the read substrate until
        # the flip bakes; a lagging store surfaces as shadow divergence, never a silent gap.
        sys.stderr.write(f"tessera.clickhouse_business_events: insert skipped: {exc}\n")


def record_business_event_row(row: Mapping[str, object]) -> None:
    """Insert one business-event row into the owned store (best-effort, non-blocking)."""
    if not _enabled():
        return
    line = business_event_line(row)
    if line is None:
        sys.stderr.write(
            "tessera.clickhouse_business_events: row without instant/event_name skipped\n"
        )
        return
    threading.Thread(target=_insert, args=(line,), daemon=True).start()
