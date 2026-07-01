"""Per-tab payloads for the Conformite command bar (reference images, tab set).

The Conformite overview (``compliance.py``) is derived live from the real runtime
signals. The remaining command-bar tabs -- Cartographie reglementaire, Obligations
& controles, Evaluations, Incidents & exceptions, Purge & retention, Preuves &
attestations, Registre des traitements -- are *governance catalogues*: regulatory
mappings, treatment registers, retention rules, evidence inventories. Exactly like
the security case identifiers, this metadata is fixed, deterministic fixture data
so the page is stable on every refetch.

The payload uses the shared, render-friendly ``CatalogTab`` shape (see
``catalog_tabs``): a KPI strip, a main table with a sticky detail panel, and a
band of bottom sections. The frontend renders each tab from this shape, so adding
or tuning a tab is a pure-data change here.

Display labels are kept in French inside the data (owners, framework names, column
headers and section titles are all part of the regulatory content), matching how
every other catalogue page in Tessera carries its domain text.
"""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from typing import cast

from tessera.observability.catalog_tabs import (
    CatalogTab,
    DetailField,
    DetailList,
    SectionItem,
    TabColumn,
    TabDetail,
    TabKpi,
    TabRow,
    TabSection,
    badge as _badge,
    bar as _bar,
    delta as _delta,
    owner as _owner,
)

__all__ = ["build_tabs"]


# Recurring owners across the regulatory catalogue.
_CLAIRE = _owner("Claire Martin", "AI Governance Lead")
_DAMIEN = _owner("Damien Leroy", "DPO")
_SOPHIE = _owner("Sophie Bernard", "Risk Manager")
_YACINE = _owner("Yacine Sekri", "AI Management")
_NADIA = _owner("Nadia El Idrissi", "CISO")
_THOMAS = _owner("Thomas Klein", "Audit Manager")


def _generer() -> list[str]:
    return ["Voir le detail", "Ouvrir les preuves", "Generer evidence pack"]


# --- Cartographie reglementaire ------------------------------------------


def _tab_mapping() -> CatalogTab:
    kpis = [
        TabKpi("Cadres actifs", "7", tone="good"),
        TabKpi("Obligations mappees", "512", delta="+8.2%", delta_good=True, tone="good"),
        TabKpi("Controles lies", "1 284", delta="+5.1%", delta_good=True),
        TabKpi("Preuves disponibles", "1 105", delta="+3.4%", delta_good=True),
        TabKpi("Obligations a risque", "28", delta="-4.0%", delta_good=True, tone="warn"),
        TabKpi("Evidence pack readiness", "86", unit="%", tone="good"),
    ]
    columns = [
        TabColumn("framework", "Cadre", "text"),
        TabColumn("article", "Article / Domaine", "text"),
        TabColumn("obligations", "Obligations", "delta", "right"),
        TabColumn("controls", "Controles", "delta", "right"),
        TabColumn("signals", "Signaux", "delta", "right"),
        TabColumn("evidence", "Preuves", "bar", "right"),
        TabColumn("owner", "Owner", "owner"),
        TabColumn("status", "Statut", "badge"),
    ]
    rows = [
        TabRow(
            "ai_act",
            {
                "framework": "EU AI Act",
                "article": "Ch. I-VI, Art. 1-85",
                "obligations": _delta("96", "+6%", True),
                "controls": _delta("248", "+5%", True),
                "signals": _delta("312", "+5%", True),
                "evidence": _bar(276, 350),
                "owner": _CLAIRE,
                "status": _badge("Partiel", "warning"),
            },
        ),
        TabRow(
            "rgpd",
            {
                "framework": "RGPD (UE)",
                "article": "Art. 5, 6, 12-22, 32-49",
                "obligations": _delta("124", "+5%", True),
                "controls": _delta("312", "+4%", True),
                "signals": _delta("428", "+6%", True),
                "evidence": _bar(362, 420),
                "owner": _DAMIEN,
                "status": _badge("Conforme", "success"),
            },
        ),
        TabRow(
            "dora",
            {
                "framework": "DORA",
                "article": "Art. 5, 15, 23-28, 30-44",
                "obligations": _delta("84", "+5%", True),
                "controls": _delta("198", "+5%", True),
                "signals": _delta("221", "+4%", True),
                "evidence": _bar(174, 240),
                "owner": _SOPHIE,
                "status": _badge("Partiel", "warning"),
            },
        ),
        TabRow(
            "iso42001",
            {
                "framework": "ISO/IEC 42001",
                "article": "4-10 (SMIA)",
                "obligations": _delta("52", "+2%", True),
                "controls": _delta("168", "+3%", True),
                "signals": _delta("190", "+3%", True),
                "evidence": _bar(162, 190),
                "owner": _YACINE,
                "status": _badge("Conforme", "success"),
            },
        ),
        TabRow(
            "iso27001",
            {
                "framework": "ISO 27001",
                "article": "A.5-A.18",
                "obligations": _delta("112", "+3%", True),
                "controls": _delta("246", "+5%", True),
                "signals": _delta("318", "+4%", True),
                "evidence": _bar(312, 360),
                "owner": _NADIA,
                "status": _badge("Conforme", "success"),
            },
        ),
        TabRow(
            "soc2",
            {
                "framework": "SOC 2 Type II",
                "article": "CC1-CC9",
                "obligations": _delta("18", "+0%", True),
                "controls": _delta("96", "+4%", True),
                "signals": _delta("54", "+5%", True),
                "evidence": _bar(41, 55),
                "owner": _THOMAS,
                "status": _badge("Partiel", "warning"),
            },
        ),
        TabRow(
            "internal",
            {
                "framework": "Politiques internes",
                "article": "Pol. AI-01 a AI-12",
                "obligations": _delta("46", "+3%", True),
                "controls": _delta("128", "+2%", True),
                "signals": _delta("96", "+3%", True),
                "evidence": _bar(88, 110),
                "owner": _CLAIRE,
                "status": _badge("Conforme", "success"),
            },
        ),
    ]
    detail = TabDetail(
        eyebrow="Cadre",
        title="EU AI Act",
        status_label="Partiel",
        status_tone="warning",
        summary="Systemes d'IA a haut risque, GPAI, transparence et surveillance humaine.",
        fields=[
            DetailField("Articles applicables", "Art. 5, 9, 13, 14, 50"),
            DetailField("Obligations mappees", "96 / 96"),
            DetailField("Controles mappes", "248"),
            DetailField("Signaux lies", "312"),
            DetailField("Preuves disponibles", "276 / 350"),
            DetailField("Niveau de risque residuel", "Moyen", "warning"),
            DetailField("Prochaine revue", "30 jun 2026"),
        ],
        lists=[
            DetailList(
                "Dernieres preuves",
                [
                    {"label": "EV-2026-06-0321"},
                    {"label": "EV-2026-06-0312"},
                    {"label": "EV-2026-06-0290"},
                ],
            ),
            DetailList(
                "Owner",
                [{"label": "Claire Martin", "sub": "AI Governance Lead"}],
            ),
        ],
        actions=["Voir toutes les preuves", *_generer()],
    )
    sections = [
        TabSection(
            "Cadres a surveiller",
            "list",
            items=[
                SectionItem(
                    "NIS2 Directive",
                    "Applicable des classification",
                    "T3 2026",
                    "Nouveau",
                    "info",
                ),
                SectionItem(
                    "Data Act",
                    "Applicable partielle",
                    "T4 2026",
                    "Veille",
                    "neutral",
                ),
                SectionItem(
                    "AI Liability Directive",
                    "Proposition en cours",
                    "T1 2027",
                    "Veille",
                    "neutral",
                ),
            ],
            cta="Voir tous les cadres a surveiller",
        ),
        TabSection(
            "Echeances reglementaires",
            "list",
            items=[
                SectionItem(
                    "EU AI Act - Art. 15 (rapport annuel)",
                    "dans 15 jours",
                    "30 jun 2026",
                    badge_tone="warning",
                ),
                SectionItem(
                    "DORA - Art. 28 (test de resilience)",
                    "dans 45 jours",
                    "15 jul 2026",
                    badge_tone="neutral",
                ),
                SectionItem(
                    "RGPD - Article 30 (registre)",
                    "dans 60 jours",
                    "31 jul 2026",
                    badge_tone="neutral",
                ),
            ],
            cta="Voir toutes les echeances",
        ),
        TabSection(
            "Activites recentes",
            "activity",
            items=[
                SectionItem("Preuve EV-2026-06-0321 ajoutee a EU AI Act", "il y a 2 h"),
                SectionItem("Controle CTRL-09 mis a jour (RGPD)", "il y a 5 h"),
                SectionItem("Obligation OBL-1123 marquee conforme (RGPD)", "il y a 8 h"),
                SectionItem("Evaluation ISO 27001 terminee", "hier"),
                SectionItem("Exception EXC-2026-004 creee (DORA)", "hier"),
            ],
            cta="Voir toutes les activites",
        ),
        TabSection(
            "Actions rapides",
            "actions",
            actions=[
                "Lancer une evaluation",
                "Mapper une obligation",
                "Ouvrir les preuves",
                "Generer evidence pack",
            ],
        ),
    ]
    return CatalogTab(
        "Cartographie reglementaire",
        kpis=kpis,
        columns=columns,
        rows=rows,
        detail=detail,
        sections=sections,
    )


# --- Obligations & controles ---------------------------------------------


