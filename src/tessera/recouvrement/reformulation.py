"""Layer-3 tone reformulation for Recouvrement — the approved template is the REFERENT.

ADR 0054: the LLM may rewrite TONE only. Everything factual or regulated in the
approved template — every number, amount label, spelled date, clock time, the
legal reserve and promise clauses, the signature, the client and case identity —
must survive **verbatim** in the candidate, and the proof is deterministic: this
module's checker, never a judge. Anything the checker cannot prove intact means
the exact template is sent instead (the unconditional fallback, ADR 0054 §2).

The tone-instruction vocabulary is CLOSED (§Costs: it needs a compliance pass,
so it must be enumerable). An instruction outside it — "make it funny", "be
casual" — is refused before any model is called; the bench carries adversarial
cases whose correct outcome is exactly that refusal.

The generation call mirrors layer 1 (:mod:`tessera.recouvrement.understanding`):
one bounded LLM call behind the profile/router seam, cleared with the ADR 0034
daily ceiling, every failure a NAMED outcome so the caller falls back to the
template and telemetry counts each kind separately. The fidelity JUDGE is a
second bounded call scoring template-fidelity in [0, 1]; its number lands in the
ledger but governs nothing until it is calibrated against the human-labeled
referent (ADR 0054 §4) and its threshold stored as a governed knob.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
import unicodedata
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from tessera.recouvrement.message_templates import (
    _ENGLISH_MONTHS,
    _FRENCH_MONTHS,
    _GERMAN_MONTHS,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
    "DEFAULT_TIMEOUT_S",
    "FIDELITY_JUDGE_PROMPT_KEY",
    "FORBIDDEN_CLIENT_MESSAGE_TERMS",
    "REFORMULATOR_PROMPT_KEY",
    "TONE_INSTRUCTIONS",
    "FidelityCheck",
    "FidelityJudgement",
    "ReformulationOutcome",
    "check_must_survive",
    "gate_tone_instruction",
    "judge_template_fidelity_llm",
    "normalize_client_text",
    "reformulate_tone_llm",
]

#: Provisional bound on each layer-3 model call. A letter is longer than an intent
#: verdict, so the bound is wider than layer 1's; it becomes a governed knob with
#: the mode/threshold pair, and it only ever runs off the send path.
DEFAULT_TIMEOUT_S = 20.0

#: Prompt bundle keys (``src/tessera/agent/prompts/{fr,de,en}.yaml``);
#: ``<KEY>_version`` names each prompt's version for telemetry.
REFORMULATOR_PROMPT_KEY = "recouvrement_tone_reformulator"
FIDELITY_JUDGE_PROMPT_KEY = "recouvrement_fidelity_judge"

_CALLER = "tessera.recouvrement.reformulation"

#: The CLOSED tone-instruction vocabulary (ADR 0054 §Costs: the vocabulary is a
#: compliance surface, so it is enumerable and versioned with the code). Every id
#: has a prompt-side label per language; anything else is refused at the gate.
TONE_INSTRUCTIONS: Final[tuple[str, ...]] = ("plus_empathique", "plus_formel", "plus_concis")

#: Terms an outbound client message may never contain, checked on normalized text.
#: ONE source for the drafting policy review (``review_client_message_policy``) and
#: the layer-3 checker — two copies would drift, and a reformulation must not lose
#: a single compliance check the template path enforces (ADR 0054 §2).
FORBIDDEN_CLIENT_MESSAGE_TERMS: Final[frozenset[str]] = frozenset(
    {
        "mise en demeure",
        "sanction",
        "resiliation",
        "frais d'incident",
        "pression",
        "immediatement obligatoire",
        "nous acceptons",
        "nous vous accordons",
        "echeancier accepte",
        "echeancier valide",
    }
)

#: Sentence markers whose sentence must survive VERBATIM: the schedule reserve
#: clause and the broken-promise clause are regulated wording, not tone.
_LEGAL_SENTENCE_MARKERS: Final[dict[str, tuple[str, ...]]] = {
    "fr": ("sous réserve", "promesse de paiement"),
    "en": ("subject to", "payment commitment"),
    "de": ("vorbehaltlich", "zahlungszusage"),
}

#: The signing entity — a letter that loses its issuer is not the bank's letter.
_SIGNATURE: Final = "Crédit Aurore"

_MONTHS_BY_LANGUAGE: Final[dict[str, tuple[str, ...]]] = {
    "fr": _FRENCH_MONTHS,
    "en": _ENGLISH_MONTHS,
    "de": _GERMAN_MONTHS,
}

#: Whitespace canon: NBSP / narrow-NBSP / runs collapse to one space, so a survival
#: comparison never fails on the difference between a grouped amount's thin space
#: and a model's plain one — while every visible character stays significant.
_WS = re.compile(r"[\u00a0\u202f\s]+")

_DIGIT_RUN = re.compile(r"\d+")
_AMOUNT = re.compile(r"\d[\d\u00a0\u202f ,.]*€")
_CLOCK_TIME = re.compile(r"\b([01]?\d|2[0-3]):[0-5]\d\b")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def normalize_client_text(text: str) -> str:
    """Lowercase, accent-stripped canon for term checks (the drafting policy's canon)."""
    return "".join(
        char
        for char in unicodedata.normalize("NFD", text.lower())
        if unicodedata.category(char) != "Mn"
    )


def gate_tone_instruction(instruction: str) -> str | None:
    """The canonical instruction id, or ``None`` — the deterministic refusal gate.

    Args:
        instruction: The requested tone instruction, free text.

    Returns:
        The id from :data:`TONE_INSTRUCTIONS` it exactly names (whitespace-trimmed,
        case-insensitive), or ``None`` for anything else — including every
        adversarial instruction the bench carries. ``None`` means: no model call,
        the approved template is the answer.
    """
    canonical = instruction.strip().lower().replace(" ", "_")
    return canonical if canonical in TONE_INSTRUCTIONS else None


@dataclass(frozen=True, slots=True)
class FidelityCheck:
    """The deterministic verdict on one candidate: intact, or failures NAMED.

    ``ok`` is ``True`` only when every must-survive invariant was proven present;
    ``failures`` is the closed-ish vocabulary of what was not — each entry a
    ``kind:detail`` string, so telemetry can count kinds without parsing prose.
    """

    ok: bool
    failures: tuple[str, ...]


def _canon(text: str) -> str:
    return _WS.sub(" ", text).strip()


def _digit_runs(text: str) -> Counter[str]:
    return Counter(_DIGIT_RUN.findall(text))


def _date_pattern(language: str) -> re.Pattern[str]:
    months = "|".join(re.escape(m) for m in _MONTHS_BY_LANGUAGE[language])
    if language == "en":
        return re.compile(rf"\b(?:{months})\s+\d{{1,2}}\b")
    if language == "de":
        return re.compile(rf"\b\d{{1,2}}\.\s*(?:{months})\b")
    return re.compile(rf"\b(?:1er|\d{{1,2}})\s+(?:{months})\b")


def _legal_sentences(text: str, language: str) -> list[str]:
    markers = _LEGAL_SENTENCE_MARKERS.get(language, ())
    sentences = _SENTENCE_SPLIT.split(_canon(text))
    return [s for s in sentences if any(marker in s.lower() for marker in markers)]


def check_must_survive(
    template_text: str,
    candidate_text: str,
    *,
    language: str,
    context: Mapping[str, str] | None = None,
) -> FidelityCheck:
    """Prove every regulated fact of the template survives verbatim in the candidate.

    Deterministic on purpose (ADR 0054 §1): a judge scores tone, this proves facts.
    The rules err strict — a faithful-but-reworded amount fails, and failing sends
    the exact template, which is always safe.

    * every digit run of the template appears at least as often in the candidate,
      and the candidate introduces none of its own (no invented figures);
    * every amount label (``1 260,50 €``) survives verbatim, thin spaces canonicalised;
    * every spelled date and every clock time survives verbatim;
    * every legal sentence (reserve clause, broken-promise clause) survives verbatim;
    * the signature and every provided ``context`` identity field survive;
    * no forbidden client-message term appears (the drafting policy's own list).

    Args:
        template_text: The RENDERED approved template — the referent.
        candidate_text: The reformulation to prove.
        language: The letter's language (``fr`` / ``en`` / ``de``).
        context: Optional identity fields (``client``, ``case_id``,
            ``amount_due_label``) that must survive verbatim.

    Returns:
        The verdict, with every failure named.
    """
    template_canon = _canon(template_text)
    candidate_canon = _canon(candidate_text)
    if not candidate_canon:
        return FidelityCheck(ok=False, failures=("empty_candidate:",))
    failures = [
        *_figure_failures(template_canon, candidate_canon, language),
        *_wording_failures(template_text, candidate_canon, language, context),
        *(
            f"forbidden_term:{term}"
            for term in sorted(FORBIDDEN_CLIENT_MESSAGE_TERMS)
            if term in normalize_client_text(candidate_text)
        ),
    ]
    return FidelityCheck(ok=not failures, failures=tuple(failures))


def _figure_failures(template_canon: str, candidate_canon: str, language: str) -> list[str]:
    """Every numeric fact — digit runs, amount labels, spelled dates, clock times."""
    failures: list[str] = []
    template_runs = _digit_runs(template_canon)
    candidate_runs = _digit_runs(candidate_canon)
    for run, count in sorted(template_runs.items()):
        if candidate_runs[run] < count:
            failures.append(f"number_missing:{run}")
    failures.extend(
        f"number_invented:{run}" for run in sorted(candidate_runs.keys() - template_runs.keys())
    )
    failures.extend(
        f"amount_missing:{_canon(label)}"
        for label in _AMOUNT.findall(template_canon)
        if _canon(label) not in candidate_canon
    )
    failures.extend(
        f"date_missing:{spelled}"
        for spelled in _date_pattern(language).findall(template_canon)
        if spelled not in candidate_canon
    )
    failures.extend(
        f"time_missing:{match.group(0)}"
        for match in _CLOCK_TIME.finditer(template_canon)
        if match.group(0) not in candidate_canon
    )
    return failures


def _wording_failures(
    template_text: str,
    candidate_canon: str,
    language: str,
    context: Mapping[str, str] | None,
) -> list[str]:
    """The regulated wording — legal sentences, the signature, the identity fields."""
    failures = [
        f"clause_missing:{sentence[:60]}"
        for sentence in _legal_sentences(template_text, language)
        if sentence not in candidate_canon
    ]
    if _SIGNATURE in _canon(template_text) and _SIGNATURE not in candidate_canon:
        failures.append("signature_missing:")
    for key in ("client", "case_id", "amount_due_label"):
        value = (context or {}).get(key)
        if value and _canon(value) not in candidate_canon:
            failures.append(f"context_missing:{key}")
    return failures


# ── The two LLM calls (generation + fidelity judge), layer-1 shaped ──────────────


class _LlmLetterPayload(BaseModel):
    """The exact JSON shape the reformulator must produce — anything else is refused."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)


class _LlmFidelityPayload(BaseModel):
    """The exact JSON shape the fidelity judge must produce."""

    model_config = ConfigDict(extra="forbid")

    fidelity: float = Field(ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list, max_length=10)


@dataclass(frozen=True, slots=True)
class ReformulationOutcome:
    """One reformulation attempt: a candidate letter, or a failure naming its kind.

    ``instruction_refused`` never reached a model — the closed-vocabulary gate
    answered. Every other non-``candidate`` status mirrors layer 1's vocabulary,
    because each kind is handled and counted differently.
    """

    status: Literal[
        "candidate",
        "instruction_refused",
        "schema_invalid",
        "timeout",
        "llm_error",
        "budget_ceiling",
    ]
    text: str | None
    detail: str | None
    model: str
    prompt_version: str
    latency_ms: float


@dataclass(frozen=True, slots=True)
class FidelityJudgement:
    """The judge's graded fidelity score, or a failure naming its kind.

    The score is telemetry until calibrated (ADR 0054 §4): it lands in the ledger
    beside the deterministic check, and no threshold governs anything before the
    human-labeled referent exists and the knob stores a calibrated number.
    """

    status: Literal["scored", "schema_invalid", "timeout", "llm_error", "budget_ceiling"]
    fidelity: float | None
    reasons: tuple[str, ...]
    detail: str | None
    model: str
    prompt_version: str
    latency_ms: float


def _extract_json_object(text: str) -> str:
    """Cut the first ``{`` … last ``}`` span — models love to wrap JSON in prose."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return text
    return text[start : end + 1]


def _prompt_for(key: str, language: str) -> tuple[str, str]:
    """Resolve a layer-3 prompt and its version for ``language`` (fallback: default)."""
    from tessera.agent.reporter import load_prompts
    from tessera.settings import LanguageCode, get_settings

    try:
        resolved = LanguageCode(language)
    except ValueError:
        resolved = get_settings().default_language
    prompts = load_prompts(resolved)
    return prompts[key], prompts.get(f"{key}_version", "unversioned")


async def _cleared_model(model: str | None) -> tuple[str, None] | tuple[None, str]:
    """Clear the spend with the daily ceiling; ``(model, None)`` or ``(None, detail)``."""
    from tessera.llm.ceiling import DailyCeilingReachedError, resolve_spend_model

    try:
        return await resolve_spend_model(caller=_CALLER, model=model), None
    except DailyCeilingReachedError as exc:
        return None, str(exc)


async def _bounded_chat(
    *,
    system_prompt: str,
    user_content: str,
    model: str,
    timeout_s: float,
    max_output_tokens: int,
) -> tuple[str, str]:
    """One bounded model call via the router seam; returns ``(content, served_model)``."""
    from tessera.llm.router import ChatMessage, backend_for_model

    backend = backend_for_model(model)
    async with asyncio.timeout(timeout_s):
        response = await backend.chat(
            [
                ChatMessage(role="system", content=system_prompt),
                ChatMessage(role="user", content=user_content),
            ],
            temperature=0.0,
            max_output_tokens=max_output_tokens,
            model=model,
        )
    return response.content, response.model


async def reformulate_tone_llm(
    template_text: str,
    *,
    tone_instruction: str,
    language: str,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    model: str | None = None,
) -> ReformulationOutcome:
    """Draft a tone-rewritten candidate of the approved letter; never raise into the caller.

    The instruction passes the closed-vocabulary gate FIRST — a refused instruction
    costs no tokens and is its own named outcome. The candidate is only ever a
    CANDIDATE: the caller must run :func:`check_must_survive` and fall back to the
    exact template on any doubt (ADR 0054 §2).

    Args:
        template_text: The rendered approved template (the referent).
        tone_instruction: A tone id from :data:`TONE_INSTRUCTIONS` (anything else
            is refused at the gate).
        language: The letter's language, for prompt selection.
        timeout_s: Hard bound on the model call.
        model: Optional model override (the governed model knob / bench column);
            ``None`` serves the profile base.

    Returns:
        A candidate outcome, or a failure outcome naming its kind.
    """
    started = time.perf_counter()
    gated = gate_tone_instruction(tone_instruction)
    system_prompt, prompt_version = _prompt_for(REFORMULATOR_PROMPT_KEY, language)
    if gated is None:
        return ReformulationOutcome(
            status="instruction_refused",
            text=None,
            detail=f"tone instruction {tone_instruction!r} is outside the closed vocabulary",
            model="",
            prompt_version=prompt_version,
            latency_ms=(time.perf_counter() - started) * 1000.0,
        )
    cleared, ceiling_detail = await _cleared_model(model)
    if cleared is None:
        return ReformulationOutcome(
            status="budget_ceiling",
            text=None,
            detail=ceiling_detail,
            model="",
            prompt_version=prompt_version,
            latency_ms=(time.perf_counter() - started) * 1000.0,
        )
    user_content = f"Instruction de ton : {gated}\n\nLettre approuvée :\n{template_text}"
    try:
        content, served_model = await _bounded_chat(
            system_prompt=system_prompt,
            user_content=user_content,
            model=cleared,
            timeout_s=timeout_s,
            max_output_tokens=900,
        )
    except TimeoutError:
        return ReformulationOutcome(
            status="timeout",
            text=None,
            detail=f"no answer within {timeout_s:.1f}s",
            model=cleared,
            prompt_version=prompt_version,
            latency_ms=(time.perf_counter() - started) * 1000.0,
        )
    except Exception as exc:  # the shadow must never take a turn down with it
        return ReformulationOutcome(
            status="llm_error",
            text=None,
            detail=f"{type(exc).__name__}: {exc}",
            model=cleared,
            prompt_version=prompt_version,
            latency_ms=(time.perf_counter() - started) * 1000.0,
        )
    latency_ms = (time.perf_counter() - started) * 1000.0
    try:
        parsed = _LlmLetterPayload.model_validate(json.loads(_extract_json_object(content)))
    except (ValueError, ValidationError) as exc:
        return ReformulationOutcome(
            status="schema_invalid",
            text=None,
            detail=f"{type(exc).__name__}: {exc}",
            model=served_model,
            prompt_version=prompt_version,
            latency_ms=latency_ms,
        )
    return ReformulationOutcome(
        status="candidate",
        text=parsed.text,
        detail=None,
        model=served_model,
        prompt_version=prompt_version,
        latency_ms=latency_ms,
    )


async def judge_template_fidelity_llm(
    template_text: str,
    candidate_text: str,
    *,
    language: str,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    model: str | None = None,
) -> FidelityJudgement:
    """Score the candidate's fidelity to the approved template in [0, 1].

    The template IS the referent (ADR 0054 §1) — for the first time a fidelity
    judgement on this agent means something. The score is recorded, not obeyed:
    until the judge is calibrated against the human-labeled referent, nothing
    reads it as a decision (§4).

    Args:
        template_text: The rendered approved template.
        candidate_text: The reformulated candidate.
        language: The letter's language, for prompt selection.
        timeout_s: Hard bound on the model call.
        model: Optional model override; ``None`` serves the profile base.

    Returns:
        A scored judgement, or a failure naming its kind.
    """
    started = time.perf_counter()
    system_prompt, prompt_version = _prompt_for(FIDELITY_JUDGE_PROMPT_KEY, language)
    cleared, ceiling_detail = await _cleared_model(model)
    if cleared is None:
        return FidelityJudgement(
            status="budget_ceiling",
            fidelity=None,
            reasons=(),
            detail=ceiling_detail,
            model="",
            prompt_version=prompt_version,
            latency_ms=(time.perf_counter() - started) * 1000.0,
        )
    user_content = f"Lettre approuvée :\n{template_text}\n\nReformulation :\n{candidate_text}"
    try:
        content, served_model = await _bounded_chat(
            system_prompt=system_prompt,
            user_content=user_content,
            model=cleared,
            timeout_s=timeout_s,
            max_output_tokens=300,
        )
    except TimeoutError:
        return FidelityJudgement(
            status="timeout",
            fidelity=None,
            reasons=(),
            detail=f"no answer within {timeout_s:.1f}s",
            model=cleared,
            prompt_version=prompt_version,
            latency_ms=(time.perf_counter() - started) * 1000.0,
        )
    except Exception as exc:  # the judge must never take a turn down with it
        return FidelityJudgement(
            status="llm_error",
            fidelity=None,
            reasons=(),
            detail=f"{type(exc).__name__}: {exc}",
            model=cleared,
            prompt_version=prompt_version,
            latency_ms=(time.perf_counter() - started) * 1000.0,
        )
    latency_ms = (time.perf_counter() - started) * 1000.0
    try:
        parsed = _LlmFidelityPayload.model_validate(json.loads(_extract_json_object(content)))
    except (ValueError, ValidationError) as exc:
        return FidelityJudgement(
            status="schema_invalid",
            fidelity=None,
            reasons=(),
            detail=f"{type(exc).__name__}: {exc}",
            model=served_model,
            prompt_version=prompt_version,
            latency_ms=latency_ms,
        )
    return FidelityJudgement(
        status="scored",
        fidelity=parsed.fidelity,
        reasons=tuple(parsed.reasons),
        detail=None,
        model=served_model,
        prompt_version=prompt_version,
        latency_ms=latency_ms,
    )
