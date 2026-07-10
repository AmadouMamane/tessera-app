"""Green must mean "a turn was observed and nothing is broken", never "no bad news yet".

The health dot used to read the escalation rate alone. An agent whose canary came back red,
or whose audit ledger no longer verified, still showed green while few conversations
escalated — the colour said *healthy* and meant *not escalating much*. These tests pin the
repair, one clause at a time, and pin the one that is easy to lose: an agent nobody has
observed is amber, because unobserved is not healthy.
"""

from __future__ import annotations

import pytest

from tessera.observability.agent_health import (
    ESCALATION_HARD_PCT,
    ESCALATION_SOFT_PCT,
    health_state,
)

_HEALTHY = {
    "escalation_rate": 0.0,
    "canary_red": False,
    "integrity_broken": False,
    "turn_evidence": "observed",
}


def test_a_proven_healthy_agent_is_green() -> None:
    assert health_state(**_HEALTHY) == "good"


@pytest.mark.parametrize(
    "override",
    [
        {"canary_red": True},
        {"integrity_broken": True},
        {"escalation_rate": ESCALATION_HARD_PCT + 0.1},
    ],
    ids=["canary red", "ledger integrity broken", "escalation past the hard threshold"],
)
def test_any_broken_guarantee_turns_the_dot_red(override: dict[str, object]) -> None:
    """Each is sufficient on its own: a red dot never waits for a second reason."""
    assert health_state(**{**_HEALTHY, **override}) == "crit"


@pytest.mark.parametrize(
    "override",
    [
        {"turn_evidence": "dormant"},
        {"turn_evidence": "unverifiable"},
        {"escalation_rate": ESCALATION_SOFT_PCT + 0.1},
    ],
    ids=["no turn observed", "evidence unreadable", "escalation past the soft threshold"],
)
def test_anything_unproven_or_degrading_turns_the_dot_amber(override: dict[str, object]) -> None:
    assert health_state(**{**_HEALTHY, **override}) == "warn"


def test_an_unobserved_agent_is_never_green_however_quiet_it_is() -> None:
    """The clause the old rule lacked, and the reason this module exists.

    A dormant agent escalates nothing, breaks nothing and proves nothing. Reading that
    silence as health is exactly the trusted-true defect ADR 0017 §4 removed from the level
    badge; the dot must not reintroduce it one component away.
    """
    assert health_state(**{**_HEALTHY, "turn_evidence": "dormant"}) == "warn"
    assert health_state(**{**_HEALTHY, "turn_evidence": "unverifiable"}) == "warn"


def test_a_broken_guarantee_outranks_missing_evidence() -> None:
    """Red wins over amber: a dormant agent with a red canary is red, not merely unproven."""
    assert health_state(**{**_HEALTHY, "turn_evidence": "dormant", "canary_red": True}) == "crit"


def test_the_thresholds_are_exclusive_as_they_have_always_been() -> None:
    """Landing exactly on a threshold does not cross it — the boundary the old rule used.

    `_health` compared with `<=`, so 20.0 read green and 35.0 read amber. Rewriting the rule
    was not licence to silently move a boundary an operator has been reading for weeks.
    """
    assert health_state(**{**_HEALTHY, "escalation_rate": ESCALATION_SOFT_PCT}) == "good"
    assert health_state(**{**_HEALTHY, "escalation_rate": ESCALATION_HARD_PCT}) == "warn"


def test_a_canary_that_never_ran_is_not_a_failing_canary() -> None:
    """`canary_red=False` for an agent with no canary: no news is not bad news.

    The caller resolves "never ran" to False on purpose; whether that silence matters is
    `turn_evidence`'s question, and it answers it separately.
    """
    assert health_state(**{**_HEALTHY, "canary_red": False}) == "good"


def test_every_input_is_required() -> None:
    """A default is where an assumption hides — the lesson `trusted-true` cost us once."""
    with pytest.raises(TypeError):
        health_state(escalation_rate=0.0, canary_red=False, integrity_broken=False)  # type: ignore[call-arg]
