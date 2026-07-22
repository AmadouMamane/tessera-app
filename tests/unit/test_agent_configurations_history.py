"""OT-01 witnesses — the Configurations per-object history bounded at T.

``_build_history`` composes the durable form-save log (scoped per agent) with
the config-file provenance events (real mtimes). The as-of bound must drop
every event after T — including an mtime row whose update instant is later
than T (that update has not happened yet at T).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from tessera.observability import agent_configurations as cfg
from tessera.settings import get_settings

if TYPE_CHECKING:
    import pytest


def _log_entries() -> list[dict[str, object]]:
    return [
        {"at": "2026-06-01T10:00:00+00:00", "agent_id": "support-client", "keys": ["name"]},
        {"at": "2026-06-15T10:00:00+00:00", "agent_id": "support-client", "keys": ["model"]},
    ]


def test_the_history_at_t_drops_later_events(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cfg, "_load_change_log", _log_entries)
    policy_path = get_settings().guard.policy_path

    live = cfg._build_history(policy_path, "fr", "support-client")
    assert len(live) >= 2  # both saves, plus real file-provenance rows

    at_t = cfg._build_history(
        policy_path, "fr", "support-client", until=datetime(2026, 6, 10, tzinfo=UTC)
    )
    # Only the 01/06 save exists at T: the 15/06 save is later, and every
    # provenance mtime (today) is later still.
    assert [row["time"] for row in at_t] == ["01/06/2026 10:00"]


def test_a_live_read_keeps_the_provenance_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cfg, "_load_change_log", _log_entries)
    policy_path = get_settings().guard.policy_path
    live = cfg._build_history(policy_path, "fr", "support-client")
    actors = {row["actor"] for row in live}
    assert len(actors) >= 2  # Console (saves) AND Dépôt (file provenance)


def test_parse_at_is_tolerant() -> None:
    assert cfg._parse_at(None) is None
    assert cfg._parse_at("not-a-date") is None
    parsed = cfg._parse_at("2026-06-15T12:00:00Z")
    assert parsed == datetime(2026, 6, 15, 12, 0, tzinfo=UTC)
