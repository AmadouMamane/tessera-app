"""Manifest-generated quality nets — coverage (92) + canary (94) descriptors (ADR 0017 §4)."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import TYPE_CHECKING

from tessera.observability import business_events, quality_nets
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


def _rows(
    monkeypatch: pytest.MonkeyPatch, rows: list[dict[str, object]], *, readable: bool = True
) -> None:
    """Stub the read seam that says WHETHER THE STORE ANSWERED, not the flattening one.

    The descriptor used to call ``business_event_rows``, whose own docstring forbids exactly
    that — *"wrong for anything that derives a coverage claim from the absence"*. Stubbing the
    same seam the code reads is what makes ``readable=False`` testable at all.
    """
    monkeypatch.setattr(
        quality_nets.business_events,
        "business_event_read",
        lambda **_kw: business_events.BusinessEventRead(rows=rows, readable=readable),
    )


def _bundles(monkeypatch: pytest.MonkeyPatch, captured: list[str]) -> None:
    monkeypatch.setattr(
        quality_nets.replay,
        "persisted_bundles",
        lambda **_kw: [SimpleNamespace(captured_at=at) for at in captured],
    )


# --------------------------------------------------------------------------- #
# Coverage (signal 92)
# --------------------------------------------------------------------------- #


def test_coverage_none_for_unmanifested_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    # Every registry agent now carries a manifest (step 7 Lot 0); exercise the None path
    # against a genuinely un-manifested agent.
    monkeypatch.setattr(quality_nets, "get_agent", lambda _a: SimpleNamespace(observability=None))
    assert quality_nets.coverage_descriptor("unmanifested") is None


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


def test_a_store_that_did_not_answer_is_not_an_agent_that_emits_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The class this repo keeps re-finding: a blind read published as a measured shortfall.

    Both branches produce zero rows. Reading the flattened seam made them the same answer —
    ``no_evidence``, with every required attribute listed as missing, which renders as an agent
    that instruments nothing. One of those two is a claim about the agent and the other is a
    claim about the reader's own eyes, and only one of them is warranted.
    """
    _rows(monkeypatch, [], readable=False)
    blind = quality_nets.coverage_descriptor("recouvrement")
    _rows(monkeypatch, [])
    empty = quality_nets.coverage_descriptor("recouvrement")

    assert blind is not None and empty is not None
    assert blind["status"] == "unverifiable"
    assert empty["status"] == "no_evidence", "a store that answered 'none' still says none"
    assert blind["covered_pct"] is None and empty["covered_pct"] is None
    assert blind["missing_attributes"] == [], (
        "nothing is KNOWN to be missing when nobody could look — listing the whole contract "
        "renders as a total instrumentation failure the read cannot support"
    )
    assert empty["missing_attributes"] == empty["required_attributes"]


def test_fleet_coverage_reads_the_ledger_once_and_serves_every_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Signal 92 for the fleet, from ONE read — the shape fleet_ledger_facts established."""
    reads: list[dict[str, object]] = []

    def _one_read(**kwargs: object) -> business_events.BusinessEventRead:
        reads.append(kwargs)
        return business_events.BusinessEventRead(rows=[dict(_FULL_ROW)], readable=True)

    monkeypatch.setattr(quality_nets.business_events, "business_event_read", _one_read)
    payload = quality_nets.fleet_coverage()

    assert len(reads) == 1, "one whole-ledger read, not one per agent"
    assert reads[0].get("agent_id") is None, "the fleet read must not filter to one agent"
    agents = payload["agents"]
    assert isinstance(agents, list) and agents, "the manifested fleet must produce rows"
    covered = {str(a["agent_id"]): a["covered_pct"] for a in agents}
    assert covered["recouvrement"] == 100.0, "the agent with rows is measured"
    others = [pct for agent_id, pct in covered.items() if agent_id != "recouvrement"]
    assert all(pct is None for pct in others), "an agent with no rows carries no percentage"


def test_fleet_coverage_that_could_not_read_says_so_on_every_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ClickHouse outage must not render as a fleet that instruments nothing."""
    monkeypatch.setattr(
        quality_nets.business_events,
        "business_event_read",
        lambda **_kw: business_events.BusinessEventRead(rows=[], readable=False),
    )
    payload = quality_nets.fleet_coverage()
    agents = payload["agents"]
    assert payload["blind"] is True
    assert isinstance(agents, list)
    assert agents, "the fleet is still listed — the reader is told it cannot be judged"
    assert all(a["status"] == "unverifiable" for a in agents)
    assert all(a["covered_pct"] is None for a in agents)


# --------------------------------------------------------------------------- #
# Canary (signal 94)
# --------------------------------------------------------------------------- #

_NOW = datetime(2026, 1, 2, 0, 0, 0, tzinfo=UTC)


def test_canary_none_for_unmanifested_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(quality_nets, "get_agent", lambda _a: SimpleNamespace(observability=None))
    assert quality_nets.canary_descriptor("unmanifested") is None


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
