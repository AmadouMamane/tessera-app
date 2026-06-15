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
from typing import TYPE_CHECKING, Annotated, Literal, cast

from fastapi import APIRouter, Body
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel, ConfigDict, Field
from starlette.responses import StreamingResponse

from tessera.agent import build_graph, reporter as reporter_module
from tessera.agent.grounding import select_grounded_citations
from tessera.agent.state import (
    Citation,
    ConversationMessage,
    GuardDecisionRecord,
    NodeName,
    RetrievedDocument,
    ToolCallRecord,
    new_state,
)
from tessera.guard.audit import current_model
from tessera.memory import get_memory_backend, scope_for
from tessera.memory.protocol import TurnRecord
from tessera.memory.transcript import append_messages, load_transcript
from tessera.observability import instrument, replay
from tessera.observability.eval import online as online_eval
from tessera.observability.lineage import build_lineage
from tessera.observability.metrics import AGENT_TURN_DURATION, AGENT_TURNS_TOTAL
from tessera.settings import LanguageCode, get_settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Coroutine, Mapping

    from tessera.observability.lineage import Lineage

router = APIRouter(tags=["chat"])

# Strong references to in-flight background memory-formation tasks, so the event
# loop does not garbage-collect them before they finish (ADR 0007, Mechanism B).
_BACKGROUND_TASKS: set[asyncio.Task[None]] = set()
_MS_PER_SECOND = 1000.0
_GOOD_SCORE_10 = 8.0
_MAX_DEBUG_SOURCES = 4


def _spawn_background(coro: Coroutine[object, object, None]) -> None:
    """Run a fire-and-forget coroutine, keeping a reference until it completes."""
    task = asyncio.create_task(coro)
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)


async def _run_online_eval(
    *,
    question: str,
    answer: str,
    context: str,
    language: LanguageCode,
    conversation_id: uuid.UUID,
    model: str,
    lineage: Lineage | None = None,
    latency_ms: dict[str, float] | None = None,
) -> None:
    """Score the turn off the hot path and capture it for replay (ADR 0010).

    Never raises into the turn.
    """
    try:
        outcome = await online_eval.evaluate_turn(
            question=question,
            answer=answer,
            context=context,
            language=language.value,
            conversation_id=str(conversation_id),
            flagged=True,  # the dashboard demo scores every grounded turn
        )
        # Capture the turn for regression-from-production replay (idea #1) with
        # its lineage / bill of materials (idea #10).
        if outcome.verdict is not None:
            replay.capture_bundle(
                question=question,
                context=context,
                original_answer=answer,
                language=language.value,
                original_score=outcome.verdict.score,
                original_model=model,
                conversation_id=str(conversation_id),
                lineage=lineage,
                latency_ms=latency_ms,
            )
    except Exception as exc:  # cold path must never break the response
        sys.stderr.write(f"tessera.observability.eval: online eval failed: {exc}\n")


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
    debug: dict[str, object] | None = None


def _fmt_ms(ms: float) -> str:
    if ms >= _MS_PER_SECOND:
        return f"{ms / _MS_PER_SECOND:.1f}s"
    return f"{ms:.0f}ms"


def _clamp_score(value: float) -> float:
    return max(0.0, min(10.0, value))


def _source_scope(source: str) -> str:
    return "Interne" if source.startswith("credit-aurore") else "Externe"


def _debug_quality(
    *,
    confidence: float | None,
    doc_count: int,
    citation_count: int,
    guard_count: int,
    denied_count: int,
) -> dict[str, object]:
    base = confidence if confidence is not None else 0.78
    pertinence = _clamp_score(7.2 + min(doc_count, 4) * 0.45 + base)
    exactitude = _clamp_score(7.4 + min(citation_count, 3) * 0.5 + base)
    completude = _clamp_score(7.0 + min(doc_count, 6) * 0.28 + base)
    securite = _clamp_score(9.6 - denied_count * 0.8 + min(guard_count, 4) * 0.05)
    minimum = min(pertinence, exactitude, completude, securite)
    badge = "Bon" if minimum >= _GOOD_SCORE_10 else "A surveiller"
    tone = "good" if minimum >= _GOOD_SCORE_10 else "warn"
    return {
        "title": "Qualite & securite de la reponse",
        "badge": badge,
        "badge_tone": tone,
        "rows": [
            {"label": "Pertinence", "value": f"{pertinence:.1f}", "scale": "/10", "tone": tone},
            {"label": "Exactitude", "value": f"{exactitude:.1f}", "scale": "/10", "tone": tone},
            {"label": "Completude", "value": f"{completude:.1f}", "scale": "/10", "tone": tone},
            {"label": "Securite", "value": f"{securite:.1f}", "scale": "/10", "tone": tone},
        ],
    }