def _tab_obligations() -> CatalogTab:
    kpis = [
        TabKpi("Obligations actives", "18", tone="good"),
        TabKpi("Controles lies", "284", delta="+6.0%", delta_good=True),
        TabKpi("Couverture", "89", unit="%", delta="+7.2 pp", delta_good=True, tone="good"),
        TabKpi("Signaux par preuve", "3.2", sub="moyenne"),
        TabKpi("Controles degrades", "17", delta="-3.0%", delta_good=True, tone="warn"),
        TabKpi("Evidence pack readiness", "84", unit="%", tone="good"),
    ]
    columns = [
        TabColumn("obligation", "Obligation", "text"),
        TabColumn("framework", "Cadre", "text"),
        TabColumn("control", "Controle principal", "text"),
        TabColumn("signals", "Signaux", "num", "right"),
        TabColumn("evidence", "Preuves", "bar", "right"),
        TabColumn("owner", "Owner", "owner"),
        TabColumn("status", "Statut", "badge"),
        TabColumn("coverage", "Couverture", "pct", "right"),
    ]
    rows = [
        TabRow(
            "art9",
            {
                "obligation": "Art. 9 - Systeme a haut risque",
                "framework": "EU AI Act",
                "control": "C-15.1 - Gestion du risque",
                "signals": "12",
                "evidence": _bar(28, 30),
                "owner": _CLAIRE,
                "status": _badge("Conforme", "success"),
                "coverage": {"pct": 92},
            },
        ),
        TabRow(
            "art10",
            {
                "obligation": "Art. 10 - Qualite des donnees",
                "framework": "EU AI Act",
                "control": "C-13.2 - Gouvernance des donnees",
                "signals": "9",
                "evidence": _bar(18, 26),
                "owner": _DAMIEN,
                "status": _badge("Partiel", "warning"),
                "coverage": {"pct": 78},
            },
        ),
        TabRow(
            "art13",
            {
                "obligation": "Art. 13 - Transparence & info",
                "framework": "EU AI Act",
                "control": "C-05.2 - Transparence utilisateur",
                "signals": "7",
                "evidence": _bar(14, 22),
                "owner": _SOPHIE,
                "status": _badge("Partiel", "warning"),
                "coverage": {"pct": 71},
            },
        ),
        TabRow(
            "art5",
            {
                "obligation": "Art. 5 - Principes (a-f)",
                "framework": "RGPD",
                "control": "C-08.2 - Minimisation",
                "signals": "14",
                "evidence": _bar(31, 33),
                "owner": _YACINE,
                "status": _badge("Conforme", "success"),
                "coverage": {"pct": 95},
            },
        ),
        TabRow(
            "art30",
            {
                "obligation": "Art. 30 - Registre des activites",
                "framework": "RGPD",
                "control": "C-30.1 - Tenue du registre",
                "signals": "6",
                "evidence": _bar(24, 26),
                "owner": _NADIA,
                "status": _badge("Conforme", "success"),
                "coverage": {"pct": 93},
            },
        ),
        TabRow(
            "dora28",
            {
                "obligation": "DORA - Art. 28 (sous-traitance TIC)",
                "framework": "DORA",
                "control": "C-DORA.1 - Risques TIC",
                "signals": "8",
                "evidence": _bar(12, 20),
                "owner": _THOMAS,
                "status": _badge("Partiel", "warning"),
                "coverage": {"pct": 64},
            },
        ),
        TabRow(
            "isoA6",
            {
                "obligation": "ISO 27001 - A.6.1.3",
                "framework": "ISO 27001",
                "control": "C-06.1 - Roles & responsabilites",
                "signals": "5",
                "evidence": _bar(21, 24),
                "owner": _NADIA,
                "status": _badge("Conforme", "success"),
                "coverage": {"pct": 88},
            },
        ),
    ]
    detail = TabDetail(
        eyebrow="Obligation",
        title="Art. 9 - Systeme a haut risque",
        status_label="Conforme",
        status_tone="success",
        summary="Maintenir un systeme de gestion des risques pour l'IA a haut risque.",
        fields=[
            DetailField("Cadre", "EU AI Act"),
            DetailField("Controle principal", "C-15.1 - Gestion du risque"),
            DetailField("Signaux lies", "12"),
            DetailField("Preuves disponibles", "28 / 30"),
            DetailField("Risque residuel", "Faible", "success"),
            DetailField("Prochaine revue", "30 jun 2026"),
            DetailField("Owner", "Claire Martin"),
        ],
        lists=[
            DetailList(
                "Controles mappes (4)",
                [
                    {"label": "C-15.1 - Gestion du risque", "badge": "Conforme", "tone": "success"},
                    {
                        "label": "C-15.2 - Mesures d'attenuation",
                        "badge": "Conforme",
                        "tone": "success",
                    },
                    {"label": "C-09.1 - Surveillance", "badge": "Partiel", "tone": "warning"},
                    {"label": "C-04.1 - Tests adverses", "badge": "Conforme", "tone": "success"},
                ],
            ),
        ],
        actions=_generer(),
    )
    sections = [
        TabSection(
            "Controles a revoir",
            "list",
            items=[
                SectionItem(
                    "C-13.2 - Gouvernance des donnees", badge="Partiel", badge_tone="warning"
                ),
                SectionItem("C-12.2 - Disponibilite", badge="Moyen", badge_tone="warning"),
                SectionItem("C-08.1 - Pseudonymisation", badge="Partiel", badge_tone="warning"),
                SectionItem("C-05.2 - Transparence", badge="Partiel", badge_tone="warning"),
                SectionItem("C-DORA.1 - Risques TIC", badge="Moyen", badge_tone="warning"),
            ],
            cta="Voir tous les controles a revoir",
        ),
        TabSection(
            "Gaps de couverture",
            "list",
            items=[
                SectionItem(
                    "C-13.2 - Donnees", "EU AI Act - Art. 10", badge="Gap", badge_tone="danger"
                ),
                SectionItem(
                    "DORA - Art. 28", "Sous-traitance TIC", badge="Gap", badge_tone="danger"
                ),
                SectionItem("RGPD - Art. 35", "AIPD a finaliser", badge="Gap", badge_tone="danger"),
            ],
            cta="Voir les gaps",
        ),
        TabSection(
            "Activites recentes",
            "activity",
            items=[
                SectionItem("Preuve EV-2026-06-0318 liee a C-15.1", "il y a 1 h"),
                SectionItem("Controle CTRL-13 repasse conforme", "il y a 4 h"),
                SectionItem("Obligation Art. 13 marquee partielle", "il y a 7 h"),
                SectionItem("Revue C-30.1 planifiee", "hier"),
            ],
            cta="Voir toutes les activites",
        ),
        TabSection(
            "Echeances de remediation",
            "list",
            items=[
                SectionItem(
                    "C-13.2 - Plan de remediation",
                    "dans 12 jours",
                    "27 jun 2026",
                    badge_tone="warning",
                ),
                SectionItem(
                    "C-DORA.1 - Test resilience",
                    "dans 30 jours",
                    "15 jul 2026",
                    badge_tone="neutral",
                ),
                SectionItem(
                    "C-05.2 - Transparence UX", "dans 22 jours", "07 jul 2026", badge_tone="neutral"
                ),
            ],
            cta="Voir toutes les echeances",
        ),
    ]
    return CatalogTab(
        "Obligations & controles",
        kpis=kpis,
        columns=columns,
        rows=rows,
        detail=detail,
        sections=sections,
    )


# --- Evaluations ----------------------------------------------------------


def _tab_evaluations() -> CatalogTab:
    kpis = [
        TabKpi("Campagnes d'evaluation", "7", tone="good"),
        TabKpi(
            "Score de conformite", "76", unit="%", delta="+3.0 pp", delta_good=True, tone="warn"
        ),
        TabKpi("Controles passes", "512", delta="+4.0%", delta_good=True),
        TabKpi("Ecarts ouverts", "28", delta="-6.0%", delta_good=True, tone="warn"),
        TabKpi("Preuves rejouees", "105", delta="+5.0%", delta_good=True),
        TabKpi("Evidence pack readiness", "86", unit="%", tone="good"),
    ]
    columns = [
        TabColumn("campaign", "Campagne / domaine", "text"),
        TabColumn("coverage", "Couverture", "pct", "right"),
        TabColumn("score", "Score", "pct", "right"),
        TabColumn("obligations", "Obligations", "num", "right"),
        TabColumn("controls", "Controles", "num", "right"),
        TabColumn("signals", "Signaux", "num", "right"),
        TabColumn("evidence", "Preuves", "bar", "right"),
        TabColumn("owner", "Owner", "owner"),
        TabColumn("status", "Statut", "badge"),
    ]
    rows = [
        TabRow(
            "ai_act",
            {
                "campaign": "EU AI Act",
                "coverage": {"pct": 92},
                "score": {"pct": 82},
                "obligations": "96",
                "controls": "248",
                "signals": "312",
                "evidence": _bar(276, 350),
                "owner": _CLAIRE,
                "status": _badge("Partiel", "warning"),
            },
        ),
        TabRow(
            "rgpd",
            {
                "campaign": "RGPD",
                "coverage": {"pct": 95},
                "score": {"pct": 91},
                "obligations": "124",
                "controls": "312",
                "signals": "428",
                "evidence": _bar(362, 420),
                "owner": _DAMIEN,
                "status": _badge("Conforme", "success"),
            },
        ),
        TabRow(
            "dora",
            {
                "campaign": "DORA",
                "coverage": {"pct": 78},
                "score": {"pct": 69},
                "obligations": "84",
                "controls": "198",
                "signals": "221",
                "evidence": _bar(174, 240),
                "owner": _SOPHIE,
                "status": _badge("Partiel", "warning"),
            },
        ),
        TabRow(
            "iso42001",
            {
                "campaign": "ISO/IEC 42001",
                "coverage": {"pct": 88},
                "score": {"pct": 85},
                "obligations": "52",
                "controls": "168",
                "signals": "190",
                "evidence": _bar(162, 190),
                "owner": _YACINE,
                "status": _badge("Conforme", "success"),
            },
        ),
        TabRow(
            "iso27001",
            {
                "campaign": "ISO 27001",
                "coverage": {"pct": 90},
                "score": {"pct": 87},
                "obligations": "112",
                "controls": "246",
                "signals": "318",
                "evidence": _bar(312, 360),
                "owner": _NADIA,
                "status": _badge("Conforme", "success"),
            },
        ),
        TabRow(
            "internal",
            {
                "campaign": "Politiques internes",
                "coverage": {"pct": 83},
                "score": {"pct": 80},
                "obligations": "46",
                "controls": "128",
                "signals": "96",
                "evidence": _bar(88, 110),
                "owner": _CLAIRE,
                "status": _badge("Partiel", "warning"),
            },
        ),
    ]
    detail = TabDetail(
        eyebrow="Campagne",
        title="EU AI Act",
        status_label="Partiel",
        status_tone="warning",
        summary="Score de conformite 82 % - 11 echecs critiques, 248 controles evalues.",
        fields=[
            DetailField("Score de conformite", "82 %", "warning"),
            DetailField("Controles passes", "230 / 248"),
            DetailField("Echecs critiques", "11", "danger"),
            DetailField("Preuves rejouees", "276"),
            DetailField("Derniere campagne", "11 jun 2026"),
            DetailField("Owner", "Claire Martin"),
        ],
        lists=[
            DetailList(
                "Echecs critiques",
                [
                    {
                        "label": "Art. 10 - Gouvernance des donnees",
                        "badge": "Echec",
                        "tone": "danger",
                    },
                    {"label": "Art. 13 - Transparence", "badge": "Echec", "tone": "danger"},
                    {
                        "label": "Art. 9 - Monitoring post-marche",
                        "badge": "Echec",
                        "tone": "danger",
                    },
                ],
            ),
            DetailList(
                "Preuves liees",
                [
                    {"label": "EV-2026-06-0321"},
                    {"label": "EV-2026-06-0309"},
                ],
            ),
        ],
        actions=["Voir les ecarts", "Ouvrir les preuves", "Generer evidence pack"],
    )
    sections = [
        TabSection(
            "Plan de remediation",
            "donut",
            donut_value=0.0,
            donut_label="28 total",
            items=[
                SectionItem("Critique", value="6", badge_tone="danger"),
                SectionItem("Eleve", value="9", badge_tone="warning"),
                SectionItem("Moyen", value="8", badge_tone="info"),
                SectionItem("Faible", value="5", badge_tone="neutral"),
            ],
            cta="Voir tous les ecarts",
        ),
        TabSection(
            "Tendances des scores",
            "chart",
            series=[
                {
                    "label": "EU AI Act",
                    "color": "#3b82f6",
                    "points": [0.74, 0.76, 0.79, 0.80, 0.82],
                },
                {"label": "RGPD", "color": "#10b981", "points": [0.86, 0.88, 0.90, 0.90, 0.91]},
                {"label": "DORA", "color": "#f59e0b", "points": [0.72, 0.71, 0.70, 0.69, 0.69]},
                {
                    "label": "ISO 27001",
                    "color": "#a78bfa",
                    "points": [0.83, 0.84, 0.86, 0.86, 0.87],
                },
            ],
            cta="Voir toutes les tendances",
        ),
        TabSection(
            "Activites recentes",
            "activity",
            items=[
                SectionItem("Evaluation EU AI Act terminee", "il y a 3 h"),
                SectionItem("Campagne RGPD relancee", "il y a 6 h"),
                SectionItem("Ecart EXC-2026-007 ouvert (DORA)", "hier"),
                SectionItem("Evaluation ISO 27001 completee", "hier"),
            ],
            cta="Voir toutes les activites",
        ),
        TabSection(
            "Cadres en baisse",
            "list",
            items=[
                SectionItem("DORA", "score en baisse", "-4 pp", badge_tone="danger"),
                SectionItem(
                    "Code de conduite IA", "score en baisse", "-3 pp", badge_tone="warning"
                ),
                SectionItem("EU AI Act", "score en baisse", "-2 pp", badge_tone="warning"),
            ],
            cta="Voir tous les cadres",
        ),
    ]
    return CatalogTab(
        "Evaluations",
        kpis=kpis,
        columns=columns,
        rows=rows,
        detail=detail,
        sections=sections,
    )


