"""Phase B — completing the dimensioning (ADR 0015 §Migration B).

Locks: the agent_id + model labels on EVAL_SCORE, the newly-wired per-agent
GUARD_DECISIONS_TOTAL, the turn-span dimension stamping, and the per-dimension "data
available since" boundaries. (The score write paths moved to the owned stores in G2 —
see ``test_score_write_paths.py``.)
"""

from __future__ import annotations

import json

from tessera.observability import metrics, semconv
from tessera.observability.eval import scores as scores_mod
from tessera.observability.eval.judge import JudgeVerdict
from tessera.observability.spine.availability import dimension_availability


class _RecordingSpan:
    """Minimal span double that records set attributes (offline, no tracer needed)."""

    def __init__(self) -> None:
        self.attrs: dict[str, object] = {}

    def set_attribute(self, key: str, value: object) -> None:
        self.attrs[key] = value


class TestEvalScoreLabels:
    def test_emit_score_stamps_agent_and_model_labels(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        # The durable leg is the OWNED store since G5 (the jsonl write is retired) —
        # capture the row handed to the ClickHouse recorder and assert its dimensions.
        captured: list[dict[str, object]] = []
        monkeypatch.setattr(scores_mod.clickhouse_scores, "record_online_score", captured.append)
        verdict = JudgeVerdict(metric="faithfulness", score=0.9, rationale="x", judge_model="stub")
        scores_mod.emit_score(verdict, language="fr", agent_id="probe-agent", model="probe-model")
        sample = metrics.registry.get_sample_value(
            "tessera_eval_score_sum",
            {
                "metric": "faithfulness",
                "language": "fr",
                "agent_id": "probe-agent",
                "model": "probe-model",
            },
        )
        assert sample == 0.9
        assert captured[-1]["agent_id"] == "probe-agent"
        assert captured[-1]["model"] == "probe-model"

    def test_missing_dimensions_get_sentinels_not_crash(self) -> None:
        # A unique metric name isolates this series from other tests' emissions in the shared
        # process registry, so the sentinel labels ("none"/"unknown") are asserted exactly.
        verdict = JudgeVerdict(
            metric="probe-nometric", score=0.5, rationale="x", judge_model="stub"
        )
        scores_mod.emit_score(verdict, language="de")  # no agent, no model
        sample = metrics.registry.get_sample_value(
            "tessera_eval_score_sum",
            {"metric": "probe-nometric", "language": "de", "agent_id": "none", "model": "unknown"},
        )
        assert sample == 0.5


class TestGuardDecisionsCounter:
    def test_record_guard_decision_increments_with_agent(self) -> None:
        from tessera.guard.adapter import _record_guard_decision

        _record_guard_decision("probe_tool", "denied")
        sample = metrics.registry.get_sample_value(
            "tessera_guard_decisions_total",
            {"target": "probe_tool", "decision": "denied", "agent_id": "support-client"},
        )
        assert sample == 1.0


class TestTurnSpanStamping:
    def test_stamps_full_dimension_set(self) -> None:
        span = _RecordingSpan()
        semconv.stamp_turn_dimensions(
            span,  # type: ignore[arg-type]
            agent_id="recouvrement",
            language="fr",
            model="llama3.2:3b",
            conversation_id="conv-1",
            turn_id="turn-1",
            environment="local",
        )
        assert span.attrs[semconv.TESSERA_AGENT_ID] == "recouvrement"
        assert span.attrs[semconv.TESSERA_LANGUAGE] == "fr"
        assert span.attrs[semconv.GEN_AI_REQUEST_MODEL] == "llama3.2:3b"
        assert span.attrs[semconv.GEN_AI_CONVERSATION_ID] == "conv-1"
        assert span.attrs[semconv.TESSERA_TURN_ID] == "turn-1"
        assert span.attrs[semconv.DEPLOYMENT_ENVIRONMENT] == "local"

    def test_omits_model_when_absent(self) -> None:
        span = _RecordingSpan()
        semconv.stamp_turn_dimensions(
            span,  # type: ignore[arg-type]
            agent_id="a",
            language="en",
            model=None,
            conversation_id="c",
            turn_id="t",
            environment="ci",
        )
        assert semconv.GEN_AI_REQUEST_MODEL not in span.attrs


class TestDimensionAvailability:
    def test_per_dimension_since_boundaries(self, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        from tessera.observability import replay as replay_mod

        scores_path = tmp_path / "scores.jsonl"
        monkeypatch.setattr(scores_mod, "_scores_path", lambda: scores_path)
        monkeypatch.setattr(replay_mod, "_bundles_path", lambda: tmp_path / "bundles.jsonl")
        early, late = "2026-06-01T00:00:00+00:00", "2026-06-10T00:00:00+00:00"
        # An early org-only row (no agent, no model), then a later attributed row.
        rows = [
            {"scored_at": early, "metric": "faithfulness", "score": 0.5, "language": "fr"},
            {
                "scored_at": late,
                "metric": "faithfulness",
                "score": 0.9,
                "language": "fr",
                "agent_id": "support-client",
                "model": "llama3.2:3b",
            },
        ]
        scores_path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        since = dimension_availability()
        # TIME starts at the earliest overall; AGENT/MODEL start only where the dimension exists.
        assert since["time"] == early
        assert since["agent"] == late
        assert since["model"] == late
        assert since["language"] == early


class TestLangfuseBackfillHelpers:
    def test_conversation_id_from_session_and_metadata(self) -> None:
        from scripts.backfill_langfuse_traces import trace_agent_id, trace_conversation_id

        assert trace_conversation_id({"sessionId": "conv-9"}) == "conv-9"
        assert trace_conversation_id({"metadata": {"conversation_id": "conv-7"}}) == "conv-7"
        assert trace_conversation_id({"metadata": {}}) is None
        assert trace_agent_id({"metadata": {"agent_id": "recouvrement"}}) == "recouvrement"
        assert trace_agent_id({"metadata": {}}) is None
