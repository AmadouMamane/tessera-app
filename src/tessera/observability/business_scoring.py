"""Generic business scoring registry for specialised workflow events."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Literal, Protocol

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

__all__ = [
    "BusinessScore",
    "BusinessScorer",
    "BusinessScoringRegistry",
    "default_business_scoring_registry",
    "register_business_scorer",
    "reset_business_scoring_registry",
    "score_rows",
]


@dataclass(frozen=True, slots=True)
class BusinessScore:
    """A deterministic métier score derived from typed business events."""

    metric: str
    score: float | None
    status: Literal["scored", "unknown", "not_applicable"]
    reason: str

    def to_row(self) -> dict[str, object]:
        """Serialise the score for observability routes and replay payloads."""
        return asdict(self)


class BusinessScorer(Protocol):
    """Domain scorer plugged into the generic observability runtime."""

    scorer_id: str

    def supports(self, events: Iterable[Mapping[str, object]]) -> bool:
        """Whether this scorer owns the event family."""
        ...

    def score(self, events: Iterable[Mapping[str, object]]) -> list[BusinessScore]:
        """Return domain scores for the provided event rows."""
        ...


class BusinessScoringRegistry:
    """Registry that keeps the central runtime free of domain scoring rules."""

    def __init__(self) -> None:
        self._scorers: list[BusinessScorer] = []

    def register(self, scorer: BusinessScorer) -> None:
        """Register or replace one scorer by id."""
        self._scorers = [item for item in self._scorers if item.scorer_id != scorer.scorer_id]
        self._scorers.append(scorer)

    def score(self, events: Iterable[Mapping[str, object]]) -> list[BusinessScore]:
        """Score with every scorer that explicitly supports the rows."""
        rows = [dict(event) for event in events]
        scores: list[BusinessScore] = []
        for scorer in self._scorers:
            if scorer.supports(rows):
                scores.extend(scorer.score(rows))
        return scores

    def score_rows(self, events: Iterable[Mapping[str, object]]) -> list[dict[str, object]]:
        """Serialise every applicable score."""
        return [score.to_row() for score in self.score(events)]

    def clear(self) -> None:
        """Remove every registered scorer, for tests."""
        self._scorers.clear()


_REGISTRY = BusinessScoringRegistry()


def default_business_scoring_registry() -> BusinessScoringRegistry:
    """Return the process-wide business scoring registry."""
    return _REGISTRY


def register_business_scorer(scorer: BusinessScorer) -> None:
    """Register one domain scorer with the default registry."""
    _REGISTRY.register(scorer)


def reset_business_scoring_registry() -> None:
    """Clear the default registry, for tests that need isolation."""
    _REGISTRY.clear()


def score_rows(events: Iterable[Mapping[str, object]]) -> list[dict[str, object]]:
    """Score rows through the registered domain scorers."""
    return _REGISTRY.score_rows(events)
