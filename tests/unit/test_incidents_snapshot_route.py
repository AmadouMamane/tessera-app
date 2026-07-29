"""The incidents route serves its DEFAULT live view from the shared snapshot (ADR 0046).

Clustering the deny ledger is seconds cold and ~180 ms even warm, and the per-worker memo expires
between page visits — so the leader publishes the whole payload and the route reads the file. Only
the default (``at=None``) is served from the snapshot; an as-of-T read, or a snapshot miss, computes
fresh. This pins that branch: a present entry is returned verbatim with ZERO compute, a miss and an
as-of-T read both fall through to compute.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tessera.api.routes.observability import safety
from tessera.observability import read_snapshot as rs

if TYPE_CHECKING:
    import pytest


def _count_computes(monkeypatch: pytest.MonkeyPatch, calls: list[tuple[str, object]]) -> None:
    """Replace the real clustering with a call-counting stub returning a marker payload."""

    def _fake(lang: str, at: object) -> dict[str, object]:
        calls.append((lang, at))
        return {"posture": "computed", "lang": lang}

    monkeypatch.setattr(safety.incidents_mod, "compute_incidents_overview", _fake)


def test_default_view_served_from_snapshot_without_computing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rs.reset_read_snapshot()
    calls: list[tuple[str, object]] = []
    _count_computes(monkeypatch, calls)
    rs.write_snapshot(
        {rs.incidents_snapshot_key("fr"): {"available": True, "posture": "from-snapshot"}}
    )
    result = safety.observability_incidents(lang="fr", at=None)
    assert result == {"available": True, "posture": "from-snapshot"}
    assert calls == []  # the snapshot hit means the ledger was never clustered


def test_a_snapshot_miss_computes(monkeypatch: pytest.MonkeyPatch) -> None:
    rs.reset_read_snapshot()
    calls: list[tuple[str, object]] = []
    _count_computes(monkeypatch, calls)
    result = safety.observability_incidents(lang="fr", at=None)
    assert result == {"available": True, "posture": "computed", "lang": "fr"}
    assert calls == [("fr", None)]


def test_an_as_of_t_read_bypasses_the_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    rs.reset_read_snapshot()
    calls: list[tuple[str, object]] = []
    _count_computes(monkeypatch, calls)
    # A snapshot for the default view is present, but an as-of-T read must never serve it.
    rs.write_snapshot(
        {rs.incidents_snapshot_key("fr"): {"available": True, "posture": "from-snapshot"}}
    )
    result = safety.observability_incidents(lang="fr", at="2026-07-01T00:00:00Z")
    assert result == {"available": True, "posture": "computed", "lang": "fr"}
    assert calls == [("fr", "2026-07-01T00:00:00Z")]
