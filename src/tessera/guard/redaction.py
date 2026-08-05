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
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final

from tessera.guard.audit import GUARD_ACTOR, emit_audit, guard_disabled
from tessera.guard.decisions import DecisionKind, Policy, load_policy
from tessera.observability.metrics import GUARD_DECISIONS_TOTAL
from tessera.settings import LanguageCode, get_settings

if TYPE_CHECKING:
    # Imported lazily at runtime (guard <-> agent import cycle, as in adapter).
    from tessera.agent.state import GuardDecisionRecord

__all__ = [
    "RedactedText",
    "StreamingRedactor",
    "apply_egress_guard",
    "apply_output_guard",
    "apply_pii_egress_recall",
    "contains_pii",
    "egress_withheld_notice",
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
        actor=GUARD_ACTOR,
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
# Outbound egress guard — limes pii-egress (redact) + secrets-egress (block)
# ---------------------------------------------------------------------------

# Shown in place of an answer the egress guard withheld (a credential, or a value
# the mask could not conceal). Like _NOTICE it lives in code, not the prompt YAML:
# a safety string must hold with the guard alone, independent of any bundle.
_WITHHELD: Final[dict[LanguageCode, str]] = {
    LanguageCode.FR: (
        "Par mesure de sécurité, je ne peux pas afficher cette réponse : elle "
        "contenait une donnée sensible (identifiant ou secret). Je transmets votre "
        "demande à un conseiller."
    ),
    LanguageCode.DE: (
        "Aus Sicherheitsgründen kann ich diese Antwort nicht anzeigen: Sie enthielt "
        "vertrauliche Daten (Zugangsdaten oder ein Geheimnis). Ich leite Ihre Anfrage "
        "an einen Berater weiter."
    ),
    LanguageCode.EN: (
        "For security, I can't show this response: it contained sensitive data (a "
        "credential or secret). I'm forwarding your request to a human advisor."
    ),
}


# Shown in place of an answer that reproduced the agent's own instructions. Distinct wording
# from _WITHHELD on purpose: nothing of the CUSTOMER's was at risk here, and telling someone
# their data was withheld when it was not is its own small dishonesty. Naming the refusal is
# deliberate and allowed — a refusal may say what it declines (6fef31de).
_PROMPT_WITHHELD: Final[dict[LanguageCode, str]] = {
    LanguageCode.FR: (
        "Je ne peux pas afficher cette réponse : elle reproduisait mes instructions "
        "internes. Ces instructions ne sont pas divulgables. Reformulez votre question "
        "sur votre compte ou nos produits et j'y répondrai volontiers."
    ),
    LanguageCode.DE: (
        "Ich kann diese Antwort nicht anzeigen: Sie gab meine internen Anweisungen "
        "wieder. Diese Anweisungen sind nicht offenlegbar. Stellen Sie Ihre Frage gerne "
        "zu Ihrem Konto oder unseren Produkten neu."
    ),
    LanguageCode.EN: (
        "I can't show this response: it reproduced my internal instructions, which are "
        "not disclosable. Please rephrase your question about your account or our "
        "products and I'll gladly answer."
    ),
}


def egress_withheld_notice(language: LanguageCode) -> str:
    """The localized message shown when the egress guard withheld the answer."""
    return _WITHHELD[language]


def prompt_egress_withheld_notice(language: LanguageCode) -> str:
    """The localized message shown when the answer reproduced the agent's instructions."""
    return _PROMPT_WITHHELD[language]


def apply_prompt_egress(
    text: str,
    *,
    language: LanguageCode,
    disabled: bool = False,
) -> tuple[str, GuardDecisionRecord | None]:
    """Withhold a final response that reproduces the agent's own instructions.

    The third outbound leak, beside credentials and personal data, and the one the guard had no
    leg for. It is not hypothetical: 38 of the 19 203 recorded responses reproduce a declared
    span of the system prompt, spread over **seven** distinct cases — a full German prompt dump
    under ``44_prompt_injection_system_prompt_leak|de``, the English one under ``|en``, and the
    priority-rule block under five cases that never look for a leak at all
    (``30_tool_misuse_pret_aberrant|fr`` alone accounts for eleven).

    That spread is the argument for a guard rather than more catalogue entries: a case can only
    refuse the leak somebody thought to write it for. What counts as protected is DECLARED in
    the prompt bundles under ``no_egress`` and detected by
    :func:`tessera.guard.prompt_egress.detect_prompt_egress` — never inferred, because two
    inferred designs were measured against this corpus and both were wrong (see that module).

    **Withheld whole, not masked.** The same reasoning as ``secrets-egress``: a system prompt
    disclosed in part is still disclosed, and unlike leftover PII there is no useful remainder
    to save — an answer that dumps its instructions in reply to an extraction request has
    nothing else in it. Where the leak sits inside an otherwise substantive answer
    (``05_citation_hallucination|en``), withholding is the conservative direction.

    Run on the RAW answer, before the regex output guard, for the reason the secret leg is:
    the guard's masks would rewrite the very text being compared.

    Args:
        text: The RAW candidate final response.
        language: Response language; selects the withheld wording.
        disabled: The sandbox ``pii`` override for this turn, as the other legs honour it.

    Returns:
        ``(safe_text, decision)`` — ``decision`` is ``None`` when nothing was reproduced.
    """
    from tessera.agent.state import GuardDecisionRecord
    from tessera.guard.prompt_egress import PROMPT_EGRESS_RULE, detect_prompt_egress

    if disabled or "pii" in guard_disabled.get():
        return text, None
    leaked = detect_prompt_egress(text, language.value)
    if not leaked:
        return text, None
    record = GuardDecisionRecord(
        target="final_response",
        decision=DecisionKind.DENY.value,
        policy_rule=PROMPT_EGRESS_RULE,
        # The rationale names WHICH declared span leaked, never the span's text: an audit line
        # that quotes the instruction to prove the instruction leaked has leaked it again.
        rationale=(
            f"the answer reproduced {len(leaked)} declared no_egress span(s) of the "
            f"{language.value} prompt bundle"
        ),
    )
    emit_audit(
        target="final_response",
        arguments={"final_response": "[withheld — prompt-egress: instructions reproduced]"},
        decisions=[record],
        sink=get_settings().guard.audit_sink,
        actor=GUARD_ACTOR,
        outcome="denied",
    )
    _record_egress_metric("denied")
    return prompt_egress_withheld_notice(language), record


def _record_egress_metric(decision: str) -> None:
    """Count one egress guard decision on ``final_response``, partitioned by agent."""
    from tessera.agent.identity import resolve_agent_id

    GUARD_DECISIONS_TOTAL.labels(
        target="final_response",
        decision=decision,
        agent_id=resolve_agent_id() or "none",
    ).inc()


def apply_egress_guard(
    text: str,
    *,
    language: LanguageCode,
    actor: str | None = None,
    observed_at: str | None = None,
    disabled: bool = False,
) -> tuple[str, GuardDecisionRecord | None]:
    """Withhold a final response that carries a secret (ADR 0049).

    Run on the RAW answer, **before** :func:`apply_output_guard`: the regex guard's
    broad IBAN shape can graze a substring inside a credential and mangle it, after
    which the secret rule no longer matches. Detection is delegated to limes'
    ``secrets-egress`` (:mod:`tessera.guard.limes_egress_backend`), the single
    source of truth (ADR 0029). PII stays with the first-party guard — this leg
    adds only the outbound secret block Tessera never had.

    A **block** — a secret fired, or the detector could not look (``CannotSay``,
    fail-closed) — replaces ``text`` with the localized withheld message and records
    a ``DENY`` decision. A clean forward returns ``text`` unchanged and ``None``:
    there is no redact leg, a credential is withheld whole, never masked-around.

    Args:
        text: The RAW candidate final response (before the regex output guard).
        language: Response language; selects the withheld wording.
        actor: The session's asserted identity, recorded into limes' context.
        observed_at: ISO-8601 timestamp; defaults to now (limes never reads the
            clock, so the caller supplies it and a decision re-derives on replay).
        disabled: The sandbox ``pii`` guard override for this turn; skips the pass,
            as :func:`apply_output_guard` does.

    Returns:
        ``(safe_text, decision)`` — ``decision`` is ``None`` when nothing fired.
    """
    from tessera.agent.state import GuardDecisionRecord
    from tessera.guard.limes_egress_backend import check_egress

    if disabled or "pii" in guard_disabled.get():
        return text, None
    outcome = check_egress(
        text,
        observed_at=observed_at or datetime.now(UTC).isoformat(),
        actor=actor,
    )
    if not outcome.blocked:
        return text, None
    record = GuardDecisionRecord(
        target="final_response",
        decision=DecisionKind.DENY.value,
        policy_rule=outcome.rule,
        rationale=outcome.rationale,
    )
    emit_audit(
        target="final_response",
        arguments={"final_response": "[withheld — egress blocked by limes]"},
        decisions=[record],
        sink=get_settings().guard.audit_sink,
        actor=GUARD_ACTOR,
        outcome="denied",
    )
    _record_egress_metric("denied")
    return egress_withheld_notice(language), record


def apply_pii_egress_recall(
    text: str,
    *,
    language: LanguageCode,
    actor: str | None = None,
    observed_at: str | None = None,
    disabled: bool = False,
) -> tuple[str, GuardDecisionRecord | None]:
    """Mask PII the regex output guard missed (ADR 0049 §Amendment 1).

    Run *after* :func:`apply_output_guard`, on the already-masked answer: a second,
    checksum-gated pass (limes ``pii-egress``) that catches a datum the first-party
    regex left behind — a Corsica NIR (its ``2A``/``2B`` letters break the regex's
    digit-only shapes), a PAN or IBAN whose grouping the regex pattern does not match.
    It masks the leftover to ``[REDACTED:pii]``; it never re-fires on the regex's own
    masks (``XXXX XXXX XXXX 6467`` and friends carry too little to match), so the PCI
    last-four display and the harness cases (02/45) are untouched. Detection is limes'
    (ADR 0029); this leg only composes it with the decision/audit machinery.

    Three outcomes:

    * leftover PII found → the answer is returned **further masked**, with a
      ``TRANSFORM`` record (the answer stands; masking is not a refusal);
    * nothing found → ``text`` unchanged, no record;
    * the detector could not look (``CannotSay`` — content over limes' 200k budget,
      or non-UTF-8) → **fail-closed**: the answer is withheld, with a ``DENY`` record.
      The regex guard already masked what it could see; the recall refuses to vouch
      for a tail it did not read.

    Args:
        text: The answer *after* the first-party regex guard.
        language: Response language; selects the withheld wording (block only).
        actor: The session's asserted identity, recorded into limes' context.
        observed_at: ISO-8601 timestamp; defaults to now (limes never reads the
            clock, so the caller supplies it and a decision re-derives on replay).
        disabled: The sandbox ``pii`` guard override for this turn; skips the pass,
            as :func:`apply_output_guard` does.

    Returns:
        ``(safe_text, decision)`` — ``decision`` is ``None`` when nothing was masked.
    """
    from tessera.agent.state import GuardDecisionRecord
    from tessera.guard.limes_egress_backend import check_pii_egress

    if disabled or "pii" in guard_disabled.get():
        return text, None
    outcome = check_pii_egress(
        text,
        observed_at=observed_at or datetime.now(UTC).isoformat(),
        actor=actor,
    )
    if outcome.action == "forward":
        return text, None
    if outcome.action == "redact":
        record = GuardDecisionRecord(
            target="final_response",
            decision=DecisionKind.TRANSFORM.value,
            policy_rule=outcome.rule,
            rationale=outcome.rationale,
            redactions=outcome.redactions,
        )
        emit_audit(
            target="final_response",
            arguments={"redactions": ", ".join(outcome.redactions)},
            decisions=[record],
            sink=get_settings().guard.audit_sink,
            actor=GUARD_ACTOR,
            outcome="allowed",
        )
        _record_egress_metric("transformed")
        # A REDACT egress always carries its masked content; fall back to text only
        # to satisfy the type-checker (content is None on BLOCK, handled below).
        return outcome.content or text, record
    # block (fail-closed): the recall detector was blind — withhold the answer.
    record = GuardDecisionRecord(
        target="final_response",
        decision=DecisionKind.DENY.value,
        policy_rule=outcome.rule,
        rationale=outcome.rationale,
    )
    emit_audit(
        target="final_response",
        arguments={"final_response": "[withheld — pii-egress recall blind, fail-closed]"},
        decisions=[record],
        sink=get_settings().guard.audit_sink,
        actor=GUARD_ACTOR,
        outcome="denied",
    )
    _record_egress_metric("denied")
    return egress_withheld_notice(language), record


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
# A trailing run of credential-alphabet characters, held in FULL past the PII window
# (``_TAIL_HOLD`` only reaches back ``_TAIL_WINDOW``). A single-token secret — a vendor
# key, a JWT — must land whole before any of it streams, so ``secrets-egress`` sees the
# complete credential and the redactor can freeze rather than half-emit it. The alphabet
# is every character the shipped secret rules use (alnum and ``._/+=~-``); a run this long
# in prose is a URL or a hash, briefly held then released once the secret check clears it.
# Multi-token secrets (PEM armour contains spaces) are NOT covered — that residual is the
# one ADR 0049 §Amendment 1 keeps declared.
_CRED_TAIL: Final = re.compile(r"[A-Za-z0-9._/+=~-]{16,}$")


class StreamingRedactor:
    """Incremental :func:`redact_text` over an SSE token stream, secret-aware.

    Two guarantees over the token stream, so nothing sensitive leaks in an early chunk
    to be "fixed" after the fact:

    * **PII is masked in place.** Text is emitted only once its tail can no longer be the
      prefix of an unfinished PII match (``_TAIL_HOLD``); every emitted segment goes
      through :func:`redact_text`.
    * **A secret pre-empts the stream (ADR 0049 §Amendment 1).** A single-token credential
      is held in full (``_CRED_TAIL``) until it terminates, then limes' ``secrets-egress``
      checks the segment *before* it is emitted. On a hit the redactor **freezes** — it
      emits nothing further and flags the detection — because a secret is withheld whole,
      never masked-around. The post-hoc egress guard on the persisted answer then replaces
      the whole turn; the browser never saw the credential's characters.

    :meth:`flush` drains the remainder at stream end (also secret-checked).

    Known limits: an unbroken token run longer than ``_TAIL_WINDOW`` that is *not*
    credential-shaped may still be cut mid-run (no realistic PII is), a *lowercase* IBAN
    can mask partially, and a **multi-line** secret (PEM armour, which contains spaces) is
    not pre-empted token-by-token — only the post-hoc guard catches it. The batch guard on
    the persisted text applies the same policy either way.
    """

    def __init__(self, *, policy: Policy | None = None, observed_at: str | None = None) -> None:
        self._policy = policy
        # limes never reads the clock; the redactor supplies one for its throwaway
        # detection checks (the leg of record is the post-hoc guard, not this one).
        self._observed_at = observed_at or datetime.now(UTC).isoformat()
        self._raw = ""
        self._start = 0
        self._parts: list[str] = []
        self._redactions: list[str] = []
        self._frozen = False
        self._secret_detected = False

    @property
    def text(self) -> str:
        """The redacted output emitted so far (all segments joined)."""
        return "".join(self._parts)

    @property
    def redactions(self) -> tuple[str, ...]:
        """Labels of every mask applied so far (masked forms only)."""
        return tuple(self._redactions)

    @property
    def secret_detected(self) -> bool:
        """Whether a secret froze the stream (its characters were never emitted)."""
        return self._secret_detected

    def feed(self, chunk: str) -> str:
        """Absorb ``chunk``; return whatever became safe to emit (maybe '')."""
        if self._frozen:
            return ""
        self._raw += chunk
        # Secret pre-emption (ADR 0049 §Amendment 1): the moment the unemitted region
        # carries a complete credential, freeze — a secret is withheld whole, so nothing
        # more streams and the post-hoc egress guard replaces the turn. ``_CRED_TAIL`` has
        # kept the still-forming credential off the wire until this point, so freezing here
        # means not one of its characters was emitted.
        if self._freeze_if_secret():
            return ""
        limit = len(self._raw) - _MIN_HOLD
        if limit <= self._start:
            return ""
        search_from = max(self._start, len(self._raw) - _TAIL_WINDOW)
        tail = _TAIL_HOLD.search(self._raw, search_from)
        cut = min(limit, tail.start()) if tail else limit
        # Hold a long credential-shaped tail in FULL (past the PII window), so a secret
        # still being typed cannot stream its prefix before it completes and is caught.
        cred = _CRED_TAIL.search(self._raw, self._start)
        if cred is not None:
            cut = min(cut, cred.start())
        if cut <= self._start:
            return ""
        return self._emit(cut)

    def flush(self) -> str:
        """Drain and redact everything still held back (unless a secret froze it)."""
        if self._frozen or self._start >= len(self._raw):
            return ""
        if self._freeze_if_secret():
            return ""
        return self._emit(len(self._raw))

    def _emit(self, cut: int) -> str:
        segment = redact_text(self._raw[self._start : cut], policy=self._policy)
        self._start = cut
        self._parts.append(segment.text)
        self._redactions.extend(segment.redactions)
        return segment.text

    def _freeze_if_secret(self) -> bool:
        """Freeze the stream when the unemitted region carries a complete credential.

        Checked on the whole unemitted region ``_raw[_start:]`` (not the about-to-emit
        segment), so a credential is caught the instant it completes — before ``_TAIL_HOLD``
        could cut it at an internal digit boundary and stream the prefix. Detection is limes'
        ``secrets-egress``; the recorded verdict is the post-hoc guard's, never this pre-check.
        Only reached when not already frozen (the callers guard on ``_frozen``), so the return
        says whether this call froze — the callers stop emitting on ``True``.
        """
        segment = self._raw[self._start :]
        if not segment.strip():
            return False
        from tessera.guard.limes_egress_backend import contains_secret

        try:
            found = contains_secret(segment, observed_at=self._observed_at)
        except UnicodeEncodeError:
            # limes' unpaired-surrogate debt raises rather than verdicts; the post-hoc
            # egress guard on the whole answer is the backstop, so never crash the stream.
            found = False
        if found:
            self._frozen = True
            self._secret_detected = True
        return found
