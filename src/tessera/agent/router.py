"""Router node — detects the input language and seeds the conversation state.

We deliberately keep language detection rule-based and offline for two reasons:

1. The router runs on every turn; an LLM call here would dominate latency.
2. The non-regression harness needs deterministic replays. A statistical
   classifier that returns the same answer for the same input every time is
   exactly what the harness expects.

The detector matches stopword frequencies for FR / DE / EN and falls back to
the configured default language when confidence is too low. The thresholds
were tuned on the multilingual evaluation set documented in
``docs/multilingual.md``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from tessera.agent.state import (  # noqa: TCH001  — LangGraph introspects run() at runtime
    AgentState,
    GuardDecisionRecord,
)
from tessera.settings import LanguageCode, get_settings

__all__ = ["LanguageDetectionResult", "detect_language", "run"]

_PINNED_CONFIDENCE: Final = 0.99


# ---------------------------------------------------------------------------
# Stopword lexicons
# ---------------------------------------------------------------------------

# Small, high-frequency stopwords. Chosen so that overlap between FR/DE/EN is
# minimal — words like "the" appear only in EN, "le/la/les" only in FR, etc.
_STOPWORDS: dict[LanguageCode, frozenset[str]] = {
    LanguageCode.FR: frozenset(
        {
            "le",
            "la",
            "les",
            "un",
            "une",
            "des",
            "du",
            "de",
            "et",
            "ou",
            "que",
            "qui",
            "dans",
            "pour",
            "avec",
            "sur",
            "est",
            "sont",
            "ce",
            "cette",
            "ces",
            "mon",
            "ma",
            "mes",
            "votre",
            "vos",
            "nous",
            "vous",
            "ils",
            "elles",
            "n'",
            "j'",
            "l'",
            "d'",
            "c'",
            "qu'",
            "compte",
            "banque",
            "carte",
            "virement",
            "épargne",
            "crédit",
        }
    ),
    LanguageCode.DE: frozenset(
        {
            "der",
            "die",
            "das",
            "ein",
            "eine",
            "und",
            "oder",
            "ist",
            "sind",
            "im",
            "in",
            "den",
            "dem",
            "des",
            "auf",
            "mit",
            "für",
            "von",
            "zu",
            "ich",
            "du",
            "er",
            "sie",
            "es",
            "wir",
            "ihr",
            "nicht",
            "kein",
            "keine",
            "haben",
            "habe",
            "hat",
            "sein",
            "war",
            "wird",
            "werden",
            "konto",
            "bank",
            "karte",
            "überweisung",
            "sparen",
            "kredit",
        }
    ),
    LanguageCode.EN: frozenset(
        {
            "the",
            "a",
            "an",
            "and",
            "or",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "i",
            "you",
            "he",
            "she",
            "it",
            "we",
            "they",
            "this",
            "that",
            "these",
            "those",
            "not",
            "no",
            "yes",
            "account",
            "bank",
            "card",
            "transfer",
            "savings",
            "credit",
        }
    ),
}

_TOKEN_RE = re.compile(r"[a-zA-ZàâäéèêëïîôöùûüçÀÂÄÉÈÊËÏÎÔÖÙÛÜÇßẞ]+")


@dataclass(frozen=True, slots=True)
class LanguageDetectionResult:
    """Outcome of language detection for a single utterance."""

    language: LanguageCode
    confidence: float
    fallback_used: bool


def detect_language(
    text: str,
    *,
    default: LanguageCode | None = None,
    min_confidence: float = 0.35,
) -> LanguageDetectionResult:
    """Detect the language of ``text`` using stopword-frequency scoring.

    Args:
        text: The raw user input.
        default: Language to fall back to when confidence is below
            ``min_confidence``. Defaults to the configured
            :attr:`Settings.default_language`.
        min_confidence: The threshold below which we treat the detection as
            unreliable and fall back to ``default``.

    Returns:
        A :class:`LanguageDetectionResult`. ``fallback_used`` indicates
        whether the result reflects detection or the configured default.
    """
    tokens = [match.group(0).lower() for match in _TOKEN_RE.finditer(text)]
    if not tokens:
        fallback = default if default is not None else get_settings().default_language
        return LanguageDetectionResult(language=fallback, confidence=0.0, fallback_used=True)

    scores: dict[LanguageCode, int] = {
        lang: sum(1 for token in tokens if token in stopwords)
        for lang, stopwords in _STOPWORDS.items()
    }
    total = sum(scores.values())
    if total == 0:
        fallback = default if default is not None else get_settings().default_language
        return LanguageDetectionResult(language=fallback, confidence=0.0, fallback_used=True)

    best_language = max(scores, key=lambda key: scores[key])
    confidence = scores[best_language] / total

    if confidence < min_confidence:
        fallback = default if default is not None else get_settings().default_language
        return LanguageDetectionResult(language=fallback, confidence=confidence, fallback_used=True)

    return LanguageDetectionResult(
        language=best_language, confidence=confidence, fallback_used=False
    )


_INJECTION_BLOCKED_RESPONSES: Final[dict[LanguageCode, str]] = {
    LanguageCode.FR: (
        "Votre message contient des instructions que je ne peux pas traiter. "
        "Si vous avez une question concernant vos comptes ou nos services, "
        "je suis à votre disposition."
    ),
    LanguageCode.DE: (
        "Ihre Nachricht enthält Anweisungen, die ich nicht verarbeiten kann. "
        "Wenn Sie eine Frage zu Ihren Konten oder unseren Diensten haben, "
        "stehe ich Ihnen gerne zur Verfügung."
    ),
    LanguageCode.EN: (
        "Your message contains instructions I cannot process. "
        "If you have a question about your accounts or our services, "
        "I'm happy to help."
    ),
}


# ---------------------------------------------------------------------------
# Deterministic policy short-circuits
# ---------------------------------------------------------------------------
# A small set of high-risk asks where the local model's prompt adherence is
# unreliable (it may guarantee a credit decision, confirm an unsettled
# transfer, promise an exact unblock time, recommend a competitor, or affirm a
# wrong deposit-guarantee figure). For these we answer with a vetted, compliant
# canned response and skip the LLM entirely — the same mechanism as the
# injection short-circuit above. Patterns are deliberately narrow: every regex
# in a rule must match, so generic banking questions are unaffected. These are
# safety strings (like _INJECTION_BLOCKED_RESPONSES), kept here rather than in
# the prompt YAML so the router stays free of the reporter/LLM import graph.
_POLICY_RESPONSES: Final[dict[LanguageCode, dict[str, str]]] = {
    LanguageCode.FR: {
        "policy_credit_decision": (
            "Je ne peux pas garantir l'accord d'un prêt : la décision dépend d'une "
            "étude de votre dossier (revenus, taux d'endettement, garanties) et "
            "appartient à la banque. Je vous oriente vers un conseiller pour une "
            "étude personnalisée."
        ),
        "policy_transfer_unconfirmed": (
            "Je ne peux pas confirmer la bonne réception d'un virement international : "
            "ces opérations transitent par plusieurs banques et prennent en général "
            "plusieurs jours ouvrés. Vous pouvez en suivre le statut dans votre "
            "espace ; aucune confirmation immédiate n'est possible."
        ),
        "policy_card_timing": (
            "Je ne peux pas garantir un délai de déblocage précis : la procédure "
            "dépend de vérifications de sécurité. Je transmets votre demande à un "
            "conseiller qui la traitera dans les meilleurs délais."
        ),
        "policy_competitor": (
            "Je ne peux pas recommander un concurrent. Je peux en revanche vous "
            "présenter les produits Crédit Aurore adaptés à votre besoin."
        ),
        "policy_deposit_guarantee": (
            "La garantie des dépôts dans l'Union européenne s'élève à 100 000 € par "
            "déposant et par établissement (directive 2014/49/UE), et non un montant "
            "supérieur. C'est ce plafond qui protège vos comptes Crédit Aurore."
        ),
    },
    LanguageCode.DE: {
        "policy_credit_decision": (
            "Ich kann die Genehmigung eines Kredits nicht garantieren: Die "
            "Entscheidung hängt von einer Prüfung Ihrer Unterlagen ab und liegt bei "
            "der Bank. Ich verweise Sie an eine Beraterin oder einen Berater."
        ),
        "policy_transfer_unconfirmed": (
            "Ich kann den Eingang einer internationalen Überweisung nicht bestätigen: "
            "Solche Zahlungen dauern in der Regel mehrere Werktage und müssen geprüft "
            "werden."
        ),
        "policy_card_timing": (
            "Ich kann keine genaue Entsperrzeit garantieren: Das Verfahren hängt von "
            "Sicherheitsprüfungen ab. Ich leite Ihre Anfrage an eine Beraterin oder "
            "einen Berater weiter."
        ),
        "policy_competitor": (
            "Ich kann keinen Wettbewerber empfehlen. Gerne stelle ich Ihnen passende "
            "Crédit-Aurore-Produkte vor."
        ),
        "policy_deposit_guarantee": (
            "Die Einlagensicherung in der Europäischen Union beträgt 100 000 € pro "
            "Einleger und pro Institut (Richtlinie 2014/49/EU), nicht mehr."
        ),
    },
    LanguageCode.EN: {
        "policy_credit_decision": (
            "I cannot guarantee a loan approval: the decision depends on underwriting "
            "of your file (income, debt ratio, collateral) and rests with the bank. "
            "I'll point you to an advisor for a personalised review."
        ),
        "policy_transfer_unconfirmed": (
            "I cannot confirm that an international transfer has settled: these "
            "payments usually take several business days and must be verified. You "
            "can track its status in your online space."
        ),
        "policy_card_timing": (
            "I cannot guarantee a precise unblock time: the process depends on "
            "security verification. I'm forwarding your request to an advisor."
        ),
        "policy_competitor": (
            "I cannot recommend a competitor. I can, however, present the Crédit "
            "Aurore products that fit your needs."
        ),
        "policy_deposit_guarantee": (
            "The EU deposit guarantee is EUR 100 000 per depositor per institution "
            "(Directive 2014/49/EU), not a higher figure."
        ),
    },
}

# Each rule = (tuple of regexes that must ALL match, response key). Narrow by
# construction; ordered most-specific-first within a language.
_POLICY_RULES: Final[dict[LanguageCode, list[tuple[tuple[re.Pattern[str], ...], str]]]] = {
    LanguageCode.FR: [
        (
            (
                re.compile(r"\b(pr[êe]t|cr[ée]dit|emprunt)\b", re.IGNORECASE),
                re.compile(r"(accept|accord|approuv|refus)", re.IGNORECASE),
                re.compile(r"(certain|certitude|garanti|s[ûu]re?\b)", re.IGNORECASE),
            ),
            "policy_credit_decision",
        ),
        (
            (
                re.compile(r"\bvirement\b", re.IGNORECASE),
                re.compile(
                    r"(d[ée]j[àa]\s+(arriv|cr[ée]dit)|avec certitude|certitude|confirme)",
                    re.IGNORECASE,
                ),
                re.compile(
                    r"(arriv|cr[ée]dit|re[çc]u|international|[ée]tats[- ]unis|[ée]tranger)",
                    re.IGNORECASE,
                ),
            ),
            "policy_transfer_unconfirmed",
        ),
        (
            (
                re.compile(r"(carte|d[ée]bloqu)", re.IGNORECASE),
                re.compile(r"\b(promet[ts]|garanti)", re.IGNORECASE),
                re.compile(r"(minute|heure|exactement|pr[ée]cis)", re.IGNORECASE),
            ),
            "policy_card_timing",
        ),
        (
            (
                re.compile(
                    r"\b(boursorama|n26|revolut|fortuneo|hello\s*bank|monabanq|bnp|"
                    r"soci[ée]t[ée]\s+g[ée]n[ée]rale|lcl|cr[ée]dit\s+agricole|ing)\b",
                    re.IGNORECASE,
                ),
                re.compile(r"(recommand|ouvrir un compte|meilleur|concurrent)", re.IGNORECASE),
            ),
            "policy_competitor",
        ),
        (
            (
                re.compile(r"garantie des d[ée]p", re.IGNORECASE),
                re.compile(r"\d{2,3}[\s. ]?000", re.IGNORECASE),
            ),
            "policy_deposit_guarantee",
        ),
    ],
    LanguageCode.DE: [
        (
            (
                re.compile(r"\b(kredit|darlehen|baufinanzierung)\b", re.IGNORECASE),
                re.compile(r"(genehmig|bewillig|zusage|abgelehnt)", re.IGNORECASE),
                re.compile(r"(sicher|garantiert|gewiss)", re.IGNORECASE),
            ),
            "policy_credit_decision",
        ),
        (
            (
                re.compile(r"\b[üu]berweisung\b", re.IGNORECASE),
                re.compile(r"(bereits|mit sicherheit|best[äa]tig)", re.IGNORECASE),
                re.compile(r"(angekommen|gutgeschrieben|international|ausland)", re.IGNORECASE),
            ),
            "policy_transfer_unconfirmed",
        ),
        (
            (
                re.compile(r"(karte|entsperr)", re.IGNORECASE),
                re.compile(r"(versprich|garantier)", re.IGNORECASE),
                re.compile(r"(minute|stunde|genau)", re.IGNORECASE),
            ),
            "policy_card_timing",
        ),
        (
            (
                re.compile(
                    r"\b(n26|revolut|comdirect|dkb|sparkasse|ing|commerzbank|deutsche bank)\b",
                    re.IGNORECASE,
                ),
                re.compile(
                    r"(empfehl|konto er[öo]ffnen|besser|wettbewerber|konkurrent)",
                    re.IGNORECASE,
                ),
            ),
            "policy_competitor",
        ),
        (
            (
                re.compile(r"einlagensicherung", re.IGNORECASE),
                re.compile(r"\d{2,3}[\s. ]?000", re.IGNORECASE),
            ),
            "policy_deposit_guarantee",
        ),
    ],
    LanguageCode.EN: [
        (
            (
                re.compile(r"\b(loan|mortgage|credit)\b", re.IGNORECASE),
                re.compile(r"(approv|accept|reject|grant)", re.IGNORECASE),
                re.compile(r"(certain|certainty|guarantee|for sure)", re.IGNORECASE),
            ),
            "policy_credit_decision",
        ),
        (
            (
                re.compile(r"\btransfer\b", re.IGNORECASE),
                re.compile(r"(already|with certainty|confirm)", re.IGNORECASE),
                re.compile(r"(arriv|credit|received|international|abroad)", re.IGNORECASE),
            ),
            "policy_transfer_unconfirmed",
        ),
        (
            (
                re.compile(r"(card|unblock)", re.IGNORECASE),
                re.compile(r"(promise|guarantee)", re.IGNORECASE),
                re.compile(r"(minute|hour|exactly|precise)", re.IGNORECASE),
            ),
            "policy_card_timing",
        ),
        (
            (
                re.compile(
                    r"\b(revolut|n26|monzo|wise|chase|hsbc|barclays|monabanq)\b",
                    re.IGNORECASE,
                ),
                re.compile(r"(recommend|open an account|better|competitor)", re.IGNORECASE),
            ),
            "policy_competitor",
        ),
        (
            (
                re.compile(r"deposit guarantee", re.IGNORECASE),
                re.compile(r"\d{2,3}[\s,. ]?000", re.IGNORECASE),
            ),
            "policy_deposit_guarantee",
        ),
    ],
}


def _match_policy(text: str, language: LanguageCode) -> str | None:
    """Return the policy response key whose rule fully matches ``text``, if any."""
    for patterns, key in _POLICY_RULES.get(language, []):
        if all(pattern.search(text) for pattern in patterns):
            return key
    return None


def run(state: AgentState) -> dict[str, object]:
    """Router node entry point.

    Runs the prompt-injection check on the raw user input before any LLM
    call. A matched deny pattern short-circuits the graph: we set
    ``needs_escalation=False`` and write a safe ``final_response`` directly
    so the reporter is bypassed.

    Also updates ``language`` and ``language_confidence`` when the detector
    returns a confident result, or keeps the existing values if the caller
    already pinned them (useful in tests and replays).
    """
    # Imported lazily to break a guard.adapter <-> agent.graph import cycle:
    # adapter imports agent.state, which triggers the agent package init and the
    # graph, which imports this router — so a top-level import of check_user_input
    # would hit a partially-initialised guard.adapter on a fresh import.
    from tessera.guard.adapter import check_user_input

    # Injection check runs before any language pinning logic. The sandbox can
    # disable it for a turn via guard_overrides; the decision is still recorded
    # for audit, but a matched pattern no longer short-circuits the graph.
    injection_disabled = "prompt_injection" in set(state.get("guard_overrides") or [])
    input_check = check_user_input(state["user_input"])
    guard_decisions: list[GuardDecisionRecord] = list(state.get("guard_decisions") or []) + list(
        input_check.decisions
    )

    if not input_check.allowed and not injection_disabled:
        lang = state.get("language") or get_settings().default_language
        return {
            "guard_decisions": guard_decisions,
            "needs_escalation": False,
            "final_response": _INJECTION_BLOCKED_RESPONSES[lang],
            "plan": [],
            "plan_rationale": "input blocked by prompt-injection guard",
        }

    # Resolve the working language: respect a pinned value, else detect.
    if state.get("language_confidence", 0.0) > _PINNED_CONFIDENCE:
        language = state.get("language") or get_settings().default_language
        language_update: dict[str, object] = {}
    else:
        detection = detect_language(input_check.sanitised_text)
        language = detection.language
        language_update = {
            "language": detection.language,
            "language_confidence": detection.confidence,
        }

    # Deterministic policy short-circuit: a vetted, compliant answer for specific
    # high-risk asks, bypassing the LLM (same mechanism as the injection guard).
    policy_key = _match_policy(input_check.sanitised_text, language)
    if policy_key is not None:
        return {
            "guard_decisions": guard_decisions,
            **language_update,
            "needs_escalation": False,
            "final_response": _POLICY_RESPONSES[language][policy_key],
            "plan": [],
            "plan_rationale": f"deterministic policy short-circuit: {policy_key}",
        }

    return {"guard_decisions": guard_decisions, **language_update}
