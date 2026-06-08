"""Chat endpoint — invokes the agent graph and streams events as SSE.

We emit Server-Sent Events directly through Starlette's
:class:`StreamingResponse` rather than pulling a dedicated SSE helper, both
to minimise dependencies and to keep the wire format trivially auditable.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import TYPE_CHECKING, Annotated, Literal

from fastapi import APIRouter, Body
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel, ConfigDict, Field
from starlette.responses import StreamingResponse

from tessera.agent import build_graph, reporter as reporter_module
from tessera.agent.state import ConversationMessage, NodeName, deduplicate_citations, new_state
from tessera.guard.audit import current_model
from tessera.memory import get_memory_backend, scope_for
from tessera.memory.protocol import TurnRecord
from tessera.memory.transcript import append_messages, load_transcript
from tessera.observability.context import reset_turn_context, set_turn_context
from tessera.observability.evidence import build_state_evidence_bundle, persist_evidence_bundle
from tessera.observability.instrumentation import emit_event, start_span
from tessera.observability.logging import get_logger
from tessera.observability.metrics import (
    AGENT_TURN_DURATION,
    AGENT_TURNS_TOTAL,
    LANGUAGE_MISMATCHES_TOTAL,
    MEMORY_DEGRADATIONS_TOTAL,
)
from tessera.observability.profiles import resolve_profile
from tessera.observability.schema import TelemetryEvent, TelemetrySpan
from tessera.settings import LanguageCode, get_settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Coroutine

router = APIRouter(tags=["chat"])

# Strong references to in-flight background memory-formation tasks, so the event
# loop does not garbage-collect them before they finish (ADR 0007, Mechanism B).
_BACKGROUND_TASKS: set[asyncio.Task[None]] = set()
_LOGGER = get_logger(__name__)


def _spawn_background(coro: Coroutine[object, object, None]) -> None:
    """Run a fire-and-forget coroutine, keeping a reference until it completes."""
    task = asyncio.create_task(coro)
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)


# The checkpointer is keyed per turn (thread_id = turn_id) on purpose: it only
# powers the intra-turn streaming pause (interrupt before the reporter). Keying
# it by conversation would bleed one turn's per-turn accumulator channels
# (retrieved_documents, citations, tool_calls…) into the next, since their
# reducers concatenate. Cross-turn continuity is the transcript's job instead —
# see tessera.memory.transcript and ADR 0007, Mechanism A.
_checkpointer = MemorySaver()


async def _prior_messages(
    conversation_id: uuid.UUID, request: ChatRequest
) -> list[ConversationMessage] | None:
    """Resolve prior-turn context, preferring the durable server-side transcript.

    The client-supplied ``history`` is only a cold-start hint: it is used when
    the server has no transcript for this conversation (e.g. a transcript
    imported from elsewhere). If the transcript store is unreachable we degrade
    to the hint rather than failing the turn.
    """
    try:
        stored = await load_transcript(conversation_id)
    except Exception as exc:  # degrade gracefully, never block a turn
        MEMORY_DEGRADATIONS_TOTAL.labels(
            operation="transcript_load",
            reason=type(exc).__name__,
        ).inc()
        _LOGGER.warning("memory_transcript_load_failed", error=str(exc))
        stored = []
    if stored:
        return stored
    if request.history:
        return [ConversationMessage(role=h.role, content=h.content) for h in request.history]
    return None


def _streaming_graph() -> object:
    """Compile a graph that pauses before the reporter so we can stream tokens."""
    return build_graph().compile(
        checkpointer=_checkpointer,
        interrupt_before=[NodeName.REPORTER.value],
    )


class HistoryMessage(BaseModel):
    """A single prior-turn message sent by the client for multi-turn context."""

    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8_000)


class ChatRequest(BaseModel):
    """Incoming chat request body."""

    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=4_000)
    conversation_id: uuid.UUID | None = None
    subject_id: str | None = Field(
        default=None,
        max_length=200,
        description=(
            "Stable long-term-memory identity key (ADR 0007). When supplied, "
            "cross-session memory is keyed by it; otherwise it falls back to the "
            "conversation id (per-thread memory only)."
        ),
    )
    language: LanguageCode | None = Field(
        default=None,
        description="Optional language hint; the router will still verify.",
    )
    history: list[HistoryMessage] | None = Field(
        default=None,
        description="Prior conversation turns for multi-turn context injection.",
        max_length=40,
    )
    model: str | None = Field(
        default=None,
        max_length=100,
        description="Optional chat-model override (UI picker); falls back to server default.",
    )


class ChatEnvelope(BaseModel):
    """Final envelope, emitted as the last SSE event."""

    model_config = ConfigDict(extra="forbid")

    conversation_id: uuid.UUID
    turn_id: uuid.UUID
    language: LanguageCode
    final_response: str
    needs_escalation: bool
    confidence: float | None
    citations: list[dict[str, str]]
    finish_reason: Literal["complete", "escalated", "error"]


def _sse(event: str, payload: object) -> bytes:
    body = json.dumps(payload, default=str, ensure_ascii=False)
    return f"event: {event}\ndata: {body}\n\n".encode()


async def _stream_turn(request: ChatRequest) -> AsyncIterator[bytes]:  # noqa: PLR0915
    """Run one chat turn, streaming SSE events and committing evidence."""
    conversation_id = request.conversation_id or uuid.uuid4()
    turn_id = uuid.uuid4()
    language = request.language or get_settings().default_language
    pinned_confidence = 1.0 if request.language is not None else 0.0
    turn_tokens = set_turn_context(conversation_id, turn_id)
    model_token = current_model.set(request.model)
    started = time.perf_counter()

    try:
        with start_span(
            TelemetrySpan.TURN,
            {
                "turn_id": str(turn_id),
                "language": language.value,
                "model": request.model or "",
            },
        ) as span:
            emit_event(
                TelemetryEvent.TURN_STARTED,
                {
                    "turn_id": str(turn_id),
                    "language": language.value,
                    "model": request.model or "",
                },
                span=span,
            )
            prior_messages = await _prior_messages(conversation_id, request)
            initial = new_state(
                conversation_id=conversation_id,
                turn_id=turn_id,
                user_input=request.message,
                language=language,
                language_confidence=pinned_confidence,
                prior_messages=prior_messages,
                subject_id=request.subject_id,
                model=request.model,
            )

            graph = _streaming_graph()
            config: dict[str, object] = {"configurable": {"thread_id": str(turn_id)}}
            yield _sse(
                "turn.start",
                {"conversation_id": str(conversation_id), "turn_id": str(turn_id)},
            )

            try:
                await graph.ainvoke(initial, config=config)  # type: ignore[attr-defined]
            except Exception as exc:
                AGENT_TURNS_TOTAL.labels(language=language.value, outcome="error").inc()
                span.record_exception(exc)
                yield _sse("turn.error", {"error": str(exc)})
                return

            snapshot = graph.get_state(config)  # type: ignore[attr-defined]
            state = snapshot.values
            final_response: str
            if NodeName.REPORTER.value in (snapshot.next or ()):
                docs = state.get("retrieved_documents", [])
                draft = state.get("draft_response", "")
                tokens: list[str] = []
                if docs:
                    async for token in reporter_module.astream_synthesise(state):
                        tokens.append(token)
                        yield _sse("turn.token", {"token": token})
                    final_response = "".join(tokens)
                elif draft:
                    final_response = reporter_module.render(state)
                else:
                    from tessera.agent.reporter import _FALLBACK_RESPONSES

                    final_response = _FALLBACK_RESPONSES[state["language"]]
            else:
                final_response = str(state.get("final_response", ""))

            duration = time.perf_counter() - started
            resolved_language: LanguageCode = state.get("language", language)
            if request.language is not None and request.language is not resolved_language:
                LANGUAGE_MISMATCHES_TOTAL.labels(
                    expected=request.language.value,
                    actual=resolved_language.value,
                ).inc()
            AGENT_TURN_DURATION.labels(language=resolved_language.value).observe(duration)
            needs_escalation = bool(state.get("needs_escalation", False))
            outcome: Literal["complete", "escalated"] = (
                "escalated" if needs_escalation else "complete"
            )
            AGENT_TURNS_TOTAL.labels(language=resolved_language.value, outcome=outcome).inc()

            user_msg = ConversationMessage(role="user", content=request.message)
            assistant_msg = ConversationMessage(role="assistant", content=final_response)
            try:
                await append_messages(conversation_id, turn_id, [user_msg, assistant_msg])
            except Exception as exc:
                MEMORY_DEGRADATIONS_TOTAL.labels(
                    operation="transcript_append",
                    reason=type(exc).__name__,
                ).inc()
                _LOGGER.warning("memory_transcript_append_failed", error=str(exc))

            _spawn_background(
                get_memory_backend().record(
                    scope=scope_for(
                        conversation_id,
                        resolved_language,
                        subject_id=request.subject_id,
                    ),
                    turn=TurnRecord(
                        user_input=request.message,
                        final_response=final_response,
                        messages=[*(prior_messages or []), user_msg, assistant_msg],
                        language=resolved_language,
                    ),
                )
            )

            evidence_state = {**state, "final_response": final_response}
            profile = resolve_profile()
            evidence_payload: dict[str, str] | None = None
            if profile.evidence_enabled:
                bundle = build_state_evidence_bundle(
                    evidence_state,
                    final_response=final_response,
                )
                persist_evidence_bundle(bundle)
                evidence_payload = {
                    "evidence_id": bundle.evidence_id,
                    "proof_quality": bundle.proof_quality,
                    "proof_consensus": bundle.proof_consensus,
                }
                emit_event(
                    TelemetryEvent.EVIDENCE_COMMITTED,
                    {
                        "turn_id": str(turn_id),
                        "proof_quality": bundle.proof_quality,
                        "proof_consensus": bundle.proof_consensus,
                    },
                    span=span,
                )
                yield _sse("evidence.committed", evidence_payload)

            emit_event(
                TelemetryEvent.TURN_COMPLETED,
                {
                    "turn_id": str(turn_id),
                    "language": resolved_language.value,
                    "outcome": outcome,
                },
                span=span,
            )
            envelope = ChatEnvelope(
                conversation_id=conversation_id,
                turn_id=turn_id,
                language=resolved_language,
                final_response=final_response,
                needs_escalation=needs_escalation,
                confidence=state.get("confidence"),
                citations=[
                    {"source": c.source, "locator": c.locator, "language": c.language.value}
                    for c in deduplicate_citations(state.get("citations", []))
                ],
                finish_reason=outcome,
            )
            yield _sse("turn.end", envelope.model_dump())
    finally:
        current_model.reset(model_token)
        reset_turn_context(turn_tokens)


@router.post("/chat")
async def chat(
    payload: Annotated[ChatRequest, Body(...)],
) -> StreamingResponse:
    """POST /chat — Server-Sent-Events stream of the agent's turn.

    Rate limiting is applied by RateLimitMiddleware (ADR 0008), not a decorator.
    """
    return StreamingResponse(
        _stream_turn(payload),
        media_type="text/event-stream",
        headers={
            "cache-control": "no-cache",
            "connection": "keep-alive",
            "x-accel-buffering": "no",  # disable nginx buffering
        },
    )
