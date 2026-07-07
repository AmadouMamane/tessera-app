"""Hermetic in-memory ``audit_ledger`` simulator for the drain (TESS-LEDGER-001).

Not collected (``python_files = ["test_*.py"]``). Simulates just enough of the Postgres
surface the drain touches — ``pg_advisory_xact_lock`` (no-op), the event_id dedup SELECT, the
``ORDER BY seq DESC`` head read, and the INSERT — so ``drain_spool`` can be exercised
end-to-end without a database. One instance persists across drain calls, so re-drain
idempotence and cross-outage replay are testable. Returned to ``_connect_sync`` by
monkeypatch; used as a context manager exactly like the real sync connection.
"""

from __future__ import annotations

from typing import Any


class _Result:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self._rows = rows

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._rows[0] if self._rows else None

    def fetchall(self) -> list[tuple[Any, ...]]:
        return list(self._rows)


class FakeLedgerConn:
    """An append-only ledger table living in a list; the drain drives it verbatim."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        # Each row: {"seq", "payload"(dict), "prev_hash", "hash"}.
        self.rows: list[dict[str, Any]] = rows or []
        self._seq = max((r["seq"] for r in self.rows), default=0)

    def __enter__(self) -> FakeLedgerConn:
        return self

    def __exit__(self, *_: object) -> bool:
        return False

    def execute(self, sql: str, params: tuple[Any, ...] | None = None) -> _Result:
        s = " ".join(sql.split()).lower()
        if "pg_advisory_xact_lock" in s:
            return _Result([])
        if "payload->>'event_id' = any" in s:
            wanted = set((params or ([],))[0])
            hits = [
                (r["payload"].get("event_id"),)
                for r in self.rows
                if r["payload"].get("event_id") in wanted
            ]
            return _Result(hits)
        if "order by seq desc limit 1" in s:
            if not self.rows:
                return _Result([])
            tail = max(self.rows, key=lambda r: r["seq"])
            return _Result([(tail["hash"],)])
        if s.startswith("insert into"):
            assert params is not None
            _occurred_at, _agent_id, payload_json, prev_hash, hsh = params
            payload = getattr(payload_json, "obj", payload_json)
            self._seq += 1
            self.rows.append(
                {
                    "seq": self._seq,
                    "payload": dict(payload),
                    "prev_hash": prev_hash,
                    "hash": hsh,
                }
            )
            return _Result([])
        return _Result([])

    def commit(self) -> None:
        pass

    # Convenience for assertions: the landed payloads in seq order.
    def payloads(self) -> list[dict[str, Any]]:
        return [r["payload"] for r in sorted(self.rows, key=lambda r: r["seq"])]
