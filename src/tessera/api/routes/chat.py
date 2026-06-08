"""Chat endpoint — invokes the agent graph and streams events as SSE.

We emit Server-Sent Events directly through Starlette's
:class:`StreamingResponse` rather than pulling a dedicated SSE helper, both
to minimise dependencies and to keep the wire format trivially auditable.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
import uuid
from typing import TYPE_CHECKING, Annotated, Literal

from fastapi import APIRouter, Body
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel, ConfigDict, Field
from starlette.responses import StreamingResponse

from tessera.agent import build_graph, reporter as reporter_module
from tessera.agent.state import ConversationMessage, NodeName, new_state
from tessera.guard.audit import current_model
from tessera.memory import get_memory_backend, scope_for

try:
    from langfuse import Langfuse
    from langfuse.langchain import CallbackHandler
except ImportError:
    Langfuse = None
    CallbackHandler = None
from datetime import UTC
import datetime

from tessera.memory.protocol import TurnRecord
from tessera.memory.transcript import append_messages, load_transcript
from tessera.observability.metrics import AGENT_TURN_DURATION, AGENT_TURNS_TOTAL
from tessera.settings import LanguageCode, get_settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Coroutine

router = APIRouter(tags=["chat"])

# Strong references to in-flight background memory-formation tasks, so the event
# loop does not garbage-collect them before they finish (ADR 0007, Mechanism B).
_BACKGROUND_TASKS: set[asyncio.Task[None]] = set()


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
        sys.stderr.write(f"tessera.memory.transcript: load failed: {exc}\n")
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
    trace_id: str | None = None


def _sse(event: str, payload: object) -> bytes:
    body = json.dumps(payload, default=str, ensure_ascii=False)
    return f"event: {event}\ndata: {body}\n\n".encode()


async def _stream_turn(request: ChatRequest) -> AsyncIterator[bytes]:  # noqa: PLR0912, PLR0915
    from tessera.llm.budget import current_request_input, current_request_output
    current_request_input.set(0)
    current_request_output.set(0)

    conversation_id = request.conversation_id or uuid.uuid4()
    turn_id = uuid.uuid4()
    language = request.language or get_settings().default_language
    pinned_confidence = 1.0 if request.language is not None else 0.0

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
    # Record the effective model on audit entries emitted during this turn
    # (memory governance, guard) — not just the server default.
    current_model.set(request.model)

    graph = _streaming_graph()
    config: dict[str, object] = {
        "configurable": {"thread_id": str(turn_id)},
        "tags": ["chat", f"model:{request.model or 'default'}", f"lang:{language.value}"],
        "metadata": {
            "session_id": str(conversation_id),
            "user_id": request.subject_id,
        },
    }

    langfuse_handler = None
    import logging

    logger = logging.getLogger("tessera.api")
    logger.error("CallbackHandler is: %s", CallbackHandler)
    if CallbackHandler is not None:
        langfuse_handler = CallbackHandler()
        config["callbacks"] = [langfuse_handler]
        logger.error("Instantiated langfuse_handler: %s", langfuse_handler)

    started = time.perf_counter()
    from datetime import datetime

    datetime.now(UTC)

    # Yield the turn start immediately
    trace_id = langfuse_handler.last_trace_id if langfuse_handler is not None else None
    yield _sse(
        "turn.start",
        {"conversation_id": str(conversation_id), "turn_id": str(turn_id), "trace_id": trace_id},
    )

    # Phase 1: run graph up to (but not including) the reporter node.
    # Escalation and injection-block paths complete fully here.
    try:
        await graph.ainvoke(initial, config=config)  # type: ignore[attr-defined]
    except Exception as exc:
        AGENT_TURNS_TOTAL.labels(language=language.value, outcome="error").inc()
        yield _sse("turn.error", {"error": str(exc)})
        return

    snapshot = graph.get_state(config)  # type: ignore[attr-defined]
    state = snapshot.values

    # Phase 2: stream reporter when the graph is paused before it.
    # Otherwise (escalation / injection block) final_response is already set.
    final_response: str
    if NodeName.REPORTER.value in (snapshot.next or ()):
        docs = state.get("retrieved_documents", [])
        draft = state.get("draft_response", "")
        tokens: list[str] = []
        if docs:
            async for token in reporter_module.astream_synthesise(state):
                tokens.append(token)
                yield _sse("turn.token", {"token": token})
            citations_footer = reporter_module.format_citations(
                state.get("citations", []), state["language"]
            )
            final_response = "".join(tokens) + citations_footer
        elif draft:
            final_response = reporter_module.render(state)
        else:
            from tessera.agent.reporter import _FALLBACK_RESPONSES

            final_response = _FALLBACK_RESPONSES[state["language"]]
    else:
        final_response = str(state.get("final_response", ""))

    datetime.now(UTC)
    duration = time.perf_counter() - started
    resolved_language: LanguageCode = state.get("language", language)
    AGENT_TURN_DURATION.labels(language=resolved_language.value).observe(duration)
    needs_escalation = bool(state.get("needs_escalation", False))
    outcome: Literal["complete", "escalated"] = "escalated" if needs_escalation else "complete"
    AGENT_TURNS_TOTAL.labels(language=resolved_language.value, outcome=outcome).inc()

    # Persist this turn to the durable transcript (ADR 0007, Mechanism A). A
    # transcript failure must never break the user's response, so it degrades
    # to a logged warning.
    user_msg = ConversationMessage(role="user", content=request.message)
    assistant_msg = ConversationMessage(role="assistant", content=final_response)
    try:
        await append_messages(conversation_id, turn_id, [user_msg, assistant_msg])
    except Exception as exc:  # audit/persistence must not block a turn
        sys.stderr.write(f"tessera.memory.transcript: append failed: {exc}\n")

    # Mechanism B (ADR 0007): form summary/long-term memory off the hot path.
    # No-op for the window backend; real work for summary/persistent backends.
    _spawn_background(
        get_memory_backend().record(
            scope=scope_for(conversation_id, resolved_language, subject_id=request.subject_id),
            turn=TurnRecord(
                user_input=request.message,
                final_response=final_response,
                messages=[*(prior_messages or []), user_msg, assistant_msg],
                language=resolved_language,
            ),
        )
    )

    trace_id = langfuse_handler.last_trace_id if langfuse_handler is not None else None
    envelope = ChatEnvelope(
        conversation_id=conversation_id,
        turn_id=turn_id,
        language=resolved_language,
        final_response=final_response,
        needs_escalation=needs_escalation,
        confidence=state.get("confidence"),
        citations=[
            {"source": c.source, "locator": c.locator, "language": c.language.value}
            for c in state.get("citations", [])
        ],
        finish_reason=outcome,
        trace_id=trace_id,
    )

    # Langfuse trace is managed by the CallbackHandler automatically
    if langfuse_handler is not None:
        try:
            import asyncio
            if hasattr(langfuse_handler, "_langfuse_client"):
                await asyncio.to_thread(langfuse_handler._langfuse_client.flush)
            from opentelemetry import trace

            provider = trace.get_tracer_provider()
            if hasattr(provider, "force_flush"):
                await asyncio.to_thread(provider.force_flush)
        except Exception as exc:
            logging.getLogger("tessera.api").exception("Failed to flush langfuse traces")
    shadow_model = get_settings().observability.shadow_model
    if shadow_model:
        _spawn_background(
            _run_shadow_mode(
                request, conversation_id, resolved_language, prior_messages, shadow_model
            )
        )

    yield _sse("turn.end", envelope.model_dump())


async def _run_shadow_mode(
    request: ChatRequest,
    conversation_id: uuid.UUID,
    language: LanguageCode,
    prior_messages: list[ConversationMessage] | None,
    shadow_model: str,
) -> None:
    """Execute a shadow trace asynchronously, throwing away the result but recording the telemetry."""  # noqa: E501
    shadow_turn_id = uuid.uuid4()
    initial = new_state(
        conversation_id=conversation_id,
        turn_id=shadow_turn_id,
        user_input=request.message,
        language=language,
        language_confidence=1.0,
        prior_messages=prior_messages,
        subject_id=request.subject_id,
        model=shadow_model,
    )
    graph = build_graph().compile()

    config: dict[str, object] = {
        "configurable": {"thread_id": str(shadow_turn_id)},
        "tags": ["shadow", f"model:{shadow_model}", f"lang:{language.value}"],
        "metadata": {
            "session_id": str(conversation_id),
            "user_id": request.subject_id,
        },
    }
    if CallbackHandler is not None:
        langfuse_handler = CallbackHandler()
        config["callbacks"] = [langfuse_handler]

    try:
        final_state = await graph.ainvoke(initial, config=config)
        str(final_state.get("final_response", ""))
    except Exception as exc:
        import logging
        logging.getLogger("tessera.api").warning("Shadow trace graph invocation failed: %s", exc)

    if CallbackHandler is not None:
        try:
            import asyncio
            if hasattr(langfuse_handler, "_langfuse_client"):
                await asyncio.to_thread(langfuse_handler._langfuse_client.flush)
            from opentelemetry import trace

            provider = trace.get_tracer_provider()
            if hasattr(provider, "force_flush"):
                await asyncio.to_thread(provider.force_flush)
        except Exception as exc:
            import logging
            logging.getLogger("tessera.api").warning("Shadow trace forced flush failed: %s", exc)


@router.post("/chat")
async def chat(
    payload: Annotated[ChatRequest, Body(...)],
) -> StreamingResponse:
    """POST /chat — Server-Sent-Events stream of the agent's turn.

    Rate limiting is applied by RateLimitMiddleware (ADR 0008), not a decorator.
    """
    settings = get_settings()
    if settings.observability.canary_model and settings.observability.canary_ratio > 0:
        import random
        if random.random() < settings.observability.canary_ratio:
            payload.model = settings.observability.canary_model
            # Note: The 'variant' tag is usually added in the graph config
            # but setting it here is the simplest way. We will add a tag
            # to langfuse if we pass it down, but for now just modifying the model works.

    return StreamingResponse(
        _stream_turn(payload),
        media_type="text/event-stream",
        headers={
            "cache-control": "no-cache",
            "connection": "keep-alive",
            "x-accel-buffering": "no",  # disable nginx buffering
        },
    )
