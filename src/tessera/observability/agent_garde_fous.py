"""Agent Guardrails ("Garde-fous") dashboard payload (reference image 27).

The Garde-fous page governs the rules, filters and protections applied to the
assistant's answers: an active-snapshot bar (as-of-T), a KPI strip (active
rules, covered categories, block rate, blocked incidents, false-positive rate,
tests run), a filterable rules table (category, severity, status, mode,
coverage, last update, last test), three secondary panels (watchlist, quick
actions, coverage by category) and a per-rule detail panel with a Summary /
Configuration / Tests tab set, technical configuration and RBAC access.

This build ships without a live guardrail store, so the payload is a
deterministic reference fixture: values are stable across calls so the page
never "dances" on refetch. Colours/statuses/severities are emitted as keys; the
frontend maps each key to its label colour. Free-text data is verbatim French
with ASCII-only punctuation.
"""

from __future__ import annotations

__all__ = ["compute_agent_garde_fous"]


def _kpi(key: str, label: str, value: str, delta: str, good: bool) -> dict[str, object]:
    return {"key": key, "label": label, "value": value, "delta": delta, "good": good}


def _rule(
    name: str,
    category: str,
    severity: str,
    sev_tone: str,
    mode: str,
    mode_tone: str,
    coverage: int,
    updated: str,
    author: str,
    test_status: str,
    test_tone: str,
) -> dict[str, object]:
    return {
        "name": name,
        "category": category,
        "severity": severity,
        "sev_tone": sev_tone,
        "status": "Active",
        "mode": mode,
        "mode_tone": mode_tone,
        "coverage": coverage,
        "updated": updated,
        "author": author,
        "test_status": test_status,
        "test_tone": test_tone,
    }


