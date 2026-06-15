"""Agent Console (Debug) payload (reference image agent-console-normative).

The Console is the operator's interactive debug surface for a single agent
session: a status sub-bar (session id, model, prompt/sources/guardrails
versions, trace mode), a live conversation transcript on the left, and an
inspector on the right with two service-level KPIs (SLA, MTTR), a tabbed
inspector (Contexte / Sources / Outils / Garde-fous / Trace) and, under the
Contexte tab, the quality scorecard, the sources used, the tools called, the
triggered guardrails and the real-time trace of the last answer.

This build ships without a live agent-debug store, so the payload is a
deterministic reference fixture: values are stable across calls so the page
never "dances" on refetch. Colours/statuses are emitted as keys; the frontend
maps each key to its label colour. Free-text data (titles, messages) is
verbatim French with ASCII-only punctuation.
"""

from __future__ import annotations

__all__ = ["compute_agent_console"]


def compute_agent_console() -> dict[str, object]:
    """Return the full Console (Debug) payload (deterministic fixture)."""
    status: dict[str, object] = {
        "session_id": "sess_7f3e2b19",
        "live": True,
        "fields": [
            {"label": "Modele", "value": "GPT-4o mini"},
            {"label": "Prompt", "value": "v5.4.1"},
            {"label": "Sources", "value": "snapshot v3.2"},
            {"label": "Garde-fous", "value": "v3.7.2"},
            {"label": "Trace", "value": "Live"},
        ],
    }

    transcript: list[dict[str, object]] = [
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
            "latency": "12.4s",
            "intro": (
                "Les principaux risques de non-conformite au RGPD lies a la "
                "retention des conversations utilisateur sont :"
            ),
            "points": [
                {
                    "ref": "art. 5.1.e",
                    "title": "Conservation excessive",
                    "body": (
                        "garder les donnees personnelles plus longtemps que "
                        "necessaire au regard des finalites exposees."
                    ),
                },
                {
                    "ref": "art. 6",
                    "title": "Absence de base legale",
                    "body": (
                        "si la finalite n'est pas clairement definie ou si le "
                        "consentement est manquant/non valide."
                    ),
                },
                {
                    "ref": "art. 15-22",
                    "title": "Droits des personnes",
                    "body": (
                        "difficulte a repondre aux demandes d'acces, de "
                        "rectification ou d'effacement dans les delais."
                    ),
                },
                {
                    "ref": "art. 32",
                    "title": "Securite et confidentialite",
                    "body": "augmentation de la surface d'exposition en cas de fuite.",
                },
                {
                    "ref": "art. 44+",
                    "title": "Transferts hors UE",
                    "body": (
                        "risques si les conversations sont stockees ou "
                        "repliquees sans garanties adequates."
                    ),
                },
            ],
            "closing": (
                "Il est recommande d'appliquer une politique de retention "
                "proportionnee, documentee et avec journalisation des "
                "suppressions."
            ),
            "chips": [
                {"label": "Sources (4)", "kind": "info"},
                {"label": "Outils (3)", "kind": "info"},
                {"label": "Garde-fous (1)", "kind": "warn"},
                {"label": "Ajouter au jeu d'evaluation", "kind": "ghost"},
                {"label": "Creer un incident", "kind": "ghost"},
            ],
        },
    ]

    kpis: list[dict[str, object]] = [
        {"key": "sla", "label": "SLA respecte", "value": "98,6%", "good": True},
        {"key": "mttr", "label": "MTTR (7j)", "value": "23m 41s", "good": True},
    ]

    quality: dict[str, object] = {
        "title": "Qualite & securite de la reponse",
        "badge": "Bon",
        "badge_tone": "good",
        "rows": [
            {"label": "Exactitude", "value": "9.1", "scale": "/10", "tone": "good"},
            {"label": "Completude", "value": "8.8", "scale": "/10", "tone": "good"},
            {"label": "Securite", "value": "9.6", "scale": "/10", "tone": "good"},
        ],
    }

    sources: dict[str, object] = {
        "title": "Sources utilisees (4)",
        "cta": "Voir toutes",
        "rows": [
            {"label": "Politique de retention des donnees v2.3", "scope": "Interne"},
            {"label": "Registre des traitements - Assistant", "scope": "Interne"},
            {"label": "RGPD - Article 5", "scope": "Externe"},
            {"label": "CNIL - Conservation des donnees", "scope": "Externe"},
        ],
    }

    tools: dict[str, object] = {
        "title": "Outils appeles (3)",
        "rows": [
            {"name": "retrieval_policy", "status": "Succes", "tone": "good", "latency": "1.2s"},
            {"name": "rag_knowledge_base", "status": "Succes", "tone": "good", "latency": "2.1s"},
            {"name": "compliance_checker", "status": "Succes", "tone": "good", "latency": "0.8s"},
        ],
    }

    guardrails: dict[str, object] = {
        "title": "Garde-fous declenches (1)",
        "rows": [
            {
                "name": "PII Output Guard",
                "status": "Avertissement",
                "tone": "warn",
                "detail": "Aucun (e-mail) ni d'identifiant(s) detecte dans la reponse.",
            },
        ],
    }

    trace: dict[str, object] = {
        "title": "Trace en temps reel",
        "cta": "Voir la trace complete",
        "rows": [
            {"label": "Analyse de la requete", "value": "0.2s"},
            {"label": "Recherche & classification", "value": "0.4s"},
            {"label": "Recherche de sources", "value": "1.8s"},
            {"label": "Outils executes", "value": "4.1s"},
            {"label": "Generation de la reponse", "value": "3.1s"},
        ],
    }

    footer: dict[str, object] = {
        "started": "Session demarree a 14:30:58",
        "live": True,
        "context": "Plateforme Tessera",
        "language": "Francais",
        "session_id": "sess_7f3e2b19",
    }

    actions: dict[str, object] = {
        "input_placeholder": "Posez votre question a l'assistant...",
        "feedback": ["Utile", "Pas utile"],
        "footer_actions": [
            "Rejouer cette session",
            "Comparer a la version actuelle",
            "Exporter la session",
            "Cloturer la session",
        ],
        "timeline_incidents": "Timeline incidents",
        "new_session": "Nouvelle session",
        "replay": "Relire a T",
    }

    return {
        "status": status,
        "transcript": transcript,
        "kpis": kpis,
        "tabs": ["Contexte", "Sources", "Outils", "Garde-fous", "Trace"],
        "quality": quality,
        "sources": sources,
        "tools": tools,
        "guardrails": guardrails,
        "trace": trace,
        "footer": footer,
        "actions": actions,
        "title": "Console",
        "subtitle": (
            "Interagissez avec l'assistant et observez en detail les traces, "
            "sources, outils et garde-fous."
        ),
    }
