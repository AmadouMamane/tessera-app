"""The capability-declared signal registry (ADR 0015).

The registry is where honesty becomes structural: a read narrows the request scope to a
signal's declared dimensions and returns an honoured/ignored report, so the UI can badge an
unsupported filter rather than silently drop it. These tests lock the declaration table,
the report, the scope narrowing, and honest degradation (timeout / unavailable → empty).
"""

from __future__ import annotations

import pytest

from tessera.observability.spine.adapters import SpineUnavailableError
from tessera.observability.spine.capabilities import (
    CAPABILITIES,
    capability_for,
    snapshot_signal_ids,
)
from tessera.observability.spine.registry import SignalRegistry, get_registry
from tessera.observability.spine.scope import Dimension, Scope


class TestCapabilities:
    def test_fixtures_are_flagged_synthetic(self) -> None:
        # policies / replay_shadow / automations graduated to real cores; their
        # absent subsystems keep dedicated synthetic flags.
        for signal_id in ("incidents", "curation"):
            assert capability_for(signal_id).synthetic is True
        for signal_id in ("policies", "replay_shadow", "automations"):
            assert capability_for(signal_id).synthetic is False
        for signal_id in ("policy_versioning", "shadow_traffic", "automation_workflow"):
            assert capability_for(signal_id).synthetic is True

    def test_fixed_corpus_probes_are_org_wide(self) -> None:
        # A fixed-corpus probe of the shared policy declares no AGENT dimension → org-wide.
        for signal_id in ("refusal", "firewall", "audit_integrity"):
            assert capability_for(signal_id).org_wide is True
            assert Dimension.AGENT not in capability_for(signal_id).dimensions

    def test_per_agent_signals_declare_agent(self) -> None:
        for signal_id in ("slo", "toxicity", "pii_leak", "conformance"):
            assert Dimension.AGENT in capability_for(signal_id).dimensions
            assert capability_for(signal_id).org_wide is False

    def test_snapshot_ids_are_the_store_derived_hot_path(self) -> None:
        ids = set(snapshot_signal_ids())
        assert {"slo", "trend", "funnel", "scores", "toxicity", "pii_leak", "cost"} <= ids
        # The large-ledger + crypto signals stay off the hot path (Phase C brings them in).
        assert {"audit_integrity", "conformance", "governance"} & ids == set()

    def test_unknown_capability_raises(self) -> None:
        with pytest.raises(KeyError):
            capability_for("does-not-exist")


class TestReadReport:
    async def test_honoured_and_ignored_split_by_declaration(self) -> None:
        registry = get_registry()
        scope = Scope(agent_id="support", at="2026-06-12T10:00:00Z")
        # slo declares AGENT+TIME → both honoured, nothing ignored.
        result = await registry.read("slo", scope)
        assert result.report.honoured == frozenset({Dimension.AGENT, Dimension.TIME})
        assert result.report.ignored == frozenset()
        assert result.report.org_wide is False

    async def test_org_wide_signal_reports_ignored_agent(self) -> None:
        registry = get_registry()
        scope = Scope(agent_id="support", at="2026-06-12T10:00:00Z")
        # audit_integrity declares no dimensions → agent+time are reported ignored, never
        # silently applied. The read still returns (org-wide) data.
        result = await registry.read("audit_integrity", scope)
        assert result.report.org_wide is True
        assert result.report.ignored == frozenset({Dimension.AGENT, Dimension.TIME})
        assert result.report.honoured == frozenset()

    async def test_read_receives_narrowed_scope(self) -> None:
        registry = SignalRegistry()
        seen: list[Scope] = []

        async def _probe(scope: Scope) -> dict[str, object]:
            seen.append(scope)
            return {"ok": True}

        # Register under an org-wide declared id; the read must never see agent/time.
        registry.register("refusal", _probe)
        await registry.read("refusal", Scope(agent_id="support", at="2026-06-12T10:00:00Z"))
        assert seen[0].agent_id is None
        assert seen[0].at is None


class TestHonestDegradation:
    async def test_unavailable_backend_yields_empty_not_fabricated(self) -> None:
        registry = SignalRegistry()

        async def _down(_scope: Scope) -> dict[str, object]:
            raise SpineUnavailableError("langfuse down")

        registry.register("traces", _down)
        result = await registry.read("traces", Scope())
        assert result.data is None
        assert result.report.unavailable is True

    async def test_slow_signal_times_out_to_unavailable(self) -> None:
        import asyncio

        registry = SignalRegistry()

        async def _slow(_scope: Scope) -> dict[str, object]:
            await asyncio.sleep(1.0)
            return {"never": "returned"}

        registry.register("traces", _slow)
        result = await registry.read("traces", Scope(), timeout_s=0.02)
        assert result.data is None
        assert result.report.unavailable is True

    async def test_unexpected_error_degrades_one_signal_not_the_read(self) -> None:
        registry = SignalRegistry()

        async def _bug(_scope: Scope) -> dict[str, object]:
            raise ValueError("boom")

        registry.register("traces", _bug)
        result = await registry.read("traces", Scope())
        assert result.data is None
        assert result.report.unavailable is True


def test_every_declared_capability_has_a_stable_id() -> None:
    # The registry table and the id->capability map agree (no dangling declaration).
    assert all(cap.id == signal_id for signal_id, cap in CAPABILITIES.items())
