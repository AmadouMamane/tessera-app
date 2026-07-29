"""Continuous red-teaming / jailbreak drift (ADR 0010, idea #24).

A firewall measured once (#13) is a point estimate. Attacks evolve, and so does
the policy: a regex that blocked yesterday's jailbreak misses tomorrow's
paraphrase. This module replays a bundled adversarial corpus through the guard
and records the **attack-success rate** — the share of attacks that slip past —
as a timestamped snapshot. Repeated runs form a drift series: a rising rate (new
attack family) or a falling one (a policy tightening) both show up immediately.

The guard is regex-only here, so each run is fast and deterministic. The honest
takeaway the demo makes: a static pattern guard *will* leave residual success,
which is exactly why continuous red-teaming and the downstream judge matter.
"""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from tessera.guard.adapter import check_user_input
from tessera.guard.audit import GUARD_ACTOR
from tessera.guard.decisions import load_policy
from tessera.observability.firewall_efficacy import load_injection_prompts

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tessera.guard.decisions import Policy

__all__ = ["RedTeamSnapshot", "load_adversarial_corpus", "recent_snapshots", "run_redteam"]

# src/tessera/observability/redteam.py → parents[3] is the repo root.
_REPO = Path(__file__).resolve().parents[3]
_ADVERSARIAL_PATH = _REPO / "eval" / "calibration" / "adversarial_inputs.json"

_SNAPSHOTS: deque[RedTeamSnapshot] = deque(maxlen=50)
_SAMPLE_LIMIT = 3


@dataclass(frozen=True, slots=True)
class RedTeamSnapshot:
    """Attack-success rate of one red-team run over the adversarial corpus."""

    ran_at: str
    n_attacks: int
    n_blocked: int
    n_bypassed: int
    attack_success_rate: float  # n_bypassed / n_attacks, 0..1
    bypassed_samples: list[str] = field(default_factory=list)


def load_adversarial_corpus() -> list[str]:
    """Load the bundled adversarial prompts plus the failure-corpus injections."""
    extra: list[str] = json.loads(_ADVERSARIAL_PATH.read_text(encoding="utf-8"))
    return [*load_injection_prompts(), *extra]


def run_redteam(
    *, corpus: Sequence[str] | None = None, policy: Policy | None = None
) -> RedTeamSnapshot:
    """Replay the adversarial corpus through the guard and record a snapshot.

    Args:
        corpus: Adversarial prompts; the bundled corpus is loaded if omitted.
        policy: Guard policy to test; loaded if omitted.

    Returns:
        The :class:`RedTeamSnapshot`, also appended to the drift history.
    """
    attacks = list(corpus) if corpus is not None else load_adversarial_corpus()
    active_policy = policy or load_policy()

    bypassed = [
        text
        for text in attacks
        # audit=False: replaying an adversarial corpus to MEASURE the guard is not real traffic —
        # it must not append synthetic "attacks" to the opposability ledger. Decision is unchanged.
        if check_user_input(text, policy=active_policy, actor=GUARD_ACTOR, audit=False).allowed
    ]
    n_attacks = len(attacks)
    snapshot = RedTeamSnapshot(
        ran_at=datetime.now(UTC).isoformat(),
        n_attacks=n_attacks,
        n_blocked=n_attacks - len(bypassed),
        n_bypassed=len(bypassed),
        attack_success_rate=(len(bypassed) / n_attacks if n_attacks else 0.0),
        bypassed_samples=[text[:120] for text in bypassed[:_SAMPLE_LIMIT]],
    )
    _SNAPSHOTS.append(snapshot)
    return snapshot


def recent_snapshots() -> list[RedTeamSnapshot]:
    """Return the recorded red-team snapshots (newest last)."""
    return list(_SNAPSHOTS)
