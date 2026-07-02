"""Per-dimension "data available since" boundaries (ADR 0015 §Testing 2).

Stamping is **forward-only**: a dimension only exists in the durable stores from the moment
the code started stamping it (``agent_id`` since the chat path threaded the responder;
``model`` since ADR 0015 §Migration B). An as-of-T read *before* a dimension's boundary must
read org-wide (or empty) — the cockpit never pretends a dimension existed before it was
stamped. This computes each boundary **honestly** from the real data: the earliest timestamp
of a row that actually carries the dimension, ``None`` when the dimension has no data yet.

This generalises ADR 0011's ``/observability/data-range`` (which is the ``time`` boundary)
to every dimension of :class:`~tessera.observability.spine.scope.Scope`.
"""

from __future__ import annotations

from tessera.observability.replay import persisted_bundles
from tessera.observability.spine.adapters import read_scores
from tessera.observability.spine.scope import Dimension

__all__ = ["dimension_availability"]


def _min_or_none(stamps: list[str]) -> str | None:
    """The lexicographic minimum ISO instant (matches the timeline ordering), or ``None``."""
    present = [s for s in stamps if s]
    return min(present) if present else None


def dimension_availability() -> dict[str, str | None]:
    """The earliest instant real data exists for each dimension, or ``None`` if none.

    Returns a mapping keyed by :class:`Dimension` value (``time`` / ``agent`` / ``model`` /
    ``language``). ``time`` is the overall earliest durable instant (the ADR 0011 range
    start); a per-agent/model/language boundary is the earliest row that *carries* that
    dimension — so a read before it is honestly org-wide, never a fabricated per-agent past.
    """
    scores = read_scores(full=True)
    bundles = persisted_bundles(None)

    score_times = [str(s.get("scored_at", "")) for s in scores]
    bundle_times = [b.captured_at for b in bundles]

    agent_times = [str(s.get("scored_at", "")) for s in scores if s.get("agent_id")]
    agent_times += [b.captured_at for b in bundles if b.agent_id]

    model_times = [str(s.get("scored_at", "")) for s in scores if s.get("model")]
    model_times += [b.captured_at for b in bundles if b.original_model]

    language_times = [str(s.get("scored_at", "")) for s in scores if s.get("language")]
    language_times += [b.captured_at for b in bundles if b.language]

    return {
        Dimension.TIME.value: _min_or_none(score_times + bundle_times),
        Dimension.AGENT.value: _min_or_none(agent_times),
        Dimension.MODEL.value: _min_or_none(model_times),
        Dimension.LANGUAGE.value: _min_or_none(language_times),
    }
