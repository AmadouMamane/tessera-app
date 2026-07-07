"""Phase C — spine read adapters + shadow-run (ADR 0015 §Migration C), offline.

Locks the pure/offline behaviour: PromQL selector building, Langfuse metadata/limit handling,
the Langfuse->row / trace->bundle mapping in the spine reader, the source-flag factory, and the
shadow reader (serve local, record divergence). The *live* reads are covered by the
integration-tagged contract tests; nothing here touches the network.
"""

from __future__ import annotations

from tessera.observability import metrics
from tessera.observability.spine.adapters import (
    CurrentStoresReader,
    FakeSpineReader,
    set_reader,
    spine_source,
)
from tessera.observability.spine.adapters.langfuse import LangfuseAdapter, _matches_agent
from tessera.observability.spine.adapters.prometheus import PrometheusAdapter
from tessera.observability.spine.adapters.shadow import ShadowReader
from tessera.observability.spine.adapters.spine import SpineStoresReader
from tessera.observability.spine.scope import Scope


class _StubLangfuse:
    """A LangfuseAdapter stand-in returning canned rows (no network)."""

    def __init__(self, scores: list[dict[str, object]], traces: list[dict[str, object]]) -> None:
        self._scores = scores
        self._traces = traces

    def scores_by_metadata(self, scope: Scope, *, limit: int = 100) -> list[dict[str, object]]:
        return self._scores

    def traces(self, scope: Scope, *, limit: int = 100) -> list[dict[str, object]]:
        return self._traces


class TestPrometheusSelector:
    def test_org_scope_is_match_all(self) -> None:
        assert PrometheusAdapter().selector(Scope()) == ""

    def test_agent_and_language_render_a_label_selector(self) -> None:
        selector = PrometheusAdapter().selector(Scope(agent_id="support", language="fr"))
        assert selector == '{agent_id="support",language="fr"}'

    def test_quotes_are_escaped(self) -> None:
        assert PrometheusAdapter().selector(Scope(agent_id='a"b')) == '{agent_id="a\\"b"}'


class TestLangfuseHelpers:
    def test_matches_agent_org_matches_all(self) -> None:
        assert _matches_agent({"agent_id": "x"}, None) is True
        assert _matches_agent(None, None) is True

    def test_matches_agent_scoped(self) -> None:
        assert _matches_agent({"agent_id": "support"}, "support") is True
        assert _matches_agent({"tessera.agent_id": "support"}, "support") is True
        assert _matches_agent({"agent_id": "other"}, "support") is False
        assert _matches_agent(None, "support") is False

    def test_config_from_env_defaults(self) -> None:
        config = LangfuseAdapter().config
        assert config.host.startswith("http")
        assert config.public_key


class TestLangfuseDeletion:
    """The GDPR erasure primitive (ADR 0015 §Migration D), offline via stubbed HTTP."""

    def test_delete_conversation_deletes_found_traces(self) -> None:
        adapter = LangfuseAdapter()
        deleted: list[dict[str, object]] = []
        # Stub the two HTTP legs: session lookup returns two traces; delete records the body.
        adapter._get = lambda _path, _params: {  # type: ignore[method-assign]
            "data": [{"id": "t1"}, {"id": "t2"}]
        }
        adapter._delete = lambda _path, body: deleted.append(body)  # type: ignore[method-assign]
        assert adapter.delete_conversation("conv-1") == 2
        assert deleted == [{"traceIds": ["t1", "t2"]}]

    def test_delete_conversation_no_traces_is_noop(self) -> None:
        adapter = LangfuseAdapter()
        called: list[str] = []
        adapter._get = lambda _path, _params: {"data": []}  # type: ignore[method-assign]
        adapter._delete = lambda _path, _body: called.append("delete")  # type: ignore[method-assign]
        assert adapter.delete_conversation("absent") == 0
        assert called == []  # nothing to erase → the DELETE leg never fires

    def test_delete_conversation_empty_id_is_noop(self) -> None:
        adapter = LangfuseAdapter()
        called: list[str] = []
        adapter._get = lambda _path, _params: called.append("get") or {}  # type: ignore[method-assign]
        assert adapter.delete_conversation("") == 0
        assert called == []  # an empty subject id never even queries


