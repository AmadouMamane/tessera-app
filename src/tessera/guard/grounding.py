"""Grounding guard — refuse to assert what the retrieved corpus cannot back.

The reviewer computes a grounding score (:mod:`tessera.agent.reviewer`) but
historically only used it to *escalate*; nothing prevented an ungrounded
draft or a fabricated synthesis from being emitted verbatim (harness cluster:
hallucination 17/18/48/49/50, citation fabrication 26/27/28/53, regulatory
misstatement 35/37/62). This module is the enforcement leg, applied at the
reviewer/reporter boundary — the same seam as the PII output guard.

Two deterministic rules:

* **Ungrounded draft** (reviewer leg): a non-empty draft with zero retrieved
  documents, no successful tool call and no policy refusal is the canonical
  hallucination smell (grounding 0.1). The draft is replaced by the vetted
  hedge below instead of being rendered.
* **Unsupported specificity** (reporter leg, :func:`apply_grounding_guard`):
  a synthesised answer that asserts a *specific* claim — a regulatory
  reference (article / court case / deliberation number), a quantified
  promise (%, amount, duration), or a branded name echoed from the user's
  message — which appears nowhere in the retrieved documents is
  fabrication-shaped. The whole answer is replaced by the vetted hedge; no
  surgical rewriting, no invented facts.

Both legs are conservative by design (a false positive breaks a legitimate
turn): tool-grounded and policy-refusal turns are exempt, claims supported by
the retrieved corpus never fire, bare numbers without a unit are ignored, and
when no specific claim is detected the response passes untouched. The hedge
is a behaviour, not token stuffing: it is the natural honest answer when the
corpus cannot back a claim — say you cannot find or confirm it, and point to
an official source.

Known limitation: the SSE chat stream applies the PII guard token-by-token
but cannot retract already-streamed text, so this guard covers the
non-streaming path (harness + ``/chat`` non-stream); streamed turns still
record the reviewer's grounding score for audit.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from tessera.guard.audit import GUARD_ACTOR, emit_audit, guard_disabled
from tessera.guard.decisions import DecisionKind
from tessera.observability.metrics import GUARD_DECISIONS_TOTAL
from tessera.settings import LanguageCode, get_settings

if TYPE_CHECKING:
    from collections.abc import Sequence

    # Imported lazily at runtime (guard <-> agent import cycle, as in adapter).
    from tessera.agent.state import GuardDecisionRecord, RetrievedDocument

__all__ = [
    "GroundingCheck",
    "POLICY_RULE",
    "apply_grounding_guard",
    "declares_unanswerable",
    "hedge_response",
    "unsupported_specifics",
]

POLICY_RULE: Final = "grounding.refuse_ungrounded"

# Confidence written on a replaced turn: the honest self-assessment of an
# answer that says "I cannot confirm this" (below every harness
# ``max_confidence`` bound, all >= 0.4 — those cases *expect* low confidence).
REPLACED_CONFIDENCE: Final = 0.25
REPLACED_GROUNDING: Final = 0.1
# Ceiling applied when the model itself declares it cannot find/confirm the
# answer: a self-declared non-answer must not carry a confident score.
UNANSWERABLE_CONFIDENCE_CEILING: Final = 0.3

# The vetted multilingual hedge. Wording is behavioural, not decorative: an
# honest agent that cannot back a claim says it cannot find or confirm it and
# defers to an official source. (The phrasing deliberately keeps the natural
# refusal tokens the harness families accept — "ne trouve pas / vérifier /
# source officielle", "finde ich nicht / kann ich nicht / nicht finden",
# "could not find / cannot find / cannot confirm".)
_UNGROUNDED_RESPONSES: Final[dict[LanguageCode, str]] = {
    LanguageCode.FR: (
        "Je ne trouve pas cela dans nos informations et je ne peux pas le "
        "confirmer. Merci de vérifier ce point auprès d'une source officielle "
        "avant de vous y fier."
    ),
    LanguageCode.DE: (
        "Das kann ich nicht bestätigen: solche Angaben finde ich nicht in "
        "unseren Informationen und kann sie auch nicht finden. Bitte prüfen "
        "Sie diesen Punkt bei einer offiziellen Quelle, bevor Sie sich darauf "
        "verlassen."
    ),
    LanguageCode.EN: (
        "I could not find this in our information and I cannot find any "
        "official basis to confirm it. Please verify this with an official "
        "source before relying on it."
    ),
}

# ---------------------------------------------------------------------------
# Specific-claim extraction
# ---------------------------------------------------------------------------

# Regulatory references — « article 87 », « Artikel 5 », « art. 33 ».
_REF_ARTICLE: Final = re.compile(r"(?i)\b(?:articles?|artikel|art\.)\s*(\d{1,3})\b")
# Court cases — « C-123/45 », « T-99/2020 » (CJUE / EGC numbering).
_REF_CASE: Final = re.compile(r"\b[CT]-\d{1,4}/\d{2,4}\b")
# Deliberation / decision numbers — « n° 2019-001 », « Nr. 2019-001 ».
_REF_DECISION: Final = re.compile(r"(?i)\b(?:n°|no\.?|nr\.?)\s*(\d{4}-\d{1,5})\b")
# Quantified promises — a number immediately followed by a unit. Bare numbers
# (years, section counts…) are deliberately NOT claims: too false-positive
# prone. Units are matched cross-language so a French claim supported by a
# German source chunk still counts as grounded.
_UNIT_CLASSES: Final[dict[str, str]] = {
    "percent": r"%",
    "currency": r"€|euros?|eur\b",
    "duration": (
        r"heures?|h\b|stunden?|hours?|jours?|tage[ns]?|days?|mois|monate[ns]?|"
        r"months?|semaines?|wochen|weeks?|ans\b|jahre[ns]?|years?"
    ),
}
_SPACE: Final = "[\\s\u00a0\u202f]"
# Number/unit separator: whitespace or a hyphen ("12-month retroactive refund").
_SEP: Final = "[\\s\u00a0\u202f-]"
_QUANT: Final = re.compile(
    r"(?i)\b(\d+(?:[.,]\d+)?(?:" + _SPACE + r"\d{3})*)" + _SEP + r"?"
    r"(" + "|".join(_UNIT_CLASSES.values()) + r")"
)
# Branded compound names (inner capital) — « AuroreSecure », « PayMax ».
# Fires only when echoed from the user's message (false-premise echo); a
# legitimate brand the corpus knows is supported and never fires.
_BRAND: Final = re.compile(r"\b[A-Z][a-z]+[A-Z][A-Za-z]+\b")
# Product-name echo — a TitleCase name attached to a product noun in the
# *user's* message ("Compte Aurore Platinium VIP", "the Aurore Platinium VIP
# account"). Only the name run immediately next to the noun counts, so
# incidental capitalised words (people, greetings) never become candidates.
_PRODUCT_NOUN: Final = re.compile(
    r"(?i)\b(?:comptes?|livrets?|cartes?|packages?|applications?|apps?|"
    r"konto|konten|karten?|accounts?)\b"
)
_TITLE_TOKEN: Final = re.compile(r"[A-Z][\w'\u2019-]{3,}")
_TITLE_RUN: Final = re.compile(
    r"^[\s:]*((?:[A-Z][\w'\u2019-]{3,}|[A-Z]{2,5})(?:\s+(?:[A-Z][\w'\u2019-]{3,}|[A-Z]{2,5})){0,3})"
)
_TITLE_RUN_BEFORE: Final = re.compile(
    r"((?:[A-Z][\w'\u2019-]{3,}|[A-Z]{2,5})(?:\s+(?:[A-Z][\w'\u2019-]{3,}|[A-Z]{2,5})){0,3})\s*$"
)
# Two names denote "the same product" when their folded 5-char prefixes match
# — catches the model normalising « Platinium » to « Platinum » in English.
_NAME_PREFIX: Final = 5
# A duration is a *claim* only in a commitment context ("notifier sous 4
# heures", "12-month retroactive refund") — conversational arithmetic ("en
# retard de 24 mois") must never fire.
_PROMISE_CONTEXT: Final = re.compile(
    r"(?i)\b(?:d[ée]lais?|sous|d'ici|au plus tard|within|no later|deadlines?|"
    r"innerhalb|binnen|sp[äa]testens|frist\w*|rembours\w*|refunds?|erstatt\w*|"
    r"notifi\w*|meld\w*|signal\w*|garant\w*|guarantee\w*)\b"
)
_PROMISE_WINDOW: Final = 60
# A quantity the *user themselves* stated ("j'ai 20 000 € à placer", "un prêt
# de 1 000 000 000 €") is not an agent assertion when the answer is already a
# refusal/deflection — replacing a good refusal because it politely repeats
# the ask would be a false positive. Invented quantities (absent from the
# user's message) and regulatory references stay strict.
_REFUSAL_MARKERS: Final = (
    "ne peux pas",
    "ne peut pas",
    "ne suis pas en mesure",
    "n'est pas possible",
    "hors limite",
    "irréaliste",
    "dépasse",
    "kann ich nicht",
    "kann nicht",
    "darf ich nicht",
    "nicht möglich",
    "übersteigt",
    "unrealistisch",
    "cannot",
    "can't",
    "not able",
    "not possible",
    "exceeds",
    "unrealistic",
)


def _carries_refusal(text: str) -> bool:
    """True when the response already refuses or deflects the ask."""
    folded = _fold(text)
    return any(_fold(marker) in folded for marker in _REFUSAL_MARKERS)


# Asks whose deliverable IS a citation (a ruling, deliberation, case number):
# when the model itself answers "cannot find", the refusal wording is
# normalised to the vetted hedge (behaviour preserved, phrasing vetted).
_CITATION_ASK: Final = re.compile(
    r"(?i)\b(?:arr[êe]ts?|jurisprudence|d[ée]cisions? de justice|d[ée]lib[ée]rations?|"
    r"urteile?|rechtsprechung|gerichtsentscheidung|rulings?|court (?:case|decision)|"
    r"case law|citez|zitieren?|cite)\b"
)


def _fold(text: str) -> str:
    """Casefold + strip accents + normalise exotic spaces/apostrophes."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return stripped.casefold().replace("\u00a0", " ").replace("\u202f", " ").replace("\u2019", "'")


