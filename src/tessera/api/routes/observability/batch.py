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

``/observability/batch`` is scoped to ONE agent, so it cannot carry the two FLEET-WIDE reads a
GOUVERNER breakdown page makes (the fleet rollup and the per-agent snapshot fan-out).
``/observability/fleet-batch`` below is the same idea for those two: same handlers, one
round-trip.
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
from tessera.api.routes.observability.fleet import observability_fleet
from tessera.api.routes.observability.signals import (
    observability_fleet_snapshot,
    observability_snapshot,
)
from tessera.api.security import require_bearer
from tessera.observability.read_snapshot import (
    SNAPSHOT_TTL_S,
    batch_snapshot_key,
    read_snapshot,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Coroutine

router = APIRouter()


@dataclass(frozen=True)
class _BatchScope:
    """The shared scope a batch call carries; each key uses only the fields it accepts."""

    agent: str
    at: str | None
    lang: str
    days: str | None = None


# key -> (the individual route's handler, a builder for the kwargs that handler takes).
# The kwargs mirror EXACTLY what each card's client `fetchX` sends, so a panel equals the
# standalone endpoint. A handler that ignores agent/at simply has those omitted here.
_BATCH_KEYS: dict[str, tuple[Any, Callable[[_BatchScope], dict[str, Any]]]] = {
    # Sécurité — no-arg public reads
    "firewall-efficacy": (safety.observability_firewall_efficacy, lambda _s: {}),
    "refusal": (safety.observability_refusal, lambda _s: {}),
    # The recorded jailbreak-drift snapshots. Org-wide and unscoped by nature: a red-team
    # campaign is run against the deployed policy, not against one agent's week.
    "redteam": (safety.observability_redteam, lambda _s: {}),
    # These two used to sit above with the no-arg probes, because their handlers took no scope.
    # They do now, and passing it is not optional: their CURVES are computed per bucket, so a
    # card left reading all-history would print one window's number under another window's
    # line. The two ways to keep them agreeing are to scope both or neither, and neither means
    # deleting a curve that the samples support.
    "least-privilege": (
        safety.observability_least_privilege,
        lambda s: {"at": s.at, "agent": s.agent, "days": s.days},
    ),
    "cross-tenant": (
        safety.observability_cross_tenant,
        lambda s: {"at": s.at, "agent": s.agent, "days": s.days},
    ),
    "embedding-inversion": (safety.observability_embedding_inversion, lambda _s: {}),
    "erasure-coverage": (memory.observability_erasure_coverage, lambda _s: {}),
    "regression-risk": (evals.observability_regression_risk, lambda s: {"at": s.at}),
    "failed-cases": (evals.observability_failed_cases, lambda s: {"language": s.lang}),
    # Qualité-IA — as-of + agent scoped reads
    "conformance": (
        signals.observability_conformance,
        lambda s: {"at": s.at, "agent": s.agent, "days": s.days},
    ),
    "tool-validity": (
        safety.observability_tool_validity,
        lambda s: {"at": s.at, "agent": s.agent, "days": s.days},
    ),
    "playbooks": (
        safety.observability_playbooks,
        lambda s: {"at": s.at, "agent": s.agent, "days": s.days},
    ),
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


async def _compute_panels(scope: _BatchScope, keys: list[str]) -> dict[str, object]:
    """Compute the requested panels concurrently; a panel whose compute raises is omitted."""

    async def _panel(key: str) -> tuple[str, dict[str, object] | None]:
        handler, build_kwargs = _BATCH_KEYS[key]
        try:
            return key, await _run_one(handler, build_kwargs(scope))
        except Exception:  # a failing panel is omitted, never fabricated
            return key, None

    settled = await asyncio.gather(*(_panel(key) for key in keys))
    return {key: payload for key, payload in settled if payload is not None}


async def compute_all_panels(lang: str) -> dict[str, object]:
    """Every batch panel for the default org-wide scope (agent=all, at=None) — the snapshot input.

    The leader (ADR 0046) computes this once per cycle and publishes it; the endpoint below then
    serves any requested subset of it from the shared file instead of re-fanning-out the panels.
    """
    scope = _BatchScope(agent="all", at=None, lang=lang)
    return await _compute_panels(scope, list(_BATCH_KEYS))


@router.get("/observability/batch", dependencies=[Depends(require_bearer)])
async def observability_batch(
    keys: str,
    agent: str = "all",
    at: str | None = None,
    lang: str = "fr",
    days: str | None = None,
) -> dict[str, object]:
    """Return ``{"panels": {key: <that key's standalone payload>}}`` for the requested keys.

    ``keys`` is a comma-separated allowlist subset; unknown keys are ignored. The panels are
    byte-identical to each key's individual route. A key whose compute raises is omitted so the card
    renders its honest-empty (parity with a failed individual fetch). ``agent``/``at``/``lang`` are
    the shared scope; each handler takes only what it accepts.

    For the DEFAULT org-wide scope (agent=all, at=None) the whole panel set is served from the
    leader-computed shared snapshot (ADR 0046) — a file read instead of re-fanning-out 16 panels
    concurrently, which cold would stampede the shared ledger read. Any other scope (an agent
    filter, an as-of-T read) computes fresh, and so does a snapshot miss.
    """
    requested = [k for k in (part.strip() for part in keys.split(",")) if k in _BATCH_KEYS]
    # The shared snapshot is computed for the DEFAULT scope only, and a period is part of
    # the scope: serving it to a caller that asked for 24 h would hand back the leader's
    # all-history panels under a window the operator chose. A period computes fresh, for
    # the same reason an agent filter or an as-of-T read does.
    if agent == "all" and at is None and days is None:
        snap = read_snapshot(batch_snapshot_key(lang), SNAPSHOT_TTL_S)
        if snap is not None:
            return {"panels": {key: snap[key] for key in requested if key in snap}}
    scope = _BatchScope(agent=agent, at=at, lang=lang, days=days)
    return {"panels": await _compute_panels(scope, requested)}


@router.get("/observability/fleet-batch", dependencies=[Depends(require_bearer)])
async def observability_fleet_batch(
    lang: str = "fr",
    period: str | None = None,
    at: str | None = None,
    signals: str | None = None,
    org_signals: str | None = None,
) -> dict[str, object]:
    """The FLEET-WIDE reads a GOUVERNER breakdown makes, in ONE round-trip.

    A domain page's "Vue par agent" card needs the fleet rollup (``/observability/fleet``: the
    agents, their KPIs, the deduplicated org total) and then one snapshot per fleet agent
    (``/observability/fleet-snapshot``, itself already a collapsed fan-out). The two are
    INDEPENDENT — the second's ``?signals=`` comes from the page's declared domain, not from the
    first — yet the front had to await them in series, and each await is a full tunnel round-trip
    when the frontend runs on Cloud Run and the agent on-prem. This returns them at once and
    computes them CONCURRENTLY server-side. 2 round-trips become 1.

    ``?org_signals=`` adds the ORG-WIDE snapshot (``/observability/snapshot?agent=all``) as a
    third half. That is the Qualité IA page, whose first read decides the *plan* (org breach →
    alarm columns; quiet → quality columns; org-wide breach → no per-agent fan-out at all) and
    therefore cannot be coalesced with the fan-out itself — but its rollup and its org read are
    as independent as the domain pages' pair, so they travel together and that page pays 2
    round-trips instead of 3 (1 when the plan settles it org-wide).

    It invents nothing: each half is produced by the SAME handler its own route registers
    (``tests/unit/test_fleet_batch_parity.py`` pins every half against those routes at the wire),
    so the halves are byte-identical to the responses they replace. Each already degrades
    honestly on its own — the fleet to ``available: false``, the snapshot by OMITTING an agent
    whose compute raised — and those degradations are passed through untouched and
    independently: a failed fleet does not empty the snapshot, and vice versa.

    A half is computed ONLY when its parameter is present, and omitted from the body otherwise —
    so a caller never pays for a read it will not render. Note the difference from the standalone
    route this mirrors: there, an absent ``?signals=`` means *every* hot-path signal; here it
    means *no fan-out*. The caller that omits it (the quality page's first read) does not yet
    know which signals its plan will want, and defaulting to all of them would fan every agent
    out over the whole catalogue to throw most of it away.

    ``lang``/``period``/``at`` scope EVERY half: the fleet rollup exactly as its own route does,
    and the two snapshot halves through their own ``days``/``at`` parameters. This overturns the
    earlier deliberate asymmetry (the snapshot halves used to stay live and all-history while the
    rollup obeyed the rail) — argued on its own merits and decided on 2026-08-26: the breakdown
    rows and the rollup total render inside ONE card under ONE period control, and two clocks in
    one card is the very incoherence the front's period plumbing exists to end. A caller that
    sends no ``period``/``at`` (the audit-logs proof breakdown) keeps the all-history, live
    contract unchanged. The halves' ``language``/``model`` dimensions remain unexposed: no
    breakdown sends them.
    """
    halves: dict[str, Coroutine[Any, Any, object]] = {
        "fleet": observability_fleet(lang=lang, period=period, at=at)
    }
    if signals:
        halves["fleet_snapshot"] = observability_fleet_snapshot(signals=signals, days=period, at=at)
    if org_signals:
        halves["snapshot"] = observability_snapshot(
            agent="all", signals=org_signals, days=period, at=at
        )
    computed = await asyncio.gather(*halves.values())
    return dict(zip(halves, computed, strict=True))
