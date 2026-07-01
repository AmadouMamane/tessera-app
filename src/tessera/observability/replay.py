"""Deterministic trace replay / regression-from-production (ADR 0010, #1).

Every grounded production turn is captured as a :class:`ReplayBundle` — enough
to re-run it: the question, the retrieved context, the original answer, and the
faithfulness score it earned. :func:`replay` then re-generates an answer for the
same ``(question, context)`` with a *candidate* model, re-judges it, and reports
the score delta and a textual similarity. A real conversation thereby becomes a
regression test against a model or prompt change.

The capture store is an in-process ring buffer (a convenience view for the
dashboard, not the system of record). Replays are driven through the API/UI,
which is why no separate CLI process reads the buffer.
"""

from __future__ import annotations

import json
import uuid
from collections import deque
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from difflib import SequenceMatcher
from typing import TYPE_CHECKING

from tessera.llm.router import ChatMessage, backend_for_model
from tessera.observability.eval.judge import FAITHFULNESS, LLMJudge

if TYPE_CHECKING:
    from pathlib import Path

    from tessera.llm.router import ChatBackend
    from tessera.observability.eval.judge import Judge
    from tessera.observability.lineage import Lineage

__all__ = [
    "ReplayBundle",
    "ReplayResult",
    "capture_bundle",
    "get_bundle",
    "persisted_bundles",
    "purge_conversation",
    "recent_bundles",
    "replay",
]

# A bounded live view (newest 100), plus a durable append-only store so the
# bundle-backed signals (toxicity, pii, cost, anomalies…) survive a restart and
# can answer "as of T" over real history, not just the current process (ADR 0011).
_BUNDLES: deque[ReplayBundle] = deque(maxlen=100)
_WARMED = False


def _bundles_path() -> Path:
    """Durable append-only store for captured turns (next to the audit log)."""
    from tessera.settings import get_settings

    return get_settings().guard.audit_file.parent / "bundles.jsonl"


def _bundle_to_row(bundle: ReplayBundle) -> dict[str, object]:
    """Serialise a bundle to a JSON-safe row.

    ``asdict`` already turns the nested ``Lineage`` dataclass into a plain dict.
    """
    return asdict(bundle)


def _row_to_bundle(row: dict[str, object]) -> ReplayBundle | None:
    """Rebuild a bundle from a stored row, or ``None`` if it is malformed."""
    from tessera.observability.lineage import Lineage

    try:
        lineage_raw = row.get("lineage")
        lineage = Lineage(**lineage_raw) if isinstance(lineage_raw, dict) else None
        return ReplayBundle(
            bundle_id=str(row["bundle_id"]),
            captured_at=str(row["captured_at"]),
            conversation_id=(
                str(row["conversation_id"]) if row.get("conversation_id") is not None else None
            ),
            language=str(row.get("language", "")),
            question=str(row.get("question", "")),
            context=str(row.get("context", "")),
            original_answer=str(row.get("original_answer", "")),
            original_model=str(row.get("original_model", "")),
            original_score=float(row.get("original_score", 0.0)),  # type: ignore[arg-type]
            lineage=lineage,
            latency_ms=row.get("latency_ms") if isinstance(row.get("latency_ms"), dict) else None,  # type: ignore[arg-type]
            agent_id=str(row["agent_id"]) if row.get("agent_id") is not None else None,
        )
    except (KeyError, TypeError, ValueError):
        return None


def _persist(bundle: ReplayBundle) -> None:
    """Append one bundle to the durable store (best effort; never blocks a turn)."""
    try:
        path = _bundles_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(_bundle_to_row(bundle)) + "\n")
    except OSError:
        pass


def _read_persisted() -> list[ReplayBundle]:
    """Read every durably-stored bundle (oldest→newest); best effort."""
    bundles: list[ReplayBundle] = []
    try:
        path = _bundles_path()
        if not path.exists():
            return bundles
        with path.open("r", encoding="utf-8") as fp:
            for raw in fp:
                stripped = raw.strip()
                if not stripped:
                    continue
                try:
                    obj = json.loads(stripped)
                except ValueError:
                    continue
                if isinstance(obj, dict):
                    bundle = _row_to_bundle(obj)
                    if bundle is not None:
                        bundles.append(bundle)
    except OSError:
        return bundles
    return bundles


def _warm_live_buffer() -> None:
    """Seed the empty live buffer from the durable store after a restart.

    The live view is volatile; without this a fresh process shows no bundle-backed
    signals until new traffic arrives. We load the most recent ``maxlen`` rows so
    "live" and "as of now" agree immediately after a restart.
    """
    global _WARMED
    if _WARMED or _BUNDLES:
        _WARMED = True
        return
    _WARMED = True
    for bundle in _read_persisted()[-(_BUNDLES.maxlen or 100) :]:
        _BUNDLES.append(bundle)


def persisted_bundles(at: str | None = None, agent_id: str | None = None) -> list[ReplayBundle]:
    """All durably-stored bundles, optionally as of T and/or one agent's."""
    bundles = _read_persisted()
    if at is None:
        return _bundles_by_agent(bundles, agent_id)
    try:
        cutoff = datetime.fromisoformat(at)
    except ValueError:
        return _bundles_by_agent(bundles, agent_id)
    kept: list[ReplayBundle] = []
    for bundle in bundles:
        try:
            if datetime.fromisoformat(bundle.captured_at) <= cutoff:
                kept.append(bundle)
        except ValueError:
            kept.append(bundle)
    return _bundles_by_agent(kept, agent_id)


_ANSWER_SYSTEM = (
    "You are a banking support assistant. Answer the QUESTION using ONLY the "
    "CONTEXT. Be precise and do not invent facts not present in the context."
)


