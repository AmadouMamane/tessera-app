"""The ledger read seam (ADR 0015 H2, step 1): every direct consumer routes here.

Hermetic — postgres mode is simulated by monkeypatching the source switch and the table
read, so no real Postgres is needed. Proves the seam is byte-identical to a raw file parse
in ``file`` mode (the default, so the whole reader sweep is a behaviour-preserving refactor)
and reads the promoted table (ignoring the file ``path``) in ``postgres`` mode — the cut.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from tessera.guard import ledger_store
from tessera.guard.audit import _hash_core
from tessera.guard.ledger_store import (
    ledger_available,
    read_ledger_entries,
    verify_active_ledger,
)

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

_GENESIS = "0" * 64


def _write_chain(path: Path, entries: list[dict[str, object]]) -> None:
    """Write a valid hash chain of ``entries`` to ``path`` (JSON-Lines)."""
    prev = _GENESIS
    lines = []
    for entry in entries:
        linked = {**entry, "prev_hash": prev}
        linked["hash"] = _hash_core(linked)
        prev = str(linked["hash"])
        lines.append(json.dumps(linked, ensure_ascii=False))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _force_postgres(monkeypatch: pytest.MonkeyPatch, payloads: list[dict[str, object]]) -> None:
    """Simulate the cut: source=postgres, the table read returns ``payloads``."""
    monkeypatch.setattr(ledger_store, "ledger_source", lambda: "postgres")
    monkeypatch.setattr(ledger_store, "load_ledger_payloads_sync", lambda: list(payloads))


# ── file mode (the default — must be identical to a raw parse) ──────────────────


def test_read_entries_parses_explicit_file(tmp_path: Path) -> None:
    path = tmp_path / "audit.log"
    _write_chain(path, [{"type": "tessera.guard.audit", "n": 0}, {"type": "x", "n": 1}])
    entries = read_ledger_entries(path)
    assert [e["n"] for e in entries] == [0, 1]  # all types, oldest→newest (file order)
    assert entries[0]["type"] == "tessera.guard.audit"


def test_read_entries_missing_file_is_empty(tmp_path: Path) -> None:
    assert read_ledger_entries(tmp_path / "nope.log") == []


def test_read_entries_skips_malformed_lines(tmp_path: Path) -> None:
    path = tmp_path / "audit.log"
    path.write_text('{"type":"a","n":0}\nnot json\n\n{"type":"b","n":1}\n', encoding="utf-8")
    assert [e["n"] for e in read_ledger_entries(path)] == [0, 1]


def test_read_entries_defaults_to_settings_audit_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tessera.settings import get_settings

    path = tmp_path / "default.log"
    _write_chain(path, [{"type": "tessera.guard.audit", "n": 7}])
    monkeypatch.setattr(get_settings().guard, "audit_file", path)
    assert [e["n"] for e in read_ledger_entries()] == [7]


# ── postgres mode (the cut — reads the table, ignores the file path) ────────────


def test_read_entries_postgres_reads_table_ignoring_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A file exists with different content — the seam must NOT read it once cut.
    stale = tmp_path / "audit.log"
    _write_chain(stale, [{"type": "tessera.guard.audit", "n": 99}])
    _force_postgres(monkeypatch, [{"type": "tessera.guard.audit", "n": 1}, {"type": "y", "n": 2}])
    assert [e["n"] for e in read_ledger_entries(stale)] == [1, 2]


# ── verify_active_ledger: source-aware, path-preserving in file mode ────────────


def test_verify_active_ledger_file_mode_uses_path(tmp_path: Path) -> None:
    path = tmp_path / "audit.log"
    _write_chain(path, [{"type": "tessera.guard.audit", "n": 0}, {"type": "z", "n": 1}])
    status = verify_active_ledger(path)
    assert status.verified is True and status.length == 2


def test_verify_active_ledger_file_mode_detects_tamper(tmp_path: Path) -> None:
    path = tmp_path / "audit.log"
    _write_chain(path, [{"type": "a", "n": 0}, {"type": "b", "n": 1}])
    lines = path.read_text(encoding="utf-8").splitlines()
    tampered = json.loads(lines[1])
    tampered["n"] = 999  # edit without re-hashing → chain breaks
    lines[1] = json.dumps(tampered, ensure_ascii=False)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert verify_active_ledger(path).verified is False


def test_verify_active_ledger_postgres_walks_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Build a valid chain, hand it to the fake table read, verify the walk holds.
    path = tmp_path / "audit.log"
    _write_chain(path, [{"type": "a", "n": 0}, {"type": "b", "n": 1}, {"type": "c", "n": 2}])
    payloads = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    _force_postgres(monkeypatch, payloads)
    status = verify_active_ledger(tmp_path / "ignored.log")
    assert status.verified is True and status.length == 3


# ── ledger_available: source-aware health ───────────────────────────────────────


def test_ledger_available_file_mode(tmp_path: Path) -> None:
    path = tmp_path / "audit.log"
    assert ledger_available(path) is False
    path.write_text("", encoding="utf-8")
    assert ledger_available(path) is True


def test_ledger_available_postgres_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ledger_store, "ledger_source", lambda: "postgres")
    monkeypatch.setattr(ledger_store, "_ledger_reachable", lambda: True)
    assert ledger_available() is True
    monkeypatch.setattr(ledger_store, "_ledger_reachable", lambda: False)
    assert ledger_available() is False
