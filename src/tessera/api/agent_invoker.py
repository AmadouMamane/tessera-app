"""HTTP turn invoker — the http binding's cockpit→agent transport (ADR 0019 §I3).

The one declared cockpit→agent path for an ``http``-binding agent: a declared consumer
(the Console; later a canary) sends a turn to the endpoint the agent EXPOSES, speaking the
ADR 0018 turn contract. This module is that transport.

Boundary (ADR 0017 §1 / ADR 0019 governing rule): invocation travels over a transport, not
a module graph. The invoker makes an HTTP request — it never imports the agent runtime
(``langgraph`` / the graph). It legitimately uses the turn-contract TypedDicts and the SDK
conformance checker (data + a pure validator, not the runtime), and it lives in
``tessera.api`` (the cockpit's server side, off the boundary-scanned control-plane tree), so
the ratchet is untouched.

Every invocation is a governed act (ADR 0019 §4): it forwards the *verified* operator
assertion (0010 Phase B — no anonymous invocation, ever), honours the declared timeout, and
emits exactly one S1 event (green on a conformant response, red on any failure). It NEVER
raises: a timeout, a refused connection, a non-2xx status or a contract violation all become
a red :class:`InvocationOutcome`, never a fabricated green (the seal's honesty invariant,
applied to invocation).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

import httpx

from tessera.agent.registry import InvocationBinding, get_agent
from tessera.agent.sdk.testkit.turn_contract_conformance import verify_turn_result
from tessera.api.operator import OPERATOR_ASSERTION_HEADER

if TYPE_CHECKING:
    from collections.abc import Callable

    from tessera.agent.turn_contract import TurnInput
    from tessera.authz import Actor

__all__ = [
    "DEFAULT_HTTP_TIMEOUT_MS",
    "HttpTurnInvoker",
    "InvocationOutcome",
]

#: Fallback timeout when a manifest declares ``http`` without an explicit ``timeout_ms``.
#: The schema already models it as optional; a bounded default keeps the invoker from ever
#: hanging on a wedged agent.
DEFAULT_HTTP_TIMEOUT_MS = 15_000

#: HTTP status floor treated as an agent-side failure (a red invocation).
_HTTP_ERROR_STATUS = 400


@dataclass(frozen=True, slots=True)
class InvocationOutcome:
    """The result of one http invocation — green iff the agent returned a conformant TurnResult."""

    ok: bool
    verdict: Literal["green", "red"]
    duration_ms: float
    result: dict[str, object] | None = None
    status_code: int | None = None
    error: str | None = None
    #: Turn-contract violations when the response was reachable but non-conformant (ADR 0019 §I3).
    conformance: tuple[str, ...] = field(default_factory=tuple)


def _default_client_factory(timeout_s: float) -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=timeout_s)


class HttpTurnInvoker:
    """Send one turn to an ``http``-binding agent and record the governed act.

    ``client_factory`` is injectable so tests drive the invoker over an ``httpx.MockTransport``
    without a live server (the same fake-seam discipline as the canary's ``InProcessChatInvoker``).
    """

    binding = InvocationBinding.HTTP

    def __init__(
        self, *, client_factory: Callable[[float], httpx.AsyncClient] | None = None
    ) -> None:
        self._client_factory = client_factory or _default_client_factory

    async def invoke(
        self,
        agent_id: str,
        turn_input: TurnInput,
        *,
        operator_assertion: str,
        actor: Actor,
        conversation_id: str,
        turn_id: str,
        synthetic: bool,
    ) -> InvocationOutcome:
        """Drive one http turn; a failure becomes a red outcome, never a raise.

        ``operator_assertion`` is the verified token the route resolved (0010 Phase B); the
        invoker forwards it verbatim and refuses an empty one (no anonymous invocation, §4).
        One S1 event is emitted whichever way the turn goes — the invocation happened either way.

        ``actor`` is WHO drove the turn — an :class:`Actor`, not a string, so the route cannot
        hand this an invented name and the ledger cannot receive one.

        ``synthetic`` (ADR 0019 §Amendment 1 A1.1) is the turn's posture, written onto the wire
        here — the one place the platform speaks to an out-of-process agent, so the one place it
        can be forgotten. It has **no default**: today every declared consumer of this binding is
        a test bench (the Console) or a canary, and both pass ``True``; a future consumer that
        drives product traffic through the binding must say so deliberately rather than inherit
        a stamp that would quietly delete its events from every business surface.
        """
        started = datetime.now(UTC)
        outcome = await self._drive(
            agent_id,
            turn_input,
            operator_assertion=operator_assertion,
            started=started,
            synthetic=synthetic,
        )
        self._audit(
            agent_id=agent_id,
            actor=actor,
            outcome=outcome,
            conversation_id=conversation_id,
            turn_id=turn_id,
        )
        return outcome

    async def _drive(
        self,
        agent_id: str,
        turn_input: TurnInput,
        *,
        operator_assertion: str,
        started: datetime,
        synthetic: bool,
    ) -> InvocationOutcome:
        invocation = get_agent(agent_id).invocation
        if invocation.binding is not InvocationBinding.HTTP or not invocation.endpoint:
            return self._red(
                started, error=f"agent {agent_id!r} declares no http invocation binding"
            )
        if not operator_assertion:
            # No anonymous invocation, ever (§4): refuse before touching the network.
            return self._red(started, error="missing operator assertion (no anonymous invocation)")
        timeout_s = (invocation.timeout_ms or DEFAULT_HTTP_TIMEOUT_MS) / 1000.0
        headers = {
            OPERATOR_ASSERTION_HEADER: operator_assertion,
            "content-type": "application/json",
        }
        # The caller's declared posture wins over anything the TurnInput happened to carry: the
        # platform, not its input, is the authority on whether it is testing the agent (§A1.1).
        body: dict[str, object] = {**turn_input, "synthetic": synthetic}
        try:
            async with self._client_factory(timeout_s) as client:
                response = await client.post(invocation.endpoint, json=body, headers=headers)
        except httpx.TimeoutException:
            return self._red(
                started, error=f"timeout after {invocation.timeout_ms or DEFAULT_HTTP_TIMEOUT_MS}ms"
            )
        except httpx.HTTPError as exc:  # connect error, protocol error, …
            return self._red(started, error=f"{type(exc).__name__}: {exc}")
        return self._interpret(response, started)

    def _interpret(self, response: httpx.Response, started: datetime) -> InvocationOutcome:
        status = response.status_code
        if status >= _HTTP_ERROR_STATUS:
            return self._red(started, error=f"agent returned HTTP {status}", status_code=status)
        try:
            body = response.json()
        except ValueError:
            return self._red(started, error="response was not valid JSON", status_code=status)
        violations = verify_turn_result(body)
        if violations:
            # Reachable but broke its declared contract — a red, and the violations say why.
            return self._red(
                started,
                error="response is not a conformant TurnResult",
                status_code=status,
                conformance=tuple(violations),
            )
        return InvocationOutcome(
            ok=True,
            verdict="green",
            duration_ms=_elapsed_ms(started),
            result=dict(body),
            status_code=status,
        )

    @staticmethod
    def _red(
        started: datetime,
        *,
        error: str,
        status_code: int | None = None,
        conformance: tuple[str, ...] = (),
    ) -> InvocationOutcome:
        return InvocationOutcome(
            ok=False,
            verdict="red",
            duration_ms=_elapsed_ms(started),
            status_code=status_code,
            error=error,
            conformance=conformance,
        )

    @staticmethod
    def _audit(
        *,
        agent_id: str,
        actor: Actor,
        outcome: InvocationOutcome,
        conversation_id: str,
        turn_id: str,
    ) -> None:
        from tessera.guard.audit import emit_agent_invocation

        emit_agent_invocation(
            agent_id=agent_id,
            binding=InvocationBinding.HTTP.value,
            verdict=outcome.verdict,
            actor=actor,
            conversation_id=conversation_id,
            turn_id=turn_id,
            duration_ms=outcome.duration_ms,
            status_code=outcome.status_code,
            error=outcome.error,
        )


def _elapsed_ms(started: datetime) -> float:
    return (datetime.now(UTC) - started).total_seconds() * 1000.0
