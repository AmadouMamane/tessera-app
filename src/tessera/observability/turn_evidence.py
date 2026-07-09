"""Turn-evidence read — the fact that folds *real emission* into the L1 level (ADR 0017 §F).

ADR 0017 §4 says "L1 Observable" and §Governing rule says *the cockpit reads the spine*. This
module closes the §7 remote-profile ingestion gap named by the ADR but never built: L1 must
mean the cockpit **observes** the agent emitting turns, not merely that its AgentSpec declares
it will. The evidence is the Prometheus counter ``tessera_agent_turns_total`` — a spine store
the cockpit already owns (0015 keeps Prometheus for every aggregate number), so an
**out-of-process** agent's OTLP metrics reach the cockpit through the collector's Prometheus
exporter with **no cockpit import and no agent-specific code** (the two-profiles-one-wire seam).

Honesty (0016 / the project rule):

* An unreachable metrics store cannot *disprove* emission — but it cannot *prove* it either.
  Evidence-unknown therefore yields **no proof**, and a computed level never rests on an
  assumption. It used to: unknown was silently trusted as observed, so a fleet with no
  metrics store displayed an L1 that looked computed while it was merely declared. That is
  the over-claim class this project forbids, and it is gone.
* Nothing is lost by refusing to guess. The unproven rung is not hidden — the caller also
  reads what the manifest *declares* and the badge renders the attenuated
  "L1 declared · no evidence" variant, which distinguishes ``unverifiable`` (store off or
  down) from ``dormant`` (store read, agent has emitted nothing).
* The read is a deployment capability, gated by ``TESSERA_LEVEL_TURN_EVIDENCE`` and shipped
  **off** (like every 0015/0017 store flip). Off ⇒ ``unverifiable`` ⇒ no computed L1
  anywhere, which is the honest reading of a cockpit that observes nothing. Turning it on is
  a config action, recorded, never faked.

Evidence horizon: the query sums the **cumulative** ``tessera_agent_turns_total`` counter as
an instant vector — there is deliberately **no rolling window** today. "Dormant" therefore
means "no turn observed over the metrics store's retention", not "no turn in the last N
hours". The UI wording must not promise a recency this query does not measure. Introducing a
window (``increase(...[24h])``) would change what evidence *means* and belongs in its own
slice, not in a badge change.
"""

from __future__ import annotations

import os
from typing import Literal

from tessera.observability.spine.adapters.base import SpineUnavailableError
from tessera.observability.spine.adapters.prometheus import PrometheusAdapter

__all__ = [
    "TurnEvidence",
    "agents_with_turn_evidence",
    "has_turn_evidence",
    "turn_evidence_enabled",
    "turn_evidence_state",
]

#: Why the cockpit does or does not have turn evidence for an agent. ``unverifiable`` and
#: ``dormant`` both mean *no proof*; they differ in whose silence it is — the store's or the
#: agent's — and the badge tooltip must say which.
TurnEvidence = Literal["observed", "dormant", "unverifiable"]

#: The per-agent turn counter every profile emits (semconv / metrics.py). A positive value
#: for an agent_id is the honest evidence that the cockpit has observed it processing turns.
_TURNS_METRIC = "tessera_agent_turns_total"

_ENABLE_FLAG = "TESSERA_LEVEL_TURN_EVIDENCE"
_TRUTHY = {"1", "true", "yes", "on"}
#: A PromQL instant-vector sample is ``[timestamp, "value"]`` — a 2-tuple.
_SAMPLE_LEN = 2


def turn_evidence_enabled() -> bool:
    """Whether the L1 turn-evidence read is enabled for this deployment (config flip)."""
    return os.environ.get(_ENABLE_FLAG, "").strip().lower() in _TRUTHY


def agents_with_turn_evidence() -> set[str] | None:
    """The set of ``agent_id`` s Prometheus has observed emitting turns.

    ``None`` means *evidence unknown* — the read is disabled, or the metrics store is
    unreachable — in which case the level trusts the declared contract. A returned set is
    authoritative: an agent absent from it (with the store reachable) has no observed turns.
    """
    if not turn_evidence_enabled():
        return None
    try:
        rows = PrometheusAdapter().instant(f"sum by (agent_id) ({_TURNS_METRIC})")
    except SpineUnavailableError:
        return None
    observed: set[str] = set()
    for row in rows:
        metric = row.get("metric")
        value = row.get("value")
        if not isinstance(metric, dict) or not isinstance(value, list) or len(value) != _SAMPLE_LEN:
            continue
        agent_id = metric.get("agent_id")
        try:
            count = float(value[1])
        except (TypeError, ValueError):
            continue
        if isinstance(agent_id, str) and agent_id and count > 0:
            observed.add(agent_id)
    return observed


def turn_evidence_state(agent_id: str | None, observed: set[str] | None = None) -> TurnEvidence:
    """Why the cockpit does or does not have turn evidence for ``agent_id``.

    - ``observed`` — the store was read and counts turns for this agent. The only proof.
    - ``unverifiable`` — the read is disabled or the store is unreachable. Nothing is known.
    - ``dormant`` — the store was read and this agent is absent from it: no turn emitted.

    Pass a pre-fetched ``observed`` set (from :func:`agents_with_turn_evidence`) to check a
    whole fleet against one Prometheus read; omit it for a single-agent resolve.
    """
    if observed is None:
        observed = agents_with_turn_evidence()
    if observed is None:
        return "unverifiable"
    return "observed" if agent_id and agent_id in observed else "dormant"


def has_turn_evidence(agent_id: str | None, observed: set[str] | None = None) -> bool:
    """Whether the cockpit has **observed** turns for ``agent_id`` — proof, never assumption.

    Evidence-unknown is not evidence. Callers that want to show what the manifest promises
    read the declared rung separately; they never obtain it by trusting a silent store.
    """
    return turn_evidence_state(agent_id, observed) == "observed"