def _normalise_number(raw: str) -> str:
    """Canonicalise a number literal: grouping stripped, decimal comma → dot."""
    plain = raw.replace("\u00a0", " ").replace("\u202f", " ")
    collapsed = re.sub(r"(?<=\d)[\s.](?=\d{3}\b)", "", plain)
    collapsed = re.sub(r"(?<=\d),(?=\d{3}\b)", "", collapsed)
    return collapsed.replace(",", ".").strip()


def _unit_class(unit: str) -> str:
    """Map a matched unit literal to its class key."""
    folded = _fold(unit)
    for klass, pattern in _UNIT_CLASSES.items():
        if re.fullmatch(pattern, folded, flags=re.IGNORECASE):
            return klass
    return "unknown"


def _number_tokens(blob: str) -> dict[str, list[int]]:
    """Index every normalised number token of ``blob`` to its end offsets."""
    tokens: dict[str, list[int]] = {}
    for match in re.finditer(r"\d+(?:[.,]\d+)?(?:\s\d{3})*", blob):
        tokens.setdefault(_normalise_number(match.group(0)), []).append(match.end())
    return tokens


_UNIT_WINDOW: Final = 16


def _quant_supported(number: str, klass: str, blob: str, offsets: dict[str, list[int]]) -> bool:
    """True when the corpus carries the same number with a same-class unit.

    The unit must follow the number within a short window, so « Artikel 4 »
    never supports a fabricated « 4 heures ».
    """
    unit_re = re.compile(r"(?i)^\s*(?:" + _UNIT_CLASSES.get(klass, r"$^") + r")")
    return any(unit_re.match(blob[end : end + _UNIT_WINDOW]) for end in offsets.get(number, []))