# --- Incidents & exceptions ----------------------------------------------


def _tab_incidents() -> CatalogTab:
    kpis = [
        TabKpi("Incidents ouverts", "42", delta="-5.0%", delta_good=True, tone="warn"),
        TabKpi("Controles degrades", "27", delta="-3.0%", delta_good=True, tone="warn"),
        TabKpi("Exceptions approuvees", "14", tone="good"),
        TabKpi("Exceptions depassees", "7", delta="+2.0%", delta_good=False, tone="bad"),
        TabKpi("Preuves manquantes", "38", delta="-4.0%", delta_good=True, tone="warn"),
        TabKpi("Evidence pack readiness", "72", unit="%", tone="warn"),
    ]
    columns = [
        TabColumn("id", "ID", "mono"),
        TabColumn("type", "Type", "badge"),
        TabColumn("scope", "Cadre / obligation", "text"),
        TabColumn("control", "Controle depasse", "text"),
        TabColumn("signal", "Signal", "badge"),
        TabColumn("owner", "Owner", "owner"),
        TabColumn("due", "Echeance", "text", "right"),
        TabColumn("status", "Statut", "badge"),
    ]
    rows = [
        TabRow(
            "EXC-2026-007",
            {
                "id": "EXC-2026-007",
                "type": _badge("Exception", "info"),
                "scope": "RGPD - Art. 6 (3)",
                "control": "C-08.2 - Minimisation",
                "signal": _badge("Critique", "danger"),
                "owner": _DAMIEN,
                "due": "30 jun 2026",
                "status": _badge("En cours", "warning"),
            },
        ),
        TabRow(
            "INC-2026-003",
            {
                "id": "INC-2026-003",
                "type": _badge("Incident", "danger"),
                "scope": "EU AI Act - Art. 13",
                "control": "C-05.2 - Transparence",
                "signal": _badge("Eleve", "warning"),
                "owner": _CLAIRE,
                "due": "22 jun 2026",
                "status": _badge("Ouvert", "danger"),
            },
        ),
        TabRow(
            "INC-2026-002",
            {
                "id": "INC-2026-002",
                "type": _badge("Incident", "danger"),
                "scope": "DORA - Art. 17",
                "control": "C-DORA.1 - Risques TIC",
                "signal": _badge("Eleve", "warning"),
                "owner": _SOPHIE,
                "due": "19 jun 2026",
                "status": _badge("En cours", "warning"),
            },
        ),
        TabRow(
            "EXC-2026-009",
            {
                "id": "EXC-2026-009",
                "type": _badge("Exception", "info"),
                "scope": "RGPD - Art. 30",
                "control": "C-30.1 - Registre",
                "signal": _badge("Moyen", "info"),
                "owner": _NADIA,
                "due": "07 jul 2026",
                "status": _badge("Approuvee", "success"),
            },
        ),
        TabRow(
            "EXC-2026-011",
            {
                "id": "EXC-2026-011",
                "type": _badge("Exception", "info"),
                "scope": "ISO 27001 - A.12.4",
                "control": "C-12.4 - Journalisation",
                "signal": _badge("Moyen", "info"),
                "owner": _THOMAS,
                "due": "12 jul 2026",
                "status": _badge("Approuvee", "success"),
            },
        ),
        TabRow(
            "INC-2026-001",
            {
                "id": "INC-2026-001",
                "type": _badge("Incident", "danger"),
                "scope": "EU AI Act - Art. 10",
                "control": "C-13.2 - Donnees",
                "signal": _badge("Critique", "danger"),
                "owner": _CLAIRE,
                "due": "18 jun 2026",
                "status": _badge("Depassee", "danger"),
            },
        ),
    ]
    detail = TabDetail(
        eyebrow="Exception",
        title="EXC-2026-014",
        status_label="Approuvee",
        status_tone="success",
        summary="Derogation temporaire RGPD - Art. 6 (3) en attente de mesure compensatoire.",
        fields=[
            DetailField("Cause mere", "Base legale a reconfirmer"),
            DetailField("Obligation liee", "RGPD - Art. 6 (3)"),
            DetailField("Controle", "C-08.2 - Minimisation"),
            DetailField("Preuve liee", "EV-2026-06-0204"),
            DetailField("Echeance", "30 jun 2026", "warning"),
            DetailField("Risque residuel", "Eleve", "danger"),
            DetailField("Owner", "Damien Leroy"),
        ],
        lists=[
            DetailList(
                "Mesure compensatoire",
                [
                    {"label": "Pseudonymisation renforcee"},
                    {"label": "Revue trimestrielle dediee"},
                ],
            ),
            DetailList(
                "Chaine d'approbation",
                [
                    {"label": "Nadia El Idrissi", "badge": "Validee", "tone": "success"},
                    {"label": "Sophie Bernard", "badge": "Validee", "tone": "success"},
                    {"label": "Comite Conformite", "badge": "En attente", "tone": "warning"},
                ],
            ),
        ],
        actions=[
            "Nouvelle exception",
            "Ouvrir la preuve",
            "Ajouter une preuve",
            "Generer evidence pack",
        ],
    )
    sections = [
        TabSection(
            "Exceptions a echeance proche",
            "list",
            items=[
                SectionItem("EXC-2026-007", "RGPD - Art. 6", "30 jun 2026", badge_tone="warning"),
                SectionItem("EXC-2026-005", "DORA - Art. 28", "02 jul 2026", badge_tone="neutral"),
                SectionItem(
                    "EXC-2026-002", "EU AI Act - Art. 13", "05 jul 2026", badge_tone="neutral"
                ),
            ],
            cta="Voir toutes les exceptions",
        ),
        TabSection(
            "Activites recentes",
            "activity",
            items=[
                SectionItem("INC-2026-003 escalade a Sophie Bernard", "il y a 1 h"),
                SectionItem("EXC-2026-009 approuvee", "il y a 4 h"),
                SectionItem("Preuve EV-2026-06-0204 ajoutee", "il y a 6 h"),
                SectionItem("INC-2026-001 marquee depassee", "hier"),
            ],
            cta="Voir toutes les activites",
        ),
        TabSection(
            "Tendances d'ecarts",
            "chart",
            series=[
                {"label": "Incidents", "color": "#ef4444", "points": [38, 41, 44, 43, 42]},
                {"label": "Exceptions", "color": "#3b82f6", "points": [9, 11, 12, 13, 14]},
                {"label": "Resolution", "color": "#10b981", "points": [22, 24, 28, 31, 34]},
            ],
            cta="Voir toutes les tendances",
        ),
        TabSection(
            "Owners sollicites",
            "bars",
            bars=[
                {"label": "Claire Martin", "value": 0.9, "tone": "danger"},
                {"label": "Damien Leroy", "value": 0.7, "tone": "warning"},
                {"label": "Sophie Bernard", "value": 0.55, "tone": "warning"},
                {"label": "Yacine Sekri", "value": 0.4, "tone": "info"},
            ],
        ),
    ]
    return CatalogTab(
        "Incidents & exceptions",
        kpis=kpis,
        columns=columns,
        rows=rows,
        detail=detail,
        sections=sections,
    )


# --- Purge & retention ----------------------------------------------------


