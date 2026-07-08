"""Turn-contract conformance suite — the ADR 0019 §I3 http-binding gate.

ADR 0019 §I3: *"an agent declaring ``http`` must speak the turn contract"*. The http
binding is a promise — the agent exposes a turn endpoint whose response is the ADR 0018
:class:`~tessera.agent.turn_contract.TurnResult` serialisation. This suite is the
reusable check that promise is kept: pass it the JSON the endpoint returned and it lists
the contract violations (empty ⇒ conforming). Both the cockpit's invoker (before it
trusts a response) and an agent repo's own CI (before it declares ``http``) run it.

The authoritative key set is :data:`~tessera.agent.turn_contract.TURN_RESULT_KEYS`,
imported here, never re-listed (0015 one-canonical-source). The platform rule is the one
the reference runtime is pinned to (``tests/unit/test_turn_contract_acceptance.py``): a
conformant result carries **all** the contract keys (present, correctly typed — an
inapplicable field is an empty list / ``None``, never absent), so a consumer can read any
of them without a shape probe.
"""

from __future__ import annotations

# The one canonical key set (camelCase wire form), defined next to the TurnResult TypedDict.
from tessera.agent.turn_contract import TURN_RESULT_KEYS

__all__ = [
    "TURN_RESULT_KEYS",
    "assert_turn_result",
    "verify_turn_result",
]

#: The contract keys that must serialise as JSON arrays (an inapplicable one is ``[]``).
_LIST_KEYS = ("cardUpdates", "suggestedActions", "businessEvents", "businessScores")
#: The contract keys that must serialise as JSON objects when present (``null`` allowed for
#: ``artifact`` — a turn need not produce one; ``decisions`` is an object).
_OBJECT_KEYS = ("decisions",)


def verify_turn_result(payload: object) -> list[str]:
    """Return the turn-contract violations for an http agent's response (empty ⇒ conforming).

    A conformant response is a JSON object carrying every :data:`TURN_RESULT_KEYS` entry,
    with ``visibleReply`` a string, the array fields arrays, and ``decisions`` an object.
    Extra keys are tolerated (the acceptance rule is a superset check) — the contract is
    "carries at least the keys", so a richer agent is still conformant.
    """
    if not isinstance(payload, dict):
        return [f"turn result must be a JSON object, got {type(payload).__name__}"]
    violations: list[str] = []
    for key in sorted(TURN_RESULT_KEYS - set(payload)):
        violations.append(f"missing turn-contract key {key!r}")
    reply = payload.get("visibleReply")
    if "visibleReply" in payload and not isinstance(reply, str):
        violations.append("visibleReply must be a string")
    for key in _LIST_KEYS:
        if key in payload and not isinstance(payload[key], list):
            violations.append(f"{key} must be an array")
    for key in _OBJECT_KEYS:
        if key in payload and not isinstance(payload[key], dict):
            violations.append(f"{key} must be an object")
    # ``artifact`` is object-or-null (a turn need not produce one).
    artifact = payload.get("artifact")
    if "artifact" in payload and artifact is not None and not isinstance(artifact, dict):
        violations.append("artifact must be an object or null")
    return violations


def assert_turn_result(payload: object) -> None:
    """Raise ``AssertionError`` if the response fails the turn contract (ADR 0019 §I3)."""
    violations = verify_turn_result(payload)
    assert not violations, "turn-contract (ADR 0019 §I3) violations: " + "; ".join(violations)
