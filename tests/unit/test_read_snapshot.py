"""The leader-computed shared read-snapshot (ADR 0046).

Pins the cache's contract: a fresh entry is served, a stale/missing/absent one is a MISS (the
caller then computes — the fallback that makes the snapshot purely additive), the reset hook clears
it (test isolation), and the leader's entry composition is best-effort (a failing compute omits
only its own entry). The file lives in the shared state dir; conftest resets it between tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tessera.api.routes.observability.schemas_fleet import FleetUnavailable
from tessera.observability import read_snapshot as rs

if TYPE_CHECKING:
    import pytest


def test_write_then_read_within_ttl_returns_the_payload() -> None:
    rs.reset_read_snapshot()
    payload = {"badges": {}, "notifications": {"count": 0, "items": []}}
    rs.write_snapshot({"chrome:fr": payload})
    assert rs.read_snapshot("chrome:fr", rs.SNAPSHOT_TTL_S) == payload


def test_a_zero_ttl_is_always_stale() -> None:
    rs.reset_read_snapshot()
    rs.write_snapshot({"chrome:fr": {"x": 1}})
    assert rs.read_snapshot("chrome:fr", 0.0) is None


def test_a_missing_key_is_a_miss() -> None:
    rs.reset_read_snapshot()
    rs.write_snapshot({"chrome:fr": {"x": 1}})
    assert rs.read_snapshot("chrome:de", rs.SNAPSHOT_TTL_S) is None


def test_an_absent_file_is_a_miss() -> None:
    rs.reset_read_snapshot()
    assert rs.read_snapshot("chrome:fr", rs.SNAPSHOT_TTL_S) is None


def test_reset_removes_the_file() -> None:
    rs.write_snapshot({"k": {"x": 1}})
    rs.reset_read_snapshot()
    assert rs.read_snapshot("k", rs.SNAPSHOT_TTL_S) is None


def test_snapshot_keys() -> None:
    assert rs.chrome_snapshot_key("fr") == "chrome:fr"
    assert rs.fleet_snapshot_key("fr", "d7") == "fleet:fr:d7"
    assert rs.fleet_snapshot_key("fr", None) == "fleet:fr:all"
    assert rs.batch_snapshot_key("fr") == "batch:fr"
    assert rs.inbox_snapshot_key("fr", "all") == "inbox:fr:all"
    assert rs.incidents_snapshot_key("fr") == "incidents:fr"


def _stub_all_computes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub every hot-read compute so compute_snapshot_entries is hermetic (no DB)."""

    async def _fake_fleet(lang: str, period: str | None, at: str | None) -> FleetUnavailable:
        return FleetUnavailable(available=False)

    async def _fake_panels(_lang: str) -> dict[str, object]:
        return {"ai-act": {"x": 1}, "refusal": {"y": 2}}

    monkeypatch.setattr(
        "tessera.observability.chrome._compute_chrome_uncached", lambda lang: {"lang": lang}
    )
    monkeypatch.setattr("tessera.api.routes.observability.fleet._compute_fleet", _fake_fleet)
    monkeypatch.setattr("tessera.api.routes.observability.batch.compute_all_panels", _fake_panels)
    monkeypatch.setattr(
        "tessera.observability.inbox.compute_inbox_overview", lambda **_kw: {"queue": 3}
    )
    monkeypatch.setattr(
        "tessera.observability.incidents.compute_incidents_overview",
        lambda lang, at: {"posture": lang, "at": at},
    )
    monkeypatch.setattr(
        "tessera.api.routes.audit.compute_default_overview", lambda: {"total_events": 12}
    )
    monkeypatch.setattr(
        "tessera.api.routes.audit.compute_default_page", lambda: {"entries": [], "cursor": 0}
    )


async def test_compute_entries_composes_every_hot_read(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_all_computes(monkeypatch)
    entries = await rs.compute_snapshot_entries()
    assert entries["chrome:fr"] == {"lang": "fr"}
    assert entries["chrome:de"] == {"lang": "de"}
    assert entries["chrome:en"] == {"lang": "en"}
    assert entries["fleet:fr:all"] == {"available": False}
    assert entries["fleet:fr:d7"] == {"available": False}
    assert entries["batch:fr"] == {"ai-act": {"x": 1}, "refusal": {"y": 2}}
    assert entries["inbox:fr:all"] == {"available": True, "agent": "all", "queue": 3}
    assert entries["incidents:fr"] == {"available": True, "posture": "fr", "at": None}
    assert entries["incidents:de"] == {"available": True, "posture": "de", "at": None}
    assert entries["incidents:en"] == {"available": True, "posture": "en", "at": None}
    assert entries["audit:overview"] == {"total_events": 12}
    assert entries["audit:page"] == {"entries": [], "cursor": 0}


async def test_compute_entries_omits_a_failing_compute(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_all_computes(monkeypatch)

    def _boom(lang: str) -> dict[str, object]:
        raise RuntimeError("postgres down")

    monkeypatch.setattr("tessera.observability.chrome._compute_chrome_uncached", _boom)
    entries = await rs.compute_snapshot_entries()
    assert not any(k.startswith("chrome:") for k in entries)  # every chrome entry omitted
    assert entries["fleet:fr:all"] == {"available": False}  # the others still published
    assert entries["batch:fr"] == {"ai-act": {"x": 1}, "refusal": {"y": 2}}
    assert entries["inbox:fr:all"] == {"available": True, "agent": "all", "queue": 3}


class _RecordingLogger:
    """Captures ``warning(event, **fields)`` calls so a test can assert what was logged."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def warning(self, event: str, **fields: object) -> None:
        self.calls.append((event, fields))


async def test_an_omitted_entry_names_its_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A compute that raises is not a silent hole: it logs ``entry_omitted`` with key + error."""
    _stub_all_computes(monkeypatch)
    recorder = _RecordingLogger()
    monkeypatch.setattr(rs, "_LOG", recorder)

    def _boom(lang: str) -> dict[str, object]:
        raise RuntimeError("postgres down")

    monkeypatch.setattr("tessera.observability.chrome._compute_chrome_uncached", _boom)
    await rs.compute_snapshot_entries()
    omitted = {
        fields["entry"]
        for event, fields in recorder.calls
        if event == "read_snapshot.entry_omitted"
    }
    assert omitted == {"chrome:fr", "chrome:de", "chrome:en"}
    assert all(
        "postgres down" in str(fields["error"])
        for event, fields in recorder.calls
        if event == "read_snapshot.entry_omitted"
    )
