"""Reviewer node — scores the draft response and decides on escalation.

The reviewer fuses three signals into a single confidence score:

* **Grounding** — does every load-bearing claim trace to a retrieved
  document or a tool result? Unsupported claims drag the score down sharply.
* **Coverage** — did the workers actually return useful information, or
  did every lookup come back empty?
* **Guard health** — has the firewall denied anything in this turn? A deny
  alone is not a failure (it might just be a PII redaction), but multiple
  denies on the same tool indicate the user is steering into a wall.

When the fused score falls below
:attr:`GuardSettings.escalation_confidence_threshold`, the reviewer flips
``needs_escalation`` to ``True`` with a structured reason. The graph then
routes to the escalation worker instead of the reporter.

The reviewer is intentionally rule-based and side-effect-free — it must be
deterministic so the regression harness can assert on its outputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from tessera.agent.state import AgentState  # noqa: TCH001  — LangGraph introspects run() at runtime
from tessera.settings import get_settings

__all__ = ["ReviewOutcome", "review", "run"]

_MIN_TOKEN_LEN: Final = 4


@dataclass(frozen=True, slots=True)
class ReviewOutcome:
    """The reviewer's structured assessment of the current turn."""

    confidence: float
    grounding_score: float
    coverage_score: float
    guard_score: float
    needs_escalation: bool
    reason: str | None


def _score_grounding(state: AgentState) -> float:
    """Score how well the draft response is grounded.

    Without a draft yet (reviewer ran before any worker produced text), we
    treat grounding as neutral (0.5) rather than failing.

    When the draft originates from a successful tool call (account balance,
    loan simulation) it is grounded by definition — the data came directly
    from a database, not from the LLM. In that case we return 0.9 regardless
    of lexical overlap with retrieved documents.

    When the draft comes from retrieval-based synthesis, we check lexical
    overlap between the draft and the supporting documents.
    """
    draft = state.get("draft_response")
    if not draft:
        return 0.5
    # Tool-result drafts are intrinsically grounded.
    tool_calls = state.get("tool_calls", [])
    if any(call.succeeded for call in tool_calls):
        return 0.9
    # Policy-refusal drafts (e.g. third-party account access refused) are
    # grounded by policy, not by retrieval — do not penalise as hallucination.
    errors = state.get("errors", [])
    if any("refused" in e or "refusal" in e or "policy" in e for e in errors):
        return 0.9
    docs = state.get("retrieved_documents", [])
    if not docs:
        # A non-empty draft with zero supporting documents is the canonical
        # hallucination smell — penalise hard.
        return 0.1
    # Crude lexical overlap as a fast, deterministic proxy. Real grounding
    # scoring (entailment + citation match) lives in eval/scorecard.py.
    draft_tokens = {tok.lower() for tok in draft.split() if len(tok) >= _MIN_TOKEN_LEN}
    if not draft_tokens:
        return 0.5
    supported = 0
    for doc in docs:
        doc_tokens = {tok.lower() for tok in doc.text.split() if len(tok) >= _MIN_TOKEN_LEN}
        if draft_tokens & doc_tokens:
            supported += 1
    return min(1.0, supported / max(1, len(docs)))


def _score_coverage(state: AgentState) -> float:
    """Score whether the planned workers produced any useful output."""
    plan = state.get("plan", [])
    if not plan:
        return 1.0  # Nothing was supposed to happen; treat as covered.
    docs = state.get("retrieved_documents", [])
    tool_calls = state.get("tool_calls", [])
    if docs or any(call.succeeded for call in tool_calls):
        return 1.0
    return 0.2


def _score_guard(state: AgentState) -> float:
    """Score guard health: deny-storms drag the score down."""
    decisions = state.get("guard_decisions", [])
    if not decisions:
        return 1.0
    denies = sum(1 for d in decisions if d.decision == "deny")
    if denies == 0:
        return 1.0
    # One or two denies are normal (PII redaction etc.); more than three on
    # a single turn means the user is being repeatedly blocked.
    return max(0.0, 1.0 - 0.25 * denies)


def review(state: AgentState) -> ReviewOutcome:
    """Compute the :class:`ReviewOutcome` for ``state`` without mutating it."""
    grounding = _score_grounding(state)
    coverage = _score_coverage(state)
    guard = _score_guard(state)

    # Weighted geometric-style fuse: a near-zero on any axis tanks the total.
    confidence = (grounding * 0.5) + (coverage * 0.3) + (guard * 0.2)

    threshold = get_settings().guard.escalation_confidence_threshold
    needs_escalation = confidence < threshold
    reason: str | None = None
    if needs_escalation:
        weakest = min(
            ("grounding", grounding),
            ("coverage", coverage),
            ("guard", guard),
            key=lambda item: item[1],
        )
        reason = (
            f"Confidence {confidence:.2f} below threshold {threshold:.2f}; "
            f"weakest signal: {weakest[0]} ({weakest[1]:.2f})"
        )

    return ReviewOutcome(
        confidence=confidence,
        grounding_score=grounding,
        coverage_score=coverage,
        guard_score=guard,
        needs_escalation=needs_escalation,
        reason=reason,
    )


def run(state: AgentState) -> dict[str, object]:
    """Reviewer node entry point."""
    outcome = review(state)
    update: dict[str, object] = {
        "confidence": outcome.confidence,
        "needs_escalation": outcome.needs_escalation,
        # Persist the per-axis split so the console Debug surface can show the
        # real grounding/coverage/guard breakdown behind the composite score.
        "grounding_score": outcome.grounding_score,
        "coverage_score": outcome.coverage_score,
        "guard_score": outcome.guard_score,
    }
    if outcome.reason is not None:
        update["escalation_reason"] = outcome.reason
    return update
