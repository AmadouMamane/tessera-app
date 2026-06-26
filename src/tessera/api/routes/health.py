"""Liveness, readiness, and metrics endpoints."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Response, status
from pydantic import BaseModel

from tessera import __version__
from tessera.llm import get_budget_tracker
from tessera.settings import LLMProfile, get_settings

router = APIRouter(tags=["ops"])

# Keep the readiness probe well under the container healthcheck timeout (5s) so
# a hung Ollama surfaces as not-ready rather than a probe timeout.
_READINESS_TIMEOUT_S = 4.0


async def _llm_reachable() -> bool:
    """Best-effort connectivity check for the active chat backend.

    Readiness must reflect whether the agent can actually serve a turn, not
    merely that the process is up: an unreachable Ollama is exactly the failure
    that silently degrades chat into a "handed off to an advisor" escalation,
    yet leaves liveness green. Only the on-prem Ollama path has a cheap local
    probe (``list`` hits ``/api/tags`` without loading a model); the frontier
    path is gated by the managed platform's own checks, so it reports ready.
    """
    settings = get_settings()
    if settings.resolved_llm_profile() is not LLMProfile.ON_PREM:
        return True
    import ollama

    try:
        client = ollama.AsyncClient(host=str(settings.ollama.host))
        await asyncio.wait_for(client.list(), timeout=_READINESS_TIMEOUT_S)
    except Exception:
        return False
    return True


class HealthResponse(BaseModel):
    """Body returned by ``/healthz`` and ``/readyz``."""

    status: str
    version: str
    # The deployment environment the process believes it is in (mono-env, fixed by
    # process). Read-only context for the header badge — never a re-scoping control.
    environment: str


@router.get("/healthz", response_model=HealthResponse)
async def liveness() -> HealthResponse:
    """Liveness probe — returns 200 as soon as the process is up."""
    return HealthResponse(status="ok", version=__version__, environment=get_settings().environment)


@router.get("/readyz", response_model=HealthResponse)
async def readiness(response: Response) -> HealthResponse:
    """Readiness probe — verifies the chat backend is reachable.

    Distinct from liveness so deployments can stagger, and so a container only
    reports healthy when it can actually answer a turn. Returns 503 when the
    LLM backend is unreachable, which is what flips the Docker healthcheck (and
    any orchestrator) to unhealthy instead of serving silent escalations.
    """
    env = get_settings().environment
    if not await _llm_reachable():
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(status="llm_unreachable", version=__version__, environment=env)
    return HealthResponse(status="ready", version=__version__, environment=env)


@router.get("/budget", response_class=Response, status_code=status.HTTP_200_OK)
async def budget() -> Response:
    """Return the running LLM-cost estimate as text/plain for quick scrapes."""
    snapshot = get_budget_tracker().snapshot()
    body = (
        f"input_tokens {snapshot.input_tokens}\n"
        f"output_tokens {snapshot.output_tokens}\n"
        f"estimated_cost_eur {snapshot.estimated_cost_eur:.6f}\n"
    )
    return Response(content=body, media_type="text/plain")
