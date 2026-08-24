"""Unit tests for online evaluation + the flywheel (ADR 0010, Phase 4)."""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tessera.llm.router import ChatMessage, ChatResponse
from tessera.observability.eval import flywheel, online
from tessera.observability.eval.judge import (
    FAITHFULNESS,
    GROUNDING,
    HALLUCINATION,
    JudgeVerdict,
    LLMJudge,
    rubric_for,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

_SCHEMA_SRC = Path(__file__).resolve().parents[2] / "eval" / "failures" / "_schema.json"


class _StubBackend:
    """Minimal ChatBackend returning a canned response."""

    name = "stub"
    model = "stub-judge"

    def __init__(self, content: str) -> None:
        self._content = content

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0.2,
        max_output_tokens: int | None = None,
        model: str | None = None,
    ) -> ChatResponse:
        return ChatResponse(
            content=self._content,
            model=self.model,
            input_tokens=10,
            output_tokens=5,
            finish_reason="stop",
        )

    def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0.2,
        max_output_tokens: int | None = None,
        model: str | None = None,
    ) -> AsyncIterator[str]:
        async def _gen() -> AsyncIterator[str]:
            yield self._content

        return _gen()


class _StubJudge:
    def __init__(self, score: float) -> None:
        self._score = score

    async def score(self, *, metric: str, question: str, answer: str, context: str) -> JudgeVerdict:
        return JudgeVerdict(metric=metric, score=self._score, rationale="stub", judge_model="stub")


# ── judge ─────────────────────────────────────────────────────────────────────


def test_llm_judge_parses_score_and_clamps() -> None:
    backend = _StubBackend('Here is my verdict: {"score": 1.4, "rationale": "great"} thanks')
    judge = LLMJudge(backend=backend)
    verdict = asyncio.run(judge.score(metric=FAITHFULNESS, question="q", answer="a", context="c"))
    assert verdict.metric == FAITHFULNESS
    assert verdict.score == 1.0  # clamped from 1.4
    assert verdict.rationale == "great"
    assert verdict.judge_model == "stub-judge"


def test_llm_judge_coerces_bad_score_to_zero() -> None:
    backend = _StubBackend('{"score": "n/a", "rationale": "x"}')
    judge = LLMJudge(backend=backend)
    verdict = asyncio.run(judge.score(metric=FAITHFULNESS, question="q", answer="a", context="c"))
    assert verdict.score == 0.0


def test_rubric_for_unknown_metric_raises() -> None:
    with pytest.raises(ValueError, match="unknown judge metric"):
        rubric_for("not_a_metric")


# ── online (tiered sampling + disagreement) ────────────────────────────────────


def test_should_judge_always_for_flagged() -> None:
    assert online.should_judge(flagged=True, sample_rate=0.0, roll=0.99) is True


def test_should_judge_samples_unflagged() -> None:
    assert online.should_judge(flagged=False, sample_rate=0.1, roll=0.05) is True
    assert online.should_judge(flagged=False, sample_rate=0.1, roll=0.5) is False


def test_evaluate_turn_skips_when_not_sampled() -> None:
    outcome = asyncio.run(
        online.evaluate_turn(
            question="q",
            answer="a",
            context="c",
            language="fr",
            judge=_StubJudge(0.9),
            sample_rate=0.1,
            roll=0.99,
        )
    )
    assert outcome.verdict is None
    assert outcome.disagreement is False


def test_evaluate_turn_flags_guard_judge_disagreement() -> None:
    # Guard allowed the turn but the judge finds it poorly grounded → disagreement.
    outcome = asyncio.run(
        online.evaluate_turn(
            question="q",
            answer="a",
            context="c",
            language="de",
            guard_denied=False,
            judge=_StubJudge(0.3),
            roll=0.0,
        )
    )
    assert outcome.verdict is not None
    assert outcome.verdict.score == pytest.approx(0.3)
    assert outcome.disagreement is True


