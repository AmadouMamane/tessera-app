"""Scheduled canary invocation — synthetic turns through the declared in_process_chat binding.

ADR 0019 §I4 (+ §3 closed consumer list, §4 "every invocation is a governed act"). The canary
quality net (signal 94) shipped in step 6b as *declared, not simulated*: the descriptor was
manifest-generated but the scheduled synthetic execution was deferred for lack of exactly one
primitive — a governed way for the platform to send a turn to an agent. ADR 0019's invocation
binding is that primitive; this module is the consumer that was waiting for it.

The runner mirrors the Hica-seal off-chrono scheduler (``tessera.guard.seal`` + ``api.main``): one
honest boot posture line, **idle by default**, a background loop per scheduled agent firing at the
manifest cadence, best-effort and off every request path. The invocation drives the SAME in-process
seam the eval harness uses (``compile_graph().ainvoke`` — the agent package invoked directly, ADR
0019 §3), wrapped in :func:`synthetic_turn` so every business event it emits is stamped synthetic
and can NEVER enter business metrics (§4). Each invocation emits ONE S1 event
(``tessera.agent.canary``) — the governed-act audit AND the durable freshness record the canary
descriptor reads. A cycle failure yields a RED verdict, never a fabricated green (the seal's H3
honesty invariant, applied to invocation).

Boundary (ADR 0017 §1 / ADR 0019 governing rule): the binding is a *transport*, not a module
graph — but this module IS the agent-runtime-side consumer, so it legitimately imports the runtime.
It is not the control plane; the control plane (``tessera.observability`` + the cockpit read API)
never imports it back — the canary descriptor reads freshness from the S1 ledger, not from here.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable

from tessera.agent.agentspec import InvocationBinding
from tessera.agent.registry import list_agents

if TYPE_CHECKING:
    from tessera.settings import Settings

__all__ = [
    "CanaryCycleResult",
    "CanaryInvoker",
    "CanaryTurnOutcome",
    "InProcessChatInvoker",
    "ScheduledCanary",
    "canary_posture",
    "run_canary_cycle",
    "scheduled_canaries",
]

#: The synthetic probe message a canary turn carries — deliberately identified as synthetic so it
#: is unmistakable in any trace or transcript. It only needs to exercise the pipeline end to end.
_CANARY_PROBE = "healthcheck: synthetic canary probe — please disregard"


@dataclass(frozen=True, slots=True)
class ScheduledCanary:
    """One agent the canary scheduler drives, with the cadence its manifest declares."""

    agent_id: str
    cadence_s: int


@dataclass(frozen=True, slots=True)
class CanaryTurnOutcome:
    """What one invocation of the binding produced (the invoker's raw result)."""

    ok: bool
    duration_ms: float
    error: str | None = None


@dataclass(frozen=True, slots=True)
class CanaryCycleResult:
    """What one canary cycle did — for the scheduler's log and the S1 audit."""

    agent_id: str
    verdict: Literal["green", "red"]
    binding: str
    conversation_id: str
    turn_id: str
    duration_ms: float
    error: str | None = None


@runtime_checkable
class CanaryInvoker(Protocol):
    """Sends one synthetic turn to an agent over the binding, returning a green/red outcome."""

    async def invoke(
        self, agent_id: str, *, conversation_id: str, turn_id: str
    ) -> CanaryTurnOutcome:
        """Drive one synthetic turn; never raise — a failure is an ``ok=False`` outcome."""
        ...


class InProcessChatInvoker:
    """Drive a synthetic turn through the in_process_chat seam (``compile_graph().ainvoke``).

    The production invoker — it runs the real graph (and the LLM), so it is exercised only by live
    / integration verification, never by the hermetic unit suite (a fake invoker stands in there,
    the same discipline as the seal's ``Rfc3161Provider``). It never raises: any failure (LLM down,
    bad state) becomes an ``ok=False`` outcome so the cycle records an honest RED, never a fake
    green.
    """

    binding = InvocationBinding.IN_PROCESS_CHAT

    async def invoke(
        self, agent_id: str, *, conversation_id: str, turn_id: str
    ) -> CanaryTurnOutcome:
        """Drive one synthetic turn through the graph; a failure becomes an ``ok=False`` outcome."""
        from tessera.agent import compile_graph
        from tessera.agent.identity import current_agent_id
        from tessera.agent.registry import get_agent
        from tessera.agent.state import new_state
        from tessera.observability.business_events import synthetic_turn
        from tessera.settings import LanguageCode

        started = datetime.now(UTC)
        try:
            agent = get_agent(agent_id)
            initial = new_state(
                conversation_id=uuid.UUID(conversation_id),
                turn_id=uuid.UUID(turn_id),
                user_input=_CANARY_PROBE,
                language=LanguageCode(agent.default_language),
            )
            token = current_agent_id.set(agent_id)
            try:
                # The synthetic mark scopes the whole turn: every business event emitted deep in
                # the graph inherits it and is excluded from business metrics by declaration (§4).
                with synthetic_turn():
                    await compile_graph().ainvoke(initial)
            finally:
                current_agent_id.reset(token)
        except (
            Exception
        ) as exc:  # a canary must never crash the scheduler — RED, never a fake green
            return CanaryTurnOutcome(ok=False, duration_ms=_elapsed_ms(started), error=_reason(exc))
        return CanaryTurnOutcome(ok=True, duration_ms=_elapsed_ms(started))


def _elapsed_ms(started: datetime) -> float:
    return (datetime.now(UTC) - started).total_seconds() * 1000.0


def _reason(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"


def scheduled_canaries() -> list[ScheduledCanary]:
    """The agents the scheduler drives: declared ``in_process_chat`` binding + a canary cadence.

    Reads the registry (the boundary-allowed manifest seam). An agent without a cadence is not
    scheduled; the cadence-requires-in_process_chat invariant is enforced at manifest load, so a
    scheduled agent always has a real seam to drive.
    """
    scheduled: list[ScheduledCanary] = []
    for agent in list_agents():
        invocation = agent.invocation
        if (
            invocation.binding is InvocationBinding.IN_PROCESS_CHAT
            and invocation.canary_cadence_s is not None
        ):
            scheduled.append(
                ScheduledCanary(agent_id=agent.id, cadence_s=invocation.canary_cadence_s)
            )
    return scheduled


def canary_posture(settings: Settings | None = None) -> dict[str, object]:
    """The canary scheduler's boot posture — one honest log line + the start decision.

    The single source of "are we scheduling canaries?", so the boot log and the scheduler can never
    disagree (the seal-posture discipline). ``scheduling`` is true only when the operator has
    enabled the master switch AND at least one manifest declares a cadence — otherwise the scheduler
    idles and says so.
    """
    from tessera.settings import get_settings

    resolved = settings or get_settings()
    enabled = bool(resolved.observability.canary_scheduler_enabled)
    scheduled = scheduled_canaries()
    return {
        "enabled": enabled,
        "scheduled": [{"agent_id": s.agent_id, "cadence_s": s.cadence_s} for s in scheduled],
        "scheduling": enabled and bool(scheduled),
    }


async def run_canary_cycle(
    agent_id: str, *, invoker: CanaryInvoker | None = None
) -> CanaryCycleResult:
    """Run one canary cycle for ``agent_id`` (ADR 0019 §I4).

    Builds a synthetic turn, drives it through the binding, and appends ONE S1 event recording the
    invocation and its verdict — emitted on green AND red (the invocation happened either way; the
    ledger is where governed acts live). The S1 entry doubles as the descriptor's freshness record.
    """
    from tessera.guard.audit import CANARY_ACTOR, emit_canary_invocation

    resolved = invoker or InProcessChatInvoker()
    binding = InvocationBinding.IN_PROCESS_CHAT.value  # the only binding the scheduler drives (I4)
    conversation_id = str(uuid.uuid4())
    turn_id = str(uuid.uuid4())
    outcome = await resolved.invoke(agent_id, conversation_id=conversation_id, turn_id=turn_id)
    verdict: Literal["green", "red"] = "green" if outcome.ok else "red"
    emit_canary_invocation(
        agent_id=agent_id,
        binding=binding,
        verdict=verdict,
        conversation_id=conversation_id,
        turn_id=turn_id,
        duration_ms=outcome.duration_ms,
        error=outcome.error,
        # No human ordered this turn — the scheduler fired it. Named, not blank, and not
        # "operator": a reader must never have to guess whether a person was behind a probe.
        actor=CANARY_ACTOR,
    )
    return CanaryCycleResult(
        agent_id=agent_id,
        verdict=verdict,
        binding=binding,
        conversation_id=conversation_id,
        turn_id=turn_id,
        duration_ms=outcome.duration_ms,
        error=outcome.error,
    )
