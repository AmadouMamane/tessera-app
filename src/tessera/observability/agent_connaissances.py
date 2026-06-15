"""Agent Knowledge ("Connaissances") dashboard payload (reference image 01).

The Connaissances page lists the knowledge sources the agent is grounded on: a
KPI strip (attached sources, query coverage, freshness, citation rate, retrieval
hit-rate), a filterable sources table (type, status, coverage, freshness,
citation rate) and a detail panel for the selected source with a Usage /
Grounded answers / Settings tab set, an at-a-glance usage block, the latest
grounded answers and per-agent actions.

This build ships without a live knowledge-analytics store, so the payload is a
deterministic reference fixture: values are stable across calls so the page
never "dances" on refetch. Colours/statuses are emitted as keys; the frontend
maps each key to its label colour. Free-text data is verbatim French with
ASCII-only punctuation.
"""

from __future__ import annotations

__all__ = ["compute_agent_connaissances"]


def _kpi(key: str, label: str, value: str, series: list[int]) -> dict[str, object]:
    return {"key": key, "label": label, "value": value, "series": series}


def _row(
    name: str,
    path: str,
    type_: str,
    status: str,
    status_tone: str,
    coverage: int | None,
    freshness: str,
    citation: str,
) -> dict[str, object]:
    return {
        "name": name,
        "path": path,
        "type": type_,
        "status": status,
        "status_tone": status_tone,
        "coverage": coverage,
        "freshness": freshness,
        "citation": citation,
    }


def compute_agent_connaissances() -> dict[str, object]:
    """Return the full Connaissances dashboard payload (deterministic fixture)."""
    kpis: list[dict[str, object]] = [
        _kpi("sources", "Sources rattachees", "12", [9, 10, 10, 11, 11, 12, 12]),
        _kpi("coverage", "Couverture des requetes", "91%", [82, 84, 86, 87, 88, 90, 91]),
        _kpi("freshness", "Fraicheur", "2 j", [4, 3, 3, 2, 2, 2, 2]),
        _kpi("citation", "Taux de citation", "87%", [79, 80, 82, 83, 85, 86, 87]),
        _kpi("hitrate", "Hit-rate retrieval", "94%", [88, 89, 90, 91, 92, 93, 94]),
    ]

    filters: dict[str, object] = {
        "search": "Rechercher une source rattachee...",
        "selects": [
            {"label": "Statut", "value": "Tous"},
            {"label": "Type", "value": "Tous"},
            {"label": "Periode", "value": "30 derniers jours"},
        ],
        "more": "Filtres",
    }

    columns = ["Source", "Type", "Statut", "Couverture", "Fraicheur", "Taux de citation"]
    rows: list[dict[str, object]] = [
        _row(
            "Guide Onboarding Clients",
            "/docs/onboarding/",
            "PDF",
            "Active",
            "good",
            98,
            "Aujourd'hui",
            "92%",
        ),
        _row("FAQ Produits & Services", "/faq/", "Confluence", "Active", "good", 95, "1 j", "89%"),
        _row("Conditions Generales", "/legal/cgv.pdf", "PDF", "Active", "good", 90, "3 j", "84%"),
        _row(
            "Base de connaissances interne",
            "/kb/interne/",
            "SharePoint",
            "Active",
            "good",
            90,
            "1 j",
            "88%",
        ),
        _row("Politiques & Procedures", "/policies/", "PDF", "Active", "good", 88, "7 j", "81%"),
        _row(
            "Catalogue Produits",
            "/catalog/produits/",
            "Base de donnees",
            "Active",
            "good",
            96,
            "1 j",
            "78%",
        ),
        _row(
            "Tickets resolus (anonymises)",
            "/tickets/resolus/",
            "API",
            "Active",
            "good",
            75,
            "-",
            "72%",
        ),
        _row("Reglementation", "/regulation/", "Web", "Active", "good", 89, "-", "80%"),
        _row(
            "Communiques officiels", "/communiques/", "Web", "Desactivee", "off", None, "12 j", "-"
        ),
    ]

    detail: dict[str, object] = {
        "name": "Guide Onboarding Clients",
        "status": "Active",
        "status_tone": "good",
        "tabs": ["Usage", "Reponses ancrees", "Parametres"],
        "summary_title": "Resume",
        "summary": (
            "Guide complet du processus d'onboarding des nouveaux clients, "
            "incluant les etapes cles, documents requis et bonnes pratiques."
        ),
        "usage_title": "Utilisation par cet agent",
        "usage": [
            {"label": "Taux de citation", "value": "92%"},
            {"label": "Couverture des requetes", "value": "98%"},
            {"label": "Derniere utilisation", "value": "Aujourd'hui a 10:42"},
            {"label": "Reponses ancrees (30 j)", "value": "412"},
        ],
        "answers_title": "Dernieres reponses ancrees citees",
        "answers": [
            {
                "text": "Quelles sont les etapes de l'onboarding client ?",
                "time": "Aujourd'hui 10:31",
            },
            {"text": "Quels documents sont requis pour creer un compte ?", "time": "Hier 16:02"},
            {
                "text": "Quel est le delai pour le contrat signe par le client ?",
                "time": "Hier 11:47",
            },
        ],
        "actions_title": "Actions",
        "toggle_label": "Active pour cet agent",
        "toggle_on": True,
        "detach": "Detacher de l'agent",
        "full_sheet": "Voir la fiche complete dans Sources & memoire",
    }

    return {
        "title": "Connaissances",
        "subtitle": "Les sources sur lesquelles cet agent est ancre.",
        "actions": {
            "manage": "Gerer le catalogue",
            "memory": "Sources & memoire",
            "attach": "Rattacher une source",
        },
        "kpis": kpis,
        "filters": filters,
        "table": {"columns": columns, "rows": rows, "count": "1-9 sur 9 sources"},
        "detail": detail,
    }
