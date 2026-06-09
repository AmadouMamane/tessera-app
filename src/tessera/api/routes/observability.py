"""Observability read endpoints for the dashboard (ADR 0010).

Exposes the recent online-eval scores so the dashboard can surface
eval-as-telemetry live. Aggregate quality scores are a public surface
(ADR 0009), so this endpoint is unauthenticated like ``/healthz``.
"""

from __future__ import annotations

import sys
from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from tessera.observability import (
    consistency as consistency_mod,
    contradiction as contradiction_mod,
    corpus_injection as corpus_injection_mod,
    firewall_efficacy as firewall_mod,
    language_routing as language_routing_mod,
    pii_leak as pii_leak_mod,
    provenance as provenance_mod,
    redteam as redteam_mod,
    replay as replay_mod,
    retrieval_quality as retrieval_quality_mod,
    robustness as robustness_mod,
    sessions as sessions_mod,
    steganography as steganography_mod,
    tool_validity as tool_validity_mod,
)
from tessera.observability.eval.calibration import calibrate, load_gold_set
from tessera.observability.eval.ensemble import evaluate_ensemble
from tessera.observability.eval.judge import LLMJudge
from tessera.observability.eval.scores import recent_scores

router = APIRouter(tags=["observability"])


class ReplayRequest(BaseModel):
    """Replay a captured turn against a candidate model."""

    model_config = ConfigDict(extra="forbid")

    bundle_id: str
    model: str


class ConsistencyRequest(BaseModel):
    """Measure self-consistency of a captured turn."""

    model_config = ConfigDict(extra="forbid")

    bundle_id: str
    samples: int = Field(default=3, ge=2, le=8)


class RobustnessRequest(BaseModel):
    """Measure robustness-under-noise of a captured turn."""

    model_config = ConfigDict(extra="forbid")

    bundle_id: str


class EnsembleRequest(BaseModel):
    """Score a captured turn with a multi-judge ensemble."""

    model_config = ConfigDict(extra="forbid")

    bundle_id: str


# Calibration runs the judge over the gold set (slow), so cache it per process.
_calibration_cache: dict[str, object] | None = None


@router.get("/observability/scores")
async def observability_scores() -> dict[str, object]:
    """Return the most recent online-eval scores (newest last)."""
    return {"scores": recent_scores()}


@router.get("/observability/calibration")
async def observability_calibration() -> dict[str, object]:
    """Return the judge's calibration against the human gold set (cached).

    The first call runs the judge over the gold set and may take a few seconds;
    subsequent calls return the cached report. Degrades to ``available: false``
    when the judge or gold set is unavailable, so the dashboard never errors.
    """
    global _calibration_cache
    if _calibration_cache is None:
        try:
            report = await calibrate(LLMJudge(), load_gold_set())
            _calibration_cache = {"available": True, **asdict(report)}
        except Exception as exc:  # never break the dashboard on a judge/IO error
            sys.stderr.write(f"tessera.observability.calibration: failed: {exc}\n")
            return {"available": False}
    return _calibration_cache


@router.get("/observability/replays")
async def observability_replays() -> dict[str, object]:
    """List the captured turns available for regression replay (newest last)."""
    return {"bundles": [asdict(b) for b in replay_mod.recent_bundles()]}


@router.post("/observability/replay")
async def observability_replay(payload: ReplayRequest) -> dict[str, object]:
    """Replay a captured turn against a candidate model and diff the result."""
    bundle = replay_mod.get_bundle(payload.bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="replay bundle not found")
    result = await replay_mod.replay(bundle, model=payload.model)
    return asdict(result)


@router.post("/observability/consistency")
async def observability_consistency(payload: ConsistencyRequest) -> dict[str, object]:
    """Measure the self-consistency / uncertainty of a captured turn."""
    bundle = replay_mod.get_bundle(payload.bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="replay bundle not found")
    report = await consistency_mod.measure_consistency(
        question=bundle.question,
        context=bundle.context,
        model=bundle.original_model,
        samples=payload.samples,
    )
    return asdict(report)


@router.post("/observability/robustness")
async def observability_robustness(payload: RobustnessRequest) -> dict[str, object]:
    """Measure how stable a captured turn is under input noise."""
    bundle = replay_mod.get_bundle(payload.bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="replay bundle not found")
    report = await robustness_mod.measure_robustness(
        question=bundle.question, context=bundle.context, model=bundle.original_model
    )
    return asdict(report)