def _tab_retention() -> CatalogTab:
    kpis = [
        TabKpi("Ressources sous retention", "38", tone="good"),
        TabKpi("Delais de purge respectes", "112", delta="+2.0%", delta_good=True),
        TabKpi("Jobs de purge planifies", "246", delta="+4.0%", delta_good=True),
        TabKpi("Legal holds actifs", "8", sub="dossiers"),
        TabKpi("Ecarts de retention", "8", delta="-3.0%", delta_good=True, tone="warn"),
        TabKpi("Evidence pack readiness", "86", unit="%", tone="good"),
    ]
    columns = [
        TabColumn("resource", "Ressource", "text"),
        TabColumn("basis", "Base legale / cadre", "text"),
        TabColumn("target", "Duree cible", "text", "right"),
        TabColumn("mode", "Controle de purge", "badge"),
        TabColumn("signal", "Signal", "badge"),
        TabColumn("owner", "Owner", "owner"),
        TabColumn("status", "Statut", "badge"),
    ]
    rows = [
        TabRow(
            "logs",
            {
                "resource": "Logs d'agent",
                "basis": "Interet legitime - RGPD Art. 6",
                "target": "90 jours",
                "mode": _badge("Automatique", "success"),
                "signal": _badge("OK", "success"),
                "owner": _NADIA,
                "status": _badge("Conforme", "success"),
            },
        ),
        TabRow(
            "transcripts",
            {
                "resource": "Transcriptions",
                "basis": "Consentement - RGPD Art. 6",
                "target": "180 jours",
                "mode": _badge("Automatique", "success"),
                "signal": _badge("Retard", "warning"),
                "owner": _DAMIEN,
                "status": _badge("En retard", "warning"),
            },
        ),
        TabRow(
            "tickets",
            {
                "resource": "Tickets support",
                "basis": "Obligation legale - LPF",
                "target": "3 ans",
                "mode": _badge("Manuel", "warning"),
                "signal": _badge("Moyen", "info"),
                "owner": _SOPHIE,
                "status": _badge("A corriger", "warning"),
            },
        ),
        TabRow(
            "exports",
            {
                "resource": "Exports SIEM",
                "basis": "Securite - ISO 27001",
                "target": "1 an",
                "mode": _badge("Automatique", "success"),
                "signal": _badge("OK", "success"),
                "owner": _NADIA,
                "status": _badge("Conforme", "success"),
            },
        ),
        TabRow(
            "embeddings",
            {
                "resource": "Embeddings",
                "basis": "Interet legitime - RGPD Art. 6",
                "target": "180 jours",
                "mode": _badge("Manuel", "warning"),
                "signal": _badge("Critique", "danger"),
                "owner": _YACINE,
                "status": _badge("Bloque", "danger"),
            },
        ),
        TabRow(
            "evals",
            {
                "resource": "Jeux d'evaluation",
                "basis": "Interet legitime - RGPD Art. 6",
                "target": "2 ans",
                "mode": _badge("Manuel", "warning"),
                "signal": _badge("OK", "success"),
                "owner": _THOMAS,
                "status": _badge("Bloque", "danger"),
            },
        ),
    ]
    detail = TabDetail(
        eyebrow="Regle de retention",
        title="Logs d'agent",
        status_label="Conforme",
        status_tone="success",
        summary="Retention 90 jours sur interet legitime, purge automatique nocturne.",
        fields=[
            DetailField("Stockage", "Cloud SQL - Postgres"),
            DetailField("Strategie de suppression", "Purge automatique"),
            DetailField("Methode de purge", "DELETE + VACUUM nocturne"),
            DetailField("Legal hold", "Aucun", "neutral"),
            DetailField("Proprietaire", "Nadia El Idrissi"),
            DetailField("Prochaine purge", "20 jun 2026"),
            DetailField("Dernier artefact de purge", "PRG-2026-06-118"),
        ],
        lists=[
            DetailList(
                "Controles lies (3)",
                [
                    {"label": "C-10.1 - Securite", "badge": "Conforme", "tone": "success"},
                    {"label": "C-06.6 - Retention", "badge": "Conforme", "tone": "success"},
                    {"label": "C-17.1 - Effacement", "badge": "Conforme", "tone": "success"},
                ],
            ),
        ],
        actions=["Forcer revue", "Ouvrir les preuves", "Generer evidence pack"],
    )
    sections = [
        TabSection(
            "Purges a venir (7 jours)",
            "list",
            items=[
                SectionItem("Embeddings", "purge manuelle", "18 jun 2026", badge_tone="danger"),
                SectionItem("Transcriptions", "purge auto", "19 jun 2026", badge_tone="warning"),
                SectionItem("Logs d'agent", "purge auto", "20 jun 2026", badge_tone="neutral"),
                SectionItem(
                    "Tickets support", "purge manuelle", "22 jun 2026", badge_tone="neutral"
                ),
            ],
            cta="Voir toutes les purges",
        ),
        TabSection(
            "Exceptions actives",
            "list",
            items=[
                SectionItem(
                    "Jeux d'evaluation", "legal hold actif", badge="Bloque", badge_tone="danger"
                ),
                SectionItem(
                    "Embeddings", "purge manuelle en retard", badge="Critique", badge_tone="danger"
                ),
                SectionItem(
                    "Tickets support", "purge manuelle", badge="A corriger", badge_tone="warning"
                ),
            ],
            cta="Voir toutes les exceptions",
        ),
        TabSection(
            "Activites recentes",
            "activity",
            items=[
                SectionItem("Purge auto Logs d'agent executee", "il y a 2 h"),
                SectionItem("Legal hold ajoute sur Jeux d'evaluation", "il y a 5 h"),
                SectionItem("Transcriptions purge en retard signalee", "il y a 9 h"),
                SectionItem("Regle Exports SIEM mise a jour", "hier"),
            ],
            cta="Voir toutes les activites",
        ),
        TabSection(
            "Couverture par systeme",
            "bars",
            bars=[
                {"label": "Postgres", "value": 0.95, "tone": "success"},
                {"label": "Object store", "value": 0.72, "tone": "warning"},
                {"label": "Vertex", "value": 0.6, "tone": "warning"},
                {"label": "Helpdesk", "value": 0.81, "tone": "info"},
                {"label": "SIEM", "value": 0.9, "tone": "success"},
            ],
        ),
    ]
    return CatalogTab(
        "Purge & retention",
        kpis=kpis,
        columns=columns,
        rows=rows,
        detail=detail,
        sections=sections,
    )


# --- Preuves & attestations ----------------------------------------------


def _tab_evidence() -> CatalogTab:
    kpis = [
        TabKpi("Preuves disponibles", "8 246", delta="+2.0%", delta_good=True, tone="good"),
        TabKpi("Attestations valides", "7 112", delta="+1.0%", delta_good=True),
        TabKpi("Preuves expirantes", "312", delta="+4.0%", delta_good=False, tone="warn"),
        TabKpi("Manquant / corrompu", "28", delta="-2.0%", delta_good=True, tone="warn"),
        TabKpi("Couverture preuve", "86", unit="%", tone="good"),
        TabKpi("Evidence pack", "Prete", tone="good"),
    ]
    columns = [
        TabColumn("id", "Preuve", "mono"),
        TabColumn("scope", "Cadre / obligation", "text"),
        TabColumn("control", "Controle", "text"),
        TabColumn("kind", "Type", "badge"),
        TabColumn("owner", "Owner", "owner"),
        TabColumn("date", "Date", "text", "right"),
        TabColumn("validity", "Validite", "text", "right"),
        TabColumn("status", "Statut", "badge"),
    ]
    rows = [
        TabRow(
            "PRV-2026-06-0123",
            {
                "id": "PRV-2026-06-0123",
                "scope": "EU AI Act - Art. 9",
                "control": "C-15.1 - Gestion du risque",
                "kind": _badge("Rapport", "info"),
                "owner": _CLAIRE,
                "date": "11 jun 2026",
                "validity": "12 mois",
                "status": _badge("Valide", "success"),
            },
        ),
        TabRow(
            "PRV-2026-06-0118",
            {
                "id": "PRV-2026-06-0118",
                "scope": "RGPD - Art. 30",
                "control": "C-30.1 - Registre",
                "kind": _badge("Export", "neutral"),
                "owner": _DAMIEN,
                "date": "10 jun 2026",
                "validity": "6 mois",
                "status": _badge("Valide", "success"),
            },
        ),
        TabRow(
            "PRV-2026-05-0091",
            {
                "id": "PRV-2026-05-0091",
                "scope": "DORA - Art. 28",
                "control": "C-DORA.1 - Risques TIC",
                "kind": _badge("Attestation", "info"),
                "owner": _SOPHIE,
                "date": "28 mai 2026",
                "validity": "30 jours",
                "status": _badge("Expirante", "warning"),
            },
        ),
        TabRow(
            "PRV-2026-06-0102",
            {
                "id": "PRV-2026-06-0102",
                "scope": "ISO 27001 - A.12",
                "control": "C-12.4 - Journalisation",
                "kind": _badge("Log signe", "neutral"),
                "owner": _NADIA,
                "date": "09 jun 2026",
                "validity": "12 mois",
                "status": _badge("Valide", "success"),
            },
        ),
        TabRow(
            "PRV-2026-04-0044",
            {
                "id": "PRV-2026-04-0044",
                "scope": "EU AI Act - Art. 13",
                "control": "C-05.2 - Transparence",
                "kind": _badge("Capture", "neutral"),
                "owner": _CLAIRE,
                "date": "14 avr 2026",
                "validity": "expiree",
                "status": _badge("Manquante", "danger"),
            },
        ),
        TabRow(
            "PRV-2026-06-0130",
            {
                "id": "PRV-2026-06-0130",
                "scope": "SOC 2 - CC7",
                "control": "C-12.2 - Disponibilite",
                "kind": _badge("Rapport", "info"),
                "owner": _THOMAS,
                "date": "12 jun 2026",
                "validity": "12 mois",
                "status": _badge("Valide", "success"),
            },
        ),
    ]
    detail = TabDetail(
        eyebrow="Preuve",
        title="PRV-2026-06-0123",
        status_label="Valide",
        status_tone="success",
        summary="Rapport de gestion du risque EU AI Act - Art. 9, signe et horodate.",
        fields=[
            DetailField("Cadre", "EU AI Act - Art. 9"),
            DetailField("Controle", "C-15.1 - Gestion du risque"),
            DetailField("Type", "Rapport"),
            DetailField("Genere le", "11 jun 2026"),
            DetailField("Validite", "12 mois"),
            DetailField("Empreinte", "sha256:9f3a...c021"),
            DetailField("Proprietaire", "Claire Martin"),
        ],
        lists=[
            DetailList(
                "Obligations liees (3)",
                [
                    {"label": "Art. 9 - Gestion du risque"},
                    {"label": "Art. 15 - Exactitude"},
                    {"label": "Art. 17 - SMQ"},
                ],
            ),
            DetailList(
                "Proprietaire & signature",
                [
                    {"label": "Claire Martin", "badge": "Signee", "tone": "success"},
                ],
            ),
        ],
        actions=["Voir evidence pack", "Telecharger preuve", "Combiner evidence pack"],
    )
    sections = [
        TabSection(
            "Preuves a renouveler (312)",
            "list",
            items=[
                SectionItem(
                    "PRV-2026-05-0091", "DORA - Art. 28", "dans 6 jours", badge_tone="warning"
                ),
                SectionItem(
                    "PRV-2026-05-0073", "RGPD - Art. 32", "dans 11 jours", badge_tone="warning"
                ),
                SectionItem(
                    "PRV-2026-05-0061", "ISO 27001 - A.9", "dans 18 jours", badge_tone="neutral"
                ),
            ],
            cta="Voir toutes les preuves a renouveler",
        ),
        TabSection(
            "Dernieres attestations",
            "activity",
            items=[
                SectionItem("PRV-2026-06-0130 generee (SOC 2)", "il y a 1 h"),
                SectionItem("PRV-2026-06-0123 signee (EU AI Act)", "il y a 3 h"),
                SectionItem("PRV-2026-06-0118 exportee (RGPD)", "il y a 6 h"),
                SectionItem("PRV-2026-06-0102 horodatee (ISO)", "hier"),
            ],
            cta="Voir toutes les attestations",
        ),
        TabSection(
            "Couverture par cadre",
            "donut",
            donut_value=0.865,
            donut_label="Couverture",
            items=[
                SectionItem("EU AI Act", value="82 %", badge_tone="warning"),
                SectionItem("RGPD", value="91 %", badge_tone="success"),
                SectionItem("DORA", value="73 %", badge_tone="warning"),
                SectionItem("ISO 27001", value="88 %", badge_tone="success"),
            ],
            cta="Voir le detail par cadre",
        ),
        TabSection(
            "Activites recentes",
            "activity",
            items=[
                SectionItem("Evidence pack EU AI Act genere", "il y a 2 h"),
                SectionItem("Preuve PRV-2026-04-0044 marquee manquante", "il y a 7 h"),
                SectionItem("Attestation DORA renouvelee", "hier"),
            ],
            cta="Voir toutes les activites",
        ),
    ]
    return CatalogTab(
        "Inventaire des preuves & attestations",
        kpis=kpis,
        columns=columns,
        rows=rows,
        detail=detail,
        sections=sections,
    )