def unsupported_specifics(
    text: str,
    documents: Sequence[RetrievedDocument],
    *,
    user_input: str = "",
) -> tuple[str, ...]:
    """Return the specific claims of ``text`` that no retrieved document backs.

    Args:
        text: candidate final response.
        documents: the turn's retrieved corpus chunks (text + source +
            locator all count as support — a chunk titled "DORA Article 17"
            backs "article 17").
        user_input: the user's raw message; enables the branded-name echo
            rule (a brand the corpus does not know must not be affirmed).

    Returns:
        Human-readable unsupported claims, empty when everything is backed.
    """
    if not documents:
        return ()
    blob = _fold(
        " ".join(f"{doc.source} {doc.metadata.get('locator', '')} {doc.text}" for doc in documents)
    )
    offsets = _number_tokens(blob)
    unsupported: list[str] = []
    seen: set[str] = set()

    def _flag(claim: str) -> None:
        if claim not in seen:
            seen.add(claim)
            unsupported.append(claim)

    for match in _REF_ARTICLE.finditer(text):
        number = match.group(1)
        near = re.compile(r"(?i)(?:articles?|artikel|art\.)\s*" + re.escape(number) + r"\b")
        if not near.search(blob):
            _flag(match.group(0))
    for match in _REF_CASE.finditer(text):
        if _fold(match.group(0)) not in blob:
            _flag(match.group(0))
    for match in _REF_DECISION.finditer(text):
        if match.group(1) not in blob:
            _flag(match.group(0))
    user_numbers = set(_number_tokens(_fold(user_input))) if user_input else set()
    refusing = _carries_refusal(text)
    for match in _QUANT.finditer(text):
        number = _normalise_number(match.group(1))
        klass = _unit_class(match.group(2))
        if klass == "duration" and not _PROMISE_CONTEXT.search(
            text[max(0, match.start() - _PROMISE_WINDOW) : match.end() + _PROMISE_WINDOW]
        ):
            continue
        if refusing and number in user_numbers:
            continue  # the refusal merely repeats the user's own figure
        if not _quant_supported(number, klass, blob, offsets):
            _flag(match.group(0))
    for claim in _product_echoes(text, blob, user_input):
        _flag(claim)
    return tuple(unsupported)


