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

**The drift series is durable** (2026-08-04). It was a ``deque(maxlen=50)`` in process memory,
which broke the module's own premise twice over: "repeated runs form a drift series" was true
only until the container restarted, and under more than one worker each process kept a
*different* series — so which history the operator saw depended on which worker answered. A
snapshot is a dated measurement of the deployed policy; losing it on a restart is losing the
only evidence that the policy used to behave differently. It is now appended to the same
durable journal the fixed-corpus probes write to
(:mod:`tessera.observability.probe_store`).

Unlike ``refusal`` and ``firewall``, red-team snapshots are **not** deduplicated by content:
each run is an explicit act somebody triggered, and "we ran it again and it still bypasses
three" is a different fact from "we have not looked since Tuesday".
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from tessera.guard.adapter import check_user_input
from tessera.guard.audit import GUARD_ACTOR
from tessera.guard.decisions import load_policy
from tessera.observability import probe_store
from tessera.observability.firewall_efficacy import load_injection_prompts

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tessera.guard.decisions import Policy

__all__ = ["RedTeamSnapshot", "load_adversarial_corpus", "recent_snapshots", "run_redteam"]

# src/tessera/observability/redteam.py → parents[3] is the repo root.
_REPO = Path(__file__).resolve().parents[3]
_ADVERSARIAL_PATH = _REPO / "eval" / "calibration" / "adversarial_inputs.json"

#: The probe's key in the durable journal.
_PROBE = "redteam"
#: How many snapshots the drift series shows. The journal itself is bounded separately; this
#: is what a reader gets back, unchanged from the ``deque(maxlen=50)`` this replaced.
_HISTORY = 50
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
    probe_store.append_probe_run(_PROBE, asdict(snapshot))
    return snapshot


def recent_snapshots() -> list[RedTeamSnapshot]:
    """Return the recorded red-team snapshots (newest last), from the durable journal.

    A malformed journal row is skipped rather than raising: this feeds a drift chart and a
    playbook input, and one bad row must not remove the rest of the history from view.
    """
    snapshots: list[RedTeamSnapshot] = []
    for run in probe_store.probe_runs(_PROBE):
        payload = run.payload
        try:
            snapshots.append(
                RedTeamSnapshot(
                    ran_at=str(payload["ran_at"]),
                    n_attacks=int(payload["n_attacks"]),
                    n_blocked=int(payload["n_blocked"]),
                    n_bypassed=int(payload["n_bypassed"]),
                    attack_success_rate=float(payload["attack_success_rate"]),
                    bypassed_samples=[str(s) for s in payload.get("bypassed_samples") or []],
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return snapshots[-_HISTORY:]
