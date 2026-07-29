"""The postgres audit read caches its VALIDATED entries on the chain head (``max(seq)``).

Mapping ~126 k payloads into ``AuditEntry`` is ~2 s, and both the audit overview (polled every 15 s)
and the default log page paid it on every request. The append-only head is a complete cache key — an
unchanged head proves every row is byte-identical — so the validation now happens once per append.
A windowed read is already bounded IN SQL and deliberately stays uncached here.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from tessera.api.routes import audit

if TYPE_CHECKING:
    import pytest


def _install(
    monkeypatch: pytest.MonkeyPatch,
    head: list[int],
    calls: list[tuple[object, object]],
) -> None:
    """Drive the postgres branch with a controllable head and a validation-call counter."""
    monkeypatch.setattr(audit, "ledger_source", lambda: "postgres")
    monkeypatch.setattr(audit, "ledger_head_seq", lambda: head[0])

    def _uncached(_path: object, *, since: object = None, until: object = None) -> list[object]:
        calls.append((since, until))
        return []

    monkeypatch.setattr(audit, "_read_entries_uncached", _uncached)


def test_full_read_is_cached_on_the_head(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two full reads at the same head validate ONCE — the second is served from the memo."""
    audit.reset_audit_entries_cache()
    head, calls = [7], []
    _install(monkeypatch, head, calls)
    audit._read_entries(audit._resolve_audit_path())
    audit._read_entries(audit._resolve_audit_path())
    assert len(calls) == 1


def test_a_new_head_revalidates(monkeypatch: pytest.MonkeyPatch) -> None:
    """A row landing (head moves) invalidates the memo — the next read re-validates."""
    audit.reset_audit_entries_cache()
    head, calls = [7], []
    _install(monkeypatch, head, calls)
    audit._read_entries(audit._resolve_audit_path())
    head[0] = 8
    audit._read_entries(audit._resolve_audit_path())
    assert len(calls) == 2


def test_a_windowed_read_bypasses_the_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """A windowed read is bounded in SQL and never touches the full-read memo (read or write)."""
    audit.reset_audit_entries_cache()
    head, calls = [7], []
    _install(monkeypatch, head, calls)
    since = datetime(2026, 7, 1, tzinfo=UTC)
    audit._read_entries(audit._resolve_audit_path(), since=since)
    audit._read_entries(audit._resolve_audit_path(), since=since)
    assert len(calls) == 2
    assert all(call[0] == since for call in calls)


def test_reset_drops_the_memo(monkeypatch: pytest.MonkeyPatch) -> None:
    """The reset hook (conftest isolation) forces the next full read to re-validate."""
    audit.reset_audit_entries_cache()
    head, calls = [7], []
    _install(monkeypatch, head, calls)
    audit._read_entries(audit._resolve_audit_path())
    audit.reset_audit_entries_cache()
    audit._read_entries(audit._resolve_audit_path())
    assert len(calls) == 2