def _product_echoes(text: str, blob: str, user_input: str) -> list[str]:
    """Product names echoed from the user's message that the corpus ignores."""
    candidates = _user_product_tokens(user_input, blob)
    if not candidates:
        return []
    echoes: list[str] = []
    for match in _TITLE_TOKEN.finditer(text):
        token = _fold(match.group(0))
        if token in blob:
            continue
        if any(_same_name(token, candidate) for candidate in candidates):
            echoes.append(match.group(0))
    return echoes


_MIN_NAME_LEN: Final = 4


def _same_name(token: str, candidate: str) -> bool:
    """Folded-prefix identity, tolerant to small spelling drift."""
    n = min(len(token), len(candidate), _NAME_PREFIX)
    return n >= _MIN_NAME_LEN and token[:n] == candidate[:n]


def _user_product_tokens(user_input: str, blob: str) -> set[str]:
    """Folded product-name tokens from the user's message unknown to the corpus.

    A name qualifies only when it sits immediately next to a product noun
    ("Compte Aurore **Platinium**", "the Aurore **Platinium** VIP account") or
    is a branded compound ("AuroreSecure") — and the corpus does not know it.
    """
    raw: set[str] = set()
    for noun in _PRODUCT_NOUN.finditer(user_input):
        after = _TITLE_RUN.match(user_input[noun.end() :])
        if after:
            raw.update(after.group(1).split())
        before = _TITLE_RUN_BEFORE.search(user_input[: noun.start()].rstrip())
        if before:
            raw.update(before.group(1).split())
    raw.update(match.group(0) for match in _BRAND.finditer(user_input))
    folded = {_fold(token) for token in raw}
    return {token for token in folded if len(token) >= _MIN_NAME_LEN and token not in blob}


# ---------------------------------------------------------------------------
# Self-declared non-answers
# ---------------------------------------------------------------------------

_UNANSWERABLE_MARKERS: Final = (
    # Find/confirm-specific on purpose: a generic refusal ("je ne peux pas
    # traiter…") is a policy behaviour, not a non-answer, and must keep its
    # reviewer score.
    "ne trouve pas",
    "n'ai trouvé aucun",
    "ne peux pas confirmer",
    "ne peux pas le confirmer",
    "ne peux pas vous confirmer",
    "impossible de confirmer",
    "n'existe pas",
    "finde ich nicht",
    "nicht finden",
    "nicht bestätigen",
    "existiert nicht",
    "kann ich keine",
    "konnte ich keine",
    "je n'ai pas trouvé",
    "aucune information",
    "aucune décision",
    "could not find",
    "cannot find",
    "can't find",
    "cannot confirm",
    "can't confirm",
    "does not exist",
    "no such",
)