# --- Registre des traitements --------------------------------------------


def _tab_registry() -> CatalogTab:
    kpis = [
        TabKpi("Traitements enregistres", "36", tone="good"),
        TabKpi("Finalites documentees", "36", delta="+5.0%", delta_good=True),
        TabKpi("Bases legales valides", "36", tone="good"),
        TabKpi("Durees de retention conformes", "33", delta="+2.0%", delta_good=True),
        TabKpi("Ecarts de registre", "4", delta="-3.0%", delta_good=True, tone="warn"),
        TabKpi("Evidence pack readiness", "84", unit="%", tone="good"),
    ]
    columns = [
        TabColumn("name", "Traitement", "text"),
        TabColumn("purpose", "Finalite", "text"),
        TabColumn("basis", "Base legale", "text"),
        TabColumn("data", "Donnees", "text"),
        TabColumn("retention", "Duree de retention", "text", "right"),
        TabColumn("controls", "Controles", "num", "right"),
        TabColumn("owner", "Owner", "owner"),
        TabColumn("status", "Statut", "badge"),
    ]
    rows = [
        TabRow(
            "scoring",
            {
                "name": "Scoring credit",
                "purpose": "Evaluation de solvabilite",
                "basis": "Contrat - RGPD Art. 6",
                "data": "Donnees financieres",
                "retention": "5 ans",
                "controls": "8",
                "owner": _SOPHIE,
                "status": _badge("Conforme", "success"),
            },
        ),
        TabRow(
            "fraud",
            {
                "name": "Lutte anti-fraude",
                "purpose": "Detection de fraude",
                "basis": "Interet legitime",
                "data": "Transactions",
                "retention": "3 ans",
                "controls": "7",
                "owner": _NADIA,
                "status": _badge("Conforme", "success"),
            },
        ),
        TabRow(
            "support",
            {
                "name": "Support client IA",
                "purpose": "Assistance conversationnelle",
                "basis": "Consentement",
                "data": "Identifiant, contenu",
                "retention": "180 jours",
                "controls": "6",
                "owner": _CLAIRE,
                "status": _badge("Partiel", "warning"),
            },
        ),
        TabRow(
            "auth",
            {
                "name": "Authentification & KYC",
                "purpose": "Verification d'identite",
                "basis": "Obligation legale",
                "data": "Identite, documents",
                "retention": "5 ans",
                "controls": "9",
                "owner": _DAMIEN,
                "status": _badge("Conforme", "success"),
            },
        ),
        TabRow(
            "kyc_screen",
            {
                "name": "KYC Screening",
                "purpose": "Sanctions & PEP",
                "basis": "Obligation legale - LCB-FT",
                "data": "Identite, listes",
                "retention": "5 ans",
                "controls": "7",
                "owner": _THOMAS,
                "status": _badge("Partiel", "warning"),
            },
        ),
    ]
    detail = TabDetail(
        eyebrow="Traitement",
        title="Scoring credit",
        status_label="Conforme",
        status_tone="success",
        summary="Evaluation de solvabilite sur base contractuelle, sans decision automatisee.",
        fields=[
            DetailField("Categorie de donnees", "Donnees financieres"),
            DetailField("Finalite", "Evaluation de solvabilite"),
            DetailField("Base legale", "Execution du contrat"),
            DetailField("Transferts", "Aucun hors UE", "success"),
            DetailField("Sous-traitants", "2 (UE)"),
            DetailField("Duree", "5 ans"),
            DetailField("Prochaine revue", "20 jun 2026"),
        ],
        lists=[
            DetailList(
                "Controles lies (4)",
                [
                    {"label": "C-08.2 - Minimisation", "badge": "Conforme", "tone": "success"},
                    {"label": "C-22.1 - Decision auto", "badge": "Conforme", "tone": "success"},
                    {"label": "C-13.2 - Donnees", "badge": "Partiel", "tone": "warning"},
                    {"label": "C-06.6 - Retention", "badge": "Conforme", "tone": "success"},
                ],
            ),
        ],
        actions=[
            "Ajouter un traitement",
            "Ouvrir les preuves",
            "Planifier une revue",
            "Generer evidence pack",
        ],
    )
    sections = [
        TabSection(
            "Registres a completer (4)",
            "list",
            items=[
                SectionItem(
                    "Privacy Impact Assessment",
                    "Support client IA",
                    badge="A faire",
                    badge_tone="warning",
                ),
                SectionItem(
                    "Base legale a justifier",
                    "KYC Screening",
                    badge="A faire",
                    badge_tone="warning",
                ),
                SectionItem(
                    "Sous-traitant a documenter",
                    "Lutte anti-fraude",
                    badge="A faire",
                    badge_tone="warning",
                ),
                SectionItem(
                    "Duree a confirmer", "Support client IA", badge="A faire", badge_tone="warning"
                ),
            ],
            cta="Voir les registres a completer",
        ),
        TabSection(
            "Revues programmees (4)",
            "list",
            items=[
                SectionItem(
                    "Scoring credit", "revue annuelle", "20 jun 2026", badge_tone="neutral"
                ),
                SectionItem(
                    "Lutte anti-fraude", "revue annuelle", "30 jun 2026", badge_tone="neutral"
                ),
                SectionItem("KYC Screening", "revue annuelle", "12 jul 2026", badge_tone="neutral"),
            ],
            cta="Voir toutes les revues",
        ),
        TabSection(
            "Activites recentes",
            "activity",
            items=[
                SectionItem("Traitement Scoring credit mis a jour", "il y a 3 h"),
                SectionItem("AIPD Support client IA ouverte", "il y a 6 h"),
                SectionItem("Base legale KYC Screening signalee", "hier"),
            ],
            cta="Voir toutes les activites",
        ),
        TabSection(
            "Exceptions liees (4)",
            "list",
            items=[
                SectionItem(
                    "EXC-2026-007", "Support client IA", badge="Partiel", badge_tone="warning"
                ),
                SectionItem(
                    "EXC-2026-009", "KYC Screening", badge="Approuvee", badge_tone="success"
                ),
                SectionItem(
                    "EXC-2026-011", "Lutte anti-fraude", badge="Approuvee", badge_tone="success"
                ),
            ],
            cta="Voir toutes les exceptions",
        ),
    ]
    return CatalogTab(
        "Registre des traitements",
        kpis=kpis,
        columns=columns,
        rows=rows,
        detail=detail,
        sections=sections,
    )


def _build_fr_tabs() -> dict[str, CatalogTab]:
    """Return the deterministic French per-tab payloads (the source of truth)."""
    return {
        "mapping": _tab_mapping(),
        "obligations": _tab_obligations(),
        "evaluations": _tab_evaluations(),
        "incidents": _tab_incidents(),
        "retention": _tab_retention(),
        "evidence": _tab_evidence(),
        "registry": _tab_registry(),
    }


# Generic translation layer (same approach as ``incidents_tabs``): the catalogue
# is authored in French; for DE / EN every string leaf of the assembled tab tree
# is mapped through ``_TR``. Unmapped strings (codes, person names, standards,
# tech, role titles) fall through verbatim, so a missing entry is a French label,
# never a crash.
_LANG_IDX = {"fr": 0, "de": 1, "en": 2}