def compute_agent_garde_fous() -> dict[str, object]:
    """Return the full Garde-fous dashboard payload (deterministic fixture)."""
    snapshot: dict[str, object] = {
        "tag": "SNAPSHOT ACTIF",
        "label": "Garde-fous a date",
        "updated_label": "Derniere mise a jour",
        "updated": "12/06/2026 07:52",
        "updated_rel": "il y a 30 min",
        "version_label": "Version active",
        "version": "v3.7.2",
        "version_status": "Active",
        "evalset_label": "Jeu d'evaluations",
        "evalset": "Prod Safety Set v2.1",
        "coverage_label": "Couverture regles",
        "coverage": 94,
        "coverage_tone": "Bonne",
        "asof": "Voir a date",
        "compare": "Comparer au snapshot precedent",
    }

    kpis: list[dict[str, object]] = [
        _kpi("rules", "Regles actives", "87", "+4 ce mois", True),
        _kpi("categories", "Categories couvertes", "12 / 13", "+1 ce mois", True),
        _kpi("block", "Taux de blocage", "0,78%", "-0,1 pt vs hier", True),
        _kpi("incidents", "Incidents bloques", "248", "+18 vs hier", True),
        _kpi("falsepos", "Taux de faux positifs", "1,2%", "-0,3 pt vs hier", True),
        _kpi("tests", "Tests executes (30j)", "12 540", "+1 120 vs 30j", True),
    ]

    filters: dict[str, object] = {
        "search": "Rechercher une regle...",
        "selects": [
            {"label": "Categorie", "value": "Toutes"},
            {"label": "Statut", "value": "Tous"},
            {"label": "Severite", "value": "Toutes"},
        ],
        "more": "Filtres",
    }

    columns = [
        "Nom de la regle",
        "Categorie",
        "Severite",
        "Statut",
        "Mode",
        "Couverture",
        "Derniere mise a jour",
        "Dernier test",
    ]
    rows: list[dict[str, object]] = [
        _rule(
            "PII - Blocage direct",
            "Confidentialite",
            "Critique",
            "crit",
            "Blocage",
            "block",
            100,
            "12/06/2026 07:52",
            "Amadou D.",
            "Reussi",
            "good",
        ),
        _rule(
            "Prompt Injection - Detection",
            "Securite",
            "Elevee",
            "high",
            "Blocage",
            "block",
            98,
            "11/06/2026 16:21",
            "Sophie L.",
            "Reussi",
            "good",
        ),
        _rule(
            "Contenu toxique & haineux",
            "Securite",
            "Elevee",
            "high",
            "Blocage",
            "block",
            96,
            "10/06/2026 09:14",
            "Nadia S.",
            "Reussi",
            "good",
        ),
        _rule(
            "Donnees medicales sensibles",
            "Reglementation",
            "Elevee",
            "high",
            "Limitation",
            "limit",
            89,
            "09/06/2026 11:03",
            "Amadou D.",
            "Reussi",
            "good",
        ),
        _rule(
            "Conseil financier non autorise",
            "Securite",
            "Moderee",
            "mod",
            "Blocage",
            "block",
            92,
            "08/06/2026 14:47",
            "Sophie L.",
            "Reussi",
            "good",
        ),
        _rule(
            "Desinformation & hallucination",
            "Qualite",
            "Majeure",
            "maj",
            "Avertissement",
            "warn",
            87,
            "07/06/2026 10:08",
            "Nadia S.",
            "Reussi",
            "good",
        ),
        _rule(
            "Usage restreint - Domaine legal",
            "Reglementation",
            "Faible",
            "low",
            "Avertissement",
            "warn",
            76,
            "06/06/2026 17:32",
            "Amadou D.",
            "Reussi",
            "good",
        ),
    ]

    watch: dict[str, object] = {
        "title": "A surveiller",
        "cta": "Voir toutes les alertes (3)",
        "items": [
            {
                "title": "Taux de blocage en hausse",
                "detail": "+0,3 pt sur 24h - PII Blocage direct",
                "tone": "warn",
            },
            {
                "title": "Faux positifs sur 'Desinformation'",
                "detail": "12 cas signales cette semaine",
                "tone": "warn",
            },
            {
                "title": "Mise a jour requise - Prod Safety Set v3.0",
                "detail": "Nouveau jeu disponible a importer",
                "tone": "info",
            },
        ],
    }

    quick: dict[str, object] = {
        "title": "Actions rapides",
        "items": [
            "Creer un garde-fou",
            "Tester un jeu",
            "Voir les exceptions",
            "Exporter les regles",
        ],
    }

    coverage: dict[str, object] = {
        "title": "Couverture par categorie",
        "items": [
            {"label": "Confidentialite", "pct": 98, "tone": "green"},
            {"label": "Securite", "pct": 95, "tone": "green"},
            {"label": "Reglementation", "pct": 88, "tone": "amber"},
            {"label": "Qualite", "pct": 82, "tone": "amber"},
            {"label": "Ethique", "pct": 71, "tone": "red"},
        ],
    }

    detail: dict[str, object] = {
        "name": "PII - Blocage direct",
        "id": "gf_pii_block_001",
        "status": "Active",
        "tabs": ["Resume", "Configuration", "Tests"],
        "description": (
            "Detecte et bloque les informations d'identification personnelle "
            "(PII) critiques : numeros de carte, emails, telephones, adresses, "
            "numeros d'identification, etc."
        ),
        "fields": [
            {"label": "Categorie", "value": "Confidentialite"},
            {"label": "Severite", "value": "Critique", "tone": "crit"},
            {"label": "Mode", "value": "Blocage"},
            {"label": "Priorite", "value": "1"},
            {"label": "Couverture", "value": "100%"},
            {"label": "Taux de blocage (30j)", "value": "0,42%"},
            {"label": "Taux de faux positifs", "value": "0,3%"},
            {"label": "Derniere mise a jour", "value": "12/06/2026 07:52"},
            {"label": "Derniere revision par", "value": "Amadou D."},
            {"label": "Dernier test", "value": "12/06/2026 07:40", "tone": "good"},
        ],
        "config_title": "Configuration technique",
        "config_cta": "Modifier",
        "config": [
            {"label": "Detecteur principal", "value": "pii-detector-v2"},
            {"label": "Analyse contextuelle", "value": "Activee"},
            {"label": "Seuil de confiance", "value": "0,85"},
            {"label": "Message", "value": "Message standard"},
            {"label": "Journalisation", "value": "Activee"},
            {"label": "Retour utilisateur", "value": "Message standard"},
        ],
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
        "title": "Garde-fous",
        "subtitle": (
            "Gerez les regles, filtres et protections appliques aux reponses de l'assistant."
        ),
        "actions": {"asof": "Voir a date (as-of)", "create": "Creer un garde-fou"},
        "snapshot": snapshot,
        "kpis": kpis,
        "filters": filters,
        "table": {"columns": columns, "rows": rows, "count": "1-7 sur 87 regles", "pages": 13},
        "watch": watch,
        "quick": quick,
        "coverage": coverage,
        "detail": detail,
    }