@router.post("/observability/ensemble")
async def observability_ensemble(payload: EnsembleRequest) -> dict[str, object]:
    """Score a captured turn with a multi-judge ensemble; flag disagreement."""
    bundle = replay_mod.get_bundle(payload.bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="replay bundle not found")
    report = await evaluate_ensemble(
        question=bundle.question, answer=bundle.original_answer, context=bundle.context
    )
    return asdict(report)


@router.get("/observability/firewall-efficacy")
async def observability_firewall_efficacy() -> dict[str, object]:
    """Detection efficacy of the guard over injection vs benign inputs."""
    return asdict(firewall_mod.compute_efficacy())


@router.get("/observability/redteam")
async def observability_redteam() -> dict[str, object]:
    """Return the recorded jailbreak-drift snapshots (newest last)."""
    return {"snapshots": [asdict(s) for s in redteam_mod.recent_snapshots()]}


@router.post("/observability/redteam")
async def observability_redteam_run() -> dict[str, object]:
    """Run the adversarial corpus through the guard and record a snapshot."""
    snapshot = redteam_mod.run_redteam()
    return {
        "latest": asdict(snapshot),
        "snapshots": [asdict(s) for s in redteam_mod.recent_snapshots()],
    }


@router.get("/observability/tool-validity")
async def observability_tool_validity() -> dict[str, object]:
    """Validity of tool calls (allowed vs denied, argument failures)."""
    return asdict(tool_validity_mod.compute_tool_validity())


@router.get("/observability/routing")
async def observability_routing() -> dict[str, object]:
    """Language-routing health: served vs detected language, code-switching."""
    turns = [(b.question, b.language) for b in replay_mod.recent_bundles()]
    return asdict(language_routing_mod.aggregate_routing(turns))


@router.get("/observability/pii-leak")
async def observability_pii_leak() -> dict[str, object]:
    """Output PII-leak rate: PII in answers absent from their grounding."""
    turns = [(b.original_answer, f"{b.question}\n{b.context}") for b in replay_mod.recent_bundles()]
    return asdict(pii_leak_mod.aggregate_leaks(turns))


@router.get("/observability/sessions")
async def observability_sessions() -> dict[str, object]:
    """Session-level goal-completion analytics from scored turns."""
    turns: list[tuple[str | None, float]] = []
    for score in recent_scores():
        conv = score.get("conversation_id")
        raw = score.get("score", 0.0)
        turns.append((conv if isinstance(conv, str) else None, float(raw)))  # type: ignore[arg-type]
    return asdict(sessions_mod.aggregate_sessions(turns))


@router.get("/observability/contradictions")
async def observability_contradictions() -> dict[str, object]:
    """Detect self-contradictions across the turns of each captured session."""
    by_conversation: dict[str, list[tuple[str, str]]] = {}
    for bundle in replay_mod.recent_bundles():
        key = bundle.conversation_id or "<none>"
        by_conversation.setdefault(key, []).append((bundle.question, bundle.original_answer))

    n_turns = 0
    pairs: list[dict[str, object]] = []
    for conversation_id, turns in by_conversation.items():
        n_turns += len(turns)
        report = await contradiction_mod.detect_contradictions(turns)
        for pair in report.contradictions:
            pairs.append({"conversation_id": conversation_id, **asdict(pair)})

    return {
        "n_sessions": len(by_conversation),
        "n_turns": n_turns,
        "n_contradictions": len(pairs),
        "pairs": pairs,
    }


@router.get("/observability/corpus-scan/{bundle_id}")
async def observability_corpus_scan(bundle_id: str) -> dict[str, object]:
    """Screen a captured turn's retrieved chunks for indirect injection."""
    bundle = replay_mod.get_bundle(bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="replay bundle not found")
    chunks = [c for c in bundle.context.split("\n\n") if c.strip()]
    return asdict(corpus_injection_mod.scan_chunks(chunks))


@router.get("/observability/steganography/{bundle_id}")
async def observability_steganography(bundle_id: str) -> dict[str, object]:
    """Detect hidden unicode (zero-width/bidi/tag) in a captured turn."""
    bundle = replay_mod.get_bundle(bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="replay bundle not found")
    return asdict(steganography_mod.scan_text(f"{bundle.question}\n{bundle.context}"))


@router.get("/observability/provenance/{bundle_id}")
async def observability_provenance(bundle_id: str) -> dict[str, object]:
    """Claim-level attribution of a captured turn to its retrieved chunks."""
    bundle = replay_mod.get_bundle(bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="replay bundle not found")
    chunks = [c for c in bundle.context.split("\n\n") if c.strip()]
    report = await provenance_mod.attribute(bundle.original_answer, chunks)
    util = retrieval_quality_mod.utilization(report, len(chunks))
    return {**asdict(report), "utilization": asdict(util)}