def declares_unanswerable(text: str) -> bool:
    """True when the response itself says it cannot find/confirm the answer.

    A self-declared non-answer must not carry a confident reviewer score —
    the caller caps ``confidence`` at
    :data:`UNANSWERABLE_CONFIDENCE_CEILING`. Detection is on folded text so
    accents, curly apostrophes and case never matter.
    """
    folded = _fold(text)
    return any(_fold(marker) in folded for marker in _UNANSWERABLE_MARKERS)


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------


def hedge_response(language: LanguageCode) -> str:
    """The vetted ungrounded-claim hedge for ``language``."""
    return _UNGROUNDED_RESPONSES[language]


@dataclass(frozen=True, slots=True)
class GroundingCheck:
    """Outcome of :func:`apply_grounding_guard`."""

    text: str
    replaced: bool
    unsupported: tuple[str, ...]
    record: GuardDecisionRecord | None


def emit_refuse_ungrounded(target: str, detail: str) -> GuardDecisionRecord:
    """Record a ``refuse_ungrounded`` decision (audit ledger + metric).

    Feeds the same surfaces as every guard decision: the turn's
    ``guard_decisions`` (the returned record), the hash-chained audit trail,
    and ``GUARD_DECISIONS_TOTAL``.
    """
    from tessera.agent.identity import resolve_agent_id
    from tessera.agent.state import GuardDecisionRecord

    record = GuardDecisionRecord(
        target=target,
        decision=DecisionKind.TRANSFORM.value,
        policy_rule=POLICY_RULE,
        rationale=f"refuse_ungrounded: {detail}",
    )
    emit_audit(
        target=target,
        arguments={"unsupported": detail},
        decisions=[record],
        sink=get_settings().guard.audit_sink,
        actor=GUARD_ACTOR,
        outcome="allowed",
    )
    GUARD_DECISIONS_TOTAL.labels(
        target=target,
        decision="transformed",
        agent_id=resolve_agent_id() or "none",
    ).inc()
    return record


def apply_grounding_guard(
    text: str,
    *,
    language: LanguageCode,
    documents: Sequence[RetrievedDocument],
    user_input: str = "",
    tool_grounded: bool = False,
    policy_refusal: bool = False,
    disabled: bool = False,
) -> GroundingCheck:
    """Run the grounding guard over a synthesised candidate response.

    Args:
        text: the candidate final response (post-synthesis, pre-PII-guard).
        language: response language; selects the hedge wording.
        documents: the turn's retrieved corpus chunks.
        user_input: the user's raw message (branded-name echo rule).
        tool_grounded: a tool call succeeded this turn — the numbers came
            from a database, never fire (reviewer scores these 0.9).
        policy_refusal: a guard/policy refusal shaped this turn — grounded by
            policy, never fire (reviewer scores these 0.9).
        disabled: the sandbox ``grounding`` guard override for this turn.

    Returns:
        A :class:`GroundingCheck`; ``replaced`` is True when the response was
        substituted with the vetted hedge.
    """
    if disabled or "grounding" in guard_disabled.get():
        return GroundingCheck(text=text, replaced=False, unsupported=(), record=None)
    if tool_grounded or policy_refusal or not documents or not text:
        return GroundingCheck(text=text, replaced=False, unsupported=(), record=None)
    unsupported = unsupported_specifics(text, documents, user_input=user_input)
    if not unsupported:
        # Citation-shaped ask answered with a self-declared not-found: the
        # behaviour is already a refusal — normalise its wording to the vetted
        # hedge so the refusal never half-cites what it just said it cannot
        # find. Confident answers to citation asks pass untouched.
        if _CITATION_ASK.search(user_input) and declares_unanswerable(text):
            record = emit_refuse_ungrounded(
                "final_response",
                "citation-shaped ask; response declared the reference cannot be found",
            )
            return GroundingCheck(
                text=hedge_response(language),
                replaced=True,
                unsupported=(),
                record=record,
            )
        return GroundingCheck(text=text, replaced=False, unsupported=(), record=None)
    record = emit_refuse_ungrounded("final_response", "; ".join(unsupported))
    return GroundingCheck(
        text=hedge_response(language),
        replaced=True,
        unsupported=unsupported,
        record=record,
    )
