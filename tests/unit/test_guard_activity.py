"""Guard-activity rollup for the public launcher band (ADR 0009).

The band's "sécurité à chaque message" column shows two counters; these tests
interrogate the thing (ADR 0026): the denial count comes from real ledger
entries (one refused message counts once; tool denials and yesterday's denials
do not), and the route degrades to ``available: false`` instead of inventing
zeros when a witness is unreachable.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tessera.api.routes.observability import fleet as fleet_routes
from tessera.observability import guard_activity

if TYPE_CHECKING:
    from pathlib import Path

_NOW = datetime(2026, 7, 21, 15, 30, tzinfo=UTC)
_MIDNIGHT = datetime(2026, 7, 21, 0, 0, tzinfo=UTC)


def _entry(
    *,
    outcome: str = "denied",
    target: str = "user_input",
    decision: str = "deny",
    occurred_at: datetime = _NOW,
    entry_type: str = "tessera.guard.audit",
    extra_decisions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    decisions = [
        {"target": target, "decision": decision, "occurred_at": occurred_at.isoformat()},
        *(extra_decisions or []),
    ]
    return {
        "type": entry_type,
        "outcome": outcome,
        "occurred_at": occurred_at.isoformat(),
        "decisions": decisions,
    }


def _write_ledger(path: Path, entries: list[dict[str, Any]]) -> Path:
    ledger = path / "audit.jsonl"
    ledger.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    return ledger


class TestBlockedSince:
    def test_counts_only_todays_user_input_denials(self, tmp_path: Path) -> None:
        ledger = _write_ledger(
            tmp_path,
            [
                _entry(),  # today's refused message — counted
                _entry(occurred_at=_NOW - timedelta(days=1)),  # yesterday — not
                _entry(target="card_block"),  # tool denial — out of scope
                _entry(outcome="allowed", decision="allow"),  # allowed turn — not
                _entry(entry_type="tessera.business.event"),  # foreign type — not
            ],
        )
        assert guard_activity.blocked_since(_MIDNIGHT, path=ledger) == 1

    def test_a_refused_message_counts_once_however_many_records(self, tmp_path: Path) -> None:
        ledger = _write_ledger(
            tmp_path,
            [
                _entry(
                    extra_decisions=[
                        {
                            "target": "user_input",
                            "decision": "deny",
                            "occurred_at": _NOW.isoformat(),
                        }
                    ]
                )
            ],
        )
        assert guard_activity.blocked_since(_MIDNIGHT, path=ledger) == 1

    def test_an_empty_ledger_is_a_real_zero(self, tmp_path: Path) -> None:
        ledger = _write_ledger(tmp_path, [])
        assert guard_activity.blocked_since(_MIDNIGHT, path=ledger) == 0


class TestLocalMidnight:
    def test_is_aware_and_starts_the_day(self) -> None:
        midnight = guard_activity.local_midnight(_NOW)
        assert midnight.tzinfo is not None
        assert (midnight.hour, midnight.minute, midnight.second) == (0, 0, 0)
        assert midnight <= _NOW


class TestBuildGuardActivity:
    @pytest.mark.asyncio
    async def test_carries_both_witnesses_and_the_window(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def _fake_checked(since: datetime) -> int:
            assert since.tzinfo is not None
            return 214

        monkeypatch.setattr(guard_activity, "count_user_turns_since", _fake_checked)
        monkeypatch.setattr(guard_activity, "_blocked_today_cached", lambda _since: 2)
        payload = await guard_activity.build_guard_activity()
        assert payload["checked_today"] == 214
        assert payload["blocked_today"] == 2
        assert isinstance(payload["since"], str)


class TestRoute:
    def _client(self) -> TestClient:
        app = FastAPI()
        app.include_router(fleet_routes.router)
        return TestClient(app, raise_server_exceptions=False)

    def test_serves_the_aggregate(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def _fake() -> dict[str, object]:
            return {"checked_today": 7, "blocked_today": 1, "since": "2026-07-21T00:00:00+00:00"}

        monkeypatch.setattr(fleet_routes.guard_activity_mod, "build_guard_activity", _fake)
        response = self._client().get("/observability/guard-activity")
        assert response.status_code == 200
        assert response.json() == {
            "available": True,
            "checked_today": 7,
            "blocked_today": 1,
            "since": "2026-07-21T00:00:00+00:00",
        }

    def test_degrades_honestly_when_a_witness_is_unreachable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def _boom() -> dict[str, object]:
            raise RuntimeError("postgres is down")

        monkeypatch.setattr(fleet_routes.guard_activity_mod, "build_guard_activity", _boom)
        response = self._client().get("/observability/guard-activity")
        assert response.status_code == 200
        assert response.json() == {"available": False}
