"""Agent Evaluations ("Evaluations") dashboard payload (reference image 29).

The Evaluations page measures, analyses and improves the quality of the
assistant's answers: an inner tab strip (overview, eval sets, results,
dimensions, comparisons, errors, versions, exports), an active-snapshot bar
(as-of-T), a KPI strip (global score, success rate, hallucinations, relevance,
source fidelity, set coverage), a filterable evaluations table (type, status,
version, score, success, hallucinations, last run, owner), three secondary
panels (watchlist, quick actions, global-score trend) and a per-evaluation
detail panel with a Summary / Configuration / Results / Activity tab set,
period results and RBAC access.

This build ships without a live evaluation store, so the payload is a
deterministic reference fixture: values are stable across calls so the page
never "dances" on refetch. Colours/statuses are emitted as keys. Free-text data
is verbatim French with ASCII-only punctuation.
"""

from __future__ import annotations

__all__ = ["compute_agent_evaluations"]


def _kpi(
    key: str,
    label: str,
    value: str,
    scale: str,
    note: str,
    note_tone: str,
    delta: str,
    delta_tone: str,
    gauge: int | None = None,
) -> dict[str, object]:
    return {
        "key": key,
        "label": label,
        "value": value,
        "scale": scale,
        "note": note,
        "note_tone": note_tone,
        "delta": delta,
        "delta_tone": delta_tone,
        "gauge": gauge,
    }


def _row(
    name: str,
    type_: str,
    type_tone: str,
    status: str,
    status_tone: str,
    version: str,
    score: str,
    success: str,
    halluc: str,
    last_run: str,
    owner: str,
    tests: str,
) -> dict[str, object]:
    return {
        "name": name,
        "type": type_,
        "type_tone": type_tone,
        "status": status,
        "status_tone": status_tone,
        "version": version,
        "score": score,
        "success": success,
        "halluc": halluc,
        "last_run": last_run,
        "owner": owner,
        "tests": tests,
    }


