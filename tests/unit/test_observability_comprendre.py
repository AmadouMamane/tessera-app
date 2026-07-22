"""Live `/comprendre` facts: one witness per tile, no process-counter shortcuts."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest

from tessera.api.routes.observability import comprendre as comprendre_route
from tessera.observability import agent_release, comprendre, guard_activity, turn_evidence

if TYPE_CHECKING:
    from pathlib import Path

_NOW = datetime(2026, 7, 22, 10, 30, tzinfo=UTC)


class _PrometheusRange:
    """Minimal range adapter carrying two agents and malformed noise."""

    def __init__(self) -> None:
        self.query = ""
        self.start = ""
        self.end = ""
        self.step = ""

    def range(self, query: str, *, start: str, end: str, step: str) -> list[dict[str, object]]:
        self.query = query
        self.start = start
        self.end = end
        self.step = step
        return [
            {
                "metric": {"agent_id": "support-client"},
                "values": [
                    [(_NOW - timedelta(hours=2)).timestamp(), "1"],
                    [(_NOW - timedelta(hours=1)).timestamp(), "2"],
                ],
            },
            {
                "metric": {"agent_id": "hello-agent"},
                "values": [[(_NOW - timedelta(minutes=10)).timestamp(), "1"]],
            },
            {"metric": {}, "values": [[_NOW.timestamp(), "99"]]},
        ]


def test_t1_reads_positive_counter_increases_inside_the_window() -> None:
    adapter = _PrometheusRange()
    observed = turn_evidence.recent_turn_evidence(
        _NOW - timedelta(hours=24),
        until=_NOW,
        adapter=adapter,  # type: ignore[arg-type]
    )

    assert set(observed) == {"support-client", "hello-agent"}
    assert observed["support-client"] == _NOW - timedelta(hours=1)
    assert observed["hello-agent"] == _NOW - timedelta(minutes=10)
    assert "increase(tessera_agent_turns_total[2m])" in adapter.query
    assert adapter.step == "60s"


def _entry(
    when: datetime,
    *,
    outcome: str = "allowed",
    synthetic: bool | None = False,
    target: str = "user_input",
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "type": "tessera.guard.audit",
        "occurred_at": when.isoformat(),
        "target": target,
        "outcome": outcome,
        "decisions": [],
    }
    if synthetic is not None:
        entry["synthetic"] = synthetic
    return entry


def _ledger(path: Path, entries: list[dict[str, Any]]) -> Path:
    file = path / "audit.jsonl"
    file.write_text("\n".join(json.dumps(entry) for entry in entries) + "\n", encoding="utf-8")
    return file


def test_t3_counts_real_guard_entries_and_ignores_a_synthetic_turn(tmp_path: Path) -> None:
    since = _NOW - timedelta(hours=8)
    base = [
        _entry(_NOW - timedelta(hours=2)),
        _entry(_NOW - timedelta(hours=1), outcome="denied", synthetic=None),
    ]
    before = guard_activity.exchange_counts_since(since, path=_ledger(tmp_path, base))

    # Mutation required by the spec: injecting a denied synthetic turn changes neither number.
    after = guard_activity.exchange_counts_since(
        since,
        path=_ledger(tmp_path, [*base, _entry(_NOW, outcome="denied", synthetic=True)]),
    )

    assert before == guard_activity.GuardExchangeCounts(controlled=2, blocked=1)
    assert after == before


def test_t3_day_starts_at_midnight_europe_paris_in_summer_and_winter() -> None:
    summer = comprendre.paris_midnight(datetime(2026, 7, 22, 0, 30, tzinfo=UTC))
    winter = comprendre.paris_midnight(datetime(2026, 1, 22, 0, 30, tzinfo=UTC))

    assert summer.isoformat() == "2026-07-22T00:00:00+02:00"
    assert winter.isoformat() == "2026-01-22T00:00:00+01:00"


def _release(
    agent_id: str,
    *,
    available: bool,
    passed: bool = False,
    catalogue: str = "v1",
    current: str = "v1",
) -> agent_release.AgentRelease:
    return agent_release.AgentRelease(
        agent_id=agent_id,
        available=available,
        passed=passed,
        catalogue_version=catalogue,
        current_catalogue_version=current,
    )


def test_t4_uses_mutually_exclusive_buckets_from_the_agent_release_seam() -> None:
    states = {
        "ready": _release("ready", available=True, passed=True),
        "stale": _release("stale", available=True, passed=True, catalogue="old"),
        "blocked": _release("blocked", available=True),
        "missing": _release("missing", available=False),
    }

    assert agent_release.fleet_release_buckets(states) == {
        "total": 4,
        "evaluated": 3,
        "ready": 1,
        "review": 3,
        "missing": 1,
        "stale": 1,
        "blocked": 1,
    }


@pytest.mark.asyncio
async def test_each_tile_mutates_independently_and_t4_equals_the_shared_seam(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observations: dict[str, datetime] = {}
    releases = {
        "ready": _release("ready", available=True, passed=True),
        "missing": _release("missing", available=False),
    }
    expected_buckets = agent_release.fleet_release_buckets(releases)

    monkeypatch.setattr(
        comprendre.turn_evidence,
        "recent_turn_evidence",
        lambda *_args, **_kwargs: observations,
    )
    monkeypatch.setattr(
        comprendre.fleet,
        "registered_agent_ids",
        lambda: {"support-client"},
    )
    monkeypatch.setattr(
        comprendre.guard_activity,
        "exchange_counts_since",
        lambda _since: guard_activity.GuardExchangeCounts(controlled=0, blocked=0),
    )
    monkeypatch.setattr(
        comprendre.agent_release,
        "fleet_release_buckets",
        lambda: expected_buckets,
    )
    verification = comprendre.AuditVerification(
        verified=False,
        length=12,
        full_verified_at="2026-07-22T09:00:00+00:00",
        checked_at=_NOW,
    )

    empty = await comprendre.build_comprendre(verification, now=_NOW)
    assert empty["fleet"] == {
        "observed_agents": None,
        "last_signal_at": None,
        "is_silent": None,
        "window_hours": 24,
    }
    assert empty["guard"]["controlled_today"] is None
    assert empty["evaluations"] == {
        "ready_agents": expected_buckets["ready"],
        "review_agents": expected_buckets["review"],
    }
    assert empty["audit"]["last_verified_at"] is None

    observations["support-client"] = _NOW - timedelta(minutes=3)
    with_signal = await comprendre.build_comprendre(verification, now=_NOW)
    assert with_signal["fleet"]["observed_agents"] == 1
    assert with_signal["fleet"]["is_silent"] is False
    assert with_signal["guard"] == empty["guard"]
    assert with_signal["evaluations"] == empty["evaluations"]

    observations["retired-agent"] = _NOW
    with_unregistered_signal = await comprendre.build_comprendre(verification, now=_NOW)
    assert with_unregistered_signal["fleet"]["observed_agents"] == 1


@pytest.mark.asyncio
async def test_t5_never_serves_a_timestamp_without_a_successful_effective_verification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(comprendre.turn_evidence, "recent_turn_evidence", lambda *_a, **_k: {})
    monkeypatch.setattr(
        comprendre.guard_activity,
        "exchange_counts_since",
        lambda _since: guard_activity.GuardExchangeCounts(controlled=0, blocked=0),
    )
    monkeypatch.setattr(
        comprendre.agent_release,
        "fleet_release_buckets",
        lambda: {
            "total": 0,
            "evaluated": 0,
            "ready": 0,
            "review": 0,
            "missing": 0,
            "stale": 0,
            "blocked": 0,
        },
    )
    forged = comprendre.AuditVerification(
        verified=False,
        length=1,
        full_verified_at="2026-07-22T09:00:00+00:00",
        checked_at=_NOW,
    )
    effective = comprendre.AuditVerification(
        verified=True,
        length=1,
        full_verified_at="2026-07-22T09:00:00+00:00",
        checked_at=_NOW,
    )

    assert (await comprendre.build_comprendre(forged, now=_NOW))["audit"] == {
        "last_verified_at": None
    }
    assert (await comprendre.build_comprendre(effective, now=_NOW))["audit"] == {
        "last_verified_at": "2026-07-22T09:00:00+00:00"
    }


@pytest.mark.asyncio
async def test_endpoint_runs_the_audit_badge_seam_and_serves_all_six_facts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Integrity:
        verified = True
        length = 4
        full_verified_at = "2026-07-22T09:00:00+00:00"

    audit_calls = 0
    received_verification: comprendre.AuditVerification | None = None

    async def fake_audit_integrity() -> _Integrity:
        nonlocal audit_calls
        audit_calls += 1
        return _Integrity()

    async def fake_build(
        verification: comprendre.AuditVerification | None,
        *,
        now: datetime | None = None,
    ) -> comprendre.ComprendreData:
        nonlocal received_verification
        received_verification = verification
        assert now is not None
        return {
            "generated_at": now.isoformat(),
            "fleet": {
                "observed_agents": 2,
                "last_signal_at": "2026-07-22T10:29:00+00:00",
                "is_silent": False,
                "window_hours": 24,
            },
            "guard": {
                "controlled_today": 9,
                "blocked_today": 3,
                "since": "2026-07-22T00:00:00+02:00",
            },
            "evaluations": {"ready_agents": 1, "review_agents": 1},
            "audit": {"last_verified_at": "2026-07-22T09:00:00+00:00"},
        }

    monkeypatch.setattr(comprendre_route.audit_routes, "audit_integrity", fake_audit_integrity)
    monkeypatch.setattr(comprendre_route.comprendre_mod, "build_comprendre", fake_build)

    response = await comprendre_route.observability_comprendre()

    assert audit_calls == 1
    assert received_verification is not None
    assert received_verification.verified is True
    assert response.model_dump()["fleet"]["observed_agents"] == 2
    assert response.model_dump()["guard"] == {
        "controlled_today": 9,
        "blocked_today": 3,
        "since": "2026-07-22T00:00:00+02:00",
    }
    assert response.model_dump()["evaluations"] == {"ready_agents": 1, "review_agents": 1}
    assert response.model_dump()["audit"] == {"last_verified_at": "2026-07-22T09:00:00+00:00"}
