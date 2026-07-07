"""The batched, cached snapshot read model (ADR 0015 §Performance).

Locks the anti-fan-out (N signals share a bounded number of upstream reads), the
read-through cache, single-flight coalescing, immutable-past caching, and the endpoint
shape + RBAC posture — the fast read model the ADR requires *before* any source swap.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from tessera.api.main import build_app
from tessera.observability.replay import ReplayBundle
from tessera.observability.spine.adapters import FakeSpineReader, set_reader
from tessera.observability.spine.scope import Scope
from tessera.observability.spine.snapshot import (
    SnapshotCache,
    compute_snapshot,
    reset_snapshot_cache,
)

if TYPE_CHECKING:
    from tessera.observability.spine.adapters.base import SpineReader

_T = "2026-06-12T10:00:00+00:00"


def _score(agent: str, metric: str = "faithfulness", score: float = 0.9) -> dict[str, object]:
    return {
        "scored_at": _T,
        "metric": metric,
        "score": score,
        "language": "fr",
        "conversation_id": "c1",
        "agent_id": agent,
    }


def _bundle(agent: str) -> ReplayBundle:
    return ReplayBundle(
        bundle_id=f"b-{agent}",
        captured_at=_T,
        conversation_id="c1",
        language="fr",
        question="q",
        context="c",
        original_answer="a",
        original_model="llama3.2:3b",
        original_score=0.9,
        lineage=None,
        latency_ms=None,
        agent_id=agent,
    )


class _CountingReader:
    """Wraps a reader and counts backend loads — the anti-fan-out / single-flight probe."""

    def __init__(self, inner: SpineReader) -> None:
        self._inner = inner
        self.calls = {"scores": 0, "bundles": 0, "audit": 0, "gating": 0}

    def scores(self, scope: Scope) -> list[dict[str, object]]:
        self.calls["scores"] += 1
        return self._inner.scores(scope)

    def bundles(self, scope: Scope) -> list[ReplayBundle]:
        self.calls["bundles"] += 1
        return self._inner.bundles(scope)

    def audit_entries(self, scope: Scope) -> list[dict[str, object]]:
        self.calls["audit"] += 1
        return self._inner.audit_entries(scope)

    def gating_scores(self, scope: Scope) -> list[dict[str, object]]:
        self.calls["gating"] += 1
        return self._inner.gating_scores(scope)


@pytest.fixture(autouse=True)
def _reset_spine() -> None:
    set_reader(None)
    reset_snapshot_cache()
    yield
    set_reader(None)
    reset_snapshot_cache()


class TestSnapshotShape:
    async def test_returns_all_hot_path_signals_with_reports(self) -> None:
        set_reader(FakeSpineReader(scores=[_score("support")], bundles=[_bundle("support")]))
        snap = await compute_snapshot(Scope())
        assert set(snap["signals"]) >= {"slo", "trend", "funnel", "scores", "toxicity", "cost"}
        slo = snap["signals"]["slo"]
        assert "data" in slo and "report" in slo
        assert slo["report"]["source"] == "local"

    async def test_shares_reads_no_per_signal_fan_out(self) -> None:
        counting = _CountingReader(FakeSpineReader(scores=[_score("support")], bundles=[]))
        set_reader(counting)
        snap = await compute_snapshot(Scope())
        # Ten signals, but scores + bundles + gating are each read exactly once.
        assert counting.calls["scores"] == 1
        assert counting.calls["bundles"] == 1
        assert counting.calls["gating"] == 1
        assert snap["meta"]["upstream_reads"] == 3

    async def test_scope_filters_by_agent(self) -> None:
        set_reader(
            FakeSpineReader(
                scores=[_score("support", score=0.9), _score("recouvrement", score=0.1)]
            )
        )
        support = await compute_snapshot(Scope(agent_id="support"))
        assert support["signals"]["slo"]["data"]["n"] == 1
        assert support["scope"]["agent"] == "support"

    async def test_signal_subset_selects_only_requested(self) -> None:
        set_reader(FakeSpineReader(scores=[_score("support")]))
        snap = await compute_snapshot(Scope(), ["slo", "scores"])
        assert set(snap["signals"]) == {"slo", "scores"}


class TestCache:
    async def test_second_read_is_a_cache_hit(self) -> None:
        counting = _CountingReader(FakeSpineReader(scores=[_score("support")]))
        set_reader(counting)
        first = await compute_snapshot(Scope())
        second = await compute_snapshot(Scope())
        assert first["meta"]["cache"] == "miss"
        assert second["meta"]["cache"] == "hit"
        # A hit never re-reads upstream.
        assert counting.calls["scores"] == 1

    async def test_single_flight_coalesces_concurrent_misses(self) -> None:
        counting = _CountingReader(FakeSpineReader(scores=[_score("support")]))
        set_reader(counting)
        results = await asyncio.gather(*(compute_snapshot(Scope()) for _ in range(8)))
        # Eight concurrent viewers of one scope → exactly one upstream pass.
        assert counting.calls["scores"] == 1
        assert sum(1 for r in results if r["meta"]["cache"] == "miss") == 1


class TestCacheSemantics:
    async def test_live_scope_expires_but_past_instant_is_immutable(self) -> None:
        cache = SnapshotCache(live_ttl=0.0)
        calls = {"n": 0}

        async def _compute() -> dict[str, object]:
            calls["n"] += 1
            return {"v": calls["n"]}

        # Live (at=None) with a zero TTL: every read recomputes (nothing is immutable).
        await cache.get_or_compute("live", immutable=False, compute=_compute)
        _, outcome = await cache.get_or_compute("live", immutable=False, compute=_compute)
        assert outcome == "miss"
        # A past instant can never change → cached indefinitely, even with a zero TTL.
        await cache.get_or_compute("past", immutable=True, compute=_compute)
        value, outcome = await cache.get_or_compute("past", immutable=True, compute=_compute)
        assert outcome == "hit"
        assert value == {"v": 3}


class TestEndpoint:
    def test_snapshot_endpoint_returns_shape_without_token(self) -> None:
        # RBAC is the shared require_bearer posture: a no-op without a configured token, so
        # the aggregate read surface stays reachable (scope is a filter, not a privilege).
        set_reader(FakeSpineReader(scores=[_score("support")]))
        client = TestClient(build_app())
        resp = client.get("/observability/snapshot")
        assert resp.status_code == 200
        body = resp.json()
        assert set(body) == {"scope", "signals", "meta"}
        assert "slo" in body["signals"]
        assert body["meta"]["upstream_reads"] <= 3

    def test_snapshot_endpoint_subset_and_scope(self) -> None:
        set_reader(
            FakeSpineReader(scores=[_score("support", score=0.9), _score("other", score=0.1)])
        )
        client = TestClient(build_app())
        resp = client.get("/observability/snapshot", params={"signals": "slo", "agent": "support"})
        assert resp.status_code == 200
        body = resp.json()
        assert set(body["signals"]) == {"slo"}
        assert body["scope"]["agent"] == "support"
        assert body["signals"]["slo"]["data"]["n"] == 1
