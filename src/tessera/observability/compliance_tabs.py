"""Per-tab payloads for the Conformite command bar (reference images, tab set).

The Conformite overview (``compliance.py``) is derived live from the real runtime
signals. The remaining command-bar tabs -- Cartographie reglementaire, Obligations
& controles, Evaluations, Incidents & exceptions, Purge & retention, Preuves &
attestations, Registre des traitements -- are *governance catalogues*: regulatory
mappings, treatment registers, retention rules, evidence inventories. Exactly like
the security case identifiers, this metadata is fixed, deterministic fixture data
so the page is stable on every refetch.

The payload uses one generic, render-friendly shape (``ComplianceTab``) shared by
every tab: a KPI strip, a main table with a sticky detail panel, and a band of
bottom sections. The frontend renders each tab from this shape, so adding or
tuning a tab is a pure-data change here.

Display labels are kept in French inside the data (owners, framework names, column
headers and section titles are all part of the regulatory content), matching how
every other catalogue page in Tessera carries its domain text.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = [
    "ComplianceTab",
    "DetailField",
    "DetailList",
    "TabColumn",
    "TabDetail",
    "TabKpi",
    "TabRow",
    "TabSection",
    "SectionItem",
    "build_tabs",
]


@dataclass(frozen=True, slots=True)
class TabKpi:
    """One KPI tile in a tab strip."""

    label: str
    value: str
    unit: str | None = None
    sub: str | None = None
    delta: str | None = None  # pre-formatted, ASCII signs, e.g. "+8.2%"
    delta_good: bool | None = None  # True -> green, False -> red
    tone: str | None = None  # good | warn | bad | neutral


@dataclass(frozen=True, slots=True)
class TabColumn:
    """A column descriptor for the main table."""

    key: str
    label: str
    kind: str = "text"  # text | num | delta | badge | owner | mono | bar | pct
    align: str = "left"


@dataclass(frozen=True, slots=True)
class TabRow:
    """One table row. ``cells`` maps column key -> render value."""

    id: str
    cells: dict[str, object]


@dataclass(frozen=True, slots=True)
class DetailField:
    """A label/value pair in the detail panel."""

    label: str
    value: str
    tone: str | None = None


@dataclass(frozen=True, slots=True)
class DetailList:
    """A small titled list inside the detail panel."""

    title: str
    items: list[dict[str, object]] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class TabDetail:
    """The sticky right-hand detail panel for the selected row."""

    eyebrow: str
    title: str
    status_label: str | None
    status_tone: str | None
    summary: str | None
    fields: list[DetailField] = field(default_factory=list)
    lists: list[DetailList] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class SectionItem:
    """One row inside a bottom section."""

    label: str
    sub: str | None = None
    value: str | None = None
    badge: str | None = None
    badge_tone: str | None = None


@dataclass(frozen=True, slots=True)
class TabSection:
    """A bottom-band panel: list / activity / donut / bars / chart / actions."""

    title: str
    kind: str  # list | activity | donut | bars | chart | actions
    items: list[SectionItem] = field(default_factory=list)
    cta: str | None = None
    donut_value: float | None = None  # 0..1
    donut_label: str | None = None
    bars: list[dict[str, object]] = field(default_factory=list)  # {label,value,tone?}
    series: list[dict[str, object]] = field(default_factory=list)  # {label,color,points}
    actions: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ComplianceTab:
    """The full payload for one command-bar tab."""

    table_title: str
    kpis: list[TabKpi] = field(default_factory=list)
    columns: list[TabColumn] = field(default_factory=list)
    rows: list[TabRow] = field(default_factory=list)
    detail: TabDetail | None = None
    sections: list[TabSection] = field(default_factory=list)


# --- small builders -------------------------------------------------------


def _owner(name: str, role: str) -> dict[str, object]:
    return {"name": name, "role": role}


def _badge(label: str, tone: str) -> dict[str, object]:
    return {"label": label, "tone": tone}


def _delta(value: str, delta: str, good: bool) -> dict[str, object]:
    return {"value": value, "delta": delta, "good": good}


def _bar(have: int, total: int) -> dict[str, object]:
    return {"have": have, "total": total, "pct": round(have / total * 100) if total else 0}


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


def _tab_mapping() -> ComplianceTab:
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
    return ComplianceTab(
        "Cartographie reglementaire",
        kpis=kpis,
        columns=columns,
        rows=rows,
        detail=detail,
        sections=sections,
    )


# --- Obligations & controles ---------------------------------------------


def _tab_obligations() -> ComplianceTab:
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
    return ComplianceTab(
        "Obligations & controles",
        kpis=kpis,
        columns=columns,
        rows=rows,
        detail=detail,
        sections=sections,
    )


# --- Evaluations ----------------------------------------------------------


def _tab_evaluations() -> ComplianceTab:
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
    return ComplianceTab(
        "Evaluations",
        kpis=kpis,
        columns=columns,
        rows=rows,
        detail=detail,
        sections=sections,
    )


# --- Incidents & exceptions ----------------------------------------------


def _tab_incidents() -> ComplianceTab:
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
    return ComplianceTab(
        "Incidents & exceptions",
        kpis=kpis,
        columns=columns,
        rows=rows,
        detail=detail,
        sections=sections,
    )


# --- Purge & retention ----------------------------------------------------


def _tab_retention() -> ComplianceTab:
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
    return ComplianceTab(
        "Purge & retention",
        kpis=kpis,
        columns=columns,
        rows=rows,
        detail=detail,
        sections=sections,
    )


# --- Preuves & attestations ----------------------------------------------


def _tab_evidence() -> ComplianceTab:
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
    return ComplianceTab(
        "Inventaire des preuves & attestations",
        kpis=kpis,
        columns=columns,
        rows=rows,
        detail=detail,
        sections=sections,
    )


# --- Registre des traitements --------------------------------------------


def _tab_registry() -> ComplianceTab:
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
    return ComplianceTab(
        "Registre des traitements",
        kpis=kpis,
        columns=columns,
        rows=rows,
        detail=detail,
        sections=sections,
    )


def build_tabs() -> dict[str, ComplianceTab]:
    """Return the deterministic per-tab payloads for the Conformite command bar."""
    return {
        "mapping": _tab_mapping(),
        "obligations": _tab_obligations(),
        "evaluations": _tab_evaluations(),
        "incidents": _tab_incidents(),
        "retention": _tab_retention(),
        "evidence": _tab_evidence(),
        "registry": _tab_registry(),
    }
