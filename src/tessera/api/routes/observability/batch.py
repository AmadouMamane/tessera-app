"""Multiplex read endpoint — several observability panels in ONE round-trip.

The cockpit dashboards fetch a dozen small signal cards, each its own client XHR. Every XHR is
one tunnel round-trip (front on Cloud Run, agent on-prem behind ngrok), and the free tunnel
serialises a burst of ~25, so a page's fan-out tailed to several seconds even though each read is
now fast. This route collapses a page's individual card reads into a single request: it invokes
the SAME handler each card's own route uses, so every panel is byte-identical to the standalone
endpoint (``tests/unit/test_obs_batch_parity.py`` pins it), and it runs them CONCURRENTLY
server-side (the reads are synchronous ``def`` handlers → offloaded to the threadpool; the two
async readers are awaited directly). N tunnel round-trips become one.

Only an allowlist of KNOWN public-aggregate read keys is dispatchable — no arbitrary handler
lookup. A key whose compute raises is OMITTED from ``panels`` (never a fabricated value); the
frontend then renders that card's honest-empty, exactly as a failed individual fetch does.
Subject-scoped reads (memory inventory, transcripts) are deliberately absent — this is the public
surface, not the GDPR one.
"""

from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends

from tessera.api.routes.observability import (
    compliance,
    console,
    evals,
    fleet,
    memory,
    safety,
    signals,
)
from tessera.api.security import require_bearer

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

router = APIRouter()


@dataclass(frozen=True)
class _BatchScope:
    """The shared scope a batch call carries; each key uses only the fields it accepts."""

    agent: str
    at: str | None
    lang: str


# key -> (the individual route's handler, a builder for the kwargs that handler takes).
# The kwargs mirror EXACTLY what each card's client `fetchX` sends, so a panel equals the
# standalone endpoint. A handler that ignores agent/at simply has those omitted here.
_BATCH_KEYS: dict[str, tuple[Any, Callable[[_BatchScope], dict[str, Any]]]] = {
    # Sécurité — no-arg public reads
    "firewall-efficacy": (safety.observability_firewall_efficacy, lambda _s: {}),
    "least-privilege": (safety.observability_least_privilege, lambda _s: {}),
    "refusal": (safety.observability_refusal, lambda _s: {}),
    "cross-tenant": (safety.observability_cross_tenant, lambda _s: {}),
    "embedding-inversion": (safety.observability_embedding_inversion, lambda _s: {}),
    "erasure-coverage": (memory.observability_erasure_coverage, lambda _s: {}),
    "regression-risk": (evals.observability_regression_risk, lambda s: {"at": s.at}),
    "failed-cases": (evals.observability_failed_cases, lambda s: {"language": s.lang}),
    # Qualité-IA — as-of + agent scoped reads
    "conformance": (signals.observability_conformance, lambda s: {"at": s.at, "agent": s.agent}),
    "tool-validity": (
        safety.observability_tool_validity,
        lambda s: {"at": s.at, "agent": s.agent},
    ),
    "playbooks": (safety.observability_playbooks, lambda s: {"at": s.at, "agent": s.agent}),
    "roadmap": (fleet.observability_roadmap, lambda s: {"at": s.at, "agent": s.agent}),
    "ai-act": (compliance.observability_ai_act, lambda s: {"at": s.at}),
    "governance": (compliance.observability_governance, lambda s: {"at": s.at, "agent": s.agent}),
    "traces-obs": (console.observability_traces_obs, lambda s: {"at": s.at}),
    "control-signals": (signals.observability_control_signals, lambda s: {"lang": s.lang}),
}


async def _run_one(handler: Any, kwargs: dict[str, Any]) -> dict[str, object]:
    """Invoke one handler off the event loop: awaited if async, threadpooled if sync ``def``."""
    if inspect.iscoroutinefunction(handler):
        result: Awaitable[dict[str, object]] = handler(**kwargs)
        return await result
    return await asyncio.to_thread(handler, **kwargs)


@router.get("/observability/batch", dependencies=[Depends(require_bearer)])
async def observability_batch(
    keys: str,
    agent: str = "all",
    at: str | None = None,
    lang: str = "fr",
) -> dict[str, object]:
    """Return ``{"panels": {key: <that key's standalone payload>}}`` for the requested keys.

    ``keys`` is a comma-separated allowlist subset; unknown keys are ignored. The panels are
    computed concurrently server-side and are byte-identical to each key's individual route. A key
    whose compute raises is omitted so the card renders its honest-empty (parity with a failed
    individual fetch). ``agent``/``at``/``lang`` are the shared scope; each handler takes only what
    it accepts.
    """
    scope = _BatchScope(agent=agent, at=at, lang=lang)
    requested = [k for k in (part.strip() for part in keys.split(",")) if k in _BATCH_KEYS]

    async def _panel(key: str) -> tuple[str, dict[str, object] | None]:
        handler, build_kwargs = _BATCH_KEYS[key]
        try:
            return key, await _run_one(handler, build_kwargs(scope))
        except Exception:  # a failing panel is omitted, never fabricated
            return key, None

    settled = await asyncio.gather(*(_panel(key) for key in requested))
    return {"panels": {key: payload for key, payload in settled if payload is not None}}
