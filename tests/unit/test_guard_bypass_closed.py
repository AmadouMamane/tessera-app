"""B1 — the guard is no longer switchable off by the caller.

Audit 2026-07-10, **P0 `guard-bypass`** — chat.py:732, :820, :725.

``POST /chat`` accepted two fields straight off the request body:

* ``system_prompt_override`` — replaces the language bundle's system prompt (a jailbreak
  primitive: the attacker writes the agent's instructions);
* ``guard_overrides`` — switches OFF guard categories by name: tool DENY rules, PII
  redaction, prompt-injection detection, grounding.

Neither was gated on ``surface`` or ``auth_state``. "Sandbox-only" was a *docstring*. Any
anonymous caller could disable the entire safety stack for their turn and stream an
unredacted PAN back over the wire.

Both are now honoured only for an OPERATOR on the COCKPIT_EMBEDDED surface — both values
server-derived (the signed operator assertion and the verified session), never from the body,
so a caller cannot lie its way into the sandbox. Off that surface the fields are DROPPED,
silently: a 4xx would confirm to an attacker that the fields are real and worth probing.
"""

from __future__ import annotations

import pytest

from tessera.agent.registry import Surface
from tessera.api.routes.chat import sandbox_overrides_allowed
from tessera.authz import AuthState

EVERY_SURFACE = list(Surface)
EVERY_AUTH_STATE = list(AuthState)


def test_the_operator_cockpit_sandbox_still_works() -> None:
    """The legitimate case must keep working — this is the console playground."""
    assert sandbox_overrides_allowed(Surface.COCKPIT_EMBEDDED, AuthState.OPERATOR) is True


@pytest.mark.parametrize("auth_state", [AuthState.ANONYMOUS, AuthState.CUSTOMER])
def test_a_non_operator_can_never_relax_the_guard(auth_state: AuthState) -> None:
    """The finding, closed: the anonymous caller of POST /chat gets the FULL guard.

    Pre-fix this was unreachable as a question — nothing consulted auth_state at all.
    """
    assert sandbox_overrides_allowed(Surface.COCKPIT_EMBEDDED, auth_state) is False


@pytest.mark.parametrize(
    "surface",
    [Surface.SHARED_CUSTOMER_WIDGET, Surface.DEDICATED_UI, Surface.API_ONLY],
)
def test_even_an_operator_cannot_relax_the_guard_off_the_cockpit(surface: Surface) -> None:
    """An operator's credentials do not turn the public widget into a sandbox.

    Both conditions are required: the customer-facing surfaces run full policy for
    everyone, so a stolen operator session cannot be used to strip PII redaction from the
    channel a real customer is talking on.
    """
    assert sandbox_overrides_allowed(surface, AuthState.OPERATOR) is False


def test_exactly_one_of_the_twelve_combinations_opens_the_sandbox() -> None:
    """Enumerate the whole space — no third path in."""
    open_combos = [
        (surface, auth)
        for surface in EVERY_SURFACE
        for auth in EVERY_AUTH_STATE
        if sandbox_overrides_allowed(surface, auth)
    ]
    assert open_combos == [(Surface.COCKPIT_EMBEDDED, AuthState.OPERATOR)]


class TestTheStreamingRedactorReadsTheGatedValue:
    """The subtlest half of the finding, and the one the audit did not list.

    `chat.py:882` computed `pii_guard_off` from **request.guard_overrides** — the raw body —
    so it sat BELOW the surface/auth gate. An anonymous caller sending
    ``guard_overrides=["pii"]`` still switched the streaming redactor off and got an
    unredacted PAN on the wire, which is precisely the harm the P0 describes. Every other
    consumer in the graph reads `state["guard_overrides"]`, which is the gated value; this
    line was the last direct read of the body, and the last unguarded path into the stack.
    """

    def test_no_code_path_reads_the_override_off_the_request_body(self) -> None:
        """A ratchet: the raw body must never again drive a guard decision."""
        import inspect

        from tessera.api.routes import chat

        source = inspect.getsource(chat)
        # Code only — a comment may name the field while discussing it.
        code = [
            line.split("#", 1)[0].strip()
            for line in source.splitlines()
            if not line.lstrip().startswith("#")
        ]
        # The ONLY permitted reads are the two assignments that apply the gate.
        raw_reads = [
            line
            for line in code
            if "request.guard_overrides" in line or "request.system_prompt_override" in line
        ]
        assert raw_reads == [
            "system_prompt_override = request.system_prompt_override if sandbox else None",
            "guard_overrides = request.guard_overrides if sandbox else None",
        ], f"a guard decision is being taken from the raw request body: {raw_reads}"
