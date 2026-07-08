"""Turn-evidence read — the fact that folds *real emission* into the L1 level (ADR 0017 §F).

ADR 0017 §4 says "L1 Observable" and §Governing rule says *the cockpit reads the spine*. This
module closes the §7 remote-profile ingestion gap named by the ADR but never built: L1 must
mean the cockpit **observes** the agent emitting turns, not merely that its AgentSpec declares
it will. The evidence is the Prometheus counter ``tessera_agent_turns_total`` — a spine store
the cockpit already owns (0015 keeps Prometheus for every aggregate number), so an
**out-of-process** agent's OTLP metrics reach the cockpit through the collector's Prometheus
exporter with **no cockpit import and no agent-specific code** (the two-profiles-one-wire seam).

Honesty (0016 / the project rule):

* An unreachable metrics store cannot *disprove* emission — evidence is "unknown", so the
  level falls back to the declared contract rather than dropping a live agent to L0 on a
  transient outage. Unknown ≠ absent.
* The read is a deployment capability, gated by ``TESSERA_LEVEL_TURN_EVIDENCE`` and shipped
  **off** (like every 0015/0017 store flip): default = trust the declaration (today's
  behaviour, hermetic CI); on = evidence-backed L1 wherever Prometheus is scraping the
  collector. Enabling it in a deployment is a config action, recorded, never faked.
"""

from __future__ import annotations

import os

from tessera.observability.spine.adapters.base import SpineUnavailableError
from tessera.observability.spine.adapters.prometheus import PrometheusAdapter

__all__ = ["agents_with_turn_evidence", "has_turn_evidence", "turn_evidence_enabled"]

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


def has_turn_evidence(agent_id: str | None, observed: set[str] | None = None) -> bool:
    """Whether the cockpit has observed turns for ``agent_id`` (evidence-unknown → trusted).

    Pass a pre-fetched ``observed`` set (from :func:`agents_with_turn_evidence`) to check a
    whole fleet against one Prometheus read; omit it for a single-agent resolve.
    """
    if not agent_id:
        return False
    if observed is None:
        observed = agents_with_turn_evidence()
    return True if observed is None else agent_id in observed