class TestSpineReaderMapping:
    def test_scores_read_the_owned_clickhouse_store_not_langfuse(self) -> None:
        # §Amendment 1 + §Correction 2b: the spine's score rows come from the owned
        # ClickHouse table; Langfuse is never consulted for a score.
        class _StubClickHouse:
            def online_scores(self, scope: Scope) -> list[dict[str, object]]:
                return [{"metric": "faithfulness", "score": 0.9, "agent_id": "support"}]

        class _NeverLangfuse:
            def scores_by_metadata(
                self, scope: Scope, *, limit: int = 100
            ) -> list[dict[str, object]]:
                raise AssertionError("Langfuse must not be read for scores (§Amendment 1)")

        reader = SpineStoresReader(
            clickhouse=_StubClickHouse(),  # type: ignore[arg-type]
            langfuse=_NeverLangfuse(),  # type: ignore[arg-type]
        )
        rows = reader.scores(Scope())
        assert rows == [{"metric": "faithfulness", "score": 0.9, "agent_id": "support"}]

    def test_gating_reads_the_owned_postgres_porteur(self) -> None:
        class _StubPostgres:
            def gating_scores(self, scope: Scope) -> list[dict[str, object]]:
                return [{"run_id": "r1", "case_id": "c1", "passed": True}]

        reader = SpineStoresReader(postgres=_StubPostgres())  # type: ignore[arg-type]
        assert reader.gating_scores(Scope())[0]["run_id"] == "r1"

    def test_bundles_map_from_traces_lossy_but_shaped(self) -> None:
        reader = SpineStoresReader(
            langfuse=_StubLangfuse(  # type: ignore[arg-type]
                scores=[],
                traces=[
                    {
                        "id": "trace-1",
                        "timestamp": "2026-06-10T00:00:00Z",
                        "sessionId": "conv-1",
                        "input": "Quel est mon solde ?",
                        "output": "100 EUR",
                        "metadata": {"agent_id": "recouvrement", "language": "fr", "model": "m"},
                    }
                ],
            )
        )
        bundle = reader.bundles(Scope())[0]
        assert bundle.bundle_id == "trace-1"
        assert bundle.conversation_id == "conv-1"
        assert bundle.question == "Quel est mon solde ?"
        assert bundle.agent_id == "recouvrement"
        assert bundle.context == ""  # content-capture gated → intentionally empty (shadow-only)

    def test_audit_entries_read_the_local_ledger(self) -> None:
        import json

        from tessera.settings import get_settings

        # The conftest autouse fixture already points guard.audit_file at a per-test tmp file;
        # its parent (the env-isolated state dir) may not be materialised yet in a bare run.
        log = get_settings().guard.audit_file
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(
            json.dumps({"type": "tessera.guard.audit", "target": "t", "agent_id": "support"})
            + "\n",
            encoding="utf-8",
        )
        reader = SpineStoresReader(langfuse=_StubLangfuse([], []))  # type: ignore[arg-type]
        entries = reader.audit_entries(Scope())
        assert len(entries) == 1


class TestShadowReader:
    def test_serves_primary_and_records_divergence(self) -> None:
        primary = FakeSpineReader(
            scores=[
                {"metric": "faithfulness", "score": 0.9, "scored_at": "2026-06-01T00:00:00+00:00"}
            ]
        )
        shadow = FakeSpineReader(scores=[])
        reader = ShadowReader(primary, shadow)
        served = reader.scores(Scope())
        assert len(served) == 1  # local is served, never the empty spine
        sample = metrics.registry.get_sample_value(
            "tessera_spine_shadow_divergence_total", {"fact": "scores", "result": "diverge"}
        )
        assert sample is not None and sample >= 1.0

    def test_unavailable_spine_records_unavailable_not_crash(self) -> None:
        from tessera.observability.spine.adapters.base import SpineUnavailableError

        class _Down:
            def scores(self, scope: Scope) -> list[dict[str, object]]:
                raise SpineUnavailableError("down")

            def bundles(self, scope: Scope) -> list[object]:
                raise SpineUnavailableError("down")

            def audit_entries(self, scope: Scope) -> list[dict[str, object]]:
                return []

        primary = FakeSpineReader(scores=[{"metric": "x", "score": 1.0, "scored_at": "t"}])
        reader = ShadowReader(primary, _Down())  # type: ignore[arg-type]
        assert len(reader.scores(Scope())) == 1  # still served from local
        sample = metrics.registry.get_sample_value(
            "tessera_spine_shadow_divergence_total", {"fact": "scores", "result": "unavailable"}
        )
        assert sample is not None and sample >= 1.0


class TestSourceFactory:
    def test_default_is_local(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.delenv("TESSERA_SPINE_SOURCE", raising=False)
        assert spine_source() == "local"

    def test_source_selects_reader(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        from tessera.observability.spine.adapters import get_reader

        for value, expected in (
            ("local", CurrentStoresReader),
            ("jsonl", CurrentStoresReader),
            ("spine", SpineStoresReader),
            ("shadow", ShadowReader),
        ):
            monkeypatch.setenv("TESSERA_SPINE_SOURCE", value)
            set_reader(None)
            assert isinstance(get_reader(), expected)
        set_reader(None)

    def test_unknown_source_falls_back_to_local(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setenv("TESSERA_SPINE_SOURCE", "bogus")
        assert spine_source() == "local"
