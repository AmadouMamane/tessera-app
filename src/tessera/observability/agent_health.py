"""The fleet's health dot, decided in one pure function with its thresholds beside it.

The dot used to answer a narrower question than the one it appears to answer. It was
computed from the escalation rate alone: an agent whose canary came back red, or whose
audit ledger no longer verifies, still showed green as long as few conversations escalated.
The colour said "healthy" and meant "not escalating much".

Three inputs decide it now, and the rule is stated once, here:

* **red** — a proof already broke: the canary's last invocation failed, the ledger's
  content integrity does not verify, or escalation has passed the hard threshold;
* **amber** — something is unproven or heading the wrong way: the cockpit has observed no
  turn from this agent (``dormant``) or cannot check (``unverifiable``), or escalation has
  passed the soft threshold;
* **green** — a turn was observed *and* nothing above holds. Green is a claim about
  evidence, never the absence of bad news.

That last clause is the whole point. An agent nobody has watched is not healthy; it is
unobserved, and the two must not share a colour.

Pure: no I/O, no clock, no settings. Every input is a **required** keyword — a default is
where an assumption hides, and this module exists because one did. The caller reads the
facts; this function only decides. Guarded by ``tests/unit/test_agent_health.py``.
"""

from __future__ import annotations

from typing import Literal

__all__ = ["ESCALATION_HARD_PCT", "ESCALATION_SOFT_PCT", "HealthState", "health_state"]

HealthState = Literal["crit", "warn", "good"]

#: Escalation rate (% of answered turns handed to a human) **above** which the dot turns
#: red. Past a third of traffic escalating, the agent is not doing the job it was deployed
#: for. Strictly greater, as the rule has always been: 35.0 itself is still amber.
ESCALATION_HARD_PCT = 35.0

#: …and above which it turns amber. At or below a fifth, escalation is the product working
#: as designed (hard cases reach a human), not a symptom.
ESCALATION_SOFT_PCT = 20.0

#: Evidence states the resolver produces (ADR 0017 §4). ``observed`` is the only one that
#: proves the cockpit has seen this agent serve a turn.
_UNPROVEN_EVIDENCE = frozenset({"dormant", "unverifiable"})


def health_state(
    *,
    escalation_rate: float,
    canary_red: bool,
    integrity_broken: bool,
    turn_evidence: str,
) -> HealthState:
    """Decide one agent's health dot from the three facts that can contradict "healthy".

    Args:
        escalation_rate: Share of answered turns escalated to a human, in percent.
        canary_red: Whether this agent's most recent canary invocation failed. ``False``
            for an agent that never ran one — a canary that never fired proves nothing bad,
            only nothing at all, which is what ``turn_evidence`` is for.
        integrity_broken: Whether the audit ledger's content integrity fails to verify.
            Fleet-wide, not per agent: a broken ledger indicts every agent it records.
        turn_evidence: ``observed`` | ``dormant`` | ``unverifiable`` (ADR 0017 §4).

    Returns:
        ``crit`` when a guarantee is already broken, ``warn`` when one is unproven or
        degrading, ``good`` only when a turn was observed and neither of the others holds.
    """
    if canary_red or integrity_broken or escalation_rate > ESCALATION_HARD_PCT:
        return "crit"
    if turn_evidence in _UNPROVEN_EVIDENCE or escalation_rate > ESCALATION_SOFT_PCT:
        return "warn"
    return "good"