@dataclass(frozen=True, slots=True)
class ReplayBundle:
    """A captured turn, replayable against a new model/prompt."""

    bundle_id: str
    captured_at: str
    conversation_id: str | None
    language: str
    question: str
    context: str
    original_answer: str
    original_model: str
    original_score: float
    lineage: Lineage | None = None
    latency_ms: dict[str, float] | None = None
    agent_id: str | None = None


@dataclass(frozen=True, slots=True)
class ReplayResult:
    """The outcome of replaying a bundle against a candidate model."""

    bundle_id: str
    original_model: str
    original_score: float
    candidate_model: str
    candidate_answer: str
    candidate_score: float
    score_delta: float  # candidate minus original (positive = improvement)
    similarity: float  # 0..1 textual similarity to the original answer


def capture_bundle(
    *,
    question: str,
    context: str,
    original_answer: str,
    language: str,
    original_score: float,
    original_model: str,
    conversation_id: str | None = None,
    agent_id: str | None = None,
    lineage: Lineage | None = None,
    latency_ms: dict[str, float] | None = None,
) -> ReplayBundle:
    """Capture a grounded turn for later replay; returns the stored bundle.

    ``agent_id`` attributes the bundle to the responding agent so per-agent
    cost / toxicity / PII / what-changed read that agent's own turns.
    """
    bundle = ReplayBundle(
        bundle_id=uuid.uuid4().hex,
        captured_at=datetime.now(UTC).isoformat(),
        conversation_id=conversation_id,
        language=language,
        question=question,
        context=context,
        original_answer=original_answer,
        original_model=original_model,
        original_score=original_score,
        lineage=lineage,
        latency_ms=latency_ms,
        agent_id=agent_id,
    )
    _warm_live_buffer()
    _BUNDLES.append(bundle)
    _persist(bundle)  # durable store for as-of-T reads (ADR 0011)
    return bundle


def _bundles_by_agent(bundles: list[ReplayBundle], agent_id: str | None) -> list[ReplayBundle]:
    """Keep only ``agent_id``'s bundles when scoped; all otherwise.

    A bundle with no ``agent_id`` (pre-tagging history) is org-only — an
    agent-scoped read excludes it rather than guessing its owner.
    """
    if agent_id is None:
        return bundles
    return [b for b in bundles if b.agent_id == agent_id]


def recent_bundles(at: str | None = None, agent_id: str | None = None) -> list[ReplayBundle]:
    """Return the captured bundles (newest last), optionally one agent's.

    Live (``at=None``) reads the bounded in-process view (seeded from the durable
    store after a restart). With ``at`` set the durable store is read and filtered
    to bundles captured at or before T — the as-of-T read behind the cockpit time
    rail (ADR 0011). With ``agent_id`` set, only that agent's bundles. Values are
    never fabricated, only filtered.
    """
    if at is not None:
        return persisted_bundles(at, agent_id)
    _warm_live_buffer()
    return _bundles_by_agent(list(_BUNDLES), agent_id)


def get_bundle(bundle_id: str) -> ReplayBundle | None:
    """Return the bundle with ``bundle_id`` if still in the live buffer."""
    _warm_live_buffer()
    return next((b for b in _BUNDLES if b.bundle_id == bundle_id), None)


def purge_conversation(conversation_id: str) -> int:
    """Drop all captured bundles for a conversation (GDPR erasure, #180).

    Erasure must reach both the live view and the durable store, so a deleted
    subject leaves no replay trace anywhere. Returns the number removed from the
    live buffer.
    """
    _warm_live_buffer()
    kept = [b for b in _BUNDLES if b.conversation_id != conversation_id]
    removed = len(_BUNDLES) - len(kept)
    _BUNDLES.clear()
    _BUNDLES.extend(kept)
    # Rewrite the durable store without the erased conversation's bundles.
    try:
        path = _bundles_path()
        if path.exists():
            surviving = [b for b in _read_persisted() if b.conversation_id != conversation_id]
            with path.open("w", encoding="utf-8") as fp:
                for bundle in surviving:
                    fp.write(json.dumps(_bundle_to_row(bundle)) + "\n")
    except OSError:
        pass
    return removed


async def replay(
    bundle: ReplayBundle,
    *,
    model: str,
    judge: Judge | None = None,
    backend: ChatBackend | None = None,
) -> ReplayResult:
    """Re-run ``bundle`` against ``model`` and diff against the original.

    Args:
        bundle: The captured turn to replay.
        model: The candidate model id to generate the new answer with.
        judge: Judge for scoring; defaults to the configured :class:`LLMJudge`.
        backend: Generation backend; defaults to ``backend_for_model(model)``.

    Returns:
        A :class:`ReplayResult` with the candidate answer, its faithfulness
        score, the delta versus the original, and textual similarity.
    """
    generator = backend or backend_for_model(model)
    messages = [
        ChatMessage(role="system", content=_ANSWER_SYSTEM),
        ChatMessage(
            role="user",
            content=f"CONTEXT:\n{bundle.context}\n\nQUESTION:\n{bundle.question}",
        ),
    ]
    response = await generator.chat(messages, temperature=0.0, model=model)
    candidate_answer = response.content

    active_judge: Judge = judge or LLMJudge()
    verdict = await active_judge.score(
        metric=FAITHFULNESS,
        question=bundle.question,
        answer=candidate_answer,
        context=bundle.context,
    )
    similarity = SequenceMatcher(None, bundle.original_answer, candidate_answer).ratio()
    return ReplayResult(
        bundle_id=bundle.bundle_id,
        original_model=bundle.original_model,
        original_score=bundle.original_score,
        candidate_model=response.model,
        candidate_answer=candidate_answer,
        candidate_score=verdict.score,
        score_delta=verdict.score - bundle.original_score,
        similarity=similarity,
    )