_TR: dict[str, tuple[str, str]] = {
    # --- KPI / status / chrome vocabulary -----------------------------------
    "Cadres actifs": ("Aktive Rahmenwerke", "Active frameworks"),
    "Cadres a surveiller": ("Zu beobachtende Rahmenwerke", "Frameworks to watch"),
    "Cadres en baisse": ("Ruecklaeufige Rahmenwerke", "Declining frameworks"),
    "Obligations actives": ("Aktive Pflichten", "Active obligations"),
    "Obligations a risque": ("Gefaehrdete Pflichten", "Obligations at risk"),
    "Obligations mappees": ("Zugeordnete Pflichten", "Mapped obligations"),
    "Controles mappes": ("Zugeordnete Kontrollen", "Mapped controls"),
    "Controles a revoir": ("Zu pruefende Kontrollen", "Controls to review"),
    "Controles degrades": ("Verschlechterte Kontrollen", "Degraded controls"),
    "Controles passes": ("Bestandene Kontrollen", "Passed controls"),
    "Controles lies": ("Verknuepfte Kontrollen", "Linked controls"),
    "Couverture": ("Abdeckung", "Coverage"),
    "Couverture par cadre": ("Abdeckung nach Rahmenwerk", "Coverage by framework"),
    "Couverture par systeme": ("Abdeckung nach System", "Coverage by system"),
    "Couverture preuve": ("Nachweisabdeckung", "Evidence coverage"),
    "Score de conformite": ("Konformitaetsscore", "Compliance score"),
    "Echecs critiques": ("Kritische Fehler", "Critical failures"),
    "Exceptions actives": ("Aktive Ausnahmen", "Active exceptions"),
    "Exceptions approuvees": ("Genehmigte Ausnahmen", "Approved exceptions"),
    "Exceptions depassees": ("Ueberfaellige Ausnahmen", "Overdue exceptions"),
    "Exceptions a echeance proche": ("Ausnahmen mit naher Frist", "Exceptions due soon"),
    "Incidents ouverts": ("Offene Vorfaelle", "Open incidents"),
    "Ecarts ouverts": ("Offene Abweichungen", "Open gaps"),
    "Gaps de couverture": ("Abdeckungsluecken", "Coverage gaps"),
    "Legal holds actifs": ("Aktive Legal Holds", "Active legal holds"),
    "Attestations valides": ("Gueltige Bescheinigungen", "Valid attestations"),
    "Preuves disponibles": ("Verfuegbare Nachweise", "Available evidence"),
    "Preuves manquantes": ("Fehlende Nachweise", "Missing evidence"),
    "Preuves expirantes": ("Ablaufende Nachweise", "Expiring evidence"),
    "Preuves rejouees": ("Wiederholte Nachweise", "Replayed evidence"),
    "Preuves liees": ("Verknuepfte Nachweise", "Linked evidence"),
    "Bases legales valides": ("Gueltige Rechtsgrundlagen", "Valid legal bases"),
    "Finalites documentees": ("Dokumentierte Zwecke", "Documented purposes"),
    "Durees de retention conformes": (
        "Konforme Aufbewahrungsfristen",
        "Compliant retention periods",
    ),
    "Delais de purge respectes": ("Eingehaltene Loeschfristen", "Purge deadlines met"),
    "Jobs de purge planifies": ("Geplante Loeschjobs", "Scheduled purge jobs"),
    "Ressources sous retention": ("Ressourcen unter Aufbewahrung", "Resources under retention"),
    "Traitements enregistres": ("Registrierte Verarbeitungen", "Registered processings"),
    "Ecarts de registre": ("Registerabweichungen", "Register gaps"),
    "Ecarts de retention": ("Aufbewahrungsabweichungen", "Retention gaps"),
    "Owners sollicites": ("Angefragte Owner", "Owners requested"),
    "Evidence pack readiness": ("Evidence-Pack-Bereitschaft", "Evidence pack readiness"),
    # --- statuses / badges ---------------------------------------------------
    "Conforme": ("Konform", "Compliant"),
    "Partiel": ("Teilweise", "Partial"),
    "Partielle": ("Teilweise", "Partial"),
    "Applicable partielle": ("Teilweise anwendbar", "Partially applicable"),
    "Applicable des classification": (
        "Anwendbar ab Klassifizierung",
        "Applicable from classification",
    ),
    "Echec": ("Fehler", "Failure"),
    "Critique": ("Kritisch", "Critical"),
    "Eleve": ("Hoch", "High"),
    "Moyen": ("Mittel", "Medium"),
    "Faible": ("Niedrig", "Low"),
    "Ouvert": ("Offen", "Open"),
    "En cours": ("Laufend", "In progress"),
    "En attente": ("Ausstehend", "Pending"),
    "En retard": ("Verspaetet", "Late"),
    "Retard": ("Verspaetung", "Late"),
    "Approuvee": ("Genehmigt", "Approved"),
    "Validee": ("Validiert", "Validated"),
    "Valide": ("Gueltig", "Valid"),
    "Signee": ("Signiert", "Signed"),
    "Prete": ("Bereit", "Ready"),
    "Nouveau": ("Neu", "New"),
    "Depassee": ("Ueberfaellig", "Overdue"),
    "Expirante": ("Ablaufend", "Expiring"),
    "Bloque": ("Blockiert", "Blocked"),
    "Manquante": ("Fehlend", "Missing"),
    "Manquant / corrompu": ("Fehlend / beschaedigt", "Missing / corrupted"),
    "Proposition en cours": ("Vorschlag laufend", "Proposal in progress"),
    "Automatique": ("Automatisch", "Automatic"),
    "Manuel": ("Manuell", "Manual"),
    "A corriger": ("Zu korrigieren", "To fix"),
    "A faire": ("Zu erledigen", "To do"),
    "Aucun": ("Keiner", "None"),
    "Aucun hors UE": ("Keiner ausserhalb der EU", "None outside the EU"),
    # --- column headers / field labels --------------------------------------
    "Cadre": ("Rahmenwerk", "Framework"),
    "Cadre / obligation": ("Rahmenwerk / Pflicht", "Framework / obligation"),
    "Article / Domaine": ("Artikel / Bereich", "Article / Domain"),
    "Articles applicables": ("Anwendbare Artikel", "Applicable articles"),
    "Obligation": ("Pflicht", "Obligation"),
    "Obligation liee": ("Verknuepfte Pflicht", "Linked obligation"),
    "Controle": ("Kontrolle", "Control"),
    "Controle principal": ("Hauptkontrolle", "Main control"),
    "Controles": ("Kontrollen", "Controls"),
    "Statut": ("Status", "Status"),
    "Score": ("Score", "Score"),
    "Type": ("Typ", "Type"),
    "Date": ("Datum", "Date"),
    "Duree": ("Dauer", "Duration"),
    "Duree cible": ("Zieldauer", "Target duration"),
    "Duree de retention": ("Aufbewahrungsdauer", "Retention period"),
    "Duree a confirmer": ("Dauer zu bestaetigen", "Duration to confirm"),
    "Echeance": ("Frist", "Due date"),
    "Owner": ("Owner", "Owner"),
    "Proprietaire": ("Eigentuemer", "Owner"),
    "Proprietaire & signature": ("Eigentuemer & Signatur", "Owner & signature"),
    "Ressource": ("Ressource", "Resource"),
    "Resolution": ("Loesung", "Resolution"),
    "Risque residuel": ("Restrisiko", "Residual risk"),
    "Niveau de risque residuel": ("Restrisikoniveau", "Residual risk level"),
    "Categorie de donnees": ("Datenkategorie", "Data category"),
    "Base legale": ("Rechtsgrundlage", "Legal basis"),
    "Base legale / cadre": ("Rechtsgrundlage / Rahmen", "Legal basis / framework"),
    "Finalite": ("Zweck", "Purpose"),
    "Traitement": ("Verarbeitung", "Processing"),
    "Campagne": ("Kampagne", "Campaign"),
    "Campagne / domaine": ("Kampagne / Bereich", "Campaign / domain"),
    "Methode de purge": ("Loeschmethode", "Purge method"),
    "Regle de retention": ("Aufbewahrungsregel", "Retention rule"),
    "Stockage": ("Speicher", "Storage"),
    "Cause mere": ("Grundursache", "Root cause"),
    "Empreinte": ("Fingerabdruck", "Fingerprint"),
    "Signal": ("Signal", "Signal"),
    "Signaux": ("Signale", "Signals"),
    "Signaux lies": ("Verknuepfte Signale", "Linked signals"),
    "Signaux par preuve": ("Signale pro Nachweis", "Signals per evidence"),
    "Validite": ("Gueltigkeit", "Validity"),
    "Veille": ("Beobachtung", "Watch"),
    "Mesure compensatoire": ("Ausgleichsmassnahme", "Compensating measure"),
    "Chaine d'approbation": ("Genehmigungskette", "Approval chain"),
    "Niveau de risque": ("Risikoniveau", "Risk level"),
    # --- section / tab titles -----------------------------------------------
    "Cartographie reglementaire": ("Regulatorische Kartierung", "Regulatory mapping"),
    "Obligations & controles": ("Pflichten & Kontrollen", "Obligations & controls"),
    "Evaluations": ("Evaluierungen", "Evaluations"),
    "Incidents & exceptions": ("Vorfaelle & Ausnahmen", "Incidents & exceptions"),
    "Purge & retention": ("Loeschung & Aufbewahrung", "Purge & retention"),
    "Registre des traitements": ("Verarbeitungsverzeichnis", "Processing register"),
    "Inventaire des preuves & attestations": (
        "Inventar der Nachweise & Bescheinigungen",
        "Evidence & attestations inventory",
    ),
    "Campagnes d'evaluation": ("Evaluierungskampagnen", "Evaluation campaigns"),
    "Jeux d'evaluation": ("Evaluierungssets", "Evaluation sets"),
    "Echeances reglementaires": ("Regulatorische Fristen", "Regulatory deadlines"),
    "Echeances de remediation": ("Behebungsfristen", "Remediation deadlines"),
    "Tendances des scores": ("Score-Trends", "Score trends"),
    "Tendances d'ecarts": ("Abweichungstrends", "Gap trends"),
    "Actions rapides": ("Schnellaktionen", "Quick actions"),
    "Activites recentes": ("Letzte Aktivitaeten", "Recent activities"),
    "Dernieres attestations": ("Letzte Bescheinigungen", "Latest attestations"),
    "Dernieres preuves": ("Letzte Nachweise", "Latest evidence"),
    "Derniere campagne": ("Letzte Kampagne", "Latest campaign"),
    "Dernier artefact de purge": ("Letztes Loesch-Artefakt", "Latest purge artifact"),
    "Controles lies (3)": ("Verknuepfte Kontrollen (3)", "Linked controls (3)"),
    "Controles lies (4)": ("Verknuepfte Kontrollen (4)", "Linked controls (4)"),
    "Controles mappes (4)": ("Zugeordnete Kontrollen (4)", "Mapped controls (4)"),
    "Obligations liees (3)": ("Verknuepfte Pflichten (3)", "Linked obligations (3)"),
    "Exceptions liees (4)": ("Verknuepfte Ausnahmen (4)", "Linked exceptions (4)"),
    "Preuves a renouveler (312)": ("Zu erneuernde Nachweise (312)", "Evidence to renew (312)"),
    "Registres a completer (4)": (
        "Zu vervollstaendigende Register (4)",
        "Registers to complete (4)",
    ),
    "Revues programmees (4)": ("Geplante Pruefungen (4)", "Scheduled reviews (4)"),
    "Purges a venir (7 jours)": ("Kommende Loeschungen (7 Tage)", "Upcoming purges (7 days)"),
    "Prochaine purge": ("Naechste Loeschung", "Next purge"),
    "Prochaine revue": ("Naechste Pruefung", "Next review"),
    "Gestion du risque": ("Risikomanagement", "Risk management"),
    "Plan de remediation": ("Behebungsplan", "Remediation plan"),
    "Strategie de suppression": ("Loeschstrategie", "Deletion strategy"),
    "Controle de purge": ("Loeschkontrolle", "Purge control"),
    "Logs d'agent": ("Agent-Protokolle", "Agent logs"),
    "Exports SIEM": ("SIEM-Exporte", "SIEM exports"),
    "Tickets support": ("Support-Tickets", "Support tickets"),
    "Transcriptions": ("Transkripte", "Transcripts"),
    "Transactions": ("Transaktionen", "Transactions"),
    "Transferts": ("Uebertragungen", "Transfers"),
    "Sous-traitants": ("Auftragsverarbeiter", "Processors"),
    "Sous-traitance TIC": ("IKT-Auslagerung", "ICT outsourcing"),
    "Donnees": ("Daten", "Data"),
    "Donnees financieres": ("Finanzdaten", "Financial data"),
    "Consentement": ("Einwilligung", "Consent"),
    "Interet legitime": ("Berechtigtes Interesse", "Legitimate interest"),
    "Obligation legale": ("Rechtliche Verpflichtung", "Legal obligation"),
    "Execution du contrat": ("Vertragserfuellung", "Contract performance"),
    "Lutte anti-fraude": ("Betrugsbekaempfung", "Anti-fraud"),
    "Detection de fraude": ("Betrugserkennung", "Fraud detection"),
    "Evaluation de solvabilite": ("Bonitaetspruefung", "Creditworthiness assessment"),
    "Scoring credit": ("Kredit-Scoring", "Credit scoring"),
    "Verification d'identite": ("Identitaetspruefung", "Identity verification"),
    "Authentification & KYC": ("Authentifizierung & KYC", "Authentication & KYC"),
    "Sanctions & PEP": ("Sanktionen & PEP", "Sanctions & PEP"),
    "Assistance conversationnelle": ("Konversationsunterstuetzung", "Conversational assistance"),
    "Support client IA": ("KI-Kundensupport", "AI customer support"),
    "Pseudonymisation renforcee": ("Verstaerkte Pseudonymisierung", "Reinforced pseudonymization"),
    "Identite, documents": ("Identitaet, Dokumente", "Identity, documents"),
    "Identite, listes": ("Identitaet, Listen", "Identity, lists"),
    "Identifiant, contenu": ("Kennung, Inhalt", "Identifier, content"),
    "Code de conduite IA": ("KI-Verhaltenskodex", "AI code of conduct"),
    "Politiques internes": ("Interne Richtlinien", "Internal policies"),
    "Privacy Impact Assessment": ("Datenschutz-Folgenabschaetzung", "Privacy Impact Assessment"),
    "AIPD a finaliser": ("DSFA abzuschliessen", "DPIA to finalize"),
    "AIPD Support client IA ouverte": (
        "DSFA KI-Kundensupport offen",
        "DPIA AI customer support open",
    ),
    "Attestation": ("Bescheinigung", "Attestation"),
    "Exception": ("Ausnahme", "Exception"),
    "Exceptions": ("Ausnahmen", "Exceptions"),
    "Incident": ("Vorfall", "Incident"),
    "Incidents": ("Vorfaelle", "Incidents"),
    "Obligations": ("Pflichten", "Obligations"),
    "Preuve": ("Nachweis", "Evidence"),
    "Preuve liee": ("Verknuepfter Nachweis", "Linked evidence"),
    "Preuves": ("Nachweise", "Evidence"),
    "Rapport": ("Bericht", "Report"),
    "Legal hold": ("Legal Hold", "Legal hold"),
    "Gap": ("Luecke", "Gap"),
    # --- CTAs ----------------------------------------------------------------
    "Ajouter un traitement": ("Verarbeitung hinzufuegen", "Add a processing"),
    "Ajouter une preuve": ("Nachweis hinzufuegen", "Add evidence"),
    "Mapper une obligation": ("Pflicht zuordnen", "Map an obligation"),
    "Nouvelle exception": ("Neue Ausnahme", "New exception"),
    "Lancer une evaluation": ("Evaluierung starten", "Launch an evaluation"),
    "Planifier une revue": ("Pruefung planen", "Schedule a review"),
    "Forcer revue": ("Pruefung erzwingen", "Force review"),
    "Generer evidence pack": ("Evidence-Pack erzeugen", "Generate evidence pack"),
    "Combiner evidence pack": ("Evidence-Pack kombinieren", "Combine evidence pack"),
    "Voir evidence pack": ("Evidence-Pack anzeigen", "View evidence pack"),
    "Ouvrir la preuve": ("Nachweis oeffnen", "Open the evidence"),
    "Ouvrir les preuves": ("Nachweise oeffnen", "Open the evidence"),
    "Telecharger preuve": ("Nachweis herunterladen", "Download evidence"),
    "Export": ("Export", "Export"),
    "Voir le detail": ("Details anzeigen", "View detail"),
    "Voir le detail par cadre": ("Detail nach Rahmenwerk anzeigen", "View detail by framework"),
    "Voir les ecarts": ("Abweichungen anzeigen", "View gaps"),
    "Voir les gaps": ("Luecken anzeigen", "View gaps"),
    "Voir les registres a completer": (
        "Zu vervollstaendigende Register anzeigen",
        "View registers to complete",
    ),
    "Voir tous les cadres": ("Alle Rahmenwerke anzeigen", "View all frameworks"),
    "Voir tous les cadres a surveiller": (
        "Alle zu beobachtenden Rahmenwerke anzeigen",
        "View all frameworks to watch",
    ),
    "Voir tous les controles a revoir": (
        "Alle zu pruefenden Kontrollen anzeigen",
        "View all controls to review",
    ),
    "Voir tous les ecarts": ("Alle Abweichungen anzeigen", "View all gaps"),
    "Voir toutes les activites": ("Alle Aktivitaeten anzeigen", "View all activities"),
    "Voir toutes les attestations": ("Alle Bescheinigungen anzeigen", "View all attestations"),
    "Voir toutes les echeances": ("Alle Fristen anzeigen", "View all deadlines"),
    "Voir toutes les exceptions": ("Alle Ausnahmen anzeigen", "View all exceptions"),
    "Voir toutes les preuves": ("Alle Nachweise anzeigen", "View all evidence"),
    "Voir toutes les preuves a renouveler": (
        "Alle zu erneuernden Nachweise anzeigen",
        "View all evidence to renew",
    ),
    "Voir toutes les purges": ("Alle Loeschungen anzeigen", "View all purges"),
    "Voir toutes les revues": ("Alle Pruefungen anzeigen", "View all reviews"),
    "Voir toutes les tendances": ("Alle Trends anzeigen", "View all trends"),
    # --- article / control labels (FR clause translated) --------------------
    "Art. 5 - Principes (a-f)": ("Art. 5 - Grundsaetze (a-f)", "Art. 5 - Principles (a-f)"),
    "Art. 9 - Gestion du risque": ("Art. 9 - Risikomanagement", "Art. 9 - Risk management"),
    "Art. 9 - Systeme a haut risque": ("Art. 9 - Hochrisikosystem", "Art. 9 - High-risk system"),
    "Art. 9 - Monitoring post-marche": (
        "Art. 9 - Post-Market-Monitoring",
        "Art. 9 - Post-market monitoring",
    ),
    "Art. 10 - Gouvernance des donnees": (
        "Art. 10 - Daten-Governance",
        "Art. 10 - Data governance",
    ),
    "Art. 10 - Qualite des donnees": ("Art. 10 - Datenqualitaet", "Art. 10 - Data quality"),
    "Art. 13 - Transparence": ("Art. 13 - Transparenz", "Art. 13 - Transparency"),
    "Art. 13 - Transparence & info": (
        "Art. 13 - Transparenz & Info",
        "Art. 13 - Transparency & info",
    ),
    "Art. 15 - Exactitude": ("Art. 15 - Genauigkeit", "Art. 15 - Accuracy"),
    "Art. 17 - SMQ": ("Art. 17 - QMS", "Art. 17 - QMS"),
    "Art. 30 - Registre des activites": (
        "Art. 30 - Taetigkeitsverzeichnis",
        "Art. 30 - Records of activities",
    ),
    "RGPD - Article 30 (registre)": (
        "DSGVO - Artikel 30 (Verzeichnis)",
        "GDPR - Article 30 (register)",
    ),
    "DORA - Art. 28 (sous-traitance TIC)": (
        "DORA - Art. 28 (IKT-Auslagerung)",
        "DORA - Art. 28 (ICT outsourcing)",
    ),
    "DORA - Art. 28 (test de resilience)": (
        "DORA - Art. 28 (Resilienztest)",
        "DORA - Art. 28 (resilience test)",
    ),
    "EU AI Act - Art. 15 (rapport annuel)": (
        "EU AI Act - Art. 15 (Jahresbericht)",
        "EU AI Act - Art. 15 (annual report)",
    ),
    "C-04.1 - Tests adverses": ("C-04.1 - Adversariale Tests", "C-04.1 - Adversarial tests"),
    "C-05.2 - Transparence": ("C-05.2 - Transparenz", "C-05.2 - Transparency"),
    "C-05.2 - Transparence UX": ("C-05.2 - Transparenz UX", "C-05.2 - Transparency UX"),
    "C-05.2 - Transparence utilisateur": (
        "C-05.2 - Nutzertransparenz",
        "C-05.2 - User transparency",
    ),
    "C-06.1 - Roles & responsabilites": (
        "C-06.1 - Rollen & Verantwortlichkeiten",
        "C-06.1 - Roles & responsibilities",
    ),
    "C-06.6 - Retention": ("C-06.6 - Aufbewahrung", "C-06.6 - Retention"),
    "C-08.1 - Pseudonymisation": ("C-08.1 - Pseudonymisierung", "C-08.1 - Pseudonymization"),
    "C-08.2 - Minimisation": ("C-08.2 - Minimierung", "C-08.2 - Minimization"),
    "C-09.1 - Surveillance": ("C-09.1 - Ueberwachung", "C-09.1 - Monitoring"),
    "C-10.1 - Securite": ("C-10.1 - Sicherheit", "C-10.1 - Security"),
    "C-12.2 - Disponibilite": ("C-12.2 - Verfuegbarkeit", "C-12.2 - Availability"),
    "C-12.4 - Journalisation": ("C-12.4 - Protokollierung", "C-12.4 - Logging"),
    "C-13.2 - Donnees": ("C-13.2 - Daten", "C-13.2 - Data"),
    "C-13.2 - Gouvernance des donnees": (
        "C-13.2 - Daten-Governance",
        "C-13.2 - Data governance",
    ),
    "C-13.2 - Plan de remediation": ("C-13.2 - Behebungsplan", "C-13.2 - Remediation plan"),
    "C-15.1 - Gestion du risque": ("C-15.1 - Risikomanagement", "C-15.1 - Risk management"),
    "C-15.2 - Mesures d'attenuation": (
        "C-15.2 - Minderungsmassnahmen",
        "C-15.2 - Mitigation measures",
    ),
    "C-17.1 - Effacement": ("C-17.1 - Loeschung", "C-17.1 - Erasure"),
    "C-22.1 - Decision auto": ("C-22.1 - Auto-Entscheidung", "C-22.1 - Auto decision"),
    "C-30.1 - Registre": ("C-30.1 - Verzeichnis", "C-30.1 - Register"),
    "C-30.1 - Tenue du registre": ("C-30.1 - Verzeichnisfuehrung", "C-30.1 - Register keeping"),
    "C-DORA.1 - Risques TIC": ("C-DORA.1 - IKT-Risiken", "C-DORA.1 - ICT risks"),
    "C-DORA.1 - Test resilience": ("C-DORA.1 - Resilienztest", "C-DORA.1 - Resilience test"),
    # --- legal-basis full strings -------------------------------------------
    "Consentement - RGPD Art. 6": ("Einwilligung - DSGVO Art. 6", "Consent - GDPR Art. 6"),
    "Contrat - RGPD Art. 6": ("Vertrag - DSGVO Art. 6", "Contract - GDPR Art. 6"),
    "Interet legitime - RGPD Art. 6": (
        "Berechtigtes Interesse - DSGVO Art. 6",
        "Legitimate interest - GDPR Art. 6",
    ),
    "Obligation legale - LCB-FT": ("Rechtliche Verpflichtung - GwG", "Legal obligation - AML-CFT"),
    "Obligation legale - LPF": ("Rechtliche Verpflichtung - LPF", "Legal obligation - LPF"),
    "Base legale a justifier": ("Rechtsgrundlage zu begruenden", "Legal basis to justify"),
    "Base legale a reconfirmer": ("Rechtsgrundlage neu zu bestaetigen", "Legal basis to reconfirm"),
    "Sous-traitant a documenter": ("Auftragsverarbeiter zu dokumentieren", "Processor to document"),
    # --- detail prose --------------------------------------------------------
    "Maintenir un systeme de gestion des risques pour l'IA a haut risque.": (
        "Ein Risikomanagementsystem fuer Hochrisiko-KI aufrechterhalten.",
        "Maintain a risk-management system for high-risk AI.",
    ),
    "Systemes d'IA a haut risque, GPAI, transparence et surveillance humaine.": (
        "Hochrisiko-KI-Systeme, GPAI, Transparenz und menschliche Aufsicht.",
        "High-risk AI systems, GPAI, transparency and human oversight.",
    ),
    "Evaluation de solvabilite sur base contractuelle, sans decision automatisee.": (
        "Bonitaetspruefung auf Vertragsbasis, ohne automatisierte Entscheidung.",
        "Creditworthiness assessment on a contractual basis, without automated decision.",
    ),
    "Derogation temporaire RGPD - Art. 6 (3) en attente de mesure compensatoire.": (
        "Befristete DSGVO-Ausnahme - Art. 6 (3), wartet auf Ausgleichsmassnahme.",
        "Temporary GDPR waiver - Art. 6 (3), pending compensating measure.",
    ),
    "Retention 90 jours sur interet legitime, purge automatique nocturne.": (
        "90 Tage Aufbewahrung auf berechtigtem Interesse, naechtliche Auto-Loeschung.",
        "90-day retention on legitimate interest, nightly automatic purge.",
    ),
    "Rapport de gestion du risque EU AI Act - Art. 9, signe et horodate.": (
        "EU-AI-Act-Risikomanagementbericht - Art. 9, signiert und mit Zeitstempel.",
        "EU AI Act risk-management report - Art. 9, signed and timestamped.",
    ),
    "Score de conformite 82 % - 11 echecs critiques, 248 controles evalues.": (
        "Konformitaetsscore 82 % - 11 kritische Fehler, 248 bewertete Kontrollen.",
        "Compliance score 82% - 11 critical failures, 248 controls evaluated.",
    ),
    # --- activity-log entries (code kept, FR clause translated) -------------
    "Controle CTRL-09 mis a jour (RGPD)": (
        "Kontrolle CTRL-09 aktualisiert (DSGVO)",
        "Control CTRL-09 updated (GDPR)",
    ),
    "Controle CTRL-13 repasse conforme": (
        "Kontrolle CTRL-13 wieder konform",
        "Control CTRL-13 back to compliant",
    ),
    "Controle depasse": ("Kontrolle ueberfaellig", "Control overdue"),
    "Obligation Art. 13 marquee partielle": (
        "Pflicht Art. 13 als teilweise markiert",
        "Obligation Art. 13 marked partial",
    ),
    "Obligation OBL-1123 marquee conforme (RGPD)": (
        "Pflicht OBL-1123 als konform markiert (DSGVO)",
        "Obligation OBL-1123 marked compliant (GDPR)",
    ),
    "Exception EXC-2026-004 creee (DORA)": (
        "Ausnahme EXC-2026-004 erstellt (DORA)",
        "Exception EXC-2026-004 created (DORA)",
    ),
    "EXC-2026-009 approuvee": ("EXC-2026-009 genehmigt", "EXC-2026-009 approved"),
    "Ecart EXC-2026-007 ouvert (DORA)": (
        "Abweichung EXC-2026-007 offen (DORA)",
        "Gap EXC-2026-007 open (DORA)",
    ),
    "INC-2026-001 marquee depassee": (
        "INC-2026-001 als ueberfaellig markiert",
        "INC-2026-001 marked overdue",
    ),
    "INC-2026-003 escalade a Sophie Bernard": (
        "INC-2026-003 an Sophie Bernard eskaliert",
        "INC-2026-003 escalated to Sophie Bernard",
    ),
    "Evaluation EU AI Act terminee": (
        "EU-AI-Act-Evaluierung abgeschlossen",
        "EU AI Act evaluation completed",
    ),
    "Evaluation ISO 27001 completee": (
        "ISO-27001-Evaluierung abgeschlossen",
        "ISO 27001 evaluation completed",
    ),
    "Evaluation ISO 27001 terminee": (
        "ISO-27001-Evaluierung abgeschlossen",
        "ISO 27001 evaluation finished",
    ),
    "Evidence pack EU AI Act genere": (
        "Evidence-Pack EU AI Act erzeugt",
        "EU AI Act evidence pack generated",
    ),
    "Campagne RGPD relancee": ("DSGVO-Kampagne neu gestartet", "GDPR campaign relaunched"),
    "Attestation DORA renouvelee": ("DORA-Bescheinigung erneuert", "DORA attestation renewed"),
    "Legal hold ajoute sur Jeux d'evaluation": (
        "Legal Hold auf Evaluierungssets hinzugefuegt",
        "Legal hold added on evaluation sets",
    ),
    "Regle Exports SIEM mise a jour": (
        "Regel SIEM-Exporte aktualisiert",
        "SIEM exports rule updated",
    ),
    "Traitement Scoring credit mis a jour": (
        "Verarbeitung Kredit-Scoring aktualisiert",
        "Credit-scoring processing updated",
    ),
    "Purge auto Logs d'agent executee": (
        "Auto-Loeschung Agent-Protokolle ausgefuehrt",
        "Auto-purge agent logs executed",
    ),
    "Transcriptions purge en retard signalee": (
        "Transkript-Loeschung verspaetet gemeldet",
        "Transcripts purge reported late",
    ),
    "Base legale KYC Screening signalee": (
        "Rechtsgrundlage KYC-Screening gemeldet",
        "KYC screening legal basis flagged",
    ),
    "Revue C-30.1 planifiee": ("Pruefung C-30.1 geplant", "Review C-30.1 scheduled"),
    "Revue trimestrielle dediee": ("Dedizierte Quartalspruefung", "Dedicated quarterly review"),
    "PRV-2026-06-0102 horodatee (ISO)": (
        "PRV-2026-06-0102 mit Zeitstempel (ISO)",
        "PRV-2026-06-0102 timestamped (ISO)",
    ),
    "PRV-2026-06-0118 exportee (RGPD)": (
        "PRV-2026-06-0118 exportiert (DSGVO)",
        "PRV-2026-06-0118 exported (GDPR)",
    ),
    "PRV-2026-06-0123 signee (EU AI Act)": (
        "PRV-2026-06-0123 signiert (EU AI Act)",
        "PRV-2026-06-0123 signed (EU AI Act)",
    ),
    "PRV-2026-06-0130 generee (SOC 2)": (
        "PRV-2026-06-0130 erzeugt (SOC 2)",
        "PRV-2026-06-0130 generated (SOC 2)",
    ),
    "Preuve EV-2026-06-0204 ajoutee": (
        "Nachweis EV-2026-06-0204 hinzugefuegt",
        "Evidence EV-2026-06-0204 added",
    ),
    "Preuve EV-2026-06-0318 liee a C-15.1": (
        "Nachweis EV-2026-06-0318 mit C-15.1 verknuepft",
        "Evidence EV-2026-06-0318 linked to C-15.1",
    ),
    "Preuve EV-2026-06-0321 ajoutee a EU AI Act": (
        "Nachweis EV-2026-06-0321 zu EU AI Act hinzugefuegt",
        "Evidence EV-2026-06-0321 added to EU AI Act",
    ),
    "Preuve PRV-2026-04-0044 marquee manquante": (
        "Nachweis PRV-2026-04-0044 als fehlend markiert",
        "Evidence PRV-2026-04-0044 marked missing",
    ),
    # --- misc ----------------------------------------------------------------
    "Comite Conformite": ("Konformitaetskomitee", "Compliance committee"),
    "Purge automatique": ("Automatische Loeschung", "Automatic purge"),
    "Securite - ISO 27001": ("Sicherheit - ISO 27001", "Security - ISO 27001"),
    "purge auto": ("Auto-Loeschung", "auto purge"),
    "purge manuelle": ("manuelle Loeschung", "manual purge"),
    "purge manuelle en retard": ("manuelle Loeschung verspaetet", "manual purge late"),
    "Genere le": ("Erstellt am", "Generated on"),
    "Log signe": ("Signiertes Protokoll", "Signed log"),
    "Derogation temporaire": ("Befristete Ausnahme", "Temporary waiver"),
    "il y a 1 h": ("vor 1 Std", "1 h ago"),
    "il y a 2 h": ("vor 2 Std", "2 h ago"),
    "il y a 3 h": ("vor 3 Std", "3 h ago"),
    "il y a 4 h": ("vor 4 Std", "4 h ago"),
    "il y a 5 h": ("vor 5 Std", "5 h ago"),
    "il y a 6 h": ("vor 6 Std", "6 h ago"),
    "il y a 7 h": ("vor 7 Std", "7 h ago"),
    "dans 6 jours": ("in 6 Tagen", "in 6 days"),
    "dans 11 jours": ("in 11 Tagen", "in 11 days"),
    "dans 12 jours": ("in 12 Tagen", "in 12 days"),
    "dans 15 jours": ("in 15 Tagen", "in 15 days"),
    "dans 18 jours": ("in 18 Tagen", "in 18 days"),
    "dans 22 jours": ("in 22 Tagen", "in 22 days"),
    "dans 30 jours": ("in 30 Tagen", "in 30 days"),
    "dans 45 jours": ("in 45 Tagen", "in 45 days"),
    "dans 60 jours": ("in 60 Tagen", "in 60 days"),
}


def _localize(value: object, idx: int) -> object:
    """Recursively map every translatable string leaf to locale ``idx`` (de/en)."""
    if isinstance(value, str):
        pair = _TR.get(value)
        return pair[idx] if pair else value
    if isinstance(value, dict):
        return {k: _localize(v, idx) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return type(value)(_localize(v, idx) for v in value)
    if is_dataclass(value) and not isinstance(value, type):
        kwargs = {f.name: _localize(getattr(value, f.name), idx) for f in fields(value)}
        return type(value)(**kwargs)
    return value


def build_tabs(lang: str = "fr") -> dict[str, CatalogTab]:
    """Return the per-tab payloads for the Conformite command bar in ``lang``.

    The fixture is authored in French (the source of truth); for ``de`` / ``en``
    each string leaf is mapped through ``_TR`` (unmapped strings fall through
    verbatim), so the governance catalogues are localized end to end.
    """
    tabs = _build_fr_tabs()
    idx = _LANG_IDX.get(lang, 0)
    if idx == 0:
        return tabs
    return {key: cast("CatalogTab", _localize(tab, idx - 1)) for key, tab in tabs.items()}
