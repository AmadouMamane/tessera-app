"""ADR 0034's daily ceiling, asked by every path that spends — not only the chat turn.

``POST /chat`` has always resolved the budget policy and refused (or degraded to a local
model) once the day's spend reached the ceiling. Nothing else did. The summariser, the
reflector, the corpus translator, the judge and five observability probes call the same
backends and increment the same meter, and none of them ever asked — so the breaker bounded
the user-facing turn and nothing else, which is exactly backwards: the probes replay whole
catalogues, and they are the expensive ones.

This module is the one place that asks, so that routing a caller through the ceiling is a
one-line change rather than a copy of the chat route's logic. It applies **the same rule**,
deliberately, so that "over the ceiling" cannot come to mean two different things:

* no stored ceiling — or a store that cannot be read — means **no ceiling**. Fails open, out
  loud, exactly as :func:`resolve_budget_policy` does. The known-good state of this deployment
  is the one with no breaker, and nothing is ever refused because a settings table is down;
* a model with no price is never gated. A local zero-cost inference does not spend euros;
* over the ceiling with ``overrun="local_fallback"`` and a free base model: serve the base;
* over the ceiling otherwise: refuse, and name the ceiling and the spend in the refusal.

The policy read hits Postgres, so it is cached for :data:`_POLICY_TTL_SECONDS`. **The spend is
not cached** — it is re-read from the tracker on every call. That asymmetry is the whole point:
the ceiling is an operator setting that changes a few times a year, while the spend is the
thing that crosses it, and caching the crossing would let a probe keep spending for a TTL
after the breaker tripped.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from tessera.llm.budget import get_budget_tracker, model_is_paid

if TYPE_CHECKING:
    from decimal import Decimal

    from tessera.api.config_overrides import BudgetPolicy

__all__ = [
    "DailyCeilingReachedError",
    "invalidate_policy_cache",
    "resolve_spend_model",
]


#: How long a read of the stored ceiling stays good. Short enough that an operator who lowers
#: the ceiling sees it take effect within a page refresh, long enough that a probe replaying a
#: catalogue does not open a Postgres connection per generated answer. Writes through
#: ``/settings`` invalidate it immediately (see :func:`invalidate_policy_cache`), so the TTL is
#: the backstop for a change made by another worker, not the mechanism.
_POLICY_TTL_SECONDS: Final[float] = 30.0

#: ``(read_at_monotonic, policy)``. ``None`` inside the tuple is a **cached** "no ceiling",
#: which is a real answer and worth caching; ``None`` for the whole tuple is "never read".
_cached_policy: tuple[float, BudgetPolicy | None] | None = None


@dataclass(frozen=True, slots=True)
class _Refusal:
    """The numbers a refusal must carry to be checkable by whoever reads it."""

    caller: str
    model: str
    ceiling_eur: Decimal
    day_spend_eur: Decimal


class DailyCeilingReachedError(RuntimeError):
    """This caller may not spend: the org's daily ceiling is reached (ADR 0034).

    Raised rather than returned so that a caller which forgets to check cannot spend by
    accident — and caught in exactly one place per surface, so a refusal reaches the operator
    as a refusal instead of as a zero. A probe that returned an empty report here would be
    indistinguishable from a probe that ran and found nothing, which is the failure mode this
    repository keeps paying for (ADR 0026).
    """

    def __init__(self, refusal: _Refusal) -> None:
        self.caller = refusal.caller
        self.model = refusal.model
        self.ceiling_eur = refusal.ceiling_eur
        self.day_spend_eur = refusal.day_spend_eur
        super().__init__(
            f"{refusal.caller}: refused to spend on {refusal.model!r} — the daily ceiling of "
            f"{refusal.ceiling_eur} EUR is reached (day spend {refusal.day_spend_eur} EUR). "
            "Raise or clear the ceiling in Settings, or wait for the Europe/Paris day to roll."
        )


def invalidate_policy_cache() -> None:
    """Drop the cached ceiling — called when the stored policy is written."""
    global _cached_policy
    _cached_policy = None


async def _policy() -> BudgetPolicy | None:
    """The stored policy, cached for :data:`_POLICY_TTL_SECONDS`."""
    global _cached_policy
    now = time.monotonic()
    if _cached_policy is not None and now - _cached_policy[0] < _POLICY_TTL_SECONDS:
        return _cached_policy[1]
    # Imported here, not at module scope: `tessera.api` imports the llm package, and a
    # top-level import would close that cycle.
    from tessera.api.config_overrides import resolve_budget_policy

    policy = await resolve_budget_policy()
    _cached_policy = (now, policy)
    return policy


async def resolve_spend_model(*, caller: str, model: str | None = None) -> str:
    """Return the model ``caller`` may actually spend on, or refuse.

    Args:
        caller: What is about to spend, named for the refusal message — a module path or a
            probe name, never a role. A refusal that cannot say who was refused is a log line
            nobody can act on (ADR 0024).
        model: The model the caller intends to use; ``None`` means the frozen base.

    Returns:
        ``model`` when there is room, or the free base model when the stored policy declares
        ``local_fallback`` and the base is free. Never ``None``: the caller gets a concrete
        model or an exception.

    Raises:
        DailyCeilingReachedError: The ceiling is reached and no free fallback exists.
    """
    from tessera.api.config_overrides import base_chat_model

    intended = model or base_chat_model()
    policy = await _policy()
    if policy is None or not model_is_paid(intended):
        return intended

    day_spend = get_budget_tracker().snapshot().day_cost_eur
    if day_spend < policy.daily_eur:
        return intended

    base = base_chat_model()
    if policy.overrun == "local_fallback" and not model_is_paid(base):
        sys.stderr.write(
            f"tessera.ceiling: {caller} over the daily ceiling {policy.daily_eur} EUR "
            f"(day spend {day_spend}) — serving the free base model {base!r} instead of "
            f"{intended!r}\n"
        )
        return base
    # A fallback onto a paid base is not a fallback. Same call the chat route makes.
    raise DailyCeilingReachedError(
        _Refusal(
            caller=caller,
            model=intended,
            ceiling_eur=policy.daily_eur,
            day_spend_eur=day_spend,
        )
    )
