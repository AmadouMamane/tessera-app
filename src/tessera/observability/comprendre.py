"""Live facts for the public `/comprendre` page.

The page explains four capabilities and pairs each with one measured fact. This module composes
those facts from the existing fleet, S1 journal, release and audit-verification seams. It owns no
counter and no store. A source that has not produced evidence yields ``None`` for its tile; the
frontend then renders the exact honest-empty reason from its locale catalogue.
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TypedDict
from zoneinfo import ZoneInfo

from tessera.observability import agent_release, fleet, guard_activity, turn_evidence

__all__ = [
    "AuditVerification",
    "ComprendreData",
    "build_comprendre",
    "paris_midnight",
]

_PARIS = ZoneInfo("Europe/Paris")
_OBSERVATION_WINDOW = timedelta(hours=24)
_FLEET_SILENT_AFTER = timedelta(minutes=15)


class FleetFact(TypedDict):
    """Observed fleet fact over the declared rolling window."""

    observed_agents: int | None
    last_signal_at: str | None
    is_silent: bool | None
    window_hours: int


class GuardFact(TypedDict):
    """Real guard exchanges since Paris midnight."""

    controlled_today: int | None
    blocked_today: int | None
    since: str


class EvaluationFact(TypedDict):
    """Release buckets shared with the Eval tile."""

    ready_agents: int | None
    review_agents: int | None


class AuditFact(TypedDict):
    """Last successful chain verification."""

    last_verified_at: str | None


class ComprendreData(TypedDict):
    """Everything an available `/observability/comprendre` response promises."""

    generated_at: str
    fleet: FleetFact
    guard: GuardFact
    evaluations: EvaluationFact
    audit: AuditFact


@dataclass(frozen=True, slots=True)
class AuditVerification:
    """The effective verification just performed through ``audit_integrity``."""

    verified: bool
    length: int
    full_verified_at: str | None
    checked_at: datetime


def paris_midnight(now: datetime) -> datetime:
    """Return the start of the current civil day in Europe/Paris.

    Args:
        now: A timezone-aware reference instant.

    Returns:
        Midnight with the correct Paris UTC offset for that date, including DST changes.

    Raises:
        ValueError: If ``now`` is timezone-naive.
    """
    if now.tzinfo is None:
        msg = "Paris midnight requires a timezone-aware instant"
        raise ValueError(msg)
    local = now.astimezone(_PARIS)
    return local.replace(hour=0, minute=0, second=0, microsecond=0)


async def _fleet_fact(now: datetime) -> FleetFact:
    since = now - _OBSERVATION_WINDOW
    try:
        observations = await asyncio.to_thread(
            turn_evidence.recent_turn_evidence,
            since,
            until=now,
        )
    except Exception as exc:
        sys.stderr.write(f"tessera.observability.comprendre.fleet: failed: {exc}\n")
        observations = {}
    registered = fleet.registered_agent_ids()
    observations = {
        agent_id: observed_at
        for agent_id, observed_at in observations.items()
        if agent_id in registered
    }
    if not observations:
        return {
            "observed_agents": None,
            "last_signal_at": None,
            "is_silent": None,
            "window_hours": int(_OBSERVATION_WINDOW.total_seconds() // 3600),
        }
    latest = max(observations.values())
    return {
        "observed_agents": len(observations),
        "last_signal_at": latest.astimezone(UTC).isoformat(),
        "is_silent": now - latest > _FLEET_SILENT_AFTER,
        "window_hours": int(_OBSERVATION_WINDOW.total_seconds() // 3600),
    }


async def _guard_fact(now: datetime) -> GuardFact:
    since = paris_midnight(now)
    try:
        counts = await asyncio.to_thread(guard_activity.exchange_counts_since, since)
    except Exception as exc:
        sys.stderr.write(f"tessera.observability.comprendre.guard: failed: {exc}\n")
        return {"controlled_today": None, "blocked_today": None, "since": since.isoformat()}
    if counts.controlled == 0:
        return {"controlled_today": None, "blocked_today": None, "since": since.isoformat()}
    return {
        "controlled_today": counts.controlled,
        "blocked_today": counts.blocked,
        "since": since.isoformat(),
    }


async def _evaluation_fact() -> EvaluationFact:
    try:
        buckets = await asyncio.to_thread(agent_release.fleet_release_buckets)
    except Exception as exc:
        sys.stderr.write(f"tessera.observability.comprendre.evaluations: failed: {exc}\n")
        return {"ready_agents": None, "review_agents": None}
    if buckets["evaluated"] == 0:
        return {"ready_agents": None, "review_agents": None}
    return {"ready_agents": buckets["ready"], "review_agents": buckets["review"]}


def _audit_fact(verification: AuditVerification | None) -> AuditFact:
    if verification is None or not verification.verified or verification.length <= 0:
        return {"last_verified_at": None}
    # Postgres persists when the complete prefix was last walked; file mode walks the entire
    # chain on this very request and therefore has no persisted checkpoint timestamp. In that
    # mode the effective successful verification time is this call's checked_at — never a
    # fabricated status, because the route constructs this object only after audit_integrity ran.
    stamp = verification.full_verified_at or verification.checked_at.astimezone(UTC).isoformat()
    return {"last_verified_at": stamp}


async def build_comprendre(
    verification: AuditVerification | None,
    *,
    now: datetime | None = None,
) -> ComprendreData:
    """Compose the four live proof tiles without letting one failed source blank the others.

    Args:
        verification: Result of the route's effective ``audit_integrity`` call, or ``None`` if
            that verification could not run.
        now: Optional aware reference instant for deterministic tests.

    Returns:
        The complete typed payload with tile-level honest empties represented by ``None``.
    """
    reference = now or datetime.now(UTC)
    if reference.tzinfo is None:
        msg = "comprendre snapshot requires a timezone-aware instant"
        raise ValueError(msg)
    fleet, guard, evaluations = await asyncio.gather(
        _fleet_fact(reference),
        _guard_fact(reference),
        _evaluation_fact(),
    )
    return {
        "generated_at": reference.astimezone(UTC).isoformat(),
        "fleet": fleet,
        "guard": guard,
        "evaluations": evaluations,
        "audit": _audit_fact(verification),
    }
