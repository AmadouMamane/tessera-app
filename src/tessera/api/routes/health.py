"""Liveness, readiness, and metrics endpoints."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Response, status
from pydantic import BaseModel

from tessera import __version__
from tessera.code_identity import identity
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
    """Body returned by ``/healthz`` and ``/readyz``.

    ``version`` is the *package* version — it changes on a release, not on a commit, and it was
    the only thing this endpoint ever said about its own code. It is therefore useless for the
    one question an operator actually has in front of a running server: **is this the code I
    think it is?** The ``code_*`` fields answer that, and they answer it *about the process*
    (ADR 0026): they are captured at import and frozen, so a checkout that moves underneath a
    live server cannot change what it reports.
    """

    status: str
    version: str
    # The deployment environment the process believes it is in (mono-env, fixed by
    # process). Read-only context for the header badge — never a re-scoping control.
    environment: str

    #: Content hash of the ``.py`` files this process LOADED. The evidence — no git required, so
    #: it works identically in a container. This is what `make dev-status` compares.
    code_digest: str
    #: The commit that content came from. ``None`` when the process cannot know — never a
    #: fabricated value that reads like knowledge.
    code_sha: str | None
    #: ``env`` (a build stamped it) · ``git`` (a source tree) · ``unknown`` (and that is a fact).
    code_sha_source: str
    #: Uncommitted edits at load time. ``None`` = unknowable, never a comfortable ``false``.
    code_dirty: bool | None


def _health(status_text: str) -> HealthResponse:
    """One body, one place the code identity is read from — frozen at import, never recomputed."""
    code = identity()
    return HealthResponse(
        status=status_text,
        version=__version__,
        environment=get_settings().environment,
        code_digest=code.digest,
        code_sha=code.sha,
        code_sha_source=code.sha_source,
        code_dirty=code.dirty,
    )


@router.get("/healthz", response_model=HealthResponse)
async def liveness() -> HealthResponse:
    """Liveness probe — returns 200 as soon as the process is up, and says what code it is.

    The code identity is a frozen constant read here, never re-derived: if this handler called
    ``git`` or hashed the filesystem, it would be reporting what is on disk **now** — which is
    the question `dev-status` was already asking, and the reason it lied for a week.
    """
    return _health("ok")


@router.get("/readyz", response_model=HealthResponse)
async def readiness(response: Response) -> HealthResponse:
    """Readiness probe — verifies the chat backend is reachable.

    Distinct from liveness so deployments can stagger, and so a container only
    reports healthy when it can actually answer a turn. Returns 503 when the
    LLM backend is unreachable, which is what flips the Docker healthcheck (and
    any orchestrator) to unhealthy instead of serving silent escalations.
    """
    if not await _llm_reachable():
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return _health("llm_unreachable")
    return _health("ready")


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
