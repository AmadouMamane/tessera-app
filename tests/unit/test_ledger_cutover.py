"""Chain continuity across the file→table cut (ADR 0015 H2, step 3).

When the flat writer stops, a fresh process must resume the chain from the TABLE head, not
the (now absent) file — otherwise the first post-cut entry would link to genesis and fork
the walk. These prove the seed switches with the source and that ``verify`` passes THROUGH
the cut boundary (genesis → last pre-cut entry → first post-cut entry, unbroken). Hermetic:
the table head is monkeypatched, no Postgres needed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tessera.guard import audit, ledger_store
from tessera.guard.audit import _GENESIS_HASH, _hash_core, _seed_chain_head
from tessera.guard.ledger_store import verify_ledger_rows

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _linked(payload: dict[str, Any], prev: str) -> dict[str, Any]:
    entry = {"type": "tessera.guard.audit", **payload, "prev_hash": prev}
    entry["hash"] = _hash_core(entry)
    return entry


def _write_chain(path: Path, count: int) -> str:
    prev = _GENESIS_HASH
    lines = []
    import json

    for n in range(count):
        e = _linked({"occurred_at": f"2026-07-02T10:00:0{n}+00:00", "n": n}, prev)
        prev = str(e["hash"])
        lines.append(json.dumps(e, ensure_ascii=False))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return prev


# ── file mode (pre-cut, unchanged) ──────────────────────────────────────────────


def test_seed_file_mode_resumes_from_the_file(tmp_path: Path) -> None:
    path = tmp_path / "audit.log"
    last = _write_chain(path, 3)
    assert _seed_chain_head("file", path) == last  # the file's tail hash


def test_seed_file_mode_empty_is_genesis(tmp_path: Path) -> None:
    assert _seed_chain_head("file", tmp_path / "nope.log") == _GENESIS_HASH
    assert _seed_chain_head("stdout", tmp_path / "nope.log") == _GENESIS_HASH


# ── postgres mode (the cut) ─────────────────────────────────────────────────────


def test_seed_postgres_mode_resumes_from_the_table_head(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A file exists with a DIFFERENT tail — post-cut we must ignore it and use the table.
    _write_chain(tmp_path / "audit.log", 2)
    monkeypatch.setenv("TESSERA_LEDGER_SOURCE", "postgres")
    monkeypatch.setattr(ledger_store, "ledger_head_hash", lambda: "table-tail-hash")
    assert _seed_chain_head("file", tmp_path / "audit.log") == "table-tail-hash"


def test_seed_postgres_mode_empty_or_unreachable_falls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Table empty/unreachable → never silently start a new chain: fall back to the file.
    last = _write_chain(tmp_path / "audit.log", 2)
    monkeypatch.setenv("TESSERA_LEDGER_SOURCE", "postgres")
    monkeypatch.setattr(ledger_store, "ledger_head_hash", lambda: None)
    assert _seed_chain_head("file", tmp_path / "audit.log") == last


def test_chain_is_continuous_through_the_cut(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Two entries are "already in the table" (pre-cut).
    e0 = _linked({"occurred_at": "2026-07-02T10:00:00+00:00", "n": 0}, _GENESIS_HASH)
    e1 = _linked({"occurred_at": "2026-07-02T10:00:01+00:00", "n": 1}, str(e0["hash"]))

    # The cut: source=postgres, the table tail is e1; a FRESH process (_last_hash reset).
    monkeypatch.setenv("TESSERA_LEDGER_SOURCE", "postgres")
    monkeypatch.setattr(ledger_store, "ledger_head_hash", lambda: str(e1["hash"]))
    monkeypatch.setattr(audit, "_last_hash", None)

    # First post-cut audit — chained via the real emitter path (stdout sink, no file/PG).
    new: dict[str, Any] = {
        "type": "tessera.guard.audit",
        "occurred_at": "2026-07-02T10:00:02+00:00",
    }
    audit._append_to_chain(new, "stdout", tmp_path / "audit.log")

    assert new["prev_hash"] == e1["hash"]  # linked to the table tail, NOT genesis
    status = verify_ledger_rows([e0, e1, new])  # verify walks THROUGH the cut boundary
    assert status.verified is True and status.length == 3
