"""Manifest-generated quality nets — coverage (92) + canary (94) descriptors (ADR 0017 §4)."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import TYPE_CHECKING

from tessera.observability import quality_nets
from tessera.observability.semconv import DEPLOYMENT_ENVIRONMENT

if TYPE_CHECKING:
    import pytest

_FULL_ROW = {
    "timestamp": "2026-01-01T00:00:00+00:00",
    "agent_id": "recouvrement",
    "conversation_id": "c1",
    "turn_id": "t1",
    "language": "fr",
    "environment": "local",
}


def _rows(monkeypatch: pytest.MonkeyPatch, rows: list[dict[str, object]]) -> None:
    monkeypatch.setattr(quality_nets.business_events, "business_event_rows", lambda **_kw: rows)


def _bundles(monkeypatch: pytest.MonkeyPatch, captured: list[str]) -> None:
    monkeypatch.setattr(
        quality_nets.replay,
        "persisted_bundles",
        lambda **_kw: [SimpleNamespace(captured_at=at) for at in captured],
    )


# --------------------------------------------------------------------------- #
# Coverage (signal 92)
# --------------------------------------------------------------------------- #


def test_coverage_none_for_unmanifested_agent() -> None:
    assert quality_nets.coverage_descriptor("support-client") is None


def test_coverage_honest_empty_without_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    _rows(monkeypatch, [])
    desc = quality_nets.coverage_descriptor("recouvrement")
    assert desc is not None
    assert desc["status"] == "no_evidence"
    assert desc["covered_pct"] is None
    assert desc["missing_attributes"] == desc["required_attributes"]


def test_coverage_full_is_100(monkeypatch: pytest.MonkeyPatch) -> None:
    _rows(monkeypatch, [dict(_FULL_ROW)])
    desc = quality_nets.coverage_descriptor("recouvrement")
    assert desc is not None
    assert desc["covered_pct"] == 100.0
    assert desc["missing_attributes"] == []
    assert desc["status"] == "measured"


def test_coverage_names_its_source_not_spans(monkeypatch: pytest.MonkeyPatch) -> None:
    """The descriptor must name business events as its source, never claim span coverage.

    Operator ruling 2026-07-08 (Point 1): the Scope-dim proxy is accepted as the honestly
    available evidence *provided the label says its source* — so the payload carries the
    source explicitly and no consumer can present it as span coverage.
    """
    for rows in ([], [dict(_FULL_ROW)]):  # honest-empty AND measured branches
        _rows(monkeypatch, rows)
        desc = quality_nets.coverage_descriptor("recouvrement")
        assert desc is not None
        assert desc["evidence_source"] == "business_events"
        assert desc["measures"] == "scope_dimensions"


def test_coverage_flags_missing_dimension(monkeypatch: pytest.MonkeyPatch) -> None:
    _rows(monkeypatch, [{**_FULL_ROW, "environment": ""}])  # environment unstamped
    desc = quality_nets.coverage_descriptor("recouvrement")
    assert desc is not None
    assert desc["covered_pct"] == 80.0
    assert desc["missing_attributes"] == [DEPLOYMENT_ENVIRONMENT]


def test_coverage_measures_the_latest_event(monkeypatch: pytest.MonkeyPatch) -> None:
    older = {**_FULL_ROW, "timestamp": "2025-01-01T00:00:00+00:00", "environment": ""}
    _rows(monkeypatch, [older, dict(_FULL_ROW)])  # newest is fully stamped
    desc = quality_nets.coverage_descriptor("recouvrement")
    assert desc is not None
    assert desc["covered_pct"] == 100.0


# --------------------------------------------------------------------------- #
# Canary (signal 94)
# --------------------------------------------------------------------------- #

_NOW = datetime(2026, 1, 2, 0, 0, 0, tzinfo=UTC)


def test_canary_none_for_unmanifested_agent() -> None:
    assert quality_nets.canary_descriptor("support-client") is None


def test_canary_targets_from_manifest_never_seen(monkeypatch: pytest.MonkeyPatch) -> None:
    _bundles(monkeypatch, [])
    desc = quality_nets.canary_descriptor("recouvrement", now=_NOW)
    assert desc is not None
    assert desc["targets"]  # recouvrement declares a workflow
    assert desc["status"] == "never"
    assert desc["age_seconds"] is None


def test_canary_fresh_when_recent(monkeypatch: pytest.MonkeyPatch) -> None:
    _bundles(monkeypatch, ["2026-01-01T12:00:00+00:00"])  # 12h before _NOW
    desc = quality_nets.canary_descriptor("recouvrement", now=_NOW)
    assert desc is not None
    assert desc["status"] == "fresh"
    assert desc["last_seen_at"] == "2026-01-01T12:00:00+00:00"


def test_canary_stale_when_old(monkeypatch: pytest.MonkeyPatch) -> None:
    _bundles(monkeypatch, ["2025-12-01T00:00:00+00:00"])  # weeks before _NOW
    desc = quality_nets.canary_descriptor("recouvrement", now=_NOW)
    assert desc is not None
    assert desc["status"] == "stale"


def test_canary_uses_the_latest_bundle(monkeypatch: pytest.MonkeyPatch) -> None:
    _bundles(monkeypatch, ["2025-12-01T00:00:00+00:00", "2026-01-01T18:00:00+00:00"])
    desc = quality_nets.canary_descriptor("recouvrement", now=_NOW)
    assert desc is not None
    assert desc["last_seen_at"] == "2026-01-01T18:00:00+00:00"
    assert desc["status"] == "fresh"
