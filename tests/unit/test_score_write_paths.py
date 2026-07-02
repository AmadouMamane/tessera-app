"""G2 — the owned score write paths (ADR 0015 §Amend.2 + §Corr.2b), offline.

Locks the two write legs to the amendments: online rows → direct ClickHouse insert (the
JSONEachRow mapping, the hermetic off-switch, the best-effort failure mode) and gating
rows → Postgres porteur (the pure report→rows builder, the run identity, the non-release
exclusion) + the session-anchored SDK mirror (stubbed — never a network call here). The
durable inserts against real backends are covered by the integration contract tests.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from tessera.observability import clickhouse_scores, langfuse_scores
from tessera.observability.eval.gating_scores import (
    GATING_METRIC,
    GatingScoreRow,
    gating_rows_from_report,
)


def _jsonl_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "scored_at": "2026-07-02T10:20:30.123456+00:00",
        "metric": "faithfulness",
        "score": 0.86,
        "language": "fr",
        "judge_model": "llama3.2:3b",
        "conversation_id": "conv-1",
        "trace_id": "t" * 32,
        "sampled": True,
        "agent_id": "support-client",
        "model": "llama3.2:3b",
    }
    row.update(overrides)
    return row


class TestOnlineScoreLine:
    def test_maps_the_jsonl_row_onto_the_correction_2b_columns(self) -> None:
        line = clickhouse_scores.online_score_line(_jsonl_row())
        assert line is not None
        payload = json.loads(line)
        assert payload["scored_at"] == "2026-07-02 10:20:30.123"  # DateTime64(3), UTC
        assert payload["metric"] == "faithfulness"
        assert payload["score"] == 0.86
        assert payload["sampled"] == 1
        assert payload["agent_id"] == "support-client"
        assert payload["trace_id"] == "t" * 32

    def test_flagged_turn_maps_sampled_zero(self) -> None:
        line = clickhouse_scores.online_score_line(_jsonl_row(sampled=False))
        assert line is not None
        assert json.loads(line)["sampled"] == 0  # 0 = flagged (always judged)

    def test_unattributed_dimensions_become_empty_strings_not_fabrications(self) -> None:
        line = clickhouse_scores.online_score_line(
            _jsonl_row(agent_id=None, model=None, trace_id=None, conversation_id=None)
        )
        assert line is not None
        payload = json.loads(line)
        assert payload["agent_id"] == ""
        assert payload["model"] == ""
        assert payload["trace_id"] == ""

    def test_row_without_instant_is_skipped_never_stamped(self) -> None:
        assert clickhouse_scores.online_score_line(_jsonl_row(scored_at=None)) is None
        assert clickhouse_scores.online_score_line(_jsonl_row(scored_at="not-a-date")) is None

    def test_naive_timestamps_are_read_as_utc(self) -> None:
        line = clickhouse_scores.online_score_line(_jsonl_row(scored_at="2026-07-02T10:00:00"))
        assert line is not None
        assert json.loads(line)["scored_at"] == "2026-07-02 10:00:00.000"


class TestRecordOnlineScore:
    def test_disabled_records_nothing(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        # The unit conftest already disables the insert; assert the gate actually holds.
        spawned: list[object] = []
        monkeypatch.setattr(
            clickhouse_scores.threading,
            "Thread",
            lambda **kwargs: spawned.append(kwargs),
        )
        clickhouse_scores.record_online_score(_jsonl_row())
        assert spawned == []

    def test_enabled_inserts_via_the_owned_table(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setenv("TESSERA_CLICKHOUSE_SCORES", "1")

        class _ImmediateThread:
            def __init__(self, target: object, args: tuple[object, ...], daemon: bool) -> None:
                self._target = target
                self._args = args

            def start(self) -> None:
                self._target(*self._args)  # type: ignore[operator]

        executed: list[tuple[str, bytes | None]] = []

        class _StubAdapter:
            table = "tessera.eval_online_scores"

            def ensure_schema(self) -> None:
                executed.append(("ensure", None))

            def execute(self, query: str, *, data: bytes | None = None) -> str:
                executed.append((query, data))
                return ""

        monkeypatch.setattr(clickhouse_scores.threading, "Thread", _ImmediateThread)
        monkeypatch.setattr(clickhouse_scores, "_get_adapter", lambda: _StubAdapter())
        clickhouse_scores.record_online_score(_jsonl_row())
        assert len(executed) == 1
        query, data = executed[0]
        assert query == "INSERT INTO tessera.eval_online_scores FORMAT JSONEachRow"
        assert data is not None and json.loads(data)["metric"] == "faithfulness"

    def test_unreachable_store_is_swallowed_not_raised(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        from tessera.observability.spine.adapters.base import SpineUnavailableError

        def _down() -> object:
            raise SpineUnavailableError("down")

        monkeypatch.setattr(clickhouse_scores, "_get_adapter", _down)
        line = clickhouse_scores.online_score_line(_jsonl_row())
        assert line is not None
        clickhouse_scores._insert(line)  # must not raise — best-effort leg


class TestGatingRowsFromReport:
    def _report(self, **overrides: object) -> dict[str, object]:
        report: dict[str, object] = {
            "run_at": "20260620T143510Z",
            "agent_id": "support-client",
            "model": "llama3.2:3b",
            "catalogue_version": "63-071edbdc",
            "results": [
                {
                    "case_id": "01_prompt_injection",
                    "language": "fr",
                    "passed": True,
                    "ended_at": "2026-06-20T14:35:10.819153+00:00",
                },
                {
                    "case_id": "02_pii_leak",
                    "language": "de",
                    "passed": False,
                    "ended_at": "2026-06-20T14:35:11.100000+00:00",
                },
            ],
        }
        report.update(overrides)
        return report

    def test_release_run_maps_to_per_case_rows(self) -> None:
        rows = gating_rows_from_report(self._report())
        assert len(rows) == 2
        first = rows[0]
        assert first.run_id == "20260620T143510Z_support-client"
        assert first.metric == GATING_METRIC
        assert first.score == 1.0 and first.passed is True
        assert rows[1].score == 0.0 and rows[1].passed is False
        assert first.scored_at == datetime(2026, 6, 20, 14, 35, 10, 819153, tzinfo=UTC)
        assert first.judge_model is None  # deterministic harness — no LLM judge

    def test_catalogue_wide_run_produces_no_gating_rows(self) -> None:
        # agent_id None (the archived catalogue probes): not the release socle — no rows,
        # never a fabricated attribution.
        assert gating_rows_from_report(self._report(agent_id=None)) == []

    def test_missing_ended_at_falls_back_to_the_run_stamp(self) -> None:
        report = self._report(
            results=[{"case_id": "01", "language": "fr", "passed": True}],
        )
        rows = gating_rows_from_report(report)
        assert rows[0].scored_at == datetime(2026, 6, 20, 14, 35, 10, tzinfo=UTC)

    def test_malformed_results_are_skipped(self) -> None:
        report = self._report(
            results=[
                {"case_id": "01", "language": "fr", "passed": True},
                {"case_id": "02"},  # no language / verdict → skipped
                "garbage",
            ],
        )
        assert len(gating_rows_from_report(report)) == 1

    def test_unparsable_run_stamp_produces_no_rows(self) -> None:
        assert gating_rows_from_report(self._report(run_at="bogus")) == []


class TestGatingMirror:
    def _row(self) -> GatingScoreRow:
        return GatingScoreRow(
            run_id="20260620T143510Z_support-client",
            case_id="01_prompt_injection",
            agent_id="support-client",
            language="fr",
            model="llama3.2:3b",
            metric=GATING_METRIC,
            score=1.0,
            passed=True,
            catalogue_version="63-071edbdc",
            judge_model=None,
            scored_at=datetime(2026, 6, 20, 14, 35, 10, tzinfo=UTC),
        )

    def test_score_id_is_stable_across_re_mirrors(self) -> None:
        assert langfuse_scores.gating_score_id(self._row()) == langfuse_scores.gating_score_id(
            self._row()
        )

    def test_rows_mirror_session_anchored_with_stable_ids(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setenv("TESSERA_LANGFUSE_SCORES", "1")  # opt back in, over a stub
        calls: list[dict[str, object]] = []

        class _StubClient:
            def create_score(self, **kwargs: object) -> None:
                calls.append(kwargs)

            def flush(self) -> None:
                calls.append({"flushed": True})

        langfuse_scores.set_client(_StubClient())
        try:
            mirrored = langfuse_scores.mirror_gating_rows([self._row()], flush=True)
        finally:
            langfuse_scores.set_client(None)
        assert mirrored == 1
        assert calls[0]["session_id"] == "20260620T143510Z_support-client"  # the run anchor
        assert calls[0]["score_id"] == langfuse_scores.gating_score_id(self._row())
        assert calls[-1] == {"flushed": True}

    def test_disabled_mirror_is_a_noop(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setenv("TESSERA_LANGFUSE_SCORES", "0")
        assert langfuse_scores.mirror_gating_rows([self._row()]) == 0

    def test_client_failure_is_swallowed(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setenv("TESSERA_LANGFUSE_SCORES", "1")

        class _Broken:
            def create_score(self, **kwargs: object) -> None:
                raise RuntimeError("boom")

            def flush(self) -> None:
                pass

        langfuse_scores.set_client(_Broken())
        try:
            assert langfuse_scores.mirror_gating_rows([self._row()]) == 0
        finally:
            langfuse_scores.set_client(None)


class TestRunnerGatingHook:
    async def test_down_store_never_fails_an_eval_run(self, monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
        from eval import runner

        async def _raise(report: object, *, flush_mirror: bool = False) -> int:
            raise RuntimeError("postgres down")

        monkeypatch.setattr("tessera.observability.eval.gating_scores.record_gating_report", _raise)
        await runner._record_gating('{"agent_id": "x", "run_at": "20260620T143510Z"}')
        captured = capsys.readouterr()
        assert "gating store unavailable" in captured.err  # warned, not raised
