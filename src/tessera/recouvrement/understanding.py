"""Layer-1 LLM understanding for Recouvrement: classify and extract, never speak (ADR 0053).

One LLM call turns a free-text operator message into a schema-validated verdict —
an intent from the manifest's closed capability vocabulary plus the two text
fields the graph consumes. The model's words never reach anyone: the output is a
validated object or a named failure, and the caller (shadow seam today, the
router in active mode) falls back to the deterministic regex ladder on every
failure kind. Failure kinds are a closed vocabulary because each one is handled
and counted differently: a ``budget_ceiling`` is policy, a ``timeout`` is
latency, a ``schema_invalid`` is the model misbehaving, an ``llm_error`` is the
backend failing — collapsing them would hide which knob to turn.

The call is metered like every other spender: it asks ADR 0034's daily ceiling
through :func:`tessera.llm.ceiling.resolve_spend_model` before spending, and a
reached ceiling degrades understanding instead of refusing the turn.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

__all__ = [
    "DEFAULT_TIMEOUT_S",
    "PROMPT_KEY",
    "UnderstandingOutcome",
    "UnderstandingVerdict",
    "classify_intent_llm",
    "intent_vocabulary",
]

#: Provisional shadow-phase timeout. ADR 0053 leaves the value to measurement; it
#: becomes a governed knob with the mode/threshold pair (slice 4). Generous on
#: purpose while the call runs off the hot path.
DEFAULT_TIMEOUT_S = 8.0

#: The prompt bundle key (``src/tessera/agent/prompts/{fr,de,en}.yaml``) holding the
#: classifier prompt; ``<PROMPT_KEY>_version`` names its version for telemetry.
PROMPT_KEY = "recouvrement_intent_classifier"

_CALLER = "tessera.recouvrement.understanding"


def intent_vocabulary() -> frozenset[str]:
    """The closed intent vocabulary IS the manifest's declared capability ids.

    Read from the registry, never from a copied list, so a manifest change reaches
    the classifier's schema without anyone remembering to mirror it (ADR 0053 §1).

    Returns:
        The capability ids the recouvrement manifest declares.
    """
    from tessera.agent.registry import get_agent

    agent = get_agent("recouvrement")
    if agent.observability is None:  # pragma: no cover — conformance requires the manifest
        return frozenset()
    return frozenset(capability.id for capability in agent.observability.capabilities)


class _LlmIntentPayload(BaseModel):
    """The exact JSON shape the model must produce — anything else is refused."""

    model_config = ConfigDict(extra="forbid")

    intent: str
    confidence: float = Field(ge=0.0, le=1.0)
    duration_months: int | None = Field(default=None, ge=1, le=999)
    requested_time: str | None = Field(default=None, pattern=r"^([01][0-9]|2[0-3]):[0-5][0-9]$")


@dataclass(frozen=True, slots=True)
class UnderstandingVerdict:
    """A schema-valid classification of one free-text operator turn."""

    intent: str
    confidence: float
    duration_months: int | None
    requested_time: str | None


@dataclass(frozen=True, slots=True)
class UnderstandingOutcome:
    """The classifier's answer, or a failure that names its kind.

    ``status == "verdict"`` carries a verdict; every other status carries a
    ``detail`` and a ``None`` verdict. ``model`` is the model that actually
    answered (or was intended, on failure paths that never reached one).
    """

    status: Literal["verdict", "schema_invalid", "timeout", "llm_error", "budget_ceiling"]
    verdict: UnderstandingVerdict | None
    detail: str | None
    model: str
    prompt_version: str
    latency_ms: float


def _extract_json_object(text: str) -> str:
    """Cut the first ``{`` … last ``}`` span — models love to wrap JSON in prose or fences."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return text
    return text[start : end + 1]


