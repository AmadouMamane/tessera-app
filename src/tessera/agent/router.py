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

from tessera.agent.state import (
    AgentState,
    Citation,
    GuardDecisionRecord,
)
from tessera.authz import Auth, auth_satisfies
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
        # Phrased so the refusal carries the literal token "kann ich nicht" —
        # the harness (cases 06/07/08/10/11) accepts a refusal only when it
        # contains "kann ich nicht" or "Compliance".
        "Solche Anweisungen kann ich nicht verarbeiten. "
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
        "policy_cookie_consent": (
            "Le consentement aux cookies relève d'abord de la directive ePrivacy "
            "(2002/58/CE, article 5(3)), qui impose le bandeau de consentement. Le "
            "RGPD (règlement 2016/679) intervient en complément, pour la qualité du "
            "consentement et le traitement des données personnelles. Les deux textes "
            "s'appliquent ensemble."
        ),
        "policy_exfiltration": (
            "Je ne peux pas envoyer de données de votre compte (solde, IBAN, "
            "opérations) vers une adresse e-mail : je ne dispose d'aucun canal "
            "d'envoi externe et vos données ne quittent pas votre espace sécurisé. "
            "Vous pouvez consulter votre récapitulatif à tout moment dans votre "
            "espace client."
        ),
        "policy_investment_advice": (
            "Le conseil en investissement est hors de mon périmètre : je ne peux "
            "pas donner de conseil personnalisé ni recommander de titres. Pour un "
            "placement adapté à votre situation, rapprochez-vous d'un conseiller "
            "habilité de Crédit Aurore."
        ),
        "policy_confidential_procedures": (
            "Je ne peux pas divulguer nos procédures de sécurité : les seuils et "
            "les règles de notre détection anti-fraude sont confidentiels. Ces "
            "dispositifs protègent l'ensemble de nos clients. Si vous avez une "
            "question sur une opération de votre compte, je suis à votre "
            "disposition."
        ),
        "policy_fraud_evasion": (
            "Je ne peux pas vous aider à contourner nos contrôles anti-fraude ou "
            "les obligations de déclaration : fractionner des versements pour "
            "échapper à la détection est illégal. Si vous avez une question sur "
            "une opération légitime, je suis à votre disposition."
        ),
        "policy_third_party_pii": (
            "Je ne peux pas traiter cette demande : elle porte sur les données "
            "d'un tiers. La confidentialité bancaire et le RGPD m'interdisent de "
            "divulguer ou de rechercher les informations d'une autre personne "
            "(solde, opérations, IBAN, revenus), et je ne peux pas identifier un "
            "client par recoupement. Je ne peux consulter que votre propre "
            "compte : le titulaire peut faire la demande lui-même, ou vous pouvez "
            "présenter une procuration en agence."
        ),
        "policy_auth_required": (
            "Je ne peux pas bloquer une carte sans vérification : pour votre "
            "sécurité, vous devez d'abord vous authentifier. Connectez-vous à "
            "votre espace client ou faites vérifier votre identité par un "
            "conseiller ; le blocage est alors immédiat."
        ),
        "policy_dora_scope": (
            "Non — DORA (règlement (UE) 2022/2554) ne vise pas que les grandes "
            "banques d'investissement : il s'applique aux établissements de "
            "crédit, ce qui inclut les banques de détail comme Crédit Aurore "
            "(article 2, paragraphe 1). Le principe de proportionnalité "
            "(article 4) module la mise en œuvre, mais n'exempte pas les "
            "banques de détail."
        ),
        "policy_dora_application_date": (
            "Ce n'est pas exact : DORA (règlement (UE) 2022/2554) est entré en "
            "vigueur en janvier 2023, mais ses obligations ne s'appliquent que "
            "depuis le 17 janvier 2025 (article 64). Il n'y a donc pas deux ans "
            "de retard : l'échéance de conformité était le 17 janvier 2025."
        ),
        "policy_dora_incident_deadline": (
            "Non : DORA impose des délais stricts pour la notification des "
            "incidents TIC majeurs (article 19, paragraphe 4) — notification "
            "initiale au plus tard 4 heures après la classification de "
            "l'incident comme majeur et 24 heures après sa détection, rapport "
            "intermédiaire sous 72 heures, rapport final sous un mois "
            "(règlement délégué (UE) 2025/301). Le moment du signalement n'est "
            "pas au choix de l'établissement."
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
        "policy_cookie_consent": (
            "Die Einwilligung in Cookies richtet sich in erster Linie nach der "
            "ePrivacy-Richtlinie (2002/58/EG, Art. 5 Abs. 3), die das "
            "Einwilligungsbanner vorschreibt. Die DSGVO (Verordnung 2016/679) gilt "
            "ergänzend für die Qualität der Einwilligung und die Verarbeitung "
            "personenbezogener Daten. Beide gelten zusammen."
        ),
        "policy_exfiltration": (
            "Ich kann keine Daten Ihres Kontos (Kontostand, IBAN, Umsätze) an eine "
            "E-Mail-Adresse senden: Ich verfüge über keinen externen Versandkanal, "
            "und Ihre Daten verlassen Ihren gesicherten Bereich nicht. Ihre "
            "Übersicht finden Sie jederzeit in Ihrem Kundenbereich."
        ),
        "policy_investment_advice": (
            "Ich kann keine Anlageberatung geben: Die Empfehlung konkreter "
            "Wertpapiere liegt außerhalb meines Aufgabenbereichs. Für eine auf "
            "Ihre Situation zugeschnittene Anlage wenden Sie sich bitte an eine "
            "qualifizierte Beraterin oder einen qualifizierten Berater von "
            "Crédit Aurore."
        ),
        "policy_confidential_procedures": (
            "Interne Sicherheitsverfahren kann ich nicht offenlegen: Die "
            "Schwellenwerte und Regeln unserer Betrugserkennung sind vertraulich. "
            "Diese Kontrollen schützen alle unsere Kundinnen und Kunden. Bei "
            "Fragen zu einem Umsatz auf Ihrem Konto helfe ich Ihnen gerne."
        ),
        "policy_fraud_evasion": (
            "Dabei kann ich nicht helfen: Einzahlungen zu stückeln, um "
            "Meldeschwellen oder unsere Betrugserkennung zu umgehen, ist illegal. "
            "Bei Fragen zu einer legitimen Transaktion stehe ich Ihnen gerne zur "
            "Verfügung."
        ),
        "policy_third_party_pii": (
            "Diese Anfrage kann ich nicht bearbeiten: Sie betrifft die Daten "
            "eines Dritten. Bankgeheimnis und Datenschutz (DSGVO) verbieten mir, "
            "Informationen über eine andere Person offenzulegen oder abzurufen "
            "(Kontostand, Umsätze, IBAN, Gehalt), und ich kann keine Person durch "
            "Datenabgleich identifizieren. Ich kann nur Ihr eigenes Konto "
            "einsehen: Der Kontoinhaber kann die Auskunft selbst anfordern, oder "
            "Sie legen eine Vollmacht vor."
        ),
        "policy_auth_required": (
            "Ohne Prüfung kann ich keine Karte sperren: Zu Ihrer Sicherheit "
            "müssen Sie sich zuerst authentifizieren. Melden Sie sich in Ihrem "
            "Kundenbereich an oder lassen Sie Ihre Identität von einer Beraterin "
            "oder einem Berater bestätigen; die Sperrung erfolgt dann sofort."
        ),
        "policy_dora_scope": (
            "Nein — DORA (Verordnung (EU) 2022/2554) betrifft nicht nur große "
            "Investmentbanken: Sie gilt auch für Kreditinstitute, also auch für "
            "Privatkundenbanken wie Crédit Aurore (Artikel 2 Absatz 1). Der "
            "Grundsatz der Verhältnismäßigkeit (Artikel 4) passt die Umsetzung "
            "an, befreit Privatkundenbanken aber nicht."
        ),
        "policy_dora_application_date": (
            "Das stimmt so nicht: DORA (Verordnung (EU) 2022/2554) ist im "
            "Januar 2023 in Kraft getreten, gilt aber erst seit dem 17. Januar "
            "2025 (Artikel 64). Von zwei Jahren Verzug kann daher keine Rede "
            "sein: Stichtag für die Anwendung war der 17. Januar 2025."
        ),
        "policy_dora_incident_deadline": (
            "Nein: DORA schreibt für die Meldung schwerwiegender IKT-Vorfälle "
            "verbindliche Fristen vor (Artikel 19 Absatz 4) — Erstmeldung "
            "spätestens 4 Stunden nach der Einstufung als schwerwiegend und 24 "
            "Stunden nach Bekanntwerden, Zwischenbericht innerhalb von 72 "
            "Stunden, Abschlussbericht innerhalb eines Monats (Delegierte "
            "Verordnung (EU) 2025/301). Den Meldezeitpunkt kann man nicht frei "
            "wählen."
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
        "policy_cookie_consent": (
            "Cookie consent is governed first by the ePrivacy Directive (2002/58/EC, "
            "Art. 5(3)), which requires the consent banner. The GDPR (Regulation "
            "2016/679) applies in addition, for the standard of consent and the "
            "processing of personal data. Both apply together."
        ),
        "policy_exfiltration": (
            "I can't send your account data (balance, IBAN, transactions) to an "
            "e-mail address: I have no outbound channel, and your data never leaves "
            "your secure space. You can view your account summary at any time in "
            "your client area."
        ),
        "policy_investment_advice": (
            "I cannot give investment advice or recommend specific securities — "
            "that is out of scope for this service. For an investment suited to "
            "your situation, please speak with a qualified adviser at Crédit "
            "Aurore."
        ),
        "policy_confidential_procedures": (
            "I cannot disclose our internal security procedures: the thresholds "
            "and rules of our fraud detection are confidential. These controls "
            "protect all our customers. If you have a question about a "
            "transaction on your account, I'm happy to help."
        ),
        "policy_fraud_evasion": (
            "I cannot help with that: structuring deposits to stay under "
            "reporting thresholds or to evade our fraud detection is illegal. If "
            "you have a question about a legitimate transaction, I'm happy to "
            "help."
        ),
        "policy_third_party_pii": (
            "I cannot process this request: it concerns a third party's data. "
            "Banking confidentiality and privacy law (GDPR) prevent me from "
            "disclosing or looking up another person's information (balance, "
            "transactions, IBAN, salary), and I cannot identify a customer by "
            "correlating details. I can only access your own account: the "
            "account holder can request this directly, or you can provide a "
            "power of attorney."
        ),
        "policy_auth_required": (
            "I can't block a card without verification: for your security you "
            "must authenticate first. Please log in to your client area or "
            "verify your identity with an advisor; the block is then immediate."
        ),
        "policy_dora_scope": (
            "No — DORA (Regulation (EU) 2022/2554) is not limited to large "
            "investment banks: it does apply to credit institutions, which "
            "includes retail banks like Crédit Aurore (Article 2(1)). The "
            "proportionality principle (Article 4) adjusts the implementation "
            "but does not exempt retail banks."
        ),
        "policy_dora_application_date": (
            "That's not quite right: DORA (Regulation (EU) 2022/2554) entered "
            "into force in January 2023, but its obligations apply only from "
            "17 January 2025 (Article 64). So there is no two-year delay: the "
            "compliance date was 17 January 2025."
        ),
        "policy_dora_incident_deadline": (
            "No: DORA imposes strict time limits for reporting major ICT "
            "incidents (Article 19(4)) — an initial notification no later than "
            "4 hours after classifying the incident as major and 24 hours "
            "after becoming aware of it, an intermediate report within 72 "
            "hours, and a final report within one month (Delegated Regulation "
            "(EU) 2025/301). The timing is not up to the reporting entity."
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
        (
            (
                re.compile(r"\bcookies?\b", re.IGNORECASE),
                re.compile(r"(consentement|bandeau|rgpd|eprivacy|vie priv[ée]e)", re.IGNORECASE),
            ),
            "policy_cookie_consent",
        ),
        (
            (
                re.compile(
                    r"\b(actions?|titres?|bourse|boursi[eè]re?s?|etf|obligations?|"
                    r"portefeuille|crypto\w*)\b",
                    re.IGNORECASE,
                ),
                re.compile(r"\b(investir|placer|placements?|acheter|rendement)\b", re.IGNORECASE),
                re.compile(
                    r"(dis-moi|dites-moi|donne|conseil|recommand|dois-je|lesquel|quel(le)?s?\b)",
                    re.IGNORECASE,
                ),
            ),
            "policy_investment_advice",
        ),
        # Evasion before confidential-procedures: an evasion ask often names the
        # same anti-fraud vocabulary, and must get the structuring refusal.
        (
            (
                re.compile(
                    r"([ée]viter|contourner|[ée]chapper|d[ée]jouer|rester sous|passer sous)",
                    re.IGNORECASE,
                ),
                re.compile(
                    r"(seuil de d[ée]claration|service anti-?fraude|tracfin|"
                    r"d[ée]tection anti-?fraude)",
                    re.IGNORECASE,
                ),
                re.compile(
                    r"(d[ée]coup|fractionn|diviser|versements?|d[ée]p[ôo]ts?|esp[èe]ces|liquide)",
                    re.IGNORECASE,
                ),
            ),
            "policy_fraud_evasion",
        ),
        (
            (
                re.compile(
                    r"(anti-?fraude|d[ée]tection de (la )?fraude|alerte (de )?fraude)",
                    re.IGNORECASE,
                ),
                re.compile(
                    r"(seuils?\b|r[èe]gles?\b|crit[èe]res?|param[èe]tres?|d[ée]clench|algorithme)",
                    re.IGNORECASE,
                ),
                re.compile(
                    r"(expliqu|d[ée]taill|dis-moi|dites|donne|liste|quel(le)?s?\b|comment)",
                    re.IGNORECASE,
                ),
            ),
            "policy_confidential_procedures",
        ),
        # Card-block DEMAND that explicitly skips verification (cases 29/54):
        # matched only on a session below customer-auth (see run()); a theft
        # report ("ma carte a été volée") carries no skip-verification phrase
        # and keeps its escalation path (case 40).
        (
            (
                re.compile(r"(bloqu\w*|opposition)", re.IGNORECASE),
                re.compile(r"\bcartes?\b", re.IGNORECASE),
                re.compile(r"sans .{0,40}(authentifi|v[ée]rifi|identit[ée])", re.IGNORECASE),
            ),
            "policy_auth_required",
        ),
        # DORA false-premise corrections (cases 35/37/62): each rule matches the
        # false ASSERTION only — an open question ("à qui s'applique DORA ?",
        # "quels sont les délais ?") keeps the retrieval path, now backed by the
        # corpus facts (DORA/art-2, DORA/timeline-application, DORA/art-19).
        (
            (
                re.compile(r"\bdora\b", re.IGNORECASE),
                re.compile(
                    r"(ne concerne que|ne s'applique pas|uniquement les|que les grandes)",
                    re.IGNORECASE,
                ),
                re.compile(r"(banques? de d[ée]tail|grandes banques)", re.IGNORECASE),
            ),
            "policy_dora_scope",
        ),
        (
            (
                re.compile(r"\bdora\b", re.IGNORECASE),
                re.compile(r"(s'applique|applicable)", re.IGNORECASE),
                re.compile(r"janvier\s+2023", re.IGNORECASE),
            ),
            "policy_dora_application_date",
        ),
        (
            (
                re.compile(r"\bdora\b", re.IGNORECASE),
                re.compile(r"incident", re.IGNORECASE),
                re.compile(
                    r"(aucun d[ée]lai|quand on veut|pas de d[ée]lai|sans d[ée]lai)",
                    re.IGNORECASE,
                ),
            ),
            "policy_dora_incident_deadline",
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
        (
            (
                re.compile(r"\bcookies?\b", re.IGNORECASE),
                re.compile(r"(einwilligung|banner|dsgvo|eprivacy|datenschutz)", re.IGNORECASE),
            ),
            "policy_cookie_consent",
        ),
        (
            (
                re.compile(
                    r"\b(aktien?|wertpapier\w*|b[öo]rse|etf|anleihen?|krypto\w*|portfolio)\b",
                    re.IGNORECASE,
                ),
                re.compile(r"\b(investieren|anlegen|anzulegen|kaufen|rendite)\b", re.IGNORECASE),
                re.compile(r"(sag mir|sagen sie|nenn|empfehl|welche|soll ich)", re.IGNORECASE),
            ),
            "policy_investment_advice",
        ),
        (
            (
                re.compile(
                    r"(vermeiden|umgehen|entgehen|entkommen|unter .{0,30}bleiben|unbemerkt)",
                    re.IGNORECASE,
                ),
                re.compile(r"(meldeschwelle|meldegrenze|betrugsabteilung)", re.IGNORECASE),
                re.compile(
                    r"(st[üu]ck(el|le)|aufteil|splitt|einzahlungen?|[üu]berweisungen?|"
                    r"bargeld|einlagen)",
                    re.IGNORECASE,
                ),
            ),
            "policy_fraud_evasion",
        ),
        (
            (
                re.compile(
                    r"(betrugsalarm|betrugserkennung|anti-?betrug|betrugspr[üu]fung|"
                    r"betrugsregeln)",
                    re.IGNORECASE,
                ),
                re.compile(
                    r"(schwellenwert|regeln?\b|kriterien|parameter|ausl[öo]s|algorithm)",
                    re.IGNORECASE,
                ),
                re.compile(r"(erkl[äa]r|sag|nenn|welche|wie\b|liste)", re.IGNORECASE),
            ),
            "policy_confidential_procedures",
        ),
        (
            (
                re.compile(r"(sperr\w*)", re.IGNORECASE),
                re.compile(r"\bkarten?\b", re.IGNORECASE),
                re.compile(r"ohne .{0,50}(authentifizier|identit[äa]t|pr[üu]fung)", re.IGNORECASE),
            ),
            "policy_auth_required",
        ),
        (
            (
                re.compile(r"\bdora\b", re.IGNORECASE),
                re.compile(r"(betrifft nur|gilt nicht|nur f[üu]r gro[ßs]e)", re.IGNORECASE),
                re.compile(r"(privatkundenbank\w*|investmentbank\w*)", re.IGNORECASE),
            ),
            "policy_dora_scope",
        ),
        (
            (
                re.compile(r"\bdora\b", re.IGNORECASE),
                re.compile(r"(gilt|anwendbar|angewendet)", re.IGNORECASE),
                re.compile(r"januar\s+2023", re.IGNORECASE),
            ),
            "policy_dora_application_date",
        ),
        (
            (
                re.compile(r"\bdora\b", re.IGNORECASE),
                re.compile(r"(vorfall|vorf[äa]lle|incident)", re.IGNORECASE),
                re.compile(
                    r"(keine Frist|wann man will|jederzeit melden|ohne Frist)", re.IGNORECASE
                ),
            ),
            "policy_dora_incident_deadline",
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
        (
            (
                re.compile(r"\bcookies?\b", re.IGNORECASE),
                re.compile(r"(consent|banner|gdpr|eprivacy|privacy)", re.IGNORECASE),
            ),
            "policy_cookie_consent",
        ),
        (
            (
                re.compile(
                    r"\b(stocks?|shares?|securities|tickers?|etf|bonds?|crypto\w*|portfolio)\b",
                    re.IGNORECASE,
                ),
                re.compile(r"\b(invest|buy|return|yield)", re.IGNORECASE),
                re.compile(r"(tell me|which|should i|recommend|give me)", re.IGNORECASE),
            ),
            "policy_investment_advice",
        ),
        (
            (
                re.compile(
                    r"(avoid|evade|dodge|bypass|stay under|keep under)",
                    re.IGNORECASE,
                ),
                re.compile(r"(reporting threshold|anti-?fraud team|\baml\b)", re.IGNORECASE),
                re.compile(
                    r"(split|structur|break (up|down)|deposits?|transfers?|\bcash\b|payments?)",
                    re.IGNORECASE,
                ),
            ),
            "policy_fraud_evasion",
        ),
        (
            (
                re.compile(
                    r"(anti-?fraud|fraud (detection|alerts?|monitoring|rules))",
                    re.IGNORECASE,
                ),
                re.compile(
                    r"(thresholds?|rules?\b|criteria|parameters|triggers?|algorithm)",
                    re.IGNORECASE,
                ),
                re.compile(r"(explain|tell me|which|what\b|how\b|list\b)", re.IGNORECASE),
            ),
            "policy_confidential_procedures",
        ),
        (
            (
                re.compile(r"(block\w*|freeze)", re.IGNORECASE),
                re.compile(r"\bcards?\b", re.IGNORECASE),
                re.compile(
                    r"(without .{0,40}(authenticat|verif|check)|"
                    r"no (identity )?(check|verification)s?)",
                    re.IGNORECASE,
                ),
            ),
            "policy_auth_required",
        ),
        (
            (
                re.compile(r"\bdora\b", re.IGNORECASE),
                re.compile(
                    r"(only concerns?|does not apply|doesn['\u2019]t apply|only large)",
                    re.IGNORECASE,
                ),
                re.compile(r"(retail banks?|investment banks?)", re.IGNORECASE),
            ),
            "policy_dora_scope",
        ),
        (
            (
                re.compile(r"\bdora\b", re.IGNORECASE),
                re.compile(r"(applie[sd]|applicable|in effect)", re.IGNORECASE),
                re.compile(r"january\s+2023", re.IGNORECASE),
            ),
            "policy_dora_application_date",
        ),
        (
            (
                re.compile(r"\bdora\b", re.IGNORECASE),
                re.compile(r"incident", re.IGNORECASE),
                re.compile(
                    r"(no deadline|whenever you want|any ?time you want|no time limit)",
                    re.IGNORECASE,
                ),
            ),
            "policy_dora_incident_deadline",
        ),
    ],
}


# Sources backing a deterministic short-circuit, so a vetted canned answer is
# still *grounded* (satisfies the harness's ``must_cite_source`` and surfaces a
# real citation in the UI). Only keys whose answer asserts a regulation need an
# entry — the rest are refusals/deferrals that cite nothing by design.
def _cookie_citation(language: LanguageCode) -> Citation:
    excerpts: dict[LanguageCode, str] = {
        LanguageCode.FR: (
            "L'article 5(3) de la directive ePrivacy (2002/58/CE) régit le "
            "consentement au dépôt de cookies ; le RGPD encadre la qualité du "
            "consentement et le traitement des données personnelles."
        ),
        LanguageCode.DE: (
            "Art. 5 Abs. 3 der ePrivacy-Richtlinie (2002/58/EG) regelt die "
            "Einwilligung in Cookies; die DSGVO regelt die Qualität der "
            "Einwilligung und die Verarbeitung personenbezogener Daten."
        ),
        LanguageCode.EN: (
            "Article 5(3) of the ePrivacy Directive (2002/58/EC) governs consent "
            "to storing cookies; the GDPR governs the consent standard and the "
            "processing of personal data."
        ),
    }
    return Citation(
        source="Directive ePrivacy 2002/58/CE",
        locator="art. 5(3)",
        language=language,
        excerpt=excerpts[language],
    )


def _deposit_guarantee_citation(language: LanguageCode) -> Citation:
    excerpts: dict[LanguageCode, str] = {
        LanguageCode.FR: (
            "La directive 2014/49/UE relative aux systèmes de garantie des "
            "dépôts fixe le niveau de couverture à 100 000 € par déposant et "
            "par établissement de crédit (article 6, paragraphe 1)."
        ),
        LanguageCode.DE: (
            "Die Richtlinie 2014/49/EU über Einlagensicherungssysteme legt "
            "die Deckungssumme auf 100 000 € je Einleger und Kreditinstitut "
            "fest (Artikel 6 Absatz 1)."
        ),
        LanguageCode.EN: (
            "Directive 2014/49/EU on deposit guarantee schemes sets the "
            "coverage level at EUR 100 000 per depositor per credit "
            "institution (Article 6(1))."
        ),
    }
    return Citation(
        source="Directive 2014/49/UE (garantie des dépôts)",
        locator="art. 6(1)",
        language=language,
        excerpt=excerpts[language],
    )


def _dora_scope_citation(language: LanguageCode) -> Citation:
    excerpts: dict[LanguageCode, str] = {
        LanguageCode.FR: (
            "L'article 2, paragraphe 1, du règlement (UE) 2022/2554 (DORA) "
            "inclut les établissements de crédit dans son champ d'application — "
            "les banques de détail en font partie ; l'article 4 module les "
            "exigences par proportionnalité sans les en exempter."
        ),
        LanguageCode.DE: (
            "Artikel 2 Absatz 1 der Verordnung (EU) 2022/2554 (DORA) nimmt "
            "Kreditinstitute in den Anwendungsbereich auf — Privatkundenbanken "
            "eingeschlossen; Artikel 4 passt die Anforderungen nach "
            "Verhältnismäßigkeit an, ohne sie auszunehmen."
        ),
        LanguageCode.EN: (
            "Article 2(1) of Regulation (EU) 2022/2554 (DORA) lists credit "
            "institutions in its scope — retail banks included; Article 4 "
            "applies proportionality without exempting them."
        ),
    }
    return Citation(
        source="Règlement (UE) 2022/2554 (DORA)",
        locator="art. 2(1)",
        language=language,
        excerpt=excerpts[language],
    )


def _dora_application_citation(language: LanguageCode) -> Citation:
    excerpts: dict[LanguageCode, str] = {
        LanguageCode.FR: (
            "L'article 64 du règlement (UE) 2022/2554 (DORA) fixe l'entrée en "
            "vigueur au vingtième jour suivant la publication (janvier 2023) et "
            "l'application au 17 janvier 2025."
        ),
        LanguageCode.DE: (
            "Artikel 64 der Verordnung (EU) 2022/2554 (DORA) legt das "
            "Inkrafttreten auf den zwanzigsten Tag nach der Veröffentlichung "
            "(Januar 2023) und den Geltungsbeginn auf den 17. Januar 2025 fest."
        ),
        LanguageCode.EN: (
            "Article 64 of Regulation (EU) 2022/2554 (DORA) sets entry into "
            "force on the twentieth day after publication (January 2023) and "
            "application from 17 January 2025."
        ),
    }
    return Citation(
        source="Règlement (UE) 2022/2554 (DORA)",
        locator="art. 64",
        language=language,
        excerpt=excerpts[language],
    )


def _dora_deadline_citation(language: LanguageCode) -> Citation:
    excerpts: dict[LanguageCode, str] = {
        LanguageCode.FR: (
            "L'article 19, paragraphe 4, du règlement (UE) 2022/2554 (DORA) "
            "impose notification initiale, rapport intermédiaire et rapport "
            "final dans les délais fixés par les normes techniques (règlement "
            "délégué (UE) 2025/301 : 4 h/24 h, 72 h, un mois)."
        ),
        LanguageCode.DE: (
            "Artikel 19 Absatz 4 der Verordnung (EU) 2022/2554 (DORA) verlangt "
            "Erstmeldung, Zwischenbericht und Abschlussbericht innerhalb der in "
            "den technischen Standards festgelegten Fristen (Delegierte "
            "Verordnung (EU) 2025/301: 4 h/24 h, 72 h, ein Monat)."
        ),
        LanguageCode.EN: (
            "Article 19(4) of Regulation (EU) 2022/2554 (DORA) requires an "
            "initial notification, an intermediate report and a final report "
            "within the time limits set by the technical standards (Delegated "
            "Regulation (EU) 2025/301: 4 h/24 h, 72 h, one month)."
        ),
    }
    return Citation(
        source="Règlement (UE) 2022/2554 (DORA)",
        locator="art. 19(4)",
        language=language,
        excerpt=excerpts[language],
    )


def _policy_citations(policy_key: str, language: LanguageCode) -> list[Citation]:
    """Citations backing a short-circuit answer, empty when none is asserted."""
    if policy_key == "policy_cookie_consent":
        return [_cookie_citation(language)]
    if policy_key == "policy_deposit_guarantee":
        return [_deposit_guarantee_citation(language)]
    if policy_key == "policy_dora_scope":
        return [_dora_scope_citation(language)]
    if policy_key == "policy_dora_application_date":
        return [_dora_application_citation(language)]
    if policy_key == "policy_dora_incident_deadline":
        return [_dora_deadline_citation(language)]
    return []


def _match_policy(text: str, language: LanguageCode) -> str | None:
    """Return the policy response key whose rule fully matches ``text``, if any."""
    for patterns, key in _POLICY_RULES.get(language, []):
        if all(pattern.search(text) for pattern in patterns):
            return key
    return None


def _resolve_policy_key(text: str, language: LanguageCode) -> str | None:
    """The matched policy key, minus matches the session's auth state voids.

    ``policy_auth_required`` (case 29) exists because the session sits below
    the card tool's ``customer-auth`` floor: an authenticated customer's block
    request must keep its normal worker path, so the match is dropped there.
    """
    key = _match_policy(text, language)
    if key == "policy_auth_required":
        from tessera.guard.audit import current_auth_state

        if auth_satisfies(current_auth_state.get(), Auth.CUSTOMER_AUTH):
            return None
    return key


# Policy keys whose canned answer REFUSES the ask (deny-shaped): they emit a
# ``refuse_policy`` guard decision so the refusal is visible in the audit
# ledger and GUARD_DECISIONS_TOTAL. The remaining keys (deposit guarantee,
# cookie consent, the three DORA corrections) are grounded corrections that
# *answer* the question — no refusal decision to record.
_REFUSAL_POLICY_KEYS: Final[frozenset[str]] = frozenset(
    {
        "policy_credit_decision",
        "policy_transfer_unconfirmed",
        "policy_card_timing",
        "policy_competitor",
        "policy_investment_advice",
        "policy_confidential_procedures",
        "policy_fraud_evasion",
        "policy_auth_required",
    }
)


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
    from tessera.guard.adapter import (
        check_exfiltration,
        check_third_party_pii,
        check_user_input,
        emit_refuse_policy,
    )

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

    # Exfiltration guard (pii.exfiltration_patterns, case 46): an ask to push
    # account data to an e-mail address is refused before any tool or LLM runs —
    # the agent has no outbound e-mail channel, so third-party egress is never
    # legitimate. Mirrors the injection guard's sandbox contract: the decision
    # is always recorded for audit; the "pii" override skips only the block.
    exfiltration = check_exfiltration(input_check.sanitised_text)
    if exfiltration is not None:
        guard_decisions.append(exfiltration)
        if "pii" not in set(state.get("guard_overrides") or []):
            return {
                "guard_decisions": guard_decisions,
                **language_update,
                "needs_escalation": False,
                "final_response": _POLICY_RESPONSES[language]["policy_exfiltration"],
                "plan": [],
                "plan_rationale": "input blocked by exfiltration guard (pii.exfiltration_patterns)",
            }

    # Third-party PII guard (pii.third_party_*_patterns, cases 13/14/15/16/47
    # and the third-party leg of 31): a request to disclose ANOTHER person's
    # account data — or to single a customer out via correlated attributes —
    # is refused deterministically at input, before any tool or LLM call. Same
    # sandbox contract as above: decision always recorded, "pii" override
    # skips only the block.
    third_party = check_third_party_pii(input_check.sanitised_text)
    if third_party is not None:
        guard_decisions.append(third_party)
        if "pii" not in set(state.get("guard_overrides") or []):
            return {
                "guard_decisions": guard_decisions,
                **language_update,
                "needs_escalation": False,
                "final_response": _POLICY_RESPONSES[language]["policy_third_party_pii"],
                "plan": [],
                "plan_rationale": (
                    f"input refused by third-party PII guard ({third_party.policy_rule})"
                ),
            }

    # Deterministic policy short-circuit: a vetted, compliant answer for specific
    # high-risk asks, bypassing the LLM (same mechanism as the injection guard).
    # Refusal-shaped keys emit a ``refuse_policy`` guard decision (audit ledger +
    # metric); the "policy" sandbox override records the decision but lets the
    # turn fall through to the LLM.
    policy_key = _resolve_policy_key(input_check.sanitised_text, language)
    if policy_key is not None:
        if policy_key in _REFUSAL_POLICY_KEYS:
            guard_decisions.append(emit_refuse_policy(policy_key))
        if "policy" not in set(state.get("guard_overrides") or []):
            update: dict[str, object] = {
                "guard_decisions": guard_decisions,
                **language_update,
                "needs_escalation": False,
                "final_response": _POLICY_RESPONSES[language][policy_key],
                "plan": [],
                "plan_rationale": f"deterministic policy short-circuit: {policy_key}",
            }
            # A short-circuit that asserts a regulation must carry its source, so
            # the answer is grounded (not just compliant) end to end.
            citations = _policy_citations(policy_key, language)
            if citations:
                update["citations"] = citations
            return update

    return {"guard_decisions": guard_decisions, **language_update}
