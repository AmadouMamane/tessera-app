"""Chat endpoint — invokes the agent graph and streams events as SSE.

We emit Server-Sent Events directly through Starlette's
:class:`StreamingResponse` rather than pulling a dedicated SSE helper, both
to minimise dependencies and to keep the wire format trivially auditable.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
import time
import uuid
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Literal, cast

from fastapi import APIRouter, Body
from langgraph.checkpoint.memory import MemorySaver
from opentelemetry import trace
from pydantic import BaseModel, ConfigDict, Field
from starlette.requests import (
    Request,  # noqa: TCH002  runtime-needed: FastAPI resolves the handler annotation
)
from starlette.responses import StreamingResponse

from tessera.agent import build_graph, reporter as reporter_module
from tessera.agent.grounding import select_grounded_citations
from tessera.agent.identity import current_agent_id

# Runtime (not TYPE_CHECKING): the §4 synthetic decision compares against
# `Surface.COCKPIT_EMBEDDED`, so the enum member must exist at run time, not only for mypy.
from tessera.agent.registry import Surface
from tessera.agent.sdk import instrument
from tessera.agent.state import (
    Citation,
    ConversationMessage,
    GuardDecisionRecord,
    NodeName,
    RetrievedDocument,
    ToolCallRecord,
    new_state,
)
from tessera.agent.supervisor import RoutingDecision, route_turn
from tessera.api.config_overrides import (
    base_chat_model,
    resolve_budget_policy,
    resolve_chat_model_override,
)
from tessera.api.operator import resolve_request_context
from tessera.api.session import issue_resume_token
from tessera.authz import AuthState
from tessera.guard.audit import (
    confirmed_tools,
    current_auth_state,
    current_model,
    current_tool_call_counts,
    emit_handoff,
    emit_routing,
    guard_disabled,
)
from tessera.guard.redaction import (
    StreamingRedactor,
    apply_output_guard,
    contains_pii,
    emit_output_redaction,
    mask_pan,
    redact_text,
    redaction_notice,
)
from tessera.llm.budget import estimate_turn_cost, get_budget_tracker, model_is_paid
from tessera.memory import memory_backend_for_state, scope_for
from tessera.memory.protocol import TurnRecord
from tessera.memory.transcript import append_messages, last_agent_for, load_transcript
from tessera.observability import replay, semconv
from tessera.observability.agent_configurations import (
    resolve_escalation_threshold,
    resolve_memory,
    resolve_retrieval,
    resolve_sampling,
    resolve_style,
)
from tessera.observability.business_events import mark_synthetic_turn
from tessera.observability.eval import online as online_eval
from tessera.observability.lineage import build_lineage
from tessera.observability.metrics import AGENT_TURN_DURATION, AGENT_TURNS_TOTAL
from tessera.observability.prompt_overlay import resolve_prompt_overlay
from tessera.settings import LanguageCode, get_settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Coroutine, Mapping

    from tessera.api.session import SessionContext
    from tessera.observability.lineage import Lineage

router = APIRouter(tags=["chat"])


# Strong references to in-flight background memory-formation tasks, so the event
# loop does not garbage-collect them before they finish (ADR 0007, Mechanism B).
_BACKGROUND_TASKS: set[asyncio.Task[None]] = set()
_MS_PER_SECOND = 1000.0
_GOOD_SCORE_10 = 8.0
_OK_SCORE_10 = 5.0
_MAX_DEBUG_SOURCES = 4


def _spawn_background(coro: Coroutine[object, object, None]) -> None:
    """Run a fire-and-forget coroutine, keeping a reference until it completes."""
    task = asyncio.create_task(coro)
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)


def _capture_prompt_messages(state: Mapping[str, object]) -> list[dict[str, str]] | None:
    """The exact assembled LLM message list, for the S2 replay record (XT-01)."""
    raw = state.get("debug_prompt_messages")
    if not isinstance(raw, list) or not raw:
        return None
    return [
        {"role": str(m.get("role", "")), "content": str(m.get("content", ""))}
        for m in raw
        if isinstance(m, dict)
    ]


def _capture_sampling(state: Mapping[str, object]) -> dict[str, float] | None:
    """The seam-resolved sampling that served the turn (ADR 0031), or ``None``."""
    raw = state.get("sampling")
    if not isinstance(raw, dict):
        return None
    resolved = {str(k): float(v) for k, v in raw.items() if isinstance(v, int | float)}
    return resolved or None


def _capture_tool_calls(state: Mapping[str, object]) -> list[dict[str, object]] | None:
    """Tool invocations as span rows: name, parent node, outcome, duration.

    Arguments and results are deliberately not captured — they can carry PII;
    the S2 record keeps the shape of the execution, not the payloads.
    """
    raw = state.get("tool_calls", [])
    if not isinstance(raw, list) or not raw:
        return None
    return [
        {
            "name": call.tool_name,
            "node": call.node,
            "succeeded": call.succeeded,
            "duration_ms": round(call.duration_ms, 1),
        }
        for call in raw
        if isinstance(call, ToolCallRecord)
    ]


async def _run_online_eval(
    *,
    question: str,
    answer: str,
    context: str,
    language: LanguageCode,
    conversation_id: uuid.UUID,
    model: str,
    agent_id: str,
    turn_id: uuid.UUID | None = None,
    lineage: Lineage | None = None,
    latency_ms: dict[str, float] | None = None,
    prompt_messages: list[dict[str, str]] | None = None,
    sampling: dict[str, float] | None = None,
    max_output_tokens: int | None = None,
    tool_calls: list[dict[str, object]] | None = None,
    node_starts: dict[str, float] | None = None,
    reporter_ms: float | None = None,
) -> None:
    """Score the turn off the hot path and capture it for replay (ADR 0010).

    ``agent_id`` attributes the score and the replay bundle to the responding
    agent, so per-agent SLO / trend / cost read the agent's own turns. The S2
    keyword group threads the execution record (assembled prompt, sampling,
    tool spans, real offsets) into the bundle — the XT-01 cassette.

    Never raises into the turn.
    """
    try:
        outcome = await online_eval.evaluate_turn(
            question=question,
            answer=answer,
            context=context,
            language=language.value,
            conversation_id=str(conversation_id),
            agent_id=agent_id,
            model=model,
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
                agent_id=agent_id,
                turn_id=str(turn_id) if turn_id is not None else None,
                lineage=lineage,
                latency_ms=latency_ms,
                prompt_messages=prompt_messages,
                sampling=sampling,
                max_output_tokens=max_output_tokens,
                tool_calls=tool_calls,
                node_starts=node_starts,
                reporter_ms=reporter_ms,
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


def is_test_turn(surface: Surface) -> bool:
    """Whether a turn entering on ``surface`` is an operator TESTING an agent (ADR 0019 §4).

    The cockpit Console is a test bench, not a customer: it reaches agents through this very
    route, so without this its turns would move business numbers exactly as customer traffic
    does. A scheduled canary is already excluded; a Console test turn was not.

    ``dedicated-ui`` is deliberately **not** a test bench, though it is equally an operator
    surface: it is recouvrement's business console, where an operator does REAL work whose
    events must count. Stamping every operator turn would silently delete that agent's entire
    business record — the opposite mistake, and the worse one.

    ``surface`` is derived server-side from the signed operator assertion
    (:func:`tessera.api.operator.resolve_request_context`) and is never asserted by the
    client, so neither error can be spoofed into existence.
    """
    return surface is Surface.COCKPIT_EMBEDDED


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
    system_prompt_override: str | None = Field(
        default=None,
        max_length=8_000,
        description=(
            "Sandbox-only system-prompt override for this turn (console playground). "
            "Replaces the language bundle's system prompt; never persisted."
        ),
    )
    guard_overrides: list[str] | None = Field(
        default=None,
        max_length=8,
        description=(
            "Sandbox-only list of guard categories to disable for this turn, e.g. "
            '["prompt_injection", "pii"]. Empty/absent = full policy applies.'
        ),
    )
    confirmed_tools: list[Literal["card_block"]] | None = Field(
        default=None,
        max_length=1,
        description=(
            "Tools explicitly confirmed through a human UI action for this turn. "
            "This channel is separate from model-generated text."
        ),
    )


class ActionConfirmationRequired(BaseModel):
    """Public-safe action metadata rendered as an explicit human control."""

    model_config = ConfigDict(extra="forbid")

    tool: Literal["card_block"]
    card_last_four: str = Field(pattern=r"^\d{4}$")


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
    confirmation_required: ActionConfirmationRequired | None = None
    debug: dict[str, object] | None = None


def _confirmation_required(state: Mapping[str, object]) -> ActionConfirmationRequired | None:
    decisions = state.get("guard_decisions")
    if not isinstance(decisions, list) or not any(
        isinstance(decision, GuardDecisionRecord)
        and decision.policy_rule == "tool.card_block.requires_confirmation"
        for decision in decisions
    ):
        return None
    calls = state.get("tool_calls")
    if not isinstance(calls, list):
        return None
    for call in calls:
        if not isinstance(call, ToolCallRecord) or call.tool_name != "card_block":
            continue
        last_four = call.arguments.get("card_last_four")
        if isinstance(last_four, str) and re.fullmatch(r"\d{4}", last_four):
            return ActionConfirmationRequired(tool="card_block", card_last_four=last_four)
    return None


def _fmt_ms(ms: float) -> str:
    if ms >= _MS_PER_SECOND:
        return f"{ms / _MS_PER_SECOND:.1f}s"
    return f"{ms:.0f}ms"


def _clamp_score(value: float) -> float:
    return max(0.0, min(10.0, value))


def _source_scope(source: str) -> str:
    return "Interne" if source.startswith("credit-aurore") else "Externe"


def _quality_row(label: str, score: float | None) -> dict[str, object]:
    """One quality row from a real 0..1 reviewer score, scaled to /10."""
    if score is None:
        return {"label": label, "value": "—", "scale": "/10", "tone": "warn"}
    value = _clamp_score(score * 10.0)
    tone = "good" if value >= _GOOD_SCORE_10 else "warn" if value >= _OK_SCORE_10 else "crit"
    return {"label": label, "value": f"{value:.1f}", "scale": "/10", "tone": tone}


def _debug_quality(
    *,
    confidence: float | None,
    grounding: float | None,
    coverage: float | None,
    guard: float | None,
    needs_escalation: bool,
) -> dict[str, object]:
    """Per-turn quality from the reviewer's *own* signals — no fabrication.

    The four rows are the reviewer's real axes: the composite confidence and the
    grounding / coverage / guard split it fused (each 0..1, scaled to /10). The
    badge reflects the reviewer's actual escalation decision, not a synthetic
    threshold over invented sub-scores.
    """
    return {
        "title": "Qualite & securite de la reponse",
        "badge": "A surveiller" if needs_escalation else "Bon",
        "badge_tone": "warn" if needs_escalation else "good",
        "rows": [
            _quality_row("Confiance", confidence),
            _quality_row("Ancrage", grounding),
            _quality_row("Couverture", coverage),
            _quality_row("Securite", guard),
        ],
    }


def _debug_sources(docs: list[RetrievedDocument], citations: list[Citation]) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    # Dedup on the *displayed label* so a source that is both cited and retrieved
    # as a document (the two loops keyed differently — locator vs chunk_id) cannot
    # surface twice. The label is also the React key on the frontend.
    seen: set[str] = set()

    def _add(source: str, locator: str) -> None:
        label = f"{source} - {locator}"
        if label in seen or len(rows) >= _MAX_DEBUG_SOURCES:
            return
        seen.add(label)
        rows.append({"label": label, "scope": _source_scope(source)})

    for citation in citations:
        _add(citation.source, citation.locator)
    for doc in docs:
        locator = doc.metadata.get("locator") or doc.chunk_id
        _add(doc.source, str(locator))
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


_TRACE_LABELS = {
    "router": "Routage",
    "planner": "Planification",
    "dispatch": "Recherche / outils",
    "product_lookup": "Recherche produit",
    "regulation_lookup": "Recherche reglementaire",
    "account_lookup": "Recherche compte",
    "simulator": "Simulation",
    "escalation_worker": "Escalade",
    "reviewer": "Garde-fous & revue",
    "reporter": "Generation de la reponse",
}


def _trace_label(key: str) -> str:
    return _TRACE_LABELS.get(key, key.replace("_", " ").title())


def _debug_trace(
    timings: Mapping[str, float],
    starts: Mapping[str, float],
    *,
    warn_keys: frozenset[str] = frozenset(),
    reporter_ms: float | None = None,
) -> dict[str, object]:
    """Build the trace waterfall from the *real* per-node timings (ADR 0010 #4).

    Each span is positioned by its **real measured start offset** (ms from the
    turn's collection origin, captured by ``instrument``) and sized by its real
    duration — so the bars cascade and parallel nodes overlap, rather than all
    starting at 0. Spans are ordered by start. The total is the real end of the
    last span (max start+duration), not a sum. No stage is fabricated: only nodes
    that actually ran (and were timed) appear. ``status`` is derived from real
    signals — a node is ``warn`` only when the turn's guard decisions flagged it.
    """
    spans: list[dict[str, object]] = []
    for key, ms in timings.items():
        duration = float(ms)
        start = float(starts.get(key, 0.0))
        spans.append(
            {
                "key": key,
                "label": _trace_label(key),
                "start_ms": round(start, 1),
                "duration_ms": round(duration, 1),
                "status": "warn" if key in warn_keys else "ok",
            }
        )
    spans.sort(key=lambda s: (cast(float, s["start_ms"]), cast(str, s["label"])))
    total = max(
        (cast(float, s["start_ms"]) + cast(float, s["duration_ms"]) for s in spans),
        default=0.0,
    )
    # The reporter streams *after* the graph pauses before it (interrupt_before),
    # so its synthesis duration is never captured by the Phase-1 node timings.
    # Append it as the final span — starting where Phase 1 ends — so the trace
    # total reconciles with the turn's wall-clock latency instead of stopping at
    # the lookups. Measured streaming wall time, not a fabricated figure.
    if reporter_ms is not None and reporter_ms > 0 and "reporter" not in timings:
        spans.append(
            {
                "key": "reporter",
                "label": _trace_label("reporter"),
                "start_ms": round(total, 1),
                "duration_ms": round(reporter_ms, 1),
                "status": "ok",
            }
        )
        total += reporter_ms
    return {
        "title": "Trace d'execution",
        "total_ms": round(total, 1),
        "count": len(spans),
        "spans": spans,
    }


def _opt_float(value: object) -> float | None:
    """Coerce a state value to ``float`` for the debug envelope, or ``None``."""
    return float(value) if isinstance(value, int | float) else None


def _as_int(value: object) -> int:
    """Coerce a state value to ``int`` for the debug envelope, defaulting to 0."""
    return int(value) if isinstance(value, int | float) else 0


def _enum_value(item: object) -> str:
    """Render a StrEnum (or any value) as its string form."""
    return item.value if isinstance(item, StrEnum) else str(item)


def _debug_prompt(state: Mapping[str, object]) -> dict[str, object] | None:
    """Surface #1 — the exact LLM message list the reporter assembled."""
    raw = state.get("debug_prompt_messages")
    if not isinstance(raw, list) or not raw:
        return None
    messages = [
        {"role": str(m.get("role", "")), "content": str(m.get("content", ""))}
        for m in raw
        if isinstance(m, dict)
    ]
    return {
        "title": "Prompt LLM assemblé",
        "messages": messages,
        "message_count": len(messages),
        "char_count": sum(len(str(m["content"])) for m in messages),
    }


def _debug_memory(state: Mapping[str, object]) -> dict[str, object] | None:
    """Surface #2 — the injected memory context (summary, ledger, long-term)."""
    raw = state.get("debug_memory")
    if not isinstance(raw, dict):
        return None
    entities = raw.get("entities")
    long_term = raw.get("long_term")
    return {
        "title": "Mémoire injectée",
        "summary": raw.get("summary"),
        "entities": [str(e) for e in entities] if isinstance(entities, list) else [],
        "long_term": [str(x) for x in long_term] if isinstance(long_term, list) else [],
        "recent_verbatim": _as_int(raw.get("recent_verbatim")),
        "backend": str(raw.get("backend", "")),
    }


def _debug_routing(state: Mapping[str, object], decision: RoutingDecision) -> dict[str, object]:
    """Surface #3 — routing decision plus the planner's plan and rationale."""
    plan = state.get("plan", [])
    plan_items = [_enum_value(w) for w in plan] if isinstance(plan, list) else []
    rationale = state.get("plan_rationale")
    return {
        "title": "Routage & plan",
        "agent_id": decision.agent_id,
        "reason": decision.reason,
        "handoff": decision.handoff,
        "from_agent": decision.from_agent,
        "plan": plan_items,
        "plan_rationale": str(rationale) if rationale is not None else None,
    }


def _debug_usage(
    state: Mapping[str, object], *, latency_ms: float, model: str
) -> dict[str, object]:
    """Surface #4 — real token counts, latency, and indicative cost."""
    input_tokens = _as_int(state.get("input_tokens"))
    output_tokens = _as_int(state.get("output_tokens"))
    provider, cost = estimate_turn_cost(
        model=model, input_tokens=input_tokens, output_tokens=output_tokens
    )
    # ADR 0031 — the sampling that actually served this turn (seam-resolved;
    # only SET parameters appear). Absent on paths that never spoke.
    sampling_raw = state.get("sampling")
    sampling = (
        {str(k): float(v) for k, v in sampling_raw.items() if isinstance(v, int | float)}
        if isinstance(sampling_raw, dict)
        else {}
    )
    # ADR 0032 — the behaviour style and hard cap that served this turn.
    style_raw = state.get("style")
    style = {str(k): str(v) for k, v in style_raw.items()} if isinstance(style_raw, dict) else {}
    max_output_tokens = state.get("max_output_tokens")
    return {
        "title": "Tokens, latence & coût",
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "latency_ms": round(latency_ms, 1),
        "estimated_cost_eur": float(cost),
        "model": model,
        "provider": provider,
        "sampling": sampling,
        "style": style,
        "max_output_tokens": max_output_tokens if isinstance(max_output_tokens, int) else None,
    }


def _debug_reviewer(state: Mapping[str, object]) -> dict[str, object]:
    """Surface #5 — the reviewer's grounding/coverage/guard split, not just confidence."""
    reason = state.get("escalation_reason")
    return {
        "title": "Scores du reviewer",
        "confidence": _opt_float(state.get("confidence")),
        "grounding": _opt_float(state.get("grounding_score")),
        "coverage": _opt_float(state.get("coverage_score")),
        "guard": _opt_float(state.get("guard_score")),
        "needs_escalation": bool(state.get("needs_escalation", False)),
        "reason": str(reason) if reason is not None else None,
        # ADR 0033 — the escalation bar this turn was judged against.
        "threshold": _opt_float(state.get("escalation_threshold")),
    }


def _debug_language(state: Mapping[str, object], *, pinned: bool) -> dict[str, object]:
    """Surface #6 — detected language and its confidence."""
    return {
        "title": "Langue détectée",
        "detected": _enum_value(state.get("language")),
        "confidence": _opt_float(state.get("language_confidence")),
        "pinned": pinned,
    }


def _debug_draft(state: Mapping[str, object], final_response: str) -> dict[str, object]:
    """Surface #7 — the model's raw output versus the final user-facing response.

    Prefers the raw (pre-strip) synthesis output so a removed ``<think>`` block or
    markup is visible; falls back to the worker draft when no LLM synthesis ran.
    """
    raw = state.get("debug_synthesis_raw")
    worker_draft = state.get("draft_response")
    if raw:
        source: str | None = str(raw)
        label = "Synthèse brute (avant nettoyage)"
    elif worker_draft:
        source = str(worker_draft)
        label = "Brouillon worker"
    else:
        source = None
        label = "Aucun brouillon"
    # The Debug surface must not become the PII channel the output guard just
    # closed: the pre-guard draft is masked too. It stays raw only under the
    # sandbox "pii" override, where the operator is explicitly probing the guard.
    overrides = state.get("guard_overrides")
    pii_guard_off = isinstance(overrides, list) and "pii" in overrides
    if source and not pii_guard_off:
        source = redact_text(source).text
    return {
        "title": "Brouillon vs réponse finale",
        "draft": source,
        "draft_label": label,
        "final": final_response,
        "changed": (source or "") != final_response,
        "draft_chars": len(source) if source else 0,
        "final_chars": len(final_response),
    }


def _debug_config(state: Mapping[str, object], *, default_model: str) -> dict[str, object]:
    """Surface #8 — the effective sandbox config that actually ran this turn."""
    override_model = state.get("model")
    guard = state.get("guard_overrides")
    return {
        "title": "Configuration effective",
        "model": str(override_model) if override_model else default_model,
        "model_source": "override" if override_model else "default",
        "system_prompt_override": bool(state.get("system_prompt_override")),
        "guard_overrides": [str(g) for g in guard] if isinstance(guard, list) else [],
    }


def _debug_from_state(
    *,
    state: Mapping[str, object],
    timings: Mapping[str, float],
    starts: Mapping[str, float],
    citations: list[Citation],
    final_response: str,
    decision: RoutingDecision,
    latency_ms: float,
    pinned_language: bool,
    reporter_ms: float | None = None,
) -> dict[str, object]:
    docs = cast(list[RetrievedDocument], state.get("retrieved_documents", []))
    tool_calls = cast(list[ToolCallRecord], state.get("tool_calls", []))
    guard_decisions = cast(list[GuardDecisionRecord], state.get("guard_decisions", []))
    confidence_raw = state.get("confidence")
    confidence = float(confidence_raw) if isinstance(confidence_raw, int | float) else None
    denied_count = sum(1 for decision in guard_decisions if decision.decision == "deny")
    # The reviewer node is where the output guard runs; mark its span as warn
    # only when the turn's real guard decisions denied or redacted output.
    flagged = denied_count > 0 or any(decision.redactions for decision in guard_decisions)
    warn_keys = frozenset({"reviewer"}) if flagged else frozenset()
    default_model = get_settings().ollama.chat_model
    model_raw = state.get("model")
    effective_model = str(model_raw) if model_raw else default_model
    debug: dict[str, object] = {
        "quality": _debug_quality(
            confidence=confidence,
            grounding=_opt_float(state.get("grounding_score")),
            coverage=_opt_float(state.get("coverage_score")),
            guard=_opt_float(state.get("guard_score")),
            needs_escalation=bool(state.get("needs_escalation", False)),
        ),
        "sources": _debug_sources(docs, citations),
        "tools": _debug_tools(tool_calls, docs, timings),
        "guardrails": _debug_guardrails(guard_decisions),
        "trace": _debug_trace(timings, starts, warn_keys=warn_keys, reporter_ms=reporter_ms),
        "tokens": len(final_response.split()),
        # Console Debug surfaces (real data only). Always present:
        "routing": _debug_routing(state, decision),
        "usage": _debug_usage(state, latency_ms=latency_ms, model=effective_model),
        "reviewer": _debug_reviewer(state),
        "language": _debug_language(state, pinned=pinned_language),
        "draft": _debug_draft(state, final_response),
        "config": _debug_config(state, default_model=default_model),
    }
    # Prompt + injected memory exist only when the synthesis path ran (an
    # escalation / injection-block turn never calls the LLM). Omit when absent
    # so the envelope never carries a null the schema would reject.
    prompt = _debug_prompt(state)
    if prompt is not None:
        debug["prompt"] = prompt
    memory = _debug_memory(state)
    if memory is not None:
        debug["memory"] = memory
    return debug


def _sse(event: str, payload: object) -> bytes:
    body = json.dumps(payload, default=str, ensure_ascii=False)
    return f"event: {event}\ndata: {body}\n\n".encode()


def sandbox_overrides_allowed(surface: Surface, auth_state: AuthState) -> bool:
    """Whether this turn may relax the guard at all (audit P0 `guard-bypass`).

    ``system_prompt_override`` and ``guard_overrides`` are the console playground's sandbox
    controls: they replace the system prompt (a jailbreak primitive) and switch off guard
    categories — tool DENY rules, PII redaction, grounding. Until this existed, "Sandbox-only"
    was a *docstring* and nothing else: the fields were read straight off the request body of
    ``POST /chat`` with no check on who was asking or where from, so ANY anonymous caller
    could disable the entire safety stack for their turn and stream an unredacted PAN back.

    Both inputs here are server-derived — ``surface`` from the signed operator assertion,
    ``auth_state`` from the verified session — never from the body. A caller cannot lie its
    way into the sandbox.
    """
    return surface is Surface.COCKPIT_EMBEDDED and auth_state is AuthState.OPERATOR


def _turn_deadline_s() -> float:
    """Wall-clock budget for one turn's graph phase.

    Reuses ``api.request_timeout_seconds``, which until now was declared in settings and
    never applied to a request — the deadline it names did not exist.
    """
    return get_settings().api.request_timeout_seconds


# What a failing turn is allowed to tell the caller. The reason is a fixed, enumerated
# token — never the exception text, which would hand an unauthenticated caller whatever
# the failure carried. The turn id is the operator's join key into the logs and the audit
# ledger: the client can report it, and only someone with log access can resolve it.
def _client_error(turn_id: object, reason: Literal["timeout", "internal"]) -> dict[str, object]:
    """Build the client-safe ``turn.error`` payload for a failed turn."""
    return {"error": reason, "turn_id": str(turn_id)}


async def _stream_turn(  # noqa: PLR0915, PLR0912  SSE turn handler is inherently statement- and branch-heavy (graph run + guarded stream + persist + eval)
    request: ChatRequest,
    *,
    surface: Surface,
    session: SessionContext,
) -> AsyncIterator[bytes]:
    conversation_id = request.conversation_id or uuid.uuid4()
    turn_id = uuid.uuid4()
    language = request.language or get_settings().default_language
    pinned_confidence = 1.0 if request.language is not None else 0.0
    auth_state = session.auth_state
    # An authenticated session binds the turn to its verified customer identity —
    # memory and the account tools resolve to one subject. The
    # client-supplied subject_id is only a fallback for the anonymous case; it can
    # never raise auth (auth_state comes from the signed session, not the body).
    effective_subject = session.subject_id or request.subject_id

    # The guard is only relaxable from the operator's own cockpit sandbox. Off that surface
    # the two override fields are DROPPED — not rejected. A 4xx would tell an attacker the
    # fields are real and worth probing; silently applying the full policy tells them nothing
    # and costs a legitimate operator nothing (audit P0 `guard-bypass`, chat.py:725-726 -> :735).
    sandbox = sandbox_overrides_allowed(surface, auth_state)
    system_prompt_override = request.system_prompt_override if sandbox else None
    guard_overrides = request.guard_overrides if sandbox else None

    prior_messages = await _prior_messages(conversation_id, request)
    initial = new_state(
        conversation_id=conversation_id,
        turn_id=turn_id,
        user_input=request.message,
        language=language,
        language_confidence=pinned_confidence,
        prior_messages=prior_messages,
        subject_id=effective_subject,
        model=request.model,
        system_prompt_override=system_prompt_override,
        guard_overrides=guard_overrides,
    )
    # Propagate sandbox guard toggles to the guard layer for this turn only.
    guard_disabled.set(frozenset(guard_overrides or ()))
    # Publish the server-derived auth-state so the guard's tool allowlist gates
    # account/PII tools on the real session (anonymous → denied, customer → ok).
    current_auth_state.set(auth_state)
    confirmed_tools.set(frozenset(request.confirmed_tools or ()))
    current_tool_call_counts.set({})
    # Per-turn agent attribution: the supervisor routes this turn to an agent
    # (parcours by default; an intent can trigger a governed handoff). The chosen
    # agent handles the whole turn and is stamped on every event, metric and
    # message. One conversation can therefore span agents.
    prev_agent = await last_agent_for(conversation_id)
    # Routing is scoped to the entry surface and the server-derived auth-state
    # (ADR 0008): the customer widget pool is {support-client, onboarding}. The
    # recouvrement agent is operator-only (ADR 0010 Phase A) — off this surface
    # entirely, so no customer session can be routed or handed into it.
    decision = route_turn(prev_agent, request.message, surface=surface, auth_state=auth_state)
    agent_id = decision.agent_id
    current_agent_id.set(agent_id)
    # ADR 0030 — the durable governed default sits between the per-turn picker and
    # the frozen base: picker > per-agent override > org override > base. Resolved
    # once per turn, after routing (the agent decides which override applies), and
    # written into the state + every attribution surface (audit context, trace
    # dimensions, eval lineage) — what serves is what is recorded.
    effective_model = request.model or await resolve_chat_model_override(agent_id)
    # ADR 0034 — the daily budget breaker sits at the same seam and gates PAID
    # models only. When the day's recorded spend has reached the ceiling:
    # local_fallback serves the frozen base if it is zero-cost, otherwise the
    # turn is blocked (the router short-circuits with the localized message).
    # No ceiling stored (or store down, loudly) → no breaker: historical truth.
    budget_overrun: str | None = None
    budget_policy = await resolve_budget_policy()
    if budget_policy is not None and model_is_paid(effective_model or base_chat_model()):
        day_spend = get_budget_tracker().snapshot().day_cost_eur
        if day_spend >= budget_policy.daily_eur:
            base = base_chat_model()
            if budget_policy.overrun == "local_fallback" and not model_is_paid(base):
                effective_model = base
                budget_overrun = "local_fallback"
            else:
                # A fallback onto a paid base is not a fallback — degrade to block.
                initial["budget_blocked"] = True
                budget_overrun = "block"
            sys.stderr.write(
                f"tessera.budget: daily ceiling {budget_policy.daily_eur} EUR reached "
                f"(day spend {day_spend}) — overrun={budget_overrun}\n"
            )
    if effective_model is not None:  # NotRequired: absent means "the base serves"
        initial["model"] = effective_model
    # Record the effective model on audit entries emitted during this turn
    # (memory governance, guard) — not just the server default.
    current_model.set(effective_model)
    # ADR 0031 — sampling resolves at the same seam as the model: once per turn,
    # after routing, from the agent's effective configuration. The reporter
    # passes it to the backend call, so the slider value and the served value
    # are the same read (fail-open to the runtime defaults inside).
    sampling = resolve_sampling(agent_id)
    initial["sampling"] = sampling
    # ADR 0032 — the behaviour selects resolve at the same seam: tone/detail/
    # length become prompt directives in the reporter, and the length's declared
    # token budget becomes the backend call's hard cap.
    style, max_output_tokens = resolve_style(agent_id)
    initial["style"] = style
    initial["max_output_tokens"] = max_output_tokens
    # ADR 0033 — the escalation threshold resolves at the same seam; the
    # reviewer reads the state, so the knob and the served bar are one read.
    escalation_threshold = resolve_escalation_threshold(agent_id)
    initial["escalation_threshold"] = escalation_threshold
    # ADR 0035 — the retrieval knobs resolve at the same seam; the lookup
    # workers read the state (off-seam paths keep their historical constants).
    initial["retrieval"] = resolve_retrieval(agent_id)
    # ADR 0036 — the memory knobs resolve at the same seam; the reporter's
    # message assembly reads the state (off-seam paths keep the org singleton).
    initial["memory"] = resolve_memory(agent_id)
    # ADR 0037 — only the APPROVED prompt overlay serves, resolved at the seam.
    overlay = resolve_prompt_overlay(agent_id)
    if overlay is not None:
        initial["prompt_overlay"] = overlay
    synthetic = is_test_turn(surface)
    if synthetic:
        mark_synthetic_turn()
    # Stamp the full dimension set on the turn's root span so the trace is queryable per
    # {agent, language, model, conversation, turn, environment} — the substrate the spine
    # reads (Langfuse metadata filter, per-dimension aggregates) — ADR 0015 §Migration B.
    semconv.stamp_turn_dimensions(
        trace.get_current_span(),
        agent_id=agent_id,
        language=language.value,
        model=effective_model,
        conversation_id=str(conversation_id),
        turn_id=str(turn_id),
        environment=get_settings().environment.value,
        synthetic=synthetic,
    )
    # ADR 0031/0032 — what serves is what is recorded: the resolved sampling and
    # the hard cap land on the same root span (gen_ai.request.*; unset
    # parameters honest-absent).
    semconv.stamp_turn_sampling(
        trace.get_current_span(), sampling, max_output_tokens=max_output_tokens
    )
    # ADR 0033 — the served escalation bar is recorded beside the sampling.
    trace.get_current_span().set_attribute(
        semconv.TESSERA_ESCALATION_THRESHOLD, escalation_threshold
    )
    # ADR 0034 — the budget breaker's decision, when it fired, is recorded too.
    if budget_overrun is not None:
        trace.get_current_span().set_attribute(semconv.TESSERA_BUDGET_OVERRUN, budget_overrun)
    # Audit EVERY routing decision (stay or switch) with its reason, so routing is
    # opposable end to end — you can prove why a turn went to a given agent from
    # the start, not just that it switched.
    emit_routing(
        agent_id=agent_id,
        conversation_id=str(conversation_id),
        turn_id=str(turn_id),
        reason=decision.reason,
        handoff=decision.handoff,
        from_agent=decision.from_agent,
    )
    if decision.handoff and decision.from_agent is not None:
        # A switch additionally emits the distinct agent->agent handoff event
        # (never the human-escalation path).
        emit_handoff(
            from_agent=decision.from_agent,
            to_agent=agent_id,
            conversation_id=str(conversation_id),
            turn_id=str(turn_id),
            reason=decision.reason,
        )

    graph = _streaming_graph()
    config: dict[str, object] = {"configurable": {"thread_id": str(turn_id)}}
    started = time.perf_counter()
    # The resume capability rides with the id it authorizes (audit 2026-07-12, F-4). The
    # widget stores both and presents them together to re-read ITS OWN transcript, now that
    # /observability/conversation-messages is operator-only. Knowing the id is no longer
    # enough — the id was never a secret, it was published next to the opening user message
    # by /observability/conversations.
    yield _sse(
        "turn.start",
        {
            "conversation_id": str(conversation_id),
            "turn_id": str(turn_id),
            "resume_token": issue_resume_token(str(conversation_id)),
        },
    )

    # Phase 1: run graph up to (but not including) the reporter node.
    # Escalation and injection-block paths complete fully here. Per-node latencies
    # are collected for the critical-path breakdown (idea #48).
    node_starts: dict[str, float] = {}
    with instrument.collect_node_timings() as node_timings:
        try:
            # One deadline for the whole graph phase — router, planner, workers and the
            # retrieval they call. Nothing below this had a deadline of its own: a hung
            # pgvector query or a frozen Vertex call held the SSE stream open forever
            # (audit `robustness-timeout`). Bounded here rather than at each leaf so a
            # turn can never outlive its budget whatever path it takes.
            async with asyncio.timeout(_turn_deadline_s()):
                await graph.ainvoke(initial, config=config)  # type: ignore[attr-defined]
        except TimeoutError:
            AGENT_TURNS_TOTAL.labels(
                agent_id=agent_id, language=language.value, outcome="error"
            ).inc()
            sys.stderr.write(
                f"tessera.chat: turn {turn_id} exceeded the {_turn_deadline_s()}s deadline\n"
            )
            yield _sse("turn.error", _client_error(turn_id, "timeout"))
            return
        except Exception as exc:
            AGENT_TURNS_TOTAL.labels(
                agent_id=agent_id, language=language.value, outcome="error"
            ).inc()
            # The cause goes to the operator's logs, never onto the wire. str(exc) hands an
            # unauthenticated caller whatever the failure happened to carry — SQL fragments,
            # internal hostnames, prompt content (audit `robustness-cluster`, chat.py:802).
            sys.stderr.write(f"tessera.chat: turn {turn_id} failed: {exc!r}\n")
            yield _sse("turn.error", _client_error(turn_id, "internal"))
            return
        # Read the real per-node start offsets while still inside the context
        # (the ContextVar is reset on exit). Feeds the trace waterfall.
        node_starts = instrument.node_start_offsets()

    snapshot = graph.get_state(config)  # type: ignore[attr-defined]
    state = snapshot.values

    # Phase 2: stream reporter when the graph is paused before it.
    # Otherwise (escalation / injection block) final_response is already set.
    final_response: str
    turn_citations: list[Citation] = list(state.get("citations", []))
    resolved_language: LanguageCode = state.get("language", language)
    # Output guard (cases 02/45): the reporter node is bypassed on the streaming
    # path, so its redaction runs here instead — on the token stream itself, not
    # just on the stored final_response (a masked transcript is worthless if the
    # raw PAN already crossed the wire). The sandbox "pii" override disables it.
    #
    # Reads the GATED value, not request.guard_overrides. This line used to read the raw
    # request body, so it survived the surface/auth check above: an anonymous caller sending
    # guard_overrides=["pii"] still switched the streaming redactor off and got an unredacted
    # PAN on the wire. It was the last unguarded path into the safety stack.
    pii_guard_off = bool(guard_overrides and "pii" in guard_overrides)
    output_guard_record: GuardDecisionRecord | None = None
    # The reporter's generation (LLM synthesis) runs here in Phase 2, outside the
    # Phase-1 node-timing context — measure it so the trace waterfall can show it.
    reporter_ms: float | None = None
    if NodeName.REPORTER.value in (snapshot.next or ()):
        reporter_perf_start = time.perf_counter()
        docs = state.get("retrieved_documents", [])
        draft = state.get("draft_response", "")
        tokens: list[str] = []
        if docs:
            # astream_synthesise threads the backend's exact per-call token usage
            # onto the state (state["input_tokens"]/["output_tokens"]) and stashes
            # the raw pre-strip output — both consumed by the Debug envelope.
            redactor = None if pii_guard_off else StreamingRedactor()
            async for token in reporter_module.astream_synthesise(state):
                tokens.append(token)
                emitted = token if redactor is None else redactor.feed(token)
                if emitted:
                    yield _sse("turn.token", {"token": emitted})
            # Cite the chunks that actually ground the answer's claims (across
            # every worker), falling back to the worker-selected citations when
            # attribution finds nothing so a turn never loses its sources.
            # Sources are surfaced as structured citations (turn.end payload +
            # UI pills), so we deliberately do not also append a text "Sources:"
            # footer to the answer — that duplicated them in the bubble.
            if redactor is None:
                final_response = "".join(tokens)
            else:
                tail = redactor.flush()
                if tail:
                    yield _sse("turn.token", {"token": tail})
                final_response = redactor.text
                if redactor.redactions:
                    output_guard_record = emit_output_redaction(redactor.redactions)
                if redactor.redactions or contains_pii(request.message):
                    # Streamed verbatim too, so the bubble and the stored
                    # final_response stay byte-identical.
                    notice = f"\n\n{redaction_notice(resolved_language)}"
                    yield _sse("turn.token", {"token": notice})
                    final_response += notice
            grounded = select_grounded_citations(final_response, docs)
            if grounded:
                turn_citations = grounded
        elif draft:
            final_response, output_guard_record = apply_output_guard(
                reporter_module.render(state),
                language=resolved_language,
                user_input=request.message,
                disabled=pii_guard_off,
            )
        else:
            from tessera.agent.reporter import _FALLBACK_RESPONSES

            final_response, output_guard_record = apply_output_guard(
                _FALLBACK_RESPONSES[resolved_language],
                language=resolved_language,
                user_input=request.message,
                disabled=pii_guard_off,
            )
        reporter_ms = (time.perf_counter() - reporter_perf_start) * _MS_PER_SECOND
    else:
        # Escalation / short-circuit texts are vetted, but the guard still
        # sweeps them so no path can return unmasked PII.
        final_response, output_guard_record = apply_output_guard(
            str(state.get("final_response", "")),
            language=resolved_language,
            disabled=pii_guard_off,
        )
    if output_guard_record is not None:
        # Surface the redact_output decision in this turn's guard_decisions
        # (Debug envelope + downstream persistence); the audit ledger entry was
        # already emitted by the guard itself.
        state["guard_decisions"] = [*state.get("guard_decisions", []), output_guard_record]

    duration = time.perf_counter() - started
    AGENT_TURN_DURATION.labels(agent_id=agent_id, language=resolved_language.value).observe(
        duration
    )
    needs_escalation = bool(state.get("needs_escalation", False))
    outcome: Literal["complete", "escalated"] = "escalated" if needs_escalation else "complete"
    AGENT_TURNS_TOTAL.labels(
        agent_id=agent_id, language=resolved_language.value, outcome=outcome
    ).inc()

    # Persist this turn to the durable transcript (ADR 0007, Mechanism A). A
    # transcript failure must never break the user's response, so it degrades
    # to a logged warning.
    # Input-leg PAN mask (docs/design/pii-input-redaction.md, Option A seam 2):
    # the durable transcript — and the context window it feeds on later turns —
    # stores the masked form. The TurnRecord below keeps the raw text so entity
    # extraction retains detection fidelity; the memory layer masks at its own
    # exits (model calls + durable writes). The sandbox "pii" override skips
    # the seam; the persistence backstops stay unconditional.
    persisted_user_text = request.message if pii_guard_off else mask_pan(request.message).text
    user_msg = ConversationMessage(role="user", content=persisted_user_text)
    raw_user_msg = ConversationMessage(role="user", content=request.message)
    assistant_msg = ConversationMessage(role="assistant", content=final_response)
    try:
        await append_messages(
            conversation_id,
            turn_id,
            [user_msg, assistant_msg],
            agent_id=agent_id,
            latency_ms=duration * _MS_PER_SECOND,
            subject_id=effective_subject,
            synthetic=synthetic,
        )
    except Exception as exc:  # audit/persistence must not block a turn
        sys.stderr.write(f"tessera.memory.transcript: append failed: {exc}\n")

    # Mechanism B (ADR 0007): form summary/long-term memory off the hot path.
    # No-op for the window backend; real work for summary/persistent backends.
    _spawn_background(
        memory_backend_for_state(state).record(
            scope=scope_for(conversation_id, resolved_language, subject_id=effective_subject),
            turn=TurnRecord(
                user_input=request.message,
                final_response=final_response,
                messages=[*(prior_messages or []), raw_user_msg, assistant_msg],
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
        # The state's model is the turn's effective one (picker > override > base,
        # ADR 0030) — the lineage must attribute what actually served.
        eval_model_raw = state.get("model")
        effective_model = (
            str(eval_model_raw) if eval_model_raw else get_settings().ollama.chat_model
        )
        # Sink 6 of the design note: the judge and the durable replay bundle
        # receive the masked question — faithful to what the model itself saw.
        # XT-01 (registre des rails): the bundle is the S2 record of this
        # execution — the exact assembled prompt, the seam-resolved sampling,
        # the tool spans with their parent node, and the real start offsets, so
        # the cassette can be re-read and replayed after this process is gone.
        max_tokens_raw = state.get("max_output_tokens")
        _spawn_background(
            _run_online_eval(
                question=persisted_user_text,
                answer=final_response,
                context=context_text,
                language=resolved_language,
                conversation_id=conversation_id,
                model=effective_model,
                agent_id=agent_id,
                turn_id=turn_id,
                lineage=build_lineage(
                    language=resolved_language.value,
                    model=effective_model,
                    documents=docs_for_eval,
                ),
                latency_ms=dict(node_timings),
                prompt_messages=_capture_prompt_messages(state),
                sampling=_capture_sampling(state),
                max_output_tokens=(
                    int(max_tokens_raw) if isinstance(max_tokens_raw, int) else None
                ),
                tool_calls=_capture_tool_calls(state),
                node_starts=dict(node_starts) or None,
                reporter_ms=reporter_ms,
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
        confirmation_required=_confirmation_required(state),
        debug=_debug_from_state(
            state=state,
            timings=node_timings,
            starts=node_starts,
            citations=turn_citations,
            final_response=final_response,
            decision=decision,
            latency_ms=duration * _MS_PER_SECOND,
            pinned_language=request.language is not None,
            reporter_ms=reporter_ms,
        ),
    )
    yield _sse("turn.end", envelope.model_dump())


@router.post("/chat")
async def chat(
    request: Request,
    payload: Annotated[ChatRequest, Body(...)],
) -> StreamingResponse:
    """POST /chat — Server-Sent-Events stream of the agent's turn.

    Rate limiting is applied by RateLimitMiddleware (ADR 0020), not a decorator.

    The entry surface and the session's auth-state are resolved here, server-side,
    from trusted signals — never read from the request body (ADR 0008). The customer
    path (signed cookie → CUSTOMER/ANONYMOUS on the shared-customer-widget) is the
    default; a valid signed operator assertion forwarded by the Next BFF lifts the
    turn to (OPERATOR, cockpit-embedded) (ADR 0010 Phase B). This is what scopes
    routing/handoff to the agents the surface and auth permit.
    """
    session, surface = resolve_request_context(request)
    return StreamingResponse(
        _stream_turn(payload, surface=surface, session=session),
        media_type="text/event-stream",
        headers={
            "cache-control": "no-cache",
            "connection": "keep-alive",
            "x-accel-buffering": "no",  # disable nginx buffering
        },
    )
