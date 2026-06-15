"""Agent Prompts ("Prompts") dashboard payload (reference image 28).

The Prompts page manages the system prompts, templates and instructions used by
the assistant and its agents: an inner tab strip (overview, templates, versions,
variables, tests, simulations, playground), an active-snapshot bar (as-of-T), a
KPI strip (active prompts, templates, success rate, tests run, average quality,
critical failures), a filterable prompts table (type, status, version, quality,
owner, tests), three secondary panels (watchlist, quick actions, quality by
type) and a per-prompt detail panel with a Summary / Configuration / Tests /
Activity tab set, tags, technical configuration, RBAC access and provenance.

This build ships without a live prompt store, so the payload is a deterministic
reference fixture: values are stable across calls so the page never "dances" on
refetch. Colours/statuses are emitted as keys. Free-text data is verbatim French
with ASCII-only punctuation.
"""

from __future__ import annotations

__all__ = ["compute_agent_prompts"]


def _kpi(
    key: str, label: str, value: str, delta: str, good: bool, gauge: int | None = None
) -> dict[str, object]:
    return {
        "key": key,
        "label": label,
        "value": value,
        "delta": delta,
        "good": good,
        "gauge": gauge,
    }


def _row(
    name: str,
    type_: str,
    type_tone: str,
    status: str,
    status_tone: str,
    version: str,
    quality: str,
    quality_tone: str,
    updated: str,
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
        "quality": quality,
        "quality_tone": quality_tone,
        "updated": updated,
        "owner": owner,
        "tests": tests,
    }


