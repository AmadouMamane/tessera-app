"""Assistant cockpit overview (Assistant page: Chat and Console sub-tabs).

Assembles the payload the operator-facing Assistant page renders. The page has
two sub-tabs that share the same grounded conversation:

* **Chat** -- the clean, customer-style transcript with the cited sources, quick
  actions and a response-feedback panel.
* **Console** -- the same exchange instrumented for review: per-turn latency and
  token cost, the tools called, the guardrails triggered, the response quality
  scores and a real-time execution trace.

The dataset is a deterministic reference fixture (this build ships without a live
session store), so the page never "dances" on refetch. The grounded conversation
(question, answer, sources, guardrail detail, suggestions) is localized to the UI
language so a German operator reviews a German sample; enum-like fields stay as
stable keys the frontend maps to localized labels and colours.
"""

from __future__ import annotations

__all__ = ["compute_assistant_overview"]

_LANG_IDX = {"fr": 0, "de": 1, "en": 2}


def _loc(lang: str, fr: str, de: str, en: str) -> str:
    """Pick the locale variant of an inline string (fr / de / en)."""
    return (fr, de, en)[_LANG_IDX.get(lang, 0)]


def _point(label: str, body: str) -> dict[str, object]:
    return {"label": label, "body": body}


def compute_assistant_overview(lang: str = "fr") -> dict[str, object]:
    """Return the full Assistant overview payload (Chat and Console).

    Args:
        lang: UI language (fr / de / en) for the grounded conversation free-text.

    Returns:
        A JSON-serialisable mapping with the session header, the grounded
        conversation, the session context, the cited sources, the tools called,
        the guardrails triggered, the response quality scores, the execution
        trace, the follow-up suggestions and the console rail KPIs -- everything
        both sub-tabs render, in one document.
    """
    session: dict[str, object] = {
        "id": "sess_7f3e2b19",
        "status": "active",
        "model": "GPT-4o mini",
        "prompt_version": "v5.4.1",
        "sources_snapshot": "snapshot v3.2",
        "guardrails_version": "v3.7.2",
        "language": _loc(lang, "Français", "Deutsch", "English"),
        "trace": "Live",
        "started_at": "14:30:58",
        "replay_at": _loc(lang, "Aujourd'hui, 14:32:18", "Heute, 14:32:18", "Today, 14:32:18"),
    }

    context: dict[str, object] = {
        "user": "alice.martin@acme.com",
        "environment": "Prod",
        "objective": _loc(lang, "Revue conformité", "Konformitaetspruefung", "Compliance review"),
        "tags": [
            _loc(lang, "rgpd", "dsgvo", "gdpr"),
            _loc(lang, "rétention", "aufbewahrung", "retention"),
            _loc(lang, "juridique", "recht", "legal"),
        ],
    }

    answer_points = [
        _point(
            _loc(
                lang,
                "Conservation excessive (art. 5.1.e)",
                "Uebermaessige Speicherung (Art. 5.1.e)",
                "Excessive retention (art. 5.1.e)",
            ),
            _loc(
                lang,
                "garder les données personnelles plus longtemps que nécessaire au "
                "regard des finalités posées.",
                "personenbezogene Daten laenger als fuer die festgelegten Zwecke "
                "erforderlich aufbewahren.",
                "keeping personal data longer than necessary for the stated purposes.",
            ),
        ),
        _point(
            _loc(
                lang,
                "Absence de base légale (art. 6)",
                "Fehlende Rechtsgrundlage (Art. 6)",
                "Missing legal basis (art. 6)",
            ),
            _loc(
                lang,
                "si la finalité n'est pas clairement définie ou si le consentement "
                "est manquant ou non valide.",
                "wenn der Zweck nicht klar definiert ist oder die Einwilligung fehlt "
                "oder ungueltig ist.",
                "if the purpose is not clearly defined or consent is missing or invalid.",
            ),
        ),
        _point(
            _loc(
                lang,
                "Droits des personnes (art. 15-22)",
                "Rechte der betroffenen Personen (Art. 15-22)",
                "Data-subject rights (art. 15-22)",
            ),
            _loc(
                lang,
                "difficulté à répondre aux demandes d'accès, de rectification ou "
                "d'effacement dans les délais.",
                "Schwierigkeiten, Auskunfts-, Berichtigungs- oder Loeschanfragen "
                "fristgerecht zu beantworten.",
                "difficulty meeting access, rectification or erasure requests on time.",
            ),
        ),
        _point(
            _loc(
                lang,
                "Sécurité et confidentialité (art. 32)",
                "Sicherheit und Vertraulichkeit (Art. 32)",
                "Security and confidentiality (art. 32)",
            ),
            _loc(
                lang,
                "augmentation de la surface d'exposition en cas de fuite ou de "
                "compromission des conversations.",
                "groessere Angriffsflaeche bei Leck oder Kompromittierung der "
                "Konversationen.",
                "a larger exposure surface in case of leakage or compromise of the "
                "conversations.",
            ),
        ),
        _point(
            _loc(
                lang,
                "Transferts hors UE (art. 44+)",
                "Uebermittlungen ausserhalb der EU (Art. 44+)",
                "Transfers outside the EU (art. 44+)",
            ),
            _loc(
                lang,
                "risques si les conversations sont stockées ou répliquées hors UE "
                "sans garanties adéquates.",
                "Risiken, wenn Konversationen ohne angemessene Garantien ausserhalb "
                "der EU gespeichert oder repliziert werden.",
                "risks if conversations are stored or replicated outside the EU "
                "without adequate safeguards.",
            ),
        ),
    ]

    messages: list[dict[str, object]] = [
        {
            "role": "user",
            "time": "14:31:02",
            "text": _loc(
                lang,
                "Quels sont les risques de non-conformité au RGPD liés à la "
                "rétention des conversations utilisateur dans notre assistant ?",
                "Welche DSGVO-Konformitaetsrisiken bestehen bei der Aufbewahrung der "
                "Nutzerkonversationen in unserem Assistenten?",
                "What are the GDPR non-compliance risks tied to retaining user "
                "conversations in our assistant?",
            ),
        },
        {
            "role": "assistant",
            "time": "14:31:07",
            "latency": "12.4 s",
            "tokens": "1.2k tokens",
            "intro": _loc(
                lang,
                "Les principaux risques de non-conformité au RGPD liés à la "
                "rétention des conversations utilisateur sont :",
                "Die wichtigsten DSGVO-Konformitaetsrisiken bei der Aufbewahrung der "
                "Nutzerkonversationen sind:",
                "The main GDPR non-compliance risks tied to retaining user "
                "conversations are:",
            ),
            "points": answer_points,
            "outro": _loc(
                lang,
                "Il est recommandé d'appliquer une politique de rétention "
                "proportionnée, documentée et automatisée avec journalisation "
                "des suppressions.",
                "Es wird empfohlen, eine verhaeltnismaessige, dokumentierte und "
                "automatisierte Aufbewahrungsrichtlinie mit Protokollierung der "
                "Loeschungen anzuwenden.",
                "It is recommended to apply a proportionate, documented and "
                "automated retention policy with deletion logging.",
            ),
        },
    ]

    sources: list[dict[str, object]] = [
        {
            "title": _loc(
                lang,
                "Politique de rétention des données v2.3",
                "Datenaufbewahrungsrichtlinie v2.3",
                "Data retention policy v2.3",
            )
        },
        {
            "title": _loc(
                lang,
                "Registre des traitements - Assistant",
                "Verarbeitungsverzeichnis - Assistent",
                "Processing register - Assistant",
            )
        },
        {"title": _loc(lang, "RGPD - Article 5", "DSGVO - Artikel 5", "GDPR - Article 5")},
        {
            "title": _loc(
                lang,
                "Guide CNIL - Conservation des données",
                "CNIL-Leitfaden - Datenaufbewahrung",
                "CNIL guide - Data retention",
            )
        },
    ]

    tools: list[dict[str, object]] = [
        {"name": "search_policy"},
        {"name": "privacy_knowledge_base"},
        {"name": "compliance_checker"},
    ]

    guardrails: list[dict[str, object]] = [
        {
            "name": "PII Output Guard",
            "detail": _loc(
                lang,
                "Masquage de mail(s) et d'identifiant(s) détecté dans la réponse.",
                "Maskierung von E-Mail(s) und Kennung(en) in der Antwort erkannt.",
                "Masking of email(s) and identifier(s) detected in the response.",
            ),
            "level": "warn",
        },
    ]

    quality: list[dict[str, object]] = [
        {"key": "pertinence", "value": 9.4},
        {"key": "exactitude", "value": 9.1},
        {"key": "completude", "value": 8.8},
    ]

    trace: list[dict[str, object]] = [
        {"key": "reception", "done": True},
        {"key": "analyse", "done": True},
        {"key": "sources", "done": True},
        {"key": "outils", "done": True},
        {"key": "gardefous", "done": True},
        {"key": "generation", "done": True},
    ]

    suggestions = [
        _loc(
            lang,
            "Quelle est notre politique de rétention actuelle ?",
            "Wie lautet unsere aktuelle Aufbewahrungsrichtlinie?",
            "What is our current retention policy?",
        ),
        _loc(
            lang,
            "Montre-moi le registre des traitements",
            "Zeige mir das Verarbeitungsverzeichnis",
            "Show me the processing register",
        ),
        _loc(
            lang,
            "Quels sont les droits des personnes concernées ?",
            "Welche Rechte haben die betroffenen Personen?",
            "What are the data-subject rights?",
        ),
    ]

    rail_kpis: list[dict[str, object]] = [
        {"key": "sla", "value": "98.6%"},
        {"key": "mttr", "value": "23m 41s"},
    ]

    return {
        "session": session,
        "context": context,
        "messages": messages,
        "sources": sources,
        "tools": tools,
        "guardrails": guardrails,
        "quality": quality,
        "trace": trace,
        "suggestions": suggestions,
        "rail_kpis": rail_kpis,
        "tenant": "Tessera Ops",
    }
