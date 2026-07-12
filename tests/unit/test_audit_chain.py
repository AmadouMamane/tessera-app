"""Unit tests for the tamper-evident audit hash chain (ADR 0010, #3)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from tessera.guard import audit
from tessera.settings import get_settings

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def audit_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the file sink at a temp file and reset the chain state."""
    path = tmp_path / "audit.log"
    settings = get_settings()
    monkeypatch.setattr(settings.guard, "audit_file", path)
    monkeypatch.setattr(audit, "_last_hash", None)
    return path


def _emit(n: int) -> None:
    for i in range(n):
        audit.emit_audit(
            target=f"tool_{i}",
            arguments={"i": i},
            decisions=[],
            sink="file",
            outcome="allowed",
            actor=audit.GUARD_ACTOR,
        )


def test_chain_verifies_when_intact(audit_file: Path) -> None:
    _emit(3)
    status = audit.verify_audit_chain(audit_file)
    assert status.verified is True
    assert status.length == 3
    assert status.broken_at is None


def test_each_entry_carries_prev_and_own_hash(audit_file: Path) -> None:
    _emit(2)
    lines = [json.loads(line) for line in audit_file.read_text().splitlines() if line.strip()]
    assert lines[0]["prev_hash"] == "0" * 64  # genesis
    assert lines[1]["prev_hash"] == lines[0]["hash"]  # linkage
    assert all(len(line["hash"]) == 64 for line in lines)
    assert lines[0]["data_residency"] == "eu"


def test_chain_detects_tampering(audit_file: Path) -> None:
    _emit(3)
    lines = audit_file.read_text().splitlines()
    # Tamper with the second entry's content without fixing its hash.
    obj = json.loads(lines[1])
    obj["outcome"] = "denied"
    lines[1] = json.dumps(obj, ensure_ascii=False)
    audit_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    status = audit.verify_audit_chain(audit_file)
    assert status.verified is False
    assert status.broken_at == 1


def test_chain_detects_deletion(audit_file: Path) -> None:
    _emit(3)
    lines = audit_file.read_text().splitlines()
    del lines[1]  # remove the middle entry → breaks linkage at the new index 1
    audit_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    status = audit.verify_audit_chain(audit_file)
    assert status.verified is False
    assert status.broken_at == 1


def test_empty_log_is_trivially_verified(tmp_path: Path) -> None:
    status = audit.verify_audit_chain(tmp_path / "does_not_exist.log")
    assert status.verified is True
    assert status.length == 0