def compute_agent_prompts() -> dict[str, object]:
    """Return the full Prompts dashboard payload (deterministic fixture)."""
    snapshot: dict[str, object] = {
        "tag": "SNAPSHOT ACTIF",
        "label": "Prompts a date",
        "updated_label": "Derniere mise a jour",
        "updated": "12/06/2026 08:05",
        "updated_rel": "il y a 18 min",
        "version_label": "Version active",
        "version": "v5.4.1",
        "version_status": "Active",
        "evalset_label": "Jeu d'evaluations",
        "evalset": "Prompt Quality Set v2.0",
        "coverage_label": "Couverture prompts",
        "coverage": 92,
        "coverage_tone": "Bonne",
        "asof": "Voir a date",
        "compare": "Comparer au snapshot precedent",
    }

    kpis: list[dict[str, object]] = [
        _kpi("prompts", "Prompts actifs", "56", "+3 ce mois", True),
        _kpi("templates", "Templates", "18", "+2 ce mois", True),
        _kpi("success", "Taux de succes", "Bonne", "", True, gauge=93),
        _kpi("tests", "Tests executes (30j)", "8 742", "+1 234 vs 30j precedents", True),
        _kpi("quality", "Qualite moyenne", "9,2 /10", "Bonne", True),
        _kpi("failures", "Echecs critiques (30j)", "24", "-18 vs 30j precedents", True),
    ]

    filters: dict[str, object] = {
        "search": "Rechercher un prompt ou un tag...",
        "selects": [
            {"label": "Type", "value": "Tous"},
            {"label": "Statut", "value": "Tous"},
            {"label": "Proprietaire", "value": "Tous"},
            {"label": "Etiquette", "value": "Toutes"},
        ],
        "more": "Filtres",
    }

    columns = [
        "Nom du prompt",
        "Type",
        "Statut",
        "Version",
        "Qualite",
        "Derniere mise a jour",
        "Proprietaire",
        "Tests (30j)",
    ]
    rows: list[dict[str, object]] = [
        _row(
            "Assistant - Systeme",
            "Systeme",
            "sys",
            "Actif",
            "good",
            "v5.4.1",
            "9.4",
            "good",
            "12/06/2026 08:05",
            "Amadou D.",
            "2 134",
        ),
        _row(
            "Reponse structuree",
            "Template",
            "tpl",
            "Actif",
            "good",
            "v3.2",
            "9.1",
            "good",
            "11/06/2026 14:22",
            "Sophie L.",
            "1 847",
        ),
        _row(
            "RAG contextuel",
            "Template",
            "tpl",
            "Actif",
            "good",
            "v2.5",
            "9.0",
            "good",
            "10/06/2026 09:51",
            "Sophie L.",
            "1 320",
        ),
        _row(
            "Agent - Recommandation",
            "Agent",
            "agt",
            "Actif",
            "good",
            "v1.8",
            "8.8",
            "warn",
            "09/06/2026 16:04",
            "Nadia S.",
            "964",
        ),
        _row(
            "Resume executif",
            "Agent",
            "agt",
            "Actif",
            "good",
            "v4.1",
            "9.2",
            "good",
            "08/06/2026 11:38",
            "Claude B.",
            "742",
        ),
        _row(
            "Agent - Extraction PII",
            "Fonction",
            "fct",
            "Actif",
            "good",
            "v2.0",
            "9.5",
            "good",
            "07/06/2026 10:12",
            "Sophie L.",
            "688",
        ),
        _row(
            "Agent - Reformulation",
            "Agent",
            "agt",
            "Actif",
            "good",
            "v1.6",
            "8.6",
            "warn",
            "06/06/2026 15:47",
            "Nadia S.",
            "521",
        ),
        _row(
            "Assistant - Tonalite IA",
            "Systeme",
            "sys",
            "Desactive",
            "off",
            "v0.9",
            "-",
            "mut",
            "05/06/2026 09:20",
            "Nadia M.",
            "104",
        ),
    ]

    watch: dict[str, object] = {
        "title": "A surveiller",
        "cta": "Voir toutes les alertes (3)",
        "items": [
            {
                "title": "Echecs critiques en hausse",
                "detail": "+6 sur 24h - Agent Recommandation",
                "tone": "crit",
            },
            {
                "title": "Qualite moyenne en baisse",
                "detail": "-0,2 pt sur 7j - Agent Reformulation",
                "tone": "warn",
            },
            {
                "title": "Tests en attente d'execution",
                "detail": "3 prompts non testes cette semaine",
                "tone": "info",
            },
        ],
    }

    quick: dict[str, object] = {
        "title": "Actions rapides",
        "items": [
            "Tester un prompt",
            "Comparer versions",
            "Creer un template",
            "Ouvrir Playground",
        ],
    }

    by_type: dict[str, object] = {
        "title": "Qualite par type",
        "cta": "Voir le detail",
        "items": [
            {"label": "Systeme", "value": "9.5", "pct": 95, "tone": "green"},
            {"label": "Template", "value": "9.2", "pct": 92, "tone": "green"},
            {"label": "Agent", "value": "8.9", "pct": 89, "tone": "amber"},
            {"label": "Fonction", "value": "9.1", "pct": 91, "tone": "green"},
        ],
    }

    detail: dict[str, object] = {
        "name": "Assistant - Systeme",
        "id": "@_prn_sys_001",
        "status": "Actif",
        "tabs": ["Resume", "Configuration", "Tests", "Activite"],
        "description": (
            "Prompt systeme principal de l'assistant. Definit le comportement "
            "global, les instructions et les regles de reponse."
        ),
        "fields": [
            {"label": "Type", "value": "Systeme"},
            {"label": "Version active", "value": "v5.4.1"},
            {"label": "Statut", "value": "Actif", "tone": "good"},
            {"label": "Derniere mise a jour", "value": "12/06/2026 08:05"},
            {"label": "Proprietaire", "value": "Amadou D."},
        ],
        "tags_label": "Tags",
        "tags": ["systeme", "principal", "assistant"],
        "config_title": "Configuration technique",
        "config_cta": "Modifier",
        "config": [
            {"label": "Modele cible", "value": "gpt-4o"},
            {"label": "Max tokens", "value": "2 048"},
            {"label": "Top p", "value": "0,9"},
            {"label": "Recurrence cache", "value": "Active (1h)"},
            {"label": "Format", "value": "FR, EN"},
        ],
        "rbac_title": "Acces RBAC",
        "rbac_cta": "Modifier",
        "rbac": [
            {"role": "ML Engineer", "access": "Lecture / Ecriture"},
            {"role": "Compliance Officer", "access": "Lecture"},
            {"role": "Admin", "access": "Lecture / Ecriture"},
        ],
        "rbac_more": "Voir toutes les permissions (5)",
        "info_title": "Informations",
        "info": [
            {"label": "Cree le", "value": "15/04/2026 10:21"},
            {"label": "Cree par", "value": "Amadou D."},
            {"label": "Modifie par", "value": "Sophie L."},
        ],
    }

    footer: list[dict[str, object]] = [
        {"label": "Source de verite", "value": "YAML / Git"},
        {"label": "Environnement", "value": "Production"},
        {"label": "Region", "value": "Europe (Paris) (UTC+2)"},
        {"label": "SOC", "value": "Connecte"},
    ]

    return {
        "title": "Prompts",
        "subtitle": (
            "Gerez les prompts systemes, templates et instructions utilises par "
            "l'assistant et les agents."
        ),
        "actions": {"asof": "Voir a date (as-of)", "create": "Creer un prompt"},
        "subtabs": [
            "Vue d'ensemble",
            "Templates",
            "Versions & historique",
            "Variables",
            "Tests & qualite",
            "Simulations",
            "Playground",
        ],
        "snapshot": snapshot,
        "kpis": kpis,
        "filters": filters,
        "table": {"columns": columns, "rows": rows, "count": "1-8 sur 56 prompts", "pages": 7},
        "watch": watch,
        "quick": quick,
        "by_type": by_type,
        "detail": detail,
        "footer": footer,
    }