def test_evaluate_turn_respects_the_declared_quality_regime() -> None:
    """ADR 0017 §A4 / ADR 0053 §4 — the judge's population is DECLARED.

    Measured leak, 2026-08-22: one operator-side /chat turn routed to recouvrement
    (declared ``business_scored``, template-assembled replies) was judged and its
    single row became the whole per-agent SLO population. The guard makes that
    unrepresentable: a non-``llm_judged`` agent is skipped even when FLAGGED, with
    the reason named — while a declared ``llm_judged`` agent and an id the registry
    does not know keep today's behaviour.
    """
    emitted: list[object] = []

    def _record(verdict: object, **_kwargs: object) -> None:
        emitted.append(verdict)

    original_emit = online.scores.emit_score
    online.scores.emit_score = _record  # type: ignore[assignment]
    try:
        skipped = asyncio.run(
            online.evaluate_turn(
                question="q",
                answer="a",
                context="c",
                language="fr",
                agent_id="recouvrement",
                flagged=True,
                judge=_StubJudge(0.1),
                roll=0.0,
            )
        )
        assert skipped.verdict is None
        assert skipped.skipped == "quality_regime"
        assert emitted == []

        judged = asyncio.run(
            online.evaluate_turn(
                question="q",
                answer="a",
                context="c",
                language="fr",
                agent_id="support-client",
                judge=_StubJudge(0.9),
                roll=0.0,
            )
        )
        assert judged.verdict is not None
        assert judged.skipped is None
        assert emitted != []

        unknown = asyncio.run(
            online.evaluate_turn(
                question="q",
                answer="a",
                context="c",
                language="fr",
                agent_id="not-a-registry-agent",
                judge=_StubJudge(0.9),
                roll=0.0,
            )
        )
        assert unknown.verdict is not None
    finally:
        online.scores.emit_score = original_emit  # type: ignore[assignment]


def test_evaluate_turn_no_disagreement_when_grounded() -> None:
    outcome = asyncio.run(
        online.evaluate_turn(
            question="q",
            answer="a",
            context="c",
            language="en",
            guard_denied=False,
            judge=_StubJudge(0.95),
            roll=0.0,
        )
    )
    assert outcome.disagreement is False


def test_new_metric_rubrics_exist() -> None:
    assert "GROUNDING" in rubric_for(GROUNDING).upper()
    assert "HALLUCINATION" in rubric_for(HALLUCINATION).upper()


class _RecordingJudge:
    """Records which metrics it was asked to score."""

    def __init__(self) -> None:
        self.metrics: list[str] = []

    async def score(self, *, metric: str, question: str, answer: str, context: str) -> JudgeVerdict:
        self.metrics.append(metric)
        return JudgeVerdict(metric=metric, score=0.9, rationale="stub", judge_model="stub")


def test_evaluate_turn_scores_faithfulness_grounding_hallucination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Isolate from the durable store: count emissions without writing a file.
    emitted: list[str] = []
    monkeypatch.setattr(
        online.scores,
        "emit_score",
        lambda verdict, **_: emitted.append(verdict.metric),
    )
    judge = _RecordingJudge()
    asyncio.run(
        online.evaluate_turn(
            question="q", answer="a", context="c", language="fr", judge=judge, roll=0.0
        )
    )
    assert judge.metrics == [FAITHFULNESS, GROUNDING, HALLUCINATION]
    assert emitted == [FAITHFULNESS, GROUNDING, HALLUCINATION]


# ── flywheel (curation into the harness) ───────────────────────────────────────


def test_curate_failure_writes_schema_valid_case(tmp_path: Path) -> None:
    failures_dir = tmp_path / "failures"
    failures_dir.mkdir()
    shutil.copy(_SCHEMA_SRC, failures_dir / "_schema.json")

    verdict = JudgeVerdict(metric=FAITHFULNESS, score=0.2, rationale="x", judge_model="llama")
    path = flywheel.curate_failure(
        verdict=verdict,
        question="Quel est le plafond de la garantie des dépôts ?",
        language="fr",
        expected_behavior="The agent must ground the deposit-guarantee figure in the corpus.",
        failures_dir=failures_dir,
    )

    assert path.exists()
    case = json.loads(path.read_text(encoding="utf-8"))
    assert case["id"] == "001_curated_low_faithfulness"
    assert case["category"] == "hallucination"
    assert case["languages"] == ["fr"]
    # Next number increments once a case exists.
    assert flywheel.next_case_number(failures_dir) == 2
