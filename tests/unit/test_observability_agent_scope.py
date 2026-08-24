"""Per-agent attribution of the cockpit's runtime signals.

The GOUVERNER/PLATEFORME surfaces carry a global ``?agent=`` filter. These tests
lock the backend half of that filter: the online-eval scores and replay bundles
are tagged with the responding agent, and the score-/bundle-/audit-backed signals
read only that agent's data when scoped — and read honestly empty for an agent with
no data, never fabricating cross-agent numbers.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from tessera.observability import replay as replay_mod
from tessera.observability.conformance import compute_conformance
from tessera.observability.eval import scores as scores_mod
from tessera.observability.tool_validity import compute_tool_validity
from tests.unit._route_helpers import call_route

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

_T0 = "2026-06-12T10:00:00+00:00"
_T1 = "2026-06-12T10:00:10+00:00"


def _score(agent: str | None, score: float) -> dict[str, object]:
    return {
        "scored_at": _T0,
        "metric": "faithfulness",
        "score": score,
        "language": "fr",
        "agent_id": agent,
    }


class TestScoreAttribution:
    def test_persisted_scores_filtered_by_agent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = tmp_path / "scores.jsonl"
        monkeypatch.setattr(scores_mod, "_scores_path", lambda: path)
        path.write_text(
            "\n".join(
                json.dumps(r)
                for r in (
                    _score("support-client", 0.9),
                    _score("recouvrement", 0.1),
                    _score(None, 0.5),  # org-only / unattributed
                )
            )
            + "\n",
            encoding="utf-8",
        )
        assert len(scores_mod.persisted_scores()) == 3  # org view = everything
        support = scores_mod.persisted_scores(None, "support-client")
        assert [s["score"] for s in support] == [0.9]
        # An agent with no scores reads honestly empty — never the org rows.
        assert scores_mod.persisted_scores(None, "nonexistent") == []

    def test_agent_and_asof_compose(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """``?agent=`` and ``?at=`` cross-filter: the read is the INTERSECTION.

        This is what lets the cockpit be sliced by agent AND by the SR-01 temporal
        rail at once (à-un-instant / historique) without the two dimensions leaking.
        """
        path = tmp_path / "scores.jsonl"
        monkeypatch.setattr(scores_mod, "_scores_path", lambda: path)

        def row(agent: str, at: str, score: float) -> dict[str, object]:
            return {"scored_at": at, "metric": "faithfulness", "score": score, "agent_id": agent}

        early, late = "2026-06-12T10:00:00+00:00", "2026-06-12T12:00:00+00:00"
        cut = "2026-06-12T11:00:00Z"
        path.write_text(
            "\n".join(
                json.dumps(r)
                for r in (
                    row("recouvrement", early, 0.1),  # in agent slice AND before T
                    row("recouvrement", late, 0.2),  # in agent slice, AFTER T
                    row("support-client", early, 0.9),  # before T, WRONG agent
                )
            )
            + "\n",
            encoding="utf-8",
        )
        # agent only → 2 recouvrement rows; asof only → 2 early rows;
        # both together → the single recouvrement row that is also ≤ T.
        assert len(scores_mod.persisted_scores(None, "recouvrement")) == 2
        assert len(scores_mod.persisted_scores(cut, None)) == 2
        intersection = scores_mod.persisted_scores(cut, "recouvrement")
        assert [s["score"] for s in intersection] == [0.1]

    def test_recent_scores_filtered_by_agent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = tmp_path / "scores.jsonl"
        monkeypatch.setattr(scores_mod, "_scores_path", lambda: path)
        path.write_text(
            json.dumps(_score("onboarding", 0.7)) + "\n",
            encoding="utf-8",
        )
        saved = list(scores_mod._RECENT)
        try:
            scores_mod._RECENT.clear()
            monkeypatch.setattr(scores_mod, "_WARMED", False)
            assert len(scores_mod.recent_scores("onboarding")) == 1
            assert scores_mod.recent_scores("support-client") == []
        finally:
            scores_mod._RECENT.clear()
            scores_mod._RECENT.extend(saved)


def _bundle_row(bundle_id: str, agent: str | None) -> dict[str, object]:
    return {
        "bundle_id": bundle_id,
        "captured_at": _T0,
        "conversation_id": "conv-1",
        "language": "fr",
        "question": "q",
        "context": "c",
        "original_answer": "a",
        "original_model": "m",
        "original_score": 0.5,
        "lineage": None,
        "latency_ms": None,
        "agent_id": agent,
    }


class TestBundleAttribution:
    def test_bundle_agent_round_trips_and_filters(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = tmp_path / "bundles.jsonl"
        monkeypatch.setattr(replay_mod, "_bundles_path", lambda: path)
        path.write_text(
            "\n".join(
                json.dumps(_bundle_row(bid, agent))
                for bid, agent in (("b0", "support-client"), ("b1", "recouvrement"))
            )
            + "\n",
            encoding="utf-8",
        )
        all_bundles = replay_mod.persisted_bundles()
        assert {b.agent_id for b in all_bundles} == {"support-client", "recouvrement"}
        scoped = replay_mod.persisted_bundles(None, "recouvrement")
        assert [b.bundle_id for b in scoped] == ["b1"]
        assert replay_mod.persisted_bundles(None, "nonexistent") == []


def _audit(target: str, outcome: str, agent: str | None, **extra: object) -> dict[str, object]:
    return {
        "type": "tessera.guard.audit",
        "target": target,
        "outcome": outcome,
        "occurred_at": _T0,
        "agent_id": agent,
        **extra,
    }


class TestAuditBackedAttribution:
    def _log(self, tmp_path: Path) -> Path:
        log = tmp_path / "audit.log"
        log.write_text(
            "\n".join(
                json.dumps(e)
                for e in (
                    _audit(
                        "account_balance",
                        "allowed",
                        "support-client",
                        arguments={"account_id": "AC-12345"},
                    ),
                    _audit(
                        "account_balance",
                        "denied",
                        "recouvrement",
                        arguments={"account_id": "AC-67890"},
                    ),
                )
            )
            + "\n",
            encoding="utf-8",
        )
        return log

    def test_conformance_filtered_by_agent(self, tmp_path: Path) -> None:
        log = self._log(tmp_path)
        assert compute_conformance(log).n_calls == 2  # org view
        assert compute_conformance(log, agent_id="support-client").n_calls == 1
        assert compute_conformance(log, agent_id="nonexistent").n_calls == 0

    def test_tool_validity_filtered_by_agent(self, tmp_path: Path) -> None:
        log = self._log(tmp_path)
        org = compute_tool_validity(log)
        assert (org.allowed, org.denied) == (1, 1)
        support = compute_tool_validity(log, agent_id="support-client")
        assert (support.allowed, support.denied) == (1, 0)
        recouvrement = compute_tool_validity(log, agent_id="recouvrement")
        assert (recouvrement.allowed, recouvrement.denied) == (0, 1)


class TestRouteContract:
    """The ``?agent=`` query param maps ``all``→org and a concrete id→scoped."""

    def test_agent_or_none_maps_all_to_org(self) -> None:
        from tessera.api.routes.observability import _agent_or_none

        assert _agent_or_none("all") is None
        assert _agent_or_none("") is None
        assert _agent_or_none("recouvrement") == "recouvrement"

    async def test_slo_route_scopes_by_agent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from tessera.api.routes import observability as obs

        path = tmp_path / "scores.jsonl"
        monkeypatch.setattr(scores_mod, "_scores_path", lambda: path)
        path.write_text(
            "\n".join(
                json.dumps(r)
                for r in (
                    _score("support-client", 0.9),
                    _score("support-client", 0.9),
                    _score("recouvrement", 0.1),
                )
            )
            + "\n",
            encoding="utf-8",
        )
        saved = list(scores_mod._RECENT)
        try:
            scores_mod._RECENT.clear()
            monkeypatch.setattr(scores_mod, "_WARMED", False)
            org = await call_route(obs.observability_slo, agent="all")
            support = await call_route(obs.observability_slo, agent="support-client")
            absent = await call_route(obs.observability_slo, agent="nonexistent")
            # The seeded recouvrement row is the 2026-08-22 leak scenario: recouvrement
            # declares business_scored, so its row never enters the judged plane — the
            # org view counts 2, not 3 (ADR 0017 §A4; filter witnessed next door in
            # test_judged_plane_is_declared.py).
            assert org["n"] == 2
            assert support["n"] == 2 and support["agent"] == "support-client"
            # An agent with no scored turns reads honestly empty, never the org rows.
            assert absent["n"] == 0 and absent["breaching"] is False
        finally:
            scores_mod._RECENT.clear()
            scores_mod._RECENT.extend(saved)
