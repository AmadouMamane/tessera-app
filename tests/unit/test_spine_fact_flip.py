"""G4 — per-fact flip, dynamic source badges, owned-store erasure, backfill key (offline).

Locks the flip machinery the amendments require: a fact graduates jsonl→spine
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
    def test_defaults_to_the_global_source(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.delenv("TESSERA_SPINE_SOURCE", raising=False)
        monkeypatch.delenv("TESSERA_SPINE_SOURCE_SCORES", raising=False)
        assert fact_source("scores") == "jsonl"
        monkeypatch.setenv("TESSERA_SPINE_SOURCE", "shadow")
        assert fact_source("scores") == "shadow"

    def test_flippable_fact_honours_its_override(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.delenv("TESSERA_SPINE_SOURCE", raising=False)
        monkeypatch.setenv("TESSERA_SPINE_SOURCE_SCORES", "spine")
        assert fact_source("scores") == "spine"
        assert fact_source("gating") == "jsonl"  # untouched fact stays on the global

    def test_invalid_override_falls_back_to_global(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.delenv("TESSERA_SPINE_SOURCE", raising=False)
        monkeypatch.setenv("TESSERA_SPINE_SOURCE_SCORES", "bogus")
        assert fact_source("scores") == "jsonl"

    def test_non_flippable_fact_ignores_overrides(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        # bundles is lossy-by-design in the spine; audit is the carve-out — no override.
        monkeypatch.delenv("TESSERA_SPINE_SOURCE", raising=False)
        monkeypatch.setenv("TESSERA_SPINE_SOURCE_BUNDLES", "spine")
        assert fact_source("bundles") == "jsonl"


class TestFactRouter:
    def test_routes_each_fact_to_its_active_source(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.delenv("TESSERA_SPINE_SOURCE", raising=False)
        monkeypatch.setenv("TESSERA_SPINE_SOURCE_SCORES", "spine")
        current = FakeSpineReader(
            scores=[{"metric": "from-jsonl"}], gating=[{"run_id": "from-jsonl"}]
        )
        spine = FakeSpineReader(
            scores=[{"metric": "from-owned"}], gating=[{"run_id": "from-owned"}]
        )
        router = FactRouter(current, spine, shadow=FakeSpineReader())
        assert router.scores(Scope())[0]["metric"] == "from-owned"  # flipped fact
        assert router.gating_scores(Scope())[0]["run_id"] == "from-jsonl"  # not flipped
        assert router.bundles(Scope()) == []  # global jsonl → current
        assert router.audit_entries(Scope()) == []  # always local

    def test_factory_builds_a_router_when_a_fact_is_overridden(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.delenv("TESSERA_SPINE_SOURCE", raising=False)
        monkeypatch.setenv("TESSERA_SPINE_SOURCE_GATING", "shadow")
        set_reader(None)
        try:
            assert isinstance(get_reader(), FactRouter)
        finally:
            set_reader(None)

    def test_factory_stays_legacy_without_overrides(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.delenv("TESSERA_SPINE_SOURCE", raising=False)
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
        set_reader(FakeSpineReader(scores=[]))
        try:
            result = await get_registry().read("scores", Scope())
            assert result.report.source == "spine"  # the flip is visible, never stale
            gating = await get_registry().read("gating", Scope())
            assert gating.report.source == "jsonl"  # unflipped fact stays honest too
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
