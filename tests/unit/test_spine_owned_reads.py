"""G3 — the spine reads the owned stores (ADR 0015 §Amend.1-2 + §Corr.2b), offline.

Locks: the ClickHouse read maps rows back to the exact jsonl shape (as-of-T pushed into
bound params; live mode mirrors the ring's org-wide-cut-then-filter semantics), the
file-archive gating reader dedups ``latest_<agent>.json`` against its timestamped twin,
the shadow reader records a ``gating`` divergence fact, and the ``gating`` snapshot
signal summarises runs without dumping the socle. Live reads are contract-tested.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from tessera.observability import metrics

if TYPE_CHECKING:
    from pathlib import Path
from tessera.observability.spine.adapters.clickhouse import ClickHouseAdapter, ClickHouseConfig
from tessera.observability.spine.adapters.current import CurrentStoresReader
from tessera.observability.spine.adapters.fake import FakeSpineReader
from tessera.observability.spine.adapters.shadow import ShadowReader
from tessera.observability.spine.scope import Scope


def _adapter() -> ClickHouseAdapter:
    return ClickHouseAdapter(
        ClickHouseConfig(
            url="http://localhost:1",
            user="u",
            password="p",  # noqa: S106 — synthetic offline credential
            database="tessera",
        )
    )


_CH_ROW = (
    '{"scored_at":"2026-07-02 16:01:25.317","metric":"faithfulness","score":0.8,'
    '"language":"fr","judge_model":"llama3.2:3b","conversation_id":"conv-1",'
    '"trace_id":"t1","sampled":0,"agent_id":"support-client","model":"llama3.2:3b"}'
)


class TestClickHouseOnlineRead:
    def test_asof_read_binds_params_and_maps_the_jsonl_shape(self) -> None:
        adapter = _adapter()
        seen: list[tuple[str, dict[str, str] | None]] = []

        def _execute(
            query: str, *, data: bytes | None = None, params: dict[str, str] | None = None
        ) -> str:
            seen.append((query, params))
            return _CH_ROW + "\n"

        adapter.execute = _execute  # type: ignore[method-assign]
        rows = adapter.online_scores(
            Scope(agent_id="support-client", at="2026-07-03T00:00:00+00:00", language="fr")
        )
        query, params = seen[0]
        assert "scored_at <= {at:DateTime64(3)}" in query  # as-of-T pushed to the store
        assert "agent_id = {agent:String}" in query
        assert params == {
            "at": "2026-07-03 00:00:00.000",
            "agent": "support-client",
            "language": "fr",
        }
        row = rows[0]
        assert row["scored_at"] == "2026-07-02T16:01:25.317+00:00"  # ISO reconstructed
        assert row["sampled"] is False  # UInt8 0 → bool (flagged turn)
        assert row["metric"] == "faithfulness"
        assert row["agent_id"] == "support-client"

    def test_live_read_mirrors_the_ring_cut_then_filters(self) -> None:
        # No `at`: the query takes the LAST 200 rows org-wide (the ring semantics) and the
        # dimension filter applies after the cut — parity with recent_scores by design.
        adapter = _adapter()
        other = _CH_ROW.replace("support-client", "someone-else")
        adapter.execute = (  # type: ignore[method-assign]
            lambda *_args, **_kwargs: other + "\n" + _CH_ROW + "\n"
        )
        rows = adapter.online_scores(Scope(agent_id="support-client"))
        assert len(rows) == 1
        assert rows[0]["agent_id"] == "support-client"

    def test_unattributed_marker_maps_back_to_none(self) -> None:
        adapter = _adapter()
        bare = (
            '{"scored_at":"2026-07-02 16:01:25.317","metric":"m","score":1.0,"language":"",'
            '"judge_model":"","conversation_id":"","trace_id":"","sampled":1,"agent_id":"",'
            '"model":""}'
        )
        adapter.execute = lambda *_args, **_kwargs: bare  # type: ignore[method-assign]
        row = adapter.online_scores(Scope())[0]
        assert row["agent_id"] is None  # "" is the unattributed marker, never an invention
        assert row["model"] is None
        assert row["sampled"] is True


def _report_payload(run_at: str, agent: str) -> str:
    return json.dumps(
        {
            "run_at": run_at,
            "agent_id": agent,
            "model": "llama3.2:3b",
            "catalogue_version": "v1",
            "results": [
                {"case_id": "01", "language": "fr", "passed": True},
                {"case_id": "02", "language": "de", "passed": False},
            ],
        }
    )


class TestCurrentGatingArchive:
    def test_reads_dedups_and_filters_the_archive(self, tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setenv("TESSERA_REPORTS_DIR", str(tmp_path))
        (tmp_path / "20260601T000000Z_support.json").write_text(
            _report_payload("20260601T000000Z", "support"), encoding="utf-8"
        )
        # latest_<agent>.json duplicates the timestamped archive — one run, not two.
        (tmp_path / "latest_support.json").write_text(
            _report_payload("20260601T000000Z", "support"), encoding="utf-8"
        )
        (tmp_path / "20260610T000000Z_onboarding.json").write_text(
            _report_payload("20260610T000000Z", "onboarding"), encoding="utf-8"
        )
        reader = CurrentStoresReader()
        rows = reader.gating_scores(Scope())
        assert len(rows) == 4  # 2 runs x 2 cases — the latest twin deduped away
        support = reader.gating_scores(Scope(agent_id="support"))
        assert {r["run_id"] for r in support} == {"20260601T000000Z_support"}
        asof = reader.gating_scores(Scope(at="2026-06-05T00:00:00+00:00"))
        assert {r["run_id"] for r in asof} == {"20260601T000000Z_support"}  # as-of-T honours
        french = reader.gating_scores(Scope(language="fr"))
        assert all(r["language"] == "fr" for r in french) and len(french) == 2

    def test_agentless_catalogue_reports_yield_nothing(self, tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setenv("TESSERA_REPORTS_DIR", str(tmp_path))
        payload = json.loads(_report_payload("20260601T000000Z", "x"))
        payload["agent_id"] = None
        (tmp_path / "20260601T000000Z.json").write_text(json.dumps(payload), encoding="utf-8")
        assert CurrentStoresReader().gating_scores(Scope()) == []


class TestShadowGating:
    def test_gating_divergence_is_recorded_with_its_own_fact(self) -> None:
        gating_row = {
            "run_id": "r1",
            "agent_id": "support",
            "scored_at": "2026-06-01T00:00:00+00:00",
        }
        reader = ShadowReader(FakeSpineReader(gating=[gating_row]), FakeSpineReader(gating=[]))
        served = reader.gating_scores(Scope())
        assert len(served) == 1  # the archive is served, never the lagging table
        sample = metrics.registry.get_sample_value(
            "tessera_spine_shadow_divergence_total", {"fact": "gating", "result": "diverge"}
        )
        assert sample is not None and sample >= 1.0


class TestGatingSignal:
    async def test_summarises_runs_without_dumping_rows(self) -> None:
        from tessera.observability.spine.context import SnapshotContext, bind_context, reset_context
        from tessera.observability.spine.signals import _read_gating

        rows = [
            {
                "run_id": "r1",
                "agent_id": "support",
                "passed": True,
                "scored_at": "2026-06-01T00:00:00+00:00",
            },
            {
                "run_id": "r1",
                "agent_id": "support",
                "passed": False,
                "scored_at": "2026-06-01T00:00:01+00:00",
            },
            {
                "run_id": "r2",
                "agent_id": "support",
                "passed": True,
                "scored_at": "2026-06-02T00:00:00+00:00",
            },
        ]
        token = bind_context(SnapshotContext(FakeSpineReader(gating=rows)))
        try:
            data = await _read_gating(Scope())
        finally:
            reset_context(token)
        assert data["row_count"] == 3
        assert data["run_count"] == 2
        latest = data["latest_run"]
        assert isinstance(latest, dict)
        assert latest["run_id"] == "r2"  # newest by scored_at
        assert latest["passed"] == 1 and latest["total"] == 1
