"""Online evaluation + the trace→dataset flywheel (ADR 0010, Phase 4).

* :mod:`judge` — LLM-as-judge, defaulting to the sovereign local summary backend.
* :mod:`scores` — eval-as-telemetry: round-trips scores into logs, metrics, spans.
* :mod:`online` — tiered, cost-aware online evaluation with guard↔judge disagreement.
* :mod:`flywheel` — curates confirmed failures into the regression harness.
"""

from __future__ import annotations

from tessera.observability.eval import flywheel, judge, online, scores

__all__ = ["flywheel", "judge", "online", "scores"]
