"""Refusal-rate calibration (ADR 0010, idea #58).

A safe agent must be calibrated in *both* directions. **Over-refusal** — turning
away a legitimate banking question — erodes trust and utility. **Under-refusal**
— carrying out a forbidden action — is a safety incident. This module measures
both against the input guard: it runs a set of legitimate questions and a set of
forbidden requests through ``check_user_input`` and reports the over- and
under-refusal rates.

It is deliberately honest about scope: the input guard catches injection-shaped
attacks, not every policy-forbidden *action* (those need the agent/judge layer),
so a non-zero under-refusal rate here quantifies exactly the gap the downstream
layers must close.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING

from tessera.guard.adapter import check_user_input
from tessera.guard.audit import GUARD_ACTOR
from tessera.guard.decisions import load_policy
from tessera.guard.limes_backend import injection_witness

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tessera.guard.decisions import Policy

__all__ = [
    "RefusalReport",
    "compute_refusal_calibration",
    "load_forbidden",
    "load_legit",
    "reset_refusal_cache",
]

# src/tessera/observability/refusal.py → parents[3] is the repo root.
_REPO = Path(__file__).resolve().parents[3]
_LEGIT_PATH = _REPO / "eval" / "calibration" / "benign_inputs.json"
_FORBIDDEN_PATH = _REPO / "eval" / "calibration" / "forbidden_inputs.json"


@dataclass(frozen=True, slots=True)
class RefusalReport:
    """Over- and under-refusal of the guard on legit vs forbidden inputs."""

    n_legit: int
    n_forbidden: int
    legit_refused: int
    forbidden_allowed: int
    over_refusal_rate: float  # legit wrongly refused, 0..1 (lower is better)
    under_refusal_rate: float  # forbidden wrongly allowed, 0..1 (lower is better)


def load_legit() -> list[str]:
    """Load the legitimate-question set (should not be refused)."""
    data: list[str] = json.loads(_LEGIT_PATH.read_text(encoding="utf-8"))
    return data


def load_forbidden() -> list[str]:
    """Load the forbidden-request set (should be refused)."""
    data: list[str] = json.loads(_FORBIDDEN_PATH.read_text(encoding="utf-8"))
    return data


# The default-corpus report is deterministic given the live policy, but scoring it runs the whole
# corpus through the guard (llama inferences). It is a batch-snapshot panel the leader recomputes
# every cycle, so uncached it burned that CPU continuously; memoise it on the policy hash so the
# corpus runs once per policy change. A custom corpus (tests) bypasses the cache.
_REFUSAL_CACHE_LOCK = Lock()
_REFUSAL_CACHE: tuple[str, RefusalReport] | None = None  # (policy_hash, report)


def reset_refusal_cache() -> None:
    """Drop the memoised default-corpus refusal report (test isolation)."""
    global _REFUSAL_CACHE
    with _REFUSAL_CACHE_LOCK:
        _REFUSAL_CACHE = None


def _refused(text: str, policy: Policy) -> bool:
    # audit=False: this is a calibration MEASUREMENT over a fixed corpus, not real user traffic —
    # it must not append to the opposability ledger (it is a batch-snapshot panel, so auditing it
    # flooded the append-only chain every cycle). The allow/deny decision is unchanged.
    return not check_user_input(text, policy=policy, actor=GUARD_ACTOR, audit=False).allowed


def compute_refusal_calibration(
    *,
    legit: Sequence[str] | None = None,
    forbidden: Sequence[str] | None = None,
    policy: Policy | None = None,
) -> RefusalReport:
    """Measure over- and under-refusal of the guard.

    The default corpus is memoised on the live policy hash (scoring it runs the whole corpus
    through the guard, and it is a batch-snapshot panel recomputed every cycle). A custom corpus
    or policy (tests) always scores fresh.

    Args:
        legit: Legitimate questions; the bundled set is loaded if omitted.
        forbidden: Forbidden requests; the bundled set is loaded if omitted.
        policy: Guard policy to test; loaded if omitted.

    Returns:
        A :class:`RefusalReport`.
    """
    if legit is not None or forbidden is not None or policy is not None:
        return _score_refusal(legit=legit, forbidden=forbidden, policy=policy)

    _, _, policy_hash = injection_witness()  # cheap: detector metadata, runs no guard checks
    global _REFUSAL_CACHE
    with _REFUSAL_CACHE_LOCK:
        cached = _REFUSAL_CACHE
        if cached is not None and cached[0] == policy_hash:
            return cached[1]
    report = _score_refusal(legit=None, forbidden=None, policy=None)
    with _REFUSAL_CACHE_LOCK:
        _REFUSAL_CACHE = (policy_hash, report)
    return report


def _score_refusal(
    *,
    legit: Sequence[str] | None = None,
    forbidden: Sequence[str] | None = None,
    policy: Policy | None = None,
) -> RefusalReport:
    """Run the guard over legit + forbidden corpora and score over/under-refusal (uncached)."""
    legit_inputs = list(legit) if legit is not None else load_legit()
    forbidden_inputs = list(forbidden) if forbidden is not None else load_forbidden()
    active_policy = policy or load_policy()

    legit_refused = sum(1 for text in legit_inputs if _refused(text, active_policy))
    forbidden_allowed = sum(1 for text in forbidden_inputs if not _refused(text, active_policy))

    n_legit = len(legit_inputs)
    n_forbidden = len(forbidden_inputs)
    return RefusalReport(
        n_legit=n_legit,
        n_forbidden=n_forbidden,
        legit_refused=legit_refused,
        forbidden_allowed=forbidden_allowed,
        over_refusal_rate=(legit_refused / n_legit if n_legit else 0.0),
        under_refusal_rate=(forbidden_allowed / n_forbidden if n_forbidden else 0.0),
    )
