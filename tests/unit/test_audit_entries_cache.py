"""The postgres audit read caches its VALIDATED entries on the chain head (``max(seq)``).

Mapping ~126 k payloads into ``AuditEntry`` is ~2 s, and the audit overview (polled every 15 s), the
default log page AND the audit-log page's rolling 7-day window all paid it on every request. The
append-only head is a complete cache key — an unchanged head proves every row is byte-identical — so
the validation now happens once per append; a windowed read filters that head-cached chain in
Python (``AuditEntry.occurred_at`` derives from the same payload field the SQL window does).
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
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


def test_a_windowed_read_shares_the_head_cache_and_filters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A windowed read validates the chain ONCE (head-cached) and filters it in Python.

    The audit-log page's window is a rolling 7 days (until=now) that changes every load, so an
    SQL-bounded windowed read never hit a cache and re-validated ~126 k payloads each time. It now
    reuses the head-cached full chain and filters on occurred_at.
    """
    audit.reset_audit_entries_cache()
    head = [7]
    calls: list[tuple[object, object]] = []
    older = SimpleNamespace(occurred_at="2026-06-01T00:00:00+00:00")
    newer = SimpleNamespace(occurred_at="2026-07-15T00:00:00+00:00")
    monkeypatch.setattr(audit, "ledger_source", lambda: "postgres")
    monkeypatch.setattr(audit, "ledger_head_seq", lambda: head[0])

    def _uncached(_path: object, *, since: object = None, until: object = None) -> list[object]:
        calls.append((since, until))
        return [older, newer]

    monkeypatch.setattr(audit, "_read_entries_uncached", _uncached)
    since = datetime(2026, 7, 1, tzinfo=UTC)
    first = audit._read_entries(audit._resolve_audit_path(), since=since)
    second = audit._read_entries(audit._resolve_audit_path(), since=since)
    assert len(calls) == 1  # validated once, from the head cache — not a per-request SQL read
    assert calls[0] == (None, None)  # the FULL read, then filtered in Python
    assert first == [newer] == second  # only the in-window entry survives the filter


def test_reset_drops_the_memo(monkeypatch: pytest.MonkeyPatch) -> None:
    """The reset hook (conftest isolation) forces the next full read to re-validate."""
    audit.reset_audit_entries_cache()
    head, calls = [7], []
    _install(monkeypatch, head, calls)
    audit._read_entries(audit._resolve_audit_path())
    audit.reset_audit_entries_cache()
    audit._read_entries(audit._resolve_audit_path())
    assert len(calls) == 2


def _install_overview(monkeypatch: pytest.MonkeyPatch, head: list[int], builds: list[int]) -> None:
    """Drive _overview_cached with a controllable head and a build-call counter (postgres)."""
    monkeypatch.setattr(audit, "ledger_source", lambda: "postgres")
    monkeypatch.setattr(audit, "ledger_head_seq", lambda: head[0])
    monkeypatch.setattr(audit, "_read_entries", lambda *_a, **_k: [])
    monkeypatch.setattr(audit, "_audit_integrity", lambda *_a, **_k: object())

    def _build(*_a: object, **_k: object) -> object:
        builds.append(1)
        return SimpleNamespace(tag=len(builds))

    monkeypatch.setattr(audit, "_build_overview", _build)


def test_overview_is_cached_on_the_head(monkeypatch: pytest.MonkeyPatch) -> None:
    """The ~1 s aggregation runs ONCE per head — the 15 s poll + leader cycle reuse the memo."""
    audit.reset_audit_entries_cache()
    head, builds = [5], []
    _install_overview(monkeypatch, head, builds)
    path = audit._resolve_audit_path()
    first = audit._overview_cached(path)
    second = audit._overview_cached(path)
    assert len(builds) == 1 and first is second  # same head → built once, same object
    head[0] = 6
    third = audit._overview_cached(path)
    assert len(builds) == 2 and third is not first  # a row landed → rebuilt


def test_overview_keys_each_window_separately(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default vs windowed are distinct keys; a repeated window hits the memo."""
    audit.reset_audit_entries_cache()
    head, builds = [5], []
    _install_overview(monkeypatch, head, builds)
    path = audit._resolve_audit_path()
    since = datetime(2026, 7, 1, tzinfo=UTC)
    audit._overview_cached(path)  # default
    audit._overview_cached(path, since=since)  # windowed — a new key
    audit._overview_cached(path, since=since)  # windowed — hits
    assert len(builds) == 2


def test_overview_not_cached_in_file_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """File mode has no head to key on — it builds directly (the entries memo covers it)."""
    audit.reset_audit_entries_cache()
    head, builds = [5], []
    _install_overview(monkeypatch, head, builds)
    monkeypatch.setattr(audit, "ledger_source", lambda: "file")
    path = audit._resolve_audit_path()
    audit._overview_cached(path)
    audit._overview_cached(path)
    assert len(builds) == 2