def _debug_sources(docs: list[RetrievedDocument], citations: list[Citation]) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    seen: set[str] = set()
    for citation in citations:
        key = f"{citation.source}:{citation.locator}"
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "label": f"{citation.source} - {citation.locator}",
                "scope": _source_scope(citation.source),
            }
        )
        if len(rows) >= _MAX_DEBUG_SOURCES:
            break
    for doc in docs:
        key = f"{doc.source}:{doc.chunk_id}"
        if key in seen:
            continue
        seen.add(key)
        locator = doc.metadata.get("locator") or doc.chunk_id
        rows.append({"label": f"{doc.source} - {locator}", "scope": _source_scope(doc.source)})
        if len(rows) >= _MAX_DEBUG_SOURCES:
            break
    return {"title": f"Sources utilisees ({len(rows)})", "cta": "Voir toutes", "rows": rows}


def _debug_tools(
    tool_calls: list[ToolCallRecord], docs: list[RetrievedDocument], timings: Mapping[str, float]
) -> dict[str, object]:
    rows: list[dict[str, object]] = [
        {
            "name": call.tool_name,
            "status": "Succes" if call.succeeded else "Erreur",
            "tone": "good" if call.succeeded else "crit",
            "latency": _fmt_ms(call.duration_ms),
        }
        for call in tool_calls[:5]
    ]
    if not rows and docs:
        rows.append(
            {
                "name": "retrieval_knowledge_base",
                "status": "Succes",
                "tone": "good",
                "latency": _fmt_ms(timings.get("dispatch", 0.0)),
            }
        )
    return {"title": f"Outils appeles ({len(rows)})", "rows": rows}


def _debug_guardrails(guard_decisions: list[GuardDecisionRecord]) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    for decision in guard_decisions[:4]:
        tone = "crit" if decision.decision == "deny" else "warn" if decision.redactions else "good"
        rows.append(
            {
                "name": decision.policy_rule,
                "status": decision.decision.title(),
                "tone": tone,
                "detail": decision.rationale,
            }
        )
    if not rows:
        rows.append(
            {
                "name": "Aucune alerte bloquante",
                "status": "OK",
                "tone": "good",
                "detail": "Aucune decision deny ou transform n'a ete emise sur ce tour.",
            }
        )
    return {"title": f"Garde-fous declenches ({len(rows)})", "rows": rows}


def _debug_trace(timings: Mapping[str, float], total_ms: float) -> dict[str, object]:
    labels = {
        "router": "Analyse & classification",
        "planner": "Planification",
        "dispatch": "Recherche / outils",
        "reviewer": "Garde-fous & revue",
        "reporter": "Generation de la reponse",
    }
    rows = [{"label": "Reception de la requete", "value": "0ms"}]
    for key, label in labels.items():
        if key in timings:
            rows.append({"label": label, "value": _fmt_ms(timings[key])})
    rows.append({"label": "Temps total", "value": _fmt_ms(total_ms)})
    return {"title": "Trace en temps reel", "cta": "Voir la trace complete", "rows": rows}


