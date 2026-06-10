"""Mid-stream guard retraction observability (ADR 0010, idea #90).

When answers are streamed token-by-token, the output guard only sees a span once
it has been assembled — but by then those tokens may already be on the user's
screen. If the guard then has to redact PII or deny an injection echo, it is
*retracting* content that already leaked. This module measures that exposure:
for each answer it finds the earliest position an output-guard trigger appears
and estimates how many tokens would already have been streamed before the guard
could intervene (the ADR 0007 interrupt-design signal).

It reuses the live guard policy's injection-deny and PII patterns, and reports
only the trigger *kind* and token offsets — never the matched text — so the
telemetry itself never re-leaks the sensitive span.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from tessera.observability.cost_anomaly import estimate_tokens

if TYPE_CHECKING:
    from tessera.guard.decisions import Policy

__all__ = ["RetractionEvent", "RetractionReport", "analyze_retractions"]


@dataclass(frozen=True, slots=True)
class RetractionEvent:
    """A turn whose streamed answer would require a mid-stream retraction."""

    kind: str  # "injection_echo" | "pii"
    tokens_before: int  # tokens already streamed before the trigger appears
    total_tokens: int
    exposure_rate: float  # tokens_before / total_tokens


@dataclass(frozen=True, slots=True)
class RetractionReport:
    """Aggregate mid-stream retraction exposure across answers."""

    n_answers: int
    n_retractions: int
    retraction_rate: float
    max_tokens_exposed: int
    mean_tokens_exposed: float
    events: list[RetractionEvent] = field(default_factory=list)


def _earliest_trigger(answer: str, policy: Policy) -> tuple[int, str] | None:
    """Return ``(char_offset, kind)`` of the earliest output-guard trigger, if any."""
    best: tuple[int, str] | None = None
    for pattern in policy.prompt_injection_deny:
        match = pattern.search(answer)
        if match is not None and (best is None or match.start() < best[0]):
            best = (match.start(), "injection_echo")
    for pattern in policy.pii_patterns:
        match = pattern.search(answer)
        if match is not None and (best is None or match.start() < best[0]):
            best = (match.start(), "pii")
    return best


def analyze_retractions(answers: list[str], *, policy: Policy) -> RetractionReport:
    """Measure the streamed-token exposure before an output-guard trigger.

    Args:
        answers: The captured answer texts (one per turn).
        policy: The live guard policy supplying injection-deny and PII patterns.

    Returns:
        A :class:`RetractionReport` with the per-turn exposure and the rate.
    """
    events: list[RetractionEvent] = []
    for answer in answers:
        trigger = _earliest_trigger(answer, policy)
        if trigger is None:
            continue
        offset, kind = trigger
        tokens_before = estimate_tokens(answer[:offset])
        total = max(estimate_tokens(answer), 1)
        events.append(
            RetractionEvent(
                kind=kind,
                tokens_before=tokens_before,
                total_tokens=total,
                exposure_rate=min(tokens_before / total, 1.0),
            )
        )
    n = len(events)
    max_exposed = max((e.tokens_before for e in events), default=0)
    mean_exposed = sum(e.tokens_before for e in events) / n if n else 0.0
    return RetractionReport(
        n_answers=len(answers),
        n_retractions=n,
        retraction_rate=n / len(answers) if answers else 0.0,
        max_tokens_exposed=max_exposed,
        mean_tokens_exposed=mean_exposed,
        events=events,
    )