def _prompt_for(language: str) -> tuple[str, str]:
    """Resolve the classifier prompt and its version for ``language`` (fallback: default).

    Args:
        language: The turn's language code; an unknown value resolves to the
            configured default rather than failing the classification.

    Returns:
        ``(system_prompt, prompt_version)`` with the intent vocabulary formatted in.
    """
    from tessera.agent.reporter import load_prompts
    from tessera.settings import LanguageCode, get_settings

    try:
        resolved = LanguageCode(language)
    except ValueError:
        resolved = get_settings().default_language
    prompts = load_prompts(resolved)
    template = prompts[PROMPT_KEY]
    version = prompts.get(f"{PROMPT_KEY}_version", "unversioned")
    return template.format(intents=", ".join(sorted(intent_vocabulary()))), version


async def classify_intent_llm(
    message: str,
    *,
    language: str,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> UnderstandingOutcome:
    """Classify one free-text turn with the profile LLM; never raise into the caller.

    The backend is the existing router seam (Vertex on the frontier profile,
    Ollama on-prem — ADR 0053 §1: both deployment targets keep a live layer 1),
    the spend is cleared with the daily ceiling first, and every failure comes
    back as a named outcome so the caller can fall back deterministically and
    telemetry can count each kind.

    Args:
        message: The operator's free-text turn, unnormalized.
        language: The turn's language code (prompt selection only).
        timeout_s: Hard bound on the model call.

    Returns:
        A verdict outcome, or a failure outcome naming its kind.
    """
    started = time.perf_counter()
    system_prompt, prompt_version = _prompt_for(language)

    from tessera.llm.ceiling import DailyCeilingReachedError, resolve_spend_model

    try:
        model = await resolve_spend_model(caller=_CALLER)
    except DailyCeilingReachedError as exc:
        return UnderstandingOutcome(
            status="budget_ceiling",
            verdict=None,
            detail=str(exc),
            model="",
            prompt_version=prompt_version,
            latency_ms=(time.perf_counter() - started) * 1000.0,
        )

    from tessera.llm.router import ChatMessage, get_chat_backend

    backend = get_chat_backend()
    try:
        async with asyncio.timeout(timeout_s):
            response = await backend.chat(
                [
                    ChatMessage(role="system", content=system_prompt),
                    ChatMessage(role="user", content=message),
                ],
                temperature=0.0,
                max_output_tokens=200,
                model=model,
            )
    except TimeoutError:
        return UnderstandingOutcome(
            status="timeout",
            verdict=None,
            detail=f"no answer within {timeout_s:.1f}s",
            model=model,
            prompt_version=prompt_version,
            latency_ms=(time.perf_counter() - started) * 1000.0,
        )
    except Exception as exc:  # the classifier must never take a turn down with it
        return UnderstandingOutcome(
            status="llm_error",
            verdict=None,
            detail=f"{type(exc).__name__}: {exc}",
            model=model,
            prompt_version=prompt_version,
            latency_ms=(time.perf_counter() - started) * 1000.0,
        )
    latency_ms = (time.perf_counter() - started) * 1000.0

    try:
        parsed = _LlmIntentPayload.model_validate(
            json.loads(_extract_json_object(response.content))
        )
    except (ValueError, ValidationError) as exc:
        return UnderstandingOutcome(
            status="schema_invalid",
            verdict=None,
            detail=f"{type(exc).__name__}: {exc}",
            model=response.model,
            prompt_version=prompt_version,
            latency_ms=latency_ms,
        )
    if parsed.intent not in intent_vocabulary():
        return UnderstandingOutcome(
            status="schema_invalid",
            verdict=None,
            detail=f"intent {parsed.intent!r} is outside the manifest vocabulary",
            model=response.model,
            prompt_version=prompt_version,
            latency_ms=latency_ms,
        )
    return UnderstandingOutcome(
        status="verdict",
        verdict=UnderstandingVerdict(
            intent=parsed.intent,
            confidence=parsed.confidence,
            duration_months=parsed.duration_months,
            requested_time=parsed.requested_time,
        ),
        detail=None,
        model=response.model,
        prompt_version=prompt_version,
        latency_ms=latency_ms,
    )
