"""Parity: the bulk fleet-snapshot equals the single-agent route it collapses.

The GOUVERNER breakdown pages called ``/observability/snapshot?agent=<id>`` once per fleet
agent — N tunnel round-trips whose intermittent tail is the free tunnel serialising them.
``/observability/fleet-snapshot`` returns them all in one response. These tests assert each
per-agent slice is byte-identical to the single-agent route over the *same* stores, so the
collapse can never silently diverge from what the cockpit renders today. Same shape and intent
as ``test_spine_signals_parity.py`` — a real read path, no fake reader.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

import pytest

from tessera.api.routes import observability as obs
from tessera.observability import replay as replay_mod
from tessera.observability.eval import scores as scores_mod
from tessera.observability.fleet import registered_agent_ids
from tessera.observability.spine.adapters import set_reader
from tessera.observability.spine.snapshot import reset_snapshot_cache

if TYPE_CHECKING:
    from pathlib import Path

_T = "2026-06-12T10:00:00+00:00"
_ASOF = "2026-06-13T00:00:00Z"
# A mix of score- and bundle-derived hot-path signals that HAVE seeded data, so parity is
# exercised on non-empty slices (not the trivial equal-empty case).
_SIGNALS = "scores,slo,toxicity,pii_leak,cost"


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
    # Bulk and single route both read the current stores (no fake reader) — same data in, so
    # any divergence is a real regression, not a fixture mismatch.
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


async def test_fleet_snapshot_slice_matches_single_agent_route() -> None:
    """Every per-agent slice is byte-identical to ``/observability/snapshot?agent=<id>``."""
    reset_snapshot_cache()
    bulk = cast(dict[str, Any], await obs.observability_fleet_snapshot(at=_ASOF, signals=_SIGNALS))
    agents = cast(list[dict[str, Any]], bulk["agents"])
    assert agents, "bulk returned no agents"
    for entry in agents:
        aid = cast(str, entry["agent_id"])
        single = cast(
            dict[str, Any],
            await obs.observability_snapshot(at=_ASOF, agent=aid, signals=_SIGNALS),
        )
        for sig in _SIGNALS.split(","):
            assert entry["snapshot"]["signals"][sig]["data"] == single["signals"][sig]["data"], (
                aid,
                sig,
            )


async def test_fleet_snapshot_covers_registered_agents_and_invents_none() -> None:
    """The response spans the registry's agents and never names one that isn't registered."""
    reset_snapshot_cache()
    bulk = cast(dict[str, Any], await obs.observability_fleet_snapshot(at=_ASOF, signals=_SIGNALS))
    returned = {cast(str, e["agent_id"]) for e in cast(list[dict[str, Any]], bulk["agents"])}
    registered = registered_agent_ids()
    # No agent invented; the seeded agents (whose compute succeeds) are present.
    assert returned <= registered
    assert {"support-client", "recouvrement"} <= returned


async def test_fleet_snapshot_default_signals_match_route() -> None:
    """With no ``?signals=`` (all hot-path signals) the slices still match the single route."""
    reset_snapshot_cache()
    bulk = cast(dict[str, Any], await obs.observability_fleet_snapshot(at=_ASOF))
    for entry in cast(list[dict[str, Any]], bulk["agents"]):
        aid = cast(str, entry["agent_id"])
        single = cast(dict[str, Any], await obs.observability_snapshot(at=_ASOF, agent=aid))
        assert entry["snapshot"]["signals"].keys() == single["signals"].keys()
        for sig in single["signals"]:
            assert entry["snapshot"]["signals"][sig]["data"] == single["signals"][sig]["data"], (
                aid,
                sig,
            )
