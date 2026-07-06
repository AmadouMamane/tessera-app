"""Output-side PII redaction — the response leg of the runtime guard.

:func:`tessera.guard.adapter.check_user_input` guards what *enters* the agent;
this module guards what *leaves* it. The same ``pii.redact_patterns`` declared
in ``policy.yaml`` are applied to the final response — and, on the API path, to
the SSE token stream — before the text is returned, persisted or evaluated
(harness cases 02 and 45). The reviewer/reporter boundary is where it runs:
:func:`tessera.agent.reporter.run` calls :func:`apply_output_guard`, and the
chat route wraps its token stream in a :class:`StreamingRedactor`.

Masking is type-aware and deliberately recognisable (the ``XXXX`` token), so a
customer still sees *which* datum was acknowledged and the harness can assert
the mask:

* card PAN → ``XXXX XXXX XXXX 6467`` (last four kept — PCI-DSS display rule);
* IBAN → ``FRXX XXXX 0123`` (country + last four, never the check digits);
* e-mail → ``XXXX@XXXX`` (no domain: a masked address must never satisfy an
  address-shaped matcher, nor name a destination);
* phone → ``XXXX 78`` (last two kept).

The policy's broad IBAN shape can graze prose (any ``LLdd`` token followed by
alphanumerics and spaces). A hit that classifies as none of the known kinds is
masked outright only when digit-heavy (data-shaped, e.g. a lowercase IBAN) and
left untouched otherwise, so ordinary sentences never get mangled.

This module also hosts the **input leg**'s single primitive, :func:`mask_pan`
(docs/design/pii-input-redaction.md): Luhn-gated, IBAN-context-aware masking of
card numbers in user-originated text before it reaches the model context or the
durable stores. Same mask form, much stricter gating — it rewrites what the
user said, so false positives are the failure mode it is built against.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from tessera.guard.audit import emit_audit, guard_disabled
from tessera.guard.decisions import DecisionKind, Policy, load_policy
from tessera.observability.metrics import GUARD_DECISIONS_TOTAL
from tessera.settings import LanguageCode, get_settings

if TYPE_CHECKING:
    # Imported lazily at runtime (guard <-> agent import cycle, as in adapter).
    from tessera.agent.state import GuardDecisionRecord

__all__ = [
    "RedactedText",
    "StreamingRedactor",
    "apply_output_guard",
    "contains_pii",
    "emit_output_redaction",
    "mask_pan",
    "redact_text",
    "redaction_notice",
]

_MASK: Final = "XXXX"
# Below this many digits, an unclassified hit is a prose graze, not data.
_GENERIC_MIN_DIGITS: Final = 8
_PAN_DIGITS: Final = (13, 19)
_PHONE_DIGITS: Final = (9, 13)
_IBAN_COMPACT: Final = re.compile(r"^[A-Z]{2}[0-9]{2}[A-Z0-9]{10,30}$")
_SEPARATORS: Final = re.compile(r"[ \u00a0./-]")
_NON_DIGIT: Final = re.compile(r"\D")

# User-facing notice appended when a response was redacted or the user's input
# carried PII. Safety strings live in code, not the prompt YAML, for the same
# reason as router._INJECTION_BLOCKED_RESPONSES: they must hold with the guard
# alone, independent of any prompt bundle. The wording carries the harness
# tokens (masqué / maskiert / masked).
_NOTICE: Final[dict[LanguageCode, str]] = {
    LanguageCode.FR: (
        "Par mesure de sécurité, les données sensibles (numéro de carte, IBAN, "
        "e-mail, téléphone) sont masquées dans mes réponses."
    ),
    LanguageCode.DE: (
        "Aus Sicherheitsgründen werden sensible Daten (Kartennummer, IBAN, "
        "E-Mail, Telefon) in meinen Antworten maskiert."
    ),
    LanguageCode.EN: (
        "For security, sensitive details (card number, IBAN, e-mail, phone) "
        "are masked in my replies."
    ),
}


@dataclass(frozen=True, slots=True)
class RedactedText:
    """The outcome of one redaction pass over a piece of text."""

    text: str
    redactions: tuple[str, ...]

    @property
    def changed(self) -> bool:
        """Whether at least one segment was masked."""
        return bool(self.redactions)


def _mask_for(matched: str) -> tuple[str, str] | None:
    """Classify one pattern hit; return ``(kind, replacement)`` or ``None``.

    ``None`` means the hit is a prose false positive of the broad IBAN shape
    (too few digits, no address form) and must stay untouched.
    """
    if "@" in matched:
        return "email", f"{_MASK}@{_MASK}"
    compact = _SEPARATORS.sub("", matched)
    if _IBAN_COMPACT.fullmatch(compact):
        return "iban", f"{compact[:2]}XX {_MASK} {compact[-4:]}"
    digits = _NON_DIGIT.sub("", matched)
    if compact.removeprefix("+").isdigit():
        phone_min, phone_max = _PHONE_DIGITS
        if matched.lstrip().startswith(("+", "0")) and phone_min <= len(digits) <= phone_max:
            return "phone", f"{_MASK} {digits[-2:]}"
        pan_min, pan_max = _PAN_DIGITS
        if pan_min <= len(digits) <= pan_max:
            return "pan", f"{_MASK} {_MASK} {_MASK} {digits[-4:]}"
    if len(digits) >= _GENERIC_MIN_DIGITS:
        return "pii", _MASK
    return None


def redact_text(text: str, *, policy: Policy | None = None) -> RedactedText:
    """Apply the policy's ``pii.redact_patterns`` to ``text``, type-aware.

    Patterns run in policy order (e-mail, IBAN, PAN, phones); a replacement
    never re-matches a later pattern, so the function is idempotent. The
    redaction labels carry only the masked forms, never the original values.
    """
    active_policy = policy or load_policy()
    redactions: list[str] = []

    def _sub(match: re.Match[str]) -> str:
        raw = match.group(0)
        hit = _mask_for(raw.strip())
        if hit is None:
            return raw
        kind, replacement = hit
        redactions.append(f"{kind}={replacement}")
        # The greedy IBAN body may swallow surrounding spaces — keep them.
        lead = raw[: len(raw) - len(raw.lstrip())]
        trail = raw[len(raw.rstrip()) :]
        return f"{lead}{replacement}{trail}"

    out = text
    for pattern in active_policy.pii_patterns:
        out = pattern.sub(_sub, out)
    return RedactedText(text=out, redactions=tuple(redactions))


def contains_pii(text: str, *, policy: Policy | None = None) -> bool:
    """True when ``text`` carries at least one maskable PII segment."""
    active_policy = policy or load_policy()
    return any(
        _mask_for(match.group(0).strip()) is not None
        for pattern in active_policy.pii_patterns
        for match in pattern.finditer(text)
    )


# ---------------------------------------------------------------------------
# Input-side PAN masking (docs/design/pii-input-redaction.md, Option A)
# ---------------------------------------------------------------------------

# A card-shaped digit run: 13-19 digits with at most one space / NBSP / dot /
# dash between digits. The lookarounds keep it off longer alphanumeric runs (a
# 20+ digit sequence is never a PAN), off '+'-prefixed international phone
# numbers, and off decimal amounts (a ",45" / ".45" tail marks money).
_PAN_INPUT_CANDIDATE: Final = re.compile(
    r"(?<![A-Za-z0-9+])\d(?:[ \u00a0.-]?\d){12,18}(?![A-Za-z0-9]|[.,]\d)"
)
# The immediate left context that marks a digit run as an IBAN *body*: the
# 2-letter country + 2 check digits head (FR76 ...), optionally followed by a
# 4-letter bank code (GB29 NWBK ...). Broad on purpose: corrupting any IBAN is
# worse than leaving a PAN clear next to an IBAN-shaped token (declared
# residual, design note §4).
_IBAN_HEAD_BEFORE: Final = re.compile(
    r"(?:^|[^A-Za-z0-9])[A-Za-z]{2}\d{2}[ \u00a0.-]*(?:[A-Za-z]{4}[ \u00a0.-]*)?$"
)
# How far back an IBAN head can sit from its body run (head + bank code + separators).
_IBAN_HEAD_WINDOW: Final = 16
# First group separator inside a declined candidate — the retry point, so a
# leading date / list number merged into the run cannot shadow a real PAN.
_PAN_GROUP_BREAK: Final = re.compile(r"[ \u00a0.-]+")


# Luhn: a doubled digit above nine folds back to a single digit (16 → 7).
_LUHN_FOLD: Final = 9


def _luhn_valid(digits: str) -> bool:
    """ISO/IEC 7812 Luhn checksum over a digit-only string."""
    total = 0
    for index, char in enumerate(reversed(digits)):
        digit = int(char)
        if index % 2 == 1:
            digit *= 2
            if digit > _LUHN_FOLD:
                digit -= _LUHN_FOLD
        total += digit
    return total % 10 == 0


def _iban_context(text: str, start: int) -> bool:
    """True when the digit run at ``start`` reads as the body of an IBAN."""
    window_start = max(0, start - _IBAN_HEAD_WINDOW)
    return _IBAN_HEAD_BEFORE.search(text, window_start, start) is not None


def mask_pan(text: str) -> RedactedText:
    """Mask Luhn-valid card numbers in *input-side* text, keeping the last four.

    The input leg of the PII guard (docs/design/pii-input-redaction.md): unlike
    :func:`redact_text` — the output leg, policy-pattern driven and deliberately
    broad — this primitive rewrites what the *user* said, so it is gated hard
    against false positives:

    * only 13-19 digit runs (single space/NBSP/dot/dash separators) qualify;
    * the run must pass the Luhn checksum, which kills ~90 % of coincidental
      digit runs (order/ticket references, long account numbers);
    * a run in IBAN context (an ``FR76``-style head, optional 4-letter bank
      code, immediately before it) is never touched — IBANs are operationally
      needed and out of PCI display scope on the input side;
    * ``+``-prefixed and leading-zero runs are phone numbers or padded
      references, never PANs (no card IIN starts with 0).

    A declined candidate is re-scanned from its next digit group, so a date or
    list number merged into the run cannot shadow a real PAN behind it. The
    masked form is the output leg's PAN form (``XXXX XXXX XXXX 6467``), which
    carries no 13-19 digit run — the function is idempotent by construction
    (asserted in the unit suite). A Luhn-INVALID card-shaped run (customer
    typo) is deliberately NOT masked: declared residual, design note §4.

    This is the single primitive every input-leg seam calls (context assembly,
    transcript/memory persistence backstops, entity-ledger screening, online
    eval); no seam re-implements detection.
    """
    if not text or not any(char.isdigit() for char in text):
        return RedactedText(text=text, redactions=())
    parts: list[str] = []
    redactions: list[str] = []
    pos = 0
    while True:
        match = _PAN_INPUT_CANDIDATE.search(text, pos)
        if match is None:
            parts.append(text[pos:])
            break
        start, end = match.span()
        raw = match.group(0)
        if _iban_context(text, start):
            # Never rewrite inside an IBAN — skip the whole body run.
            parts.append(text[pos:end])
            pos = end
            continue
        digits = _NON_DIGIT.sub("", raw)
        if digits.startswith("0") or not _luhn_valid(digits):
            # Not a PAN — retry from the candidate's next digit group.
            group_break = _PAN_GROUP_BREAK.search(raw)
            retry_at = start + group_break.end() if group_break else end
            parts.append(text[pos:retry_at])
            pos = retry_at
            continue
        replacement = f"{_MASK} {_MASK} {_MASK} {digits[-4:]}"
        redactions.append(f"pan={replacement}")
        parts.append(text[pos:start])
        parts.append(replacement)
        pos = end
    return RedactedText(text="".join(parts), redactions=tuple(redactions))


def redaction_notice(language: LanguageCode) -> str:
    """The localized one-line masking notice for ``language``."""
    return _NOTICE[language]


def emit_output_redaction(redactions: tuple[str, ...]) -> GuardDecisionRecord:
    """Record a ``redact_output`` guard decision (audit ledger + metric).

    Feeds the same surfaces as every guard decision: the turn's
    ``guard_decisions`` (the returned record), the hash-chained audit trail,
    and ``GUARD_DECISIONS_TOTAL``.
    """
    from tessera.agent.identity import resolve_agent_id
    from tessera.agent.state import GuardDecisionRecord

    record = GuardDecisionRecord(
        target="final_response",
        decision=DecisionKind.TRANSFORM.value,
        policy_rule="pii.redact_patterns",
        rationale=(f"redact_output: masked {len(redactions)} PII segment(s) in the final response"),
        redactions=redactions,
    )
    emit_audit(
        target="final_response",
        arguments={"redactions": ", ".join(redactions)},
        decisions=[record],
        sink=get_settings().guard.audit_sink,
        outcome="allowed",
    )
    GUARD_DECISIONS_TOTAL.labels(
        target="final_response",
        decision="transformed",
        agent_id=resolve_agent_id() or "none",
    ).inc()
    return record


def apply_output_guard(
    text: str,
    *,
    language: LanguageCode,
    user_input: str = "",
    disabled: bool = False,
    policy: Policy | None = None,
) -> tuple[str, GuardDecisionRecord | None]:
    """Run the output guard over a candidate final response.

    Masks PII (:func:`redact_text`), appends the localized masking notice when
    the response was redacted *or* the user's input carried PII (the customer
    is told the datum is deliberately masked whatever the model's phrasing),
    and emits the ``redact_output`` decision when something was masked.

    Args:
        text: the candidate final response.
        language: response language; selects the notice wording.
        user_input: the turn's raw user message; triggers the notice when it
            carries PII even if the model avoided echoing it.
        disabled: the sandbox ``pii`` guard override for this turn.
        policy: optional pre-loaded policy (tests).

    Returns:
        ``(safe_text, decision)`` — the decision is ``None`` when nothing was
        masked (the notice alone does not create one).
    """
    if disabled or "pii" in guard_disabled.get():
        return text, None
    redacted = redact_text(text, policy=policy)
    record = emit_output_redaction(redacted.redactions) if redacted.changed else None
    out = redacted.text
    notice = redaction_notice(language)
    input_pii = bool(user_input) and contains_pii(user_input, policy=policy)
    if (redacted.changed or input_pii) and notice not in out:
        out = f"{out.rstrip()}\n\n{notice}"
    return out, record


# ---------------------------------------------------------------------------
# Streaming
# ---------------------------------------------------------------------------

_TAIL_WINDOW: Final = 120
_MIN_HOLD: Final = 1
# Anything the *suffix* of an unfinished PII match can look like. Held back
# until it either completes (and is masked inside one emitted segment) or
# turns out to be prose (a following space/punctuation releases it). The
# word-shaped alternative doubles as an e-mail local part, so streaming is
# effectively word-granular.
_TAIL_HOLD: Final = re.compile(
    r"(?:"
    r"[A-Za-z0-9._%+-]+(?:@[A-Za-z0-9.-]*)?"  # e-mail in progress / trailing word
    r"|[A-Z]{2}[0-9]{2}[A-Z0-9 ]{0,30}"  # IBAN head + partial body
    r"|(?:\+?[0-9][ ./-]?){1,40}"  # digit-group run (PAN / phone / IBAN tail)
    r")$"
)


class StreamingRedactor:
    """Incremental :func:`redact_text` over an SSE token stream.

    Text is emitted only once its tail can no longer be the prefix of an
    unfinished PII match (``_TAIL_HOLD``), so a card number can never leak in
    an early chunk and be "fixed" after the fact. Every emitted segment goes
    through :func:`redact_text`; :meth:`flush` drains the remainder at stream
    end.

    Known limit: an unbroken token run longer than ``_TAIL_WINDOW`` (no
    realistic PII is) may be cut mid-run, and a *lowercase* IBAN can mask
    partially. The batch guard on the persisted text applies the same policy
    either way.
    """

    def __init__(self, *, policy: Policy | None = None) -> None:
        self._policy = policy
        self._raw = ""
        self._start = 0
        self._parts: list[str] = []
        self._redactions: list[str] = []

    @property
    def text(self) -> str:
        """The redacted output emitted so far (all segments joined)."""
        return "".join(self._parts)

    @property
    def redactions(self) -> tuple[str, ...]:
        """Labels of every mask applied so far (masked forms only)."""
        return tuple(self._redactions)

    def feed(self, chunk: str) -> str:
        """Absorb ``chunk``; return whatever became safe to emit (maybe '')."""
        self._raw += chunk
        limit = len(self._raw) - _MIN_HOLD
        if limit <= self._start:
            return ""
        search_from = max(self._start, len(self._raw) - _TAIL_WINDOW)
        tail = _TAIL_HOLD.search(self._raw, search_from)
        cut = min(limit, tail.start()) if tail else limit
        if cut <= self._start:
            return ""
        return self._emit(cut)

    def flush(self) -> str:
        """Drain and redact everything still held back."""
        if self._start >= len(self._raw):
            return ""
        return self._emit(len(self._raw))

    def _emit(self, cut: int) -> str:
        segment = redact_text(self._raw[self._start : cut], policy=self._policy)
        self._start = cut
        self._parts.append(segment.text)
        self._redactions.extend(segment.redactions)
        return segment.text
