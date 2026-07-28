"""Parity: the snapshot signal equals its route today (ADR 0015 §Migration A gate).

Phase A is "no behaviour change". Each hot-path snapshot signal re-derives its payload from
the shared reads; these tests assert that payload is byte-identical to the existing route
handler over the *same* stores — so the batched read model can never silently diverge from
what the cockpit renders today.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from tessera.api.routes import observability as obs
from tessera.observability import replay as replay_mod
from tessera.observability.eval import scores as scores_mod
from tessera.observability.spine.adapters import set_reader
from tessera.observability.spine.scope import Scope
from tessera.observability.spine.snapshot import compute_snapshot, reset_snapshot_cache
from tests.unit._route_helpers import call_route

if TYPE_CHECKING:
    from pathlib import Path

_T = "2026-06-12T10:00:00+00:00"
_ASOF = "2026-06-13T00:00:00Z"


def _score(agent: str, metric: str, score: float) -> dict[str, object]:
    return {
        "scored_at": _T,
        "metric": metric,
        "score": score,
        "language": "fr",
        "conversation_id": f"c-{agent}",
        "agent_id": agent,
    }


def _bundle(bundle_id: str, agent: str) -> dict[str, object]:
    return {
        "bundle_id": bundle_id,
        "captured_at": _T,
        "conversation_id": f"c-{agent}",
        "language": "fr",
        "question": "Quel est mon solde ?",
        "context": "Le solde est 100 EUR.",
        "original_answer": "Votre solde est de 100 EUR.",
        "original_model": "llama3.2:3b",
        "original_score": 0.9,
        "lineage": None,
        "latency_ms": None,
        "agent_id": agent,
    }


@pytest.fixture(autouse=True)
def _seed_stores(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Snapshot + routes both read the current stores (no fake reader) — same data in, so any
    # divergence is a real regression, not a fixture mismatch.
    set_reader(None)
    reset_snapshot_cache()
    scores_path = tmp_path / "scores.jsonl"
    bundles_path = tmp_path / "bundles.jsonl"
    monkeypatch.setattr(scores_mod, "_scores_path", lambda: scores_path)
    monkeypatch.setattr(replay_mod, "_bundles_path", lambda: bundles_path)
    scores_path.write_text(
        "\n".join(
            json.dumps(r)
            for r in (
                _score("support-client", "faithfulness", 0.9),
                _score("support-client", "grounding", 0.8),
                _score("recouvrement", "faithfulness", 0.2),
            )
        )
        + "\n",
        encoding="utf-8",
    )
    bundles_path.write_text(
        "\n".join(
            json.dumps(_bundle(bid, agent))
            for bid, agent in (("b0", "support-client"), ("b1", "recouvrement"))
        )
        + "\n",
        encoding="utf-8",
    )
    yield
    set_reader(None)
    reset_snapshot_cache()


# (signal id, route coroutine) — every store-derived hot-path signal + its route.
_SCORE_SIGNALS = {
    "scores": obs.observability_scores,
    "slo": obs.observability_slo,
    "trend": obs.observability_trend,
    "funnel": obs.observability_funnel,
}
_BUNDLE_SIGNALS = {
    "toxicity": obs.observability_toxicity,
    "pii_leak": obs.observability_pii_leak,
    "cost": obs.observability_cost,
    "anomalies": obs.observability_anomalies,
    "what_changed": obs.observability_what_changed,
}


@pytest.mark.parametrize("agent", ["all", "support-client", "recouvrement"])
async def test_snapshot_signals_match_routes(agent: str) -> None:
    scope = Scope.from_query({"at": _ASOF, "agent": agent})
    reset_snapshot_cache()
    snap = await compute_snapshot(scope, list(_SCORE_SIGNALS) + list(_BUNDLE_SIGNALS))
    for signal_id, route in {**_SCORE_SIGNALS, **_BUNDLE_SIGNALS}.items():
        expected = await call_route(route, at=_ASOF, agent=agent)
        assert snap["signals"][signal_id]["data"] == expected, signal_id


async def test_funnel_route_takes_no_agent_kw_but_matches_org() -> None:
    # funnel's route accepts (at, agent); confirm the snapshot's org read matches it.
    reset_snapshot_cache()
    snap = await compute_snapshot(Scope.from_query({"at": _ASOF, "agent": "all"}), ["funnel"])
    assert snap["signals"]["funnel"]["data"] == await call_route(
        obs.observability_funnel, at=_ASOF, agent="all"
    )


@pytest.mark.parametrize("agent", ["all", "support-client", "recouvrement"])
async def test_business_capabilities_snapshot_matches_route(agent: str) -> None:
    # step 6c fold — the business aggregate folded into the batched snapshot must be a
    # single source: the ``?signals=business_capabilities`` read == the standalone route,
    # so the Métier fan-out can retire without ever diverging from what it rendered.
    scope = Scope.from_query({"at": _ASOF, "agent": agent})
    reset_snapshot_cache()
    snap = await compute_snapshot(scope, ["business_capabilities"])
    expected = await call_route(obs.observability_business_capabilities, at=_ASOF, agent=agent)
    assert snap["signals"]["business_capabilities"]["data"] == expected
