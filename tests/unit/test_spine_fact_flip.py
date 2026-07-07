"""G4 — per-fact flip, dynamic source badges, owned-store erasure, backfill key (offline).

Locks the flip machinery the amendments require: a fact graduates local→spine
independently (``TESSERA_SPINE_SOURCE_<FACT>``), the signal's reported ``source`` is
resolved from the fact's ACTIVE source at read time (a flipped signal is visibly
flipped), GDPR erasure reaches the owned ClickHouse store (count-then-delete, bound
params, deferred-never-faked), and the backfill's dedup key collapses to the store's
millisecond precision so a re-run inserts nothing.
"""

from __future__ import annotations

from tessera.observability import erasure
from tessera.observability.clickhouse_scores import online_row_key
from tessera.observability.spine.adapters import (
    CurrentStoresReader,
    FactRouter,
    FakeSpineReader,
    fact_source,
    get_reader,
    set_reader,
)
from tessera.observability.spine.adapters.clickhouse import ClickHouseAdapter, ClickHouseConfig
from tessera.observability.spine.scope import Scope


class TestFactSource:
    def test_flippable_facts_default_to_the_owned_stores_since_g5(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        # G5 (flip + bake held): with NO env at all, the owned stores are the system of
        # record; an EXPLICIT global source remains the operator escape hatch.
        monkeypatch.delenv("TESSERA_SPINE_SOURCE", raising=False)
        monkeypatch.delenv("TESSERA_SPINE_SOURCE_SCORES", raising=False)
        assert fact_source("scores") == "spine"
        assert fact_source("gating") == "spine"
        monkeypatch.setenv("TESSERA_SPINE_SOURCE", "shadow")
        assert fact_source("scores") == "shadow"
        monkeypatch.setenv("TESSERA_SPINE_SOURCE", "local")  # the degraded fallback, explicit
        assert fact_source("scores") == "local"

    def test_flippable_fact_honours_its_override(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.delenv("TESSERA_SPINE_SOURCE", raising=False)
        monkeypatch.setenv("TESSERA_SPINE_SOURCE_SCORES", "local")
        assert fact_source("scores") == "local"  # per-fact override wins over the default
        assert fact_source("gating") == "spine"  # untouched fact keeps the G5 default

    def test_invalid_override_falls_back_to_the_default_chain(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.delenv("TESSERA_SPINE_SOURCE", raising=False)
        monkeypatch.setenv("TESSERA_SPINE_SOURCE_SCORES", "bogus")
        assert fact_source("scores") == "spine"

    def test_non_flippable_fact_ignores_overrides(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        # bundles is lossy-by-design in the spine; audit is the carve-out — no override.
        monkeypatch.delenv("TESSERA_SPINE_SOURCE", raising=False)
        monkeypatch.setenv("TESSERA_SPINE_SOURCE_BUNDLES", "spine")
        assert fact_source("bundles") == "local"

    def test_business_events_is_flippable_and_defaults_to_spine(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        # Step 4 lot 2: business_events finished its bake and now follows the owned store
        # by default; local remains the explicit degraded fallback.
        monkeypatch.delenv("TESSERA_SPINE_SOURCE", raising=False)
        monkeypatch.delenv("TESSERA_SPINE_SOURCE_BUSINESS_EVENTS", raising=False)
        assert fact_source("business_events") == "spine"
        monkeypatch.setenv("TESSERA_SPINE_SOURCE_BUSINESS_EVENTS", "local")
        assert fact_source("business_events") == "local"


class TestFactRouter:
    def test_routes_each_fact_to_its_active_source(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.delenv("TESSERA_SPINE_SOURCE", raising=False)
        monkeypatch.setenv("TESSERA_SPINE_SOURCE_SCORES", "spine")
        monkeypatch.setenv("TESSERA_SPINE_SOURCE_GATING", "local")  # explicit legacy contrast
        current = FakeSpineReader(
            scores=[{"metric": "from-local"}], gating=[{"run_id": "from-local"}]
        )
        spine = FakeSpineReader(
            scores=[{"metric": "from-owned"}], gating=[{"run_id": "from-owned"}]
        )
        router = FactRouter(current, spine, shadow=FakeSpineReader())
        assert router.scores(Scope())[0]["metric"] == "from-owned"  # flipped fact
        assert router.gating_scores(Scope())[0]["run_id"] == "from-local"  # not flipped
        assert router.bundles(Scope()) == []  # global local → current
        assert router.audit_entries(Scope()) == []  # always local

    def test_factory_builds_a_router_when_a_fact_is_overridden(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.delenv("TESSERA_SPINE_SOURCE", raising=False)
        monkeypatch.setenv("TESSERA_SPINE_SOURCE_GATING", "shadow")
        set_reader(None)
        try:
            assert isinstance(get_reader(), FactRouter)
        finally:
            set_reader(None)

    def test_factory_defaults_to_the_router_since_g5(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        # No env at all → the per-fact router (scores/gating on the owned stores).
        monkeypatch.delenv("TESSERA_SPINE_SOURCE", raising=False)
        monkeypatch.delenv("TESSERA_SPINE_SOURCE_SCORES", raising=False)
        monkeypatch.delenv("TESSERA_SPINE_SOURCE_GATING", raising=False)
        set_reader(None)
        try:
            assert isinstance(get_reader(), FactRouter)
        finally:
            set_reader(None)

    def test_explicit_global_local_is_the_legacy_escape_hatch(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setenv("TESSERA_SPINE_SOURCE", "local")
        monkeypatch.delenv("TESSERA_SPINE_SOURCE_SCORES", raising=False)
        monkeypatch.delenv("TESSERA_SPINE_SOURCE_GATING", raising=False)
        set_reader(None)
        try:
            assert isinstance(get_reader(), CurrentStoresReader)
        finally:
            set_reader(None)


class TestDynamicSourceBadge:
    async def test_fact_backed_signal_reports_its_active_source(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        from tessera.observability.spine.registry import get_registry

        monkeypatch.delenv("TESSERA_SPINE_SOURCE", raising=False)
        monkeypatch.setenv("TESSERA_SPINE_SOURCE_SCORES", "spine")
        monkeypatch.setenv("TESSERA_SPINE_SOURCE_GATING", "local")  # explicit legacy pin
        set_reader(FakeSpineReader(scores=[]))
        try:
            result = await get_registry().read("scores", Scope())
            assert result.report.source == "spine"  # the flip is visible, never stale
            gating = await get_registry().read("gating", Scope())
            assert gating.report.source == "local"  # the pinned-legacy fact says so honestly
        finally:
            set_reader(None)


class TestOwnedStoreErasure:
    def test_delete_conversation_counts_then_deletes_with_bound_params(self) -> None:
        adapter = ClickHouseAdapter(
            ClickHouseConfig(
                url="http://localhost:1",
                user="u",
                password="p",  # noqa: S106 — synthetic offline credential
                database="tessera",
            )
        )
        calls: list[tuple[str, dict[str, str] | None]] = []

        def _execute(
            query: str, *, data: bytes | None = None, params: dict[str, str] | None = None
        ) -> str:
            calls.append((query, params))
            return "2\n" if query.startswith("SELECT") else ""

        adapter.execute = _execute  # type: ignore[method-assign]
        assert adapter.delete_conversation("conv-9") == 2
        assert len(calls) == 2
        assert calls[0][0].startswith("SELECT count()")
        assert calls[1][0].startswith("DELETE FROM tessera.eval_online_scores")
        assert calls[0][1] == {"conv": "conv-9"} == calls[1][1]  # value bound, never inline

    def test_delete_conversation_zero_rows_skips_the_delete(self) -> None:
        adapter = ClickHouseAdapter(
            ClickHouseConfig(
                url="http://localhost:1",
                user="u",
                password="p",  # noqa: S106 — synthetic offline credential
                database="tessera",
            )
        )
        calls: list[str] = []
        adapter.execute = (  # type: ignore[method-assign]
            lambda query, *_args, **_kwargs: calls.append(query) or "0\n"
        )
        assert adapter.delete_conversation("unknown") == 0
        assert len(calls) == 1  # count only — no pointless mutation

    def test_purge_owned_scores_defers_when_unreachable(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        from tessera.observability.spine.adapters.base import SpineUnavailableError

        def _down(conversation_id: str) -> int:
            raise SpineUnavailableError("down")

        monkeypatch.setattr(erasure, "_owned_scores_delete", _down)
        deleted, reached = erasure.purge_owned_scores("conv-1")
        assert deleted == 0
        assert reached is False  # deferred and reported — never faked

    def test_purge_telemetry_folds_the_owned_leg(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setattr(erasure.replay_mod, "purge_conversation", lambda _c: 1)
        monkeypatch.setattr(erasure.scores_mod, "purge_conversation", lambda _c: 3)
        monkeypatch.setattr(erasure, "_owned_scores_delete", lambda _c: 3)
        monkeypatch.setattr(erasure, "_spine_delete", lambda _c: 2)
        fp = erasure.purge_telemetry("conv-1")
        assert fp.n_owned_scores == 3
        assert fp.owned_reached is True
        assert fp.n_spine == 2


class TestBackfillKey:
    def test_key_truncates_to_store_precision_and_is_stable(self) -> None:
        row = {
            "scored_at": "2026-07-02T16:01:25.317934+00:00",
            "metric": "faithfulness",
            "conversation_id": "conv-1",
            "trace_id": "t1",
        }
        key = online_row_key(row)
        assert key == ("2026-07-02 16:01:25.317", "faithfulness", "conv-1", "t1")
        assert key == online_row_key(dict(row))  # stable across calls

    def test_row_without_instant_has_no_key(self) -> None:
        assert online_row_key({"metric": "m"}) is None

    def test_backfill_inserts_exactly_the_difference(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        from scripts.backfill_owned_scores import backfill_online

        jsonl_rows = [
            {  # already in the store (same key at ms precision)
                "scored_at": "2026-07-02T16:01:25.317934+00:00",
                "metric": "faithfulness",
                "score": 0.8,
                "conversation_id": "conv-1",
                "trace_id": "t1",
                "sampled": False,
            },
            {  # missing → must be inserted
                "scored_at": "2026-07-02T16:01:28.570000+00:00",
                "metric": "grounding",
                "score": 0.8,
                "conversation_id": "conv-1",
                "trace_id": "t1",
                "sampled": False,
            },
        ]
        monkeypatch.setattr("scripts.backfill_owned_scores.persisted_scores", lambda: jsonl_rows)

        inserts: list[bytes] = []

        class _StubAdapter:
            table = "tessera.eval_online_scores"

            def ensure_schema(self) -> None:
                pass

            def execute(
                self, query: str, *, data: bytes | None = None, params: dict[str, str] | None = None
            ) -> str:
                if query.startswith("SELECT"):
                    return (
                        '{"scored_at":"2026-07-02 16:01:25.317","metric":"faithfulness",'
                        '"conversation_id":"conv-1","trace_id":"t1"}\n'
                    )
                assert data is not None
                inserts.append(data)
                return ""

        total, inserted, skipped = backfill_online(_StubAdapter())  # type: ignore[arg-type]
        assert (total, inserted, skipped) == (2, 1, 0)
        assert b"grounding" in inserts[0] and b"faithfulness" not in inserts[0]