def compute_agent_evaluations() -> dict[str, object]:
    """Return the full Evaluations dashboard payload (deterministic fixture)."""
    snapshot: dict[str, object] = {
        "tag": "SNAPSHOT ACTIF",
        "label": "Prod Quality Set v2.0",
        "updated_label": "Derniere mise a jour",
        "updated": "12/06/2026 07:42",
        "updated_rel": "il y a 40 min",
        "version_label": "Version active",
        "version": "v2.0",
        "version_status": "Actif",
        "evalset_label": "Jeu d'evaluations",
        "evalset": "1 248 cas",
        "coverage_label": "Couverture set",
        "coverage": 98,
        "coverage_tone": "Bonne",
        "asof": "Voir a date",
        "compare": "Comparer au snapshot precedent",
    }

    kpis: list[dict[str, object]] = [
        _kpi(
            "score",
            "Score global",
            "8,7",
            "/10",
            "Bonne",
            "good",
            "+0,4 vs periode precedente",
            "good",
        ),
        _kpi(
            "success",
            "Taux de reussite",
            "",
            "",
            "Bon",
            "good",
            "+3% vs periode precedente",
            "good",
            gauge=89,
        ),
        _kpi(
            "halluc",
            "Hallucinations",
            "1,6%",
            "",
            "Bon",
            "good",
            "-0,6 pt vs periode precedente",
            "good",
        ),
        _kpi(
            "relevance",
            "Pertinence",
            "9,1",
            "/10",
            "Bonne",
            "good",
            "+0,3 vs periode precedente",
            "good",
        ),
        _kpi(
            "fidelity",
            "Fidelite (sources)",
            "92%",
            "",
            "Bonne",
            "good",
            "+4% vs periode precedente",
            "good",
        ),
        _kpi(
            "coverage",
            "Couverture du set",
            "12 540",
            "",
            "tests executes",
            "muted",
            "98% du set total",
            "muted",
        ),
    ]

    filters: dict[str, object] = {
        "search": "Rechercher une evaluation...",
        "selects": [
            {"label": "Type", "value": "Tous"},
            {"label": "Statut", "value": "Tous"},
            {"label": "Proprietaire", "value": "Tous"},
            {"label": "Etiquette", "value": "Toutes"},
        ],
        "more": "Filtres",
    }

    columns = [
        "Nom de l'evaluation",
        "Type",
        "Statut",
        "Version",
        "Score global",
        "Taux reussite",
        "Hallucinations",
        "Derniere execution",
        "Proprietaire",
        "Tests",
    ]
    rows: list[dict[str, object]] = [
        _row(
            "Prod Quality Set v2.0",
            "Systeme",
            "sys",
            "Actif",
            "good",
            "v2.0",
            "8.7",
            "89%",
            "1.6%",
            "12/06/2026 07:42",
            "Amadou D.",
            "1 248",
        ),
        _row(
            "Safety & Compliance Set v1.3",
            "Systeme",
            "sys",
            "Actif",
            "good",
            "v1.3",
            "9.2",
            "94%",
            "0.4%",
            "11/06/2026 18:20",
            "Sophie L.",
            "980",
        ),
        _row(
            "RAG Quality Set v2.1",
            "Template",
            "tpl",
            "Actif",
            "good",
            "v2.1",
            "9.1",
            "92%",
            "0.8%",
            "10/06/2026 14:05",
            "Nadia S.",
            "864",
        ),
        _row(
            "Agent Performance Set v1.4",
            "Agent",
            "agt",
            "Actif",
            "good",
            "v1.4",
            "8.4",
            "86%",
            "2.1%",
            "09/06/2026 11:32",
            "Claude B.",
            "642",
        ),
        _row(
            "Tonalite & Style Set v1.2",
            "Agent",
            "agt",
            "Actif",
            "good",
            "v1.2",
            "8.6",
            "88%",
            "1.2%",
            "08/06/2026 16:48",
            "Sophie L.",
            "521",
        ),
        _row(
            "Regression Set v3.0",
            "Systeme",
            "sys",
            "Planifie",
            "info",
            "v3.0",
            "-",
            "-",
            "-",
            "Planifie demain",
            "Amadou D.",
            "0",
        ),
        _row(
            "Legacy Quality Set v1.0",
            "Systeme",
            "sys",
            "Inactif",
            "off",
            "v1.0",
            "7.8",
            "74%",
            "5.2%",
            "02/06/2026 09:10",
            "Nadia M.",
            "410",
        ),
        _row(
            "Customer Support Set v3.0",
            "Template",
            "tpl",
            "Actif",
            "good",
            "v3.0",
            "8.9",
            "90%",
            "1.0%",
            "07/06/2026 13:27",
            "Claude B.",
            "688",
        ),
    ]

    watch: dict[str, object] = {
        "title": "A surveiller",
        "cta": "Voir toutes les alertes (3)",
        "items": [
            {
                "title": "Hallucinations en legere hausse",
                "detail": "+0,3 pt sur 7j - Prod Quality",
                "tone": "crit",
            },
            {
                "title": "RAG Quality Set - score en baisse",
                "detail": "-0,2 pt sur 7j",
                "tone": "warn",
            },
            {
                "title": "Echec d'execution - Customer Support",
                "detail": "1 run interrompu hier",
                "tone": "info",
            },
        ],
    }

    quick: dict[str, object] = {
        "title": "Actions rapides",
        "items": [
            "Lancer une evaluation",
            "Comparer versions",
            "Voir les resultats",
            "Gerer les jeux",
        ],
    }

    trend: dict[str, object] = {
        "title": "Tendance du score global",
        "value": "8,7",
        "scale": "/10",
        "legend": "Score global",
        "series": [82, 83, 83, 84, 85, 85, 86, 86, 87, 87],
    }

    detail: dict[str, object] = {
        "name": "Prod Quality Set v2.0",
        "id": "@_eval_prod_001",
        "status": "Actif",
        "tabs": ["Resume", "Configuration", "Resultats", "Activite"],
        "description": (
            "Evaluation principale utilisee en production pour mesurer la "
            "qualite globale des reponses de l'assistant."
        ),
        "fields": [
            {"label": "Type", "value": "Systeme"},
            {"label": "Version active", "value": "v2.0"},
            {"label": "Statut", "value": "Actif", "tone": "good"},
            {"label": "Derniere execution", "value": "12/06/2026 07:42"},
            {"label": "Prochaine execution", "value": "13/06/2026 07:00"},
            {"label": "Modele evalue", "value": "gpt-4o-mini"},
            {"label": "Temperature", "value": "0,2"},
            {"label": "Top p", "value": "0,9"},
            {"label": "Proprietaire", "value": "Amadou D."},
        ],
        "results_title": "Resultats (periode)",
        "results_cta": "Modifier la periode",
        "results": [
            {"label": "Score global", "value": "8,7 / 10"},
            {"label": "Taux de reussite", "value": "89%"},
            {"label": "Hallucinations", "value": "1,6%"},
            {"label": "Pertinence", "value": "9,1 / 10"},
            {"label": "Fidelite (sources)", "value": "92%"},
            {"label": "Securite", "value": "9,4 / 10"},
            {"label": "Completude", "value": "8,8 / 10"},
        ],
        "results_more": "Voir tous les resultats",
        "rbac_title": "Acces RBAC",
        "rbac_cta": "Modifier",
        "rbac": [
            {"role": "ML Engineer", "access": "Lecture"},
            {"role": "Compliance Officer", "access": "Lecture / Ecriture"},
            {"role": "Admin", "access": "Lecture / Ecriture"},
        ],
        "rbac_more": "Voir toutes les permissions (5)",
    }

    return {
        "title": "Evaluations",
        "subtitle": (
            "Mesurez, analysez et ameliorez la qualite des reponses de "
            "l'assistant et des agents."
        ),
        "actions": {"asof": "Voir a date (as-of)", "create": "Creer une evaluation"},
        "subtabs": [
            "Vue d'ensemble",
            "Jeux d'evaluations",
            "Resultats",
            "Dimensions",
            "Comparaisons",
            "Erreurs",
            "Versions & historique",
            "Exports",
        ],
        "snapshot": snapshot,
        "kpis": kpis,
        "filters": filters,
        "table": {"columns": columns, "rows": rows, "count": "1-8 sur 24 evaluations", "pages": 3},
        "watch": watch,
        "quick": quick,
        "trend": trend,
        "detail": detail,
    }