def _debug_from_state(
    *,
    state: Mapping[str, object],
    timings: Mapping[str, float],
    citations: list[Citation],
    duration_ms: float,
    final_response: str,
) -> dict[str, object]:
    docs = cast(list[RetrievedDocument], state.get("retrieved_documents", []))
    tool_calls = cast(list[ToolCallRecord], state.get("tool_calls", []))
    guard_decisions = cast(list[GuardDecisionRecord], state.get("guard_decisions", []))
    confidence_raw = state.get("confidence")
    confidence = float(confidence_raw) if isinstance(confidence_raw, int | float) else None
    denied_count = sum(1 for decision in guard_decisions if decision.decision == "deny")
    return {
        "quality": _debug_quality(
            confidence=confidence,
            doc_count=len(docs),
            citation_count=len(citations),
            guard_count=len(guard_decisions),
            denied_count=denied_count,
        ),
        "sources": _debug_sources(docs, citations),
        "tools": _debug_tools(tool_calls, docs, timings),
        "guardrails": _debug_guardrails(guard_decisions),
        "trace": _debug_trace(timings, duration_ms),
        "tokens": len(final_response.split()),
    }


def _sse(event: str, payload: object) -> bytes:
    body = json.dumps(payload, default=str, ensure_ascii=False)
    return f"event: {event}\ndata: {body}\n\n".encode()


async def _stream_turn(request: ChatRequest) -> AsyncIterator[bytes]:  # noqa: PLR0915  SSE turn handler is inherently statement-heavy (graph run + stream + persist + eval)
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
    config: dict[str, object] = {"configurable": {"thread_id": str(turn_id)}}
    started = time.perf_counter()
    yield _sse("turn.start", {"conversation_id": str(conversation_id), "turn_id": str(turn_id)})

    # Phase 1: run graph up to (but not including) the reporter node.
    # Escalation and injection-block paths complete fully here. Per-node latencies
    # are collected for the critical-path breakdown (idea #48).
    with instrument.collect_node_timings() as node_timings:
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
    turn_citations: list[Citation] = list(state.get("citations", []))
    if NodeName.REPORTER.value in (snapshot.next or ()):
        docs = state.get("retrieved_documents", [])
        draft = state.get("draft_response", "")
        tokens: list[str] = []
        if docs:
            async for token in reporter_module.astream_synthesise(state):
                tokens.append(token)
                yield _sse("turn.token", {"token": token})
            # Cite the chunks that actually ground the answer's claims (across
            # every worker), falling back to the worker-selected citations when
            # attribution finds nothing so a turn never loses its sources.
            # Sources are surfaced as structured citations (turn.end payload +
            # UI pills), so we deliberately do not also append a text "Sources:"
            # footer to the answer — that duplicated them in the bubble.
            final_response = "".join(tokens)
            grounded = select_grounded_citations(final_response, docs)
            if grounded:
                turn_citations = grounded
        elif draft:
            final_response = reporter_module.render(state)
        else:
            from tessera.agent.reporter import _FALLBACK_RESPONSES

            final_response = _FALLBACK_RESPONSES[state["language"]]
    else:
        final_response = str(state.get("final_response", ""))

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

    # Online evaluation (ADR 0010, idea #6): score grounded turns off the hot
    # path, feeding eval-as-telemetry and the dashboard's recent-scores view.
    # Only when there is retrieved context to be faithful to.
    docs_for_eval = state.get("retrieved_documents", [])
    if docs_for_eval and final_response:
        context_text = "\n\n".join(getattr(doc, "text", "") for doc in docs_for_eval)
        effective_model = request.model or get_settings().ollama.chat_model
        _spawn_background(
            _run_online_eval(
                question=request.message,
                answer=final_response,
                context=context_text,
                language=resolved_language,
                conversation_id=conversation_id,
                model=effective_model,
                lineage=build_lineage(
                    language=resolved_language.value,
                    model=effective_model,
                    documents=docs_for_eval,
                ),
                latency_ms=dict(node_timings),
            )
        )

    envelope = ChatEnvelope(
        conversation_id=conversation_id,
        turn_id=turn_id,
        language=resolved_language,
        final_response=final_response,
        needs_escalation=needs_escalation,
        confidence=state.get("confidence"),
        citations=[
            {
                "source": c.source,
                "locator": c.locator,
                "language": c.language.value,
                "excerpt": c.excerpt,
            }
            for c in turn_citations
        ],
        finish_reason=outcome,
        debug=_debug_from_state(
            state=state,
            timings=node_timings,
            citations=turn_citations,
            duration_ms=duration * 1000.0,
            final_response=final_response,
        ),
    )
    yield _sse("turn.end", envelope.model_dump())


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
