"""Assistant cockpit overview (Assistant page: Chat and Console sub-tabs).

Assembles the payload the operator-facing Assistant page renders. The page has
two sub-tabs that share the same grounded conversation:

* **Chat** -- the clean, customer-style transcript with the cited sources, quick
  actions and a response-feedback panel.
* **Console** -- the same exchange instrumented for review: per-turn latency and
  token cost, the tools called, the guardrails triggered, the response quality
  scores and a real-time execution trace.

The dataset is a deterministic reference fixture (this build ships without a live
session store), so the page never "dances" on refetch. Free text (the question,
the answer, source and tool names) is verbatim French product data; enum-like
fields are exposed as stable keys the frontend maps to localized labels and
colours.
"""

from __future__ import annotations

__all__ = ["compute_assistant_overview"]


def _point(label: str, body: str) -> dict[str, object]:
    return {"label": label, "body": body}


def compute_assistant_overview() -> dict[str, object]:
    """Return the full Assistant overview payload (Chat and Console).

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
        "language": "Francais",
        "trace": "Live",
        "started_at": "14:30:58",
        "replay_at": "Aujourd'hui, 14:32:18",
    }

    context: dict[str, object] = {
        "user": "alice.martin@acme.com",
        "environment": "Prod",
        "objective": "Revue conformite",
        "tags": ["rgpd", "retention", "juridique"],
    }

    answer_points = [
        _point(
            "Conservation excessive (art. 5.1.e)",
            "garder les donnees personnelles plus longtemps que necessaire au "
            "regard des finalites posees.",
        ),
        _point(
            "Absence de base legale (art. 6)",
            "si la finalite n'est pas clairement definie ou si le consentement "
            "est manquant ou non valide.",
        ),
        _point(
            "Droits des personnes (art. 15-22)",
            "difficulte a repondre aux demandes d'acces, de rectification ou "
            "d'effacement dans les delais.",
        ),
        _point(
            "Securite et confidentialite (art. 32)",
            "augmentation de la surface d'exposition en cas de fuite ou de "
            "compromission des conversations.",
        ),
        _point(
            "Transferts hors UE (art. 44+)",
            "risques si les conversations sont stockees ou repliquees hors UE "
            "sans garanties adequates.",
        ),
    ]

    messages: list[dict[str, object]] = [
        {
            "role": "user",
            "time": "14:31:02",
            "text": (
                "Quels sont les risques de non-conformite au RGPD lies a la "
                "retention des conversations utilisateur dans notre assistant ?"
            ),
        },
        {
            "role": "assistant",
            "time": "14:31:07",
            "latency": "12.4 s",
            "tokens": "1.2k tokens",
            "intro": (
                "Les principaux risques de non-conformite au RGPD lies a la "
                "retention des conversations utilisateur sont :"
            ),
            "points": answer_points,
            "outro": (
                "Il est recommande d'appliquer une politique de retention "
                "proportionnee, documentee et automatisee avec journalisation "
                "des suppressions."
            ),
        },
    ]

    sources: list[dict[str, object]] = [
        {"title": "Politique de retention des donnees v2.3"},
        {"title": "Registre des traitements - Assistant"},
        {"title": "RGPD - Article 5"},
        {"title": "Guide CNIL - Conservation des donnees"},
    ]

    tools: list[dict[str, object]] = [
        {"name": "search_policy"},
        {"name": "privacy_knowledge_base"},
        {"name": "compliance_checker"},
    ]

    guardrails: list[dict[str, object]] = [
        {
            "name": "PII Output Guard",
            "detail": "Masquage de mail(s) et d'identifiant(s) detecte dans la reponse.",
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
        "Quelle est notre politique de retention actuelle ?",
        "Montre-moi le registre des traitements",
        "Quels sont les droits des personnes concernes ?",
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
