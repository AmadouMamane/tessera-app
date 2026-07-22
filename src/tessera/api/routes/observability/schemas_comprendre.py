"""Wire contract for the `/observability/comprendre` public aggregate."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class ComprendreFleetFact(BaseModel):
    """Observed fleet fact."""

    model_config = ConfigDict(extra="forbid")

    observed_agents: int | None
    last_signal_at: str | None
    is_silent: bool | None
    window_hours: int


class ComprendreGuardFact(BaseModel):
    """Real guard activity since Paris midnight."""

    model_config = ConfigDict(extra="forbid")

    controlled_today: int | None
    blocked_today: int | None
    since: str


class ComprendreEvaluationFact(BaseModel):
    """Shared release buckets."""

    model_config = ConfigDict(extra="forbid")

    ready_agents: int | None
    review_agents: int | None


class ComprendreAuditFact(BaseModel):
    """Effective audit verification freshness."""

    model_config = ConfigDict(extra="forbid")

    last_verified_at: str | None


class ComprendrePayload(BaseModel):
    """Available response; every tile is present, even when its evidence is empty."""

    model_config = ConfigDict(extra="forbid")

    available: Literal[True]
    generated_at: str
    fleet: ComprendreFleetFact
    guard: ComprendreGuardFact
    evaluations: ComprendreEvaluationFact
    audit: ComprendreAuditFact


class ComprendreUnavailable(BaseModel):
    """Only a composition contract break collapses the endpoint."""

    model_config = ConfigDict(extra="forbid")

    available: Literal[False]
