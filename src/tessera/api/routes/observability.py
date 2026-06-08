"""Observability read endpoints for the dashboard (ADR 0010).

Exposes the recent online-eval scores so the dashboard can surface
eval-as-telemetry live. Aggregate quality scores are a public surface
(ADR 0009), so this endpoint is unauthenticated like ``/healthz``.
"""

from __future__ import annotations

from fastapi import APIRouter

from tessera.observability.eval.scores import recent_scores

router = APIRouter(tags=["observability"])


@router.get("/observability/scores")
async def observability_scores() -> dict[str, object]:
    """Return the most recent online-eval scores (newest last)."""
    return {"scores": recent_scores()}
