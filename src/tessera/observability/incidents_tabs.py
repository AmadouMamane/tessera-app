"""Per-tab payloads for the Incidents & playbooks command bar (reference images).

The Incidents overview (``incidents.py``) is the analytics cockpit. The remaining
command-bar tabs -- Incidents, Playbooks, Orchestration, Actions, Post-mortems,
Problemes connus, Rapports -- are operational catalogues (live incident queue,
playbook library, orchestration workflows, governed actions, post-mortems, known
problems, reports). Like the security case identifiers, this is fixed,
deterministic fixture data so the page is stable on every refetch.

Each tab uses the shared ``CatalogTab`` shape (see ``catalog_tabs``); the frontend
renders any tab generically. Display labels stay in French inside the data, as on
every other catalogue page in Tessera.
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
    owner as _owner,
)

__all__ = ["build_tabs"]


# Recurring on-call / reliability owners across the operational catalogue.
_AMELIE = _owner("Amelie Dubois", "SRE Lead")
_KARIM = _owner("Karim Haddad", "On-call SRE")
_LEA = _owner("Lea Moreau", "Incident Manager")
_NICOLAS = _owner("Nicolas Faure", "Platform Eng")
_SARAH = _owner("Sarah Levy", "SecOps")
_MARC = _owner("Marc Dupont", "Reliability Eng")


# --- Incidents ------------------------------------------------------------


def _tab_incidents() -> CatalogTab:
    kpis = [
        TabKpi("Incidents ouverts", "29", delta="-8.0%", delta_good=True, tone="warn"),
        TabKpi("Incidents critiques", "6", delta="+2.0%", delta_good=False, tone="bad"),
        TabKpi("MTTD", "3m 12s", delta="-5.0%", delta_good=True, tone="good"),
        TabKpi("MTTR", "28m 20s", delta="-4.0%", delta_good=True, tone="good"),
        TabKpi("Playbooks actifs", "14", tone="good"),
        TabKpi("SLA respecte", "94", unit="%", delta="+1.0 pp", delta_good=True, tone="good"),
    ]
    columns = [
        TabColumn("id", "ID", "mono"),
        TabColumn("title", "Incident", "text"),
        TabColumn("severity", "Severite", "badge"),
        TabColumn("service", "Service", "text"),
        TabColumn("owner", "Owner", "owner"),
        TabColumn("age", "Age", "text", "right"),
        TabColumn("status", "Statut", "badge"),
    ]
    rows = [
        TabRow(
            "INC-2024-2291",
            {
                "id": "INC-2024-2291",
                "title": "Hallucination RAG sur scoring credit",
                "severity": _badge("Critique", "danger"),
                "service": "Agent RAG",
                "owner": _AMELIE,
                "age": "12 min",
                "status": _badge("En analyse", "warning"),
            },
        ),
        TabRow(
            "INC-2024-2288",
            {
                "id": "INC-2024-2288",
                "title": "Latence elevee passerelle LLM",
                "severity": _badge("Eleve", "warning"),
                "service": "Gateway",
                "owner": _KARIM,
                "age": "34 min",
                "status": _badge("Mitige", "info"),
            },
        ),
        TabRow(
            "INC-2024-2285",
            {
                "id": "INC-2024-2285",
                "title": "Fuite PII potentielle en reponse",
                "severity": _badge("Critique", "danger"),
                "service": "Guardrails",
                "owner": _SARAH,
                "age": "1 h 02",
                "status": _badge("Ouvert", "danger"),
            },
        ),
        TabRow(
            "INC-2024-2280",
            {
                "id": "INC-2024-2280",
                "title": "Echec d'outil card_block",
                "severity": _badge("Moyen", "info"),
                "service": "Tools",
                "owner": _NICOLAS,
                "age": "2 h 15",
                "status": _badge("En analyse", "warning"),
            },
        ),
        TabRow(
            "INC-2024-2274",
            {
                "id": "INC-2024-2274",
                "title": "Pic de refus injustifies",
                "severity": _badge("Eleve", "warning"),
                "service": "Agent",
                "owner": _LEA,
                "age": "3 h 40",
                "status": _badge("Mitige", "info"),
            },
        ),
        TabRow(
            "INC-2024-2269",
            {
                "id": "INC-2024-2269",
                "title": "Degradation embeddings Vertex",
                "severity": _badge("Moyen", "info"),
                "service": "Retrieval",
                "owner": _MARC,
                "age": "5 h 12",
                "status": _badge("Resolu", "success"),
            },
        ),
    ]
    detail = TabDetail(
        eyebrow="Incident",
        title="INC-2024-2291",
        status_label="Critique",
        status_tone="danger",
        summary="Hallucination detectee sur une reponse de scoring credit, playbook RAG declenche.",
        fields=[
            DetailField("Severite", "Critique", "danger"),
            DetailField("Service", "Agent RAG"),
            DetailField("Detecte", "il y a 12 min"),
            DetailField("MTTD", "3m 12s"),
            DetailField("SLA", "dans 18 min", "warning"),
            DetailField("Owner", "Amelie Dubois"),
        ],
        lists=[
            DetailList(
                "Playbook lie",
                [
                    {"label": "PB-04 RAG Hallucination", "badge": "En cours", "tone": "warning"},
                ],
            ),
            DetailList(
                "Preuves liees",
                [
                    {"label": "EV-2026-06-0481"},
                    {"label": "EV-2026-06-0479"},
                ],
            ),
        ],
        actions=["Acquitter", "Ouvrir le playbook", "Escalader"],
    )
    sections = [
        TabSection(
            "Repartition par severite",
            "donut",
            donut_value=0.0,
            donut_label="29 ouverts",
            items=[
                SectionItem("Critique", value="6", badge_tone="danger"),
                SectionItem("Eleve", value="9", badge_tone="warning"),
                SectionItem("Moyen", value="11", badge_tone="info"),
                SectionItem("Faible", value="3", badge_tone="neutral"),
            ],
        ),
        TabSection(
            "Triage",
            "list",
            items=[
                SectionItem("Nouveau", value="5", badge_tone="info"),
                SectionItem("En analyse", value="11", badge_tone="warning"),
                SectionItem("En attente", value="7", badge_tone="neutral"),
                SectionItem("Resolu (24h)", value="18", badge_tone="success"),
            ],
            cta="Ouvrir le tableau de triage",
        ),
        TabSection(
            "Activite recente",
            "activity",
            items=[
                SectionItem("INC-2024-2291 escalade en critique", "il y a 4 min"),
                SectionItem("PB-04 declenche sur INC-2024-2291", "il y a 11 min"),
                SectionItem("INC-2024-2269 resolu par Marc Dupont", "il y a 1 h"),
                SectionItem("INC-2024-2288 mitige (rollback gateway)", "il y a 1 h"),
            ],
            cta="Voir toute l'activite",
        ),
        TabSection(
            "Actions rapides",
            "actions",
            actions=[
                "Declarer un incident",
                "Lancer un playbook",
                "Escalader",
                "Exporter le journal",
            ],
        ),
    ]
    return CatalogTab(
        "File d'incidents en temps reel",
        kpis=kpis,
        columns=columns,
        rows=rows,
        detail=detail,
        sections=sections,
    )


# --- Playbooks ------------------------------------------------------------


def _tab_playbooks() -> CatalogTab:
    kpis = [
        TabKpi("Playbooks actifs", "128", tone="good"),
        TabKpi("Taux de succes", "96.3", unit="%", delta="+1.2 pp", delta_good=True, tone="good"),
        TabKpi("Executions en cours", "14", tone="good"),
        TabKpi("Temps moyen", "18m 2s", delta="-6.0%", delta_good=True),
        TabKpi("Approbations en attente", "9", delta="+1.0%", delta_good=False, tone="warn"),
        TabKpi("Playbooks bloques", "3", delta="-1.0%", delta_good=True, tone="warn"),
    ]
    columns = [
        TabColumn("id", "ID", "mono"),
        TabColumn("name", "Playbook", "text"),
        TabColumn("trigger", "Declencheur", "text"),
        TabColumn("steps", "Etapes", "num", "right"),
        TabColumn("success", "Taux succes", "pct", "right"),
        TabColumn("owner", "Owner", "owner"),
        TabColumn("status", "Statut", "badge"),
    ]
    rows = [
        TabRow(
            "PB-04",
            {
                "id": "PB-04",
                "name": "RAG Hallucination - P0",
                "trigger": "Signal hallucination",
                "steps": "6",
                "success": {"pct": 97},
                "owner": _AMELIE,
                "status": _badge("Actif", "success"),
            },
        ),
        TabRow(
            "PB-07",
            {
                "id": "PB-07",
                "name": "Fuite PII - confinement",
                "trigger": "Signal PII",
                "steps": "8",
                "success": {"pct": 94},
                "owner": _SARAH,
                "status": _badge("Actif", "success"),
            },
        ),
        TabRow(
            "PB-11",
            {
                "id": "PB-11",
                "name": "Latence gateway - rollback",
                "trigger": "Seuil latence",
                "steps": "5",
                "success": {"pct": 91},
                "owner": _KARIM,
                "status": _badge("Actif", "success"),
            },
        ),
        TabRow(
            "PB-14",
            {
                "id": "PB-14",
                "name": "Prompt injection - isolation",
                "trigger": "Signal firewall",
                "steps": "7",
                "success": {"pct": 89},
                "owner": _NICOLAS,
                "status": _badge("En revue", "warning"),
            },
        ),
        TabRow(
            "PB-18",
            {
                "id": "PB-18",
                "name": "Outil en echec - reprise",
                "trigger": "Erreur d'outil",
                "steps": "4",
                "success": {"pct": 96},
                "owner": _MARC,
                "status": _badge("Actif", "success"),
            },
        ),
        TabRow(
            "PB-21",
            {
                "id": "PB-21",
                "name": "Refus excessif - recalibrage",
                "trigger": "Pic de refus",
                "steps": "5",
                "success": {"pct": 72},
                "owner": _LEA,
                "status": _badge("Bloque", "danger"),
            },
        ),
    ]
    detail = TabDetail(
        eyebrow="Playbook",
        title="RAG Hallucination - P0",
        status_label="Actif",
        status_tone="success",
        summary="Confinement et regeneration ancree d'une reponse hallucinee, capture de preuves.",
        fields=[
            DetailField("Type", "Mitigation automatique"),
            DetailField("Declencheur", "Signal hallucination"),
            DetailField("Etapes", "6"),
            DetailField("Taux de succes", "97 %", "success"),
            DetailField("Derniere execution", "il y a 11 min"),
            DetailField("Owner", "Amelie Dubois"),
        ],
        lists=[
            DetailList(
                "Etapes (6)",
                [
                    {"label": "1. Detection de signal", "badge": "OK", "tone": "success"},
                    {"label": "2. Validation & correlation", "badge": "OK", "tone": "success"},
                    {"label": "3. Triage & enrichissement", "badge": "OK", "tone": "success"},
                    {"label": "4. Mitigation", "badge": "En cours", "tone": "warning"},
                    {"label": "5. Preuve & capture", "badge": "En attente", "tone": "neutral"},
                    {"label": "6. Cloture", "badge": "En attente", "tone": "neutral"},
                ],
            ),
            DetailList(
                "Incidents lies (3)",
                [
                    {"label": "INC-2024-2291"},
                    {"label": "INC-2024-2240"},
                    {"label": "INC-2024-2188"},
                ],
            ),
        ],
        actions=["Executer", "Approuver", "Dupliquer", "Exporter"],
    )
    sections = [
        TabSection(
            "Couverture par type d'incident",
            "donut",
            donut_value=0.83,
            donut_label="128 playbooks",
            items=[
                SectionItem("Hallucination", value="34", badge_tone="danger"),
                SectionItem("PII / securite", value="41", badge_tone="warning"),
                SectionItem("Fiabilite", value="32", badge_tone="info"),
                SectionItem("Outils", value="21", badge_tone="neutral"),
            ],
        ),
        TabSection(
            "Versions du playbook",
            "list",
            items=[
                SectionItem("PB-04 v12", "actif", "il y a 2 j", badge_tone="success"),
                SectionItem("PB-04 v11", "archive", "il y a 18 j", badge_tone="neutral"),
                SectionItem("PB-04 v10", "archive", "il y a 41 j", badge_tone="neutral"),
            ],
            cta="Voir l'historique",
        ),
        TabSection(
            "Exceptions actives",
            "list",
            items=[
                SectionItem("PB-21 - recalibrage", "bloque", badge="Bloque", badge_tone="danger"),
                SectionItem("PB-14 - isolation", "en revue", badge="Revue", badge_tone="warning"),
                SectionItem("PB-09 - quarantaine", "approuvee", badge="OK", badge_tone="success"),
            ],
            cta="Voir les exceptions",
        ),
        TabSection(
            "Executions recentes",
            "activity",
            items=[
                SectionItem("PB-04 execute sur INC-2024-2291", "il y a 11 min"),
                SectionItem("PB-11 rollback gateway reussi", "il y a 1 h"),
                SectionItem("PB-07 confinement PII reussi", "il y a 2 h"),
                SectionItem("PB-21 suspendu (echec etape 3)", "il y a 4 h"),
            ],
            cta="Voir toutes les executions",
        ),
    ]
    return CatalogTab(
        "Bibliotheque de playbooks",
        kpis=kpis,
        columns=columns,
        rows=rows,
        detail=detail,
        sections=sections,
    )


# --- Orchestration --------------------------------------------------------


def _tab_orchestration() -> CatalogTab:
    kpis = [
        TabKpi("Regles de routage", "128", tone="good"),
        TabKpi("Workflows en cours", "37", tone="good"),
        TabKpi("Cles d'automatisation", "248", delta="+4.0%", delta_good=True),
        TabKpi("Erreurs d'orchestration", "6", delta="-2.0%", delta_good=True, tone="warn"),
        TabKpi("Temps de cycle p50", "4.2s", delta="-5.0%", delta_good=True, tone="good"),
        TabKpi("Disponibilite", "37", unit="/42", tone="good"),
    ]
    columns = [
        TabColumn("id", "ID", "mono"),
        TabColumn("name", "Workflow", "text"),
        TabColumn("trigger", "Declencheur", "text"),
        TabColumn("latency", "Latence p50", "text", "right"),
        TabColumn("success", "Taux succes", "pct", "right"),
        TabColumn("owner", "Owner", "owner"),
        TabColumn("status", "Statut", "badge"),
    ]
    rows = [
        TabRow(
            "WF-CRIT-PRIV-01",
            {
                "id": "WF-CRIT-PRIV-01",
                "name": "Routage incident critique privacy",
                "trigger": "Severite critique",
                "latency": "5.1 s",
                "success": {"pct": 98},
                "owner": _SARAH,
                "status": _badge("Actif", "success"),
            },
        ),
        TabRow(
            "WF-RAG-02",
            {
                "id": "WF-RAG-02",
                "name": "Enrichissement signal RAG",
                "trigger": "Signal hallucination",
                "latency": "3.4 s",
                "success": {"pct": 96},
                "owner": _AMELIE,
                "status": _badge("Actif", "success"),
            },
        ),
        TabRow(
            "WF-GW-03",
            {
                "id": "WF-GW-03",
                "name": "Auto-remediation gateway",
                "trigger": "Seuil latence",
                "latency": "2.8 s",
                "success": {"pct": 92},
                "owner": _KARIM,
                "status": _badge("Actif", "success"),
            },
        ),
        TabRow(
            "WF-TOOL-04",
            {
                "id": "WF-TOOL-04",
                "name": "Reprise outil en echec",
                "trigger": "Erreur d'outil",
                "latency": "4.6 s",
                "success": {"pct": 88},
                "owner": _NICOLAS,
                "status": _badge("Degrade", "warning"),
            },
        ),
        TabRow(
            "WF-ESC-05",
            {
                "id": "WF-ESC-05",
                "name": "Escalade & notification astreinte",
                "trigger": "SLA a risque",
                "latency": "1.9 s",
                "success": {"pct": 99},
                "owner": _LEA,
                "status": _badge("Actif", "success"),
            },
        ),
        TabRow(
            "WF-EVID-06",
            {
                "id": "WF-EVID-06",
                "name": "Collecte de preuve & cloture",
                "trigger": "Fin de mitigation",
                "latency": "6.2 s",
                "success": {"pct": 94},
                "owner": _MARC,
                "status": _badge("Actif", "success"),
            },
        ),
    ]
    detail = TabDetail(
        eyebrow="Workflow",
        title="WF-CRIT-PRIV-01",
        status_label="Actif",
        status_tone="success",
        summary="Route les incidents critiques privacy vers SecOps avec confinement immediat.",
        fields=[
            DetailField("Declencheur", "Severite critique + domaine privacy"),
            DetailField("Etapes", "7"),
            DetailField("Latence p50", "5.1 s"),
            DetailField("Taux de succes", "98 %", "success"),
            DetailField("Executions 24h", "42"),
            DetailField("Owner", "Sarah Levy"),
        ],
        lists=[
            DetailList(
                "Conditions",
                [
                    {"label": "severite == critique", "badge": "OK", "tone": "success"},
                    {"label": "domaine == privacy", "badge": "OK", "tone": "success"},
                    {"label": "PII detectee", "badge": "OK", "tone": "success"},
                ],
            ),
            DetailList(
                "Actions en sortie",
                [
                    {"label": "Confinement reponse"},
                    {"label": "Notification SecOps"},
                    {"label": "Ouverture ticket P0"},
                ],
            ),
        ],
        actions=["Editer le workflow", "Tester a blanc", "Suspendre"],
    )
    sections = [
        TabSection(
            "Temps de cycle (p50)",
            "chart",
            series=[
                {"label": "p50", "color": "#3b82f6", "points": [4.8, 4.6, 4.4, 4.3, 4.2]},
                {"label": "p95", "color": "#f59e0b", "points": [9.1, 8.7, 8.9, 8.4, 8.2]},
            ],
            cta="Voir les latences",
        ),
        TabSection(
            "Workflows par famille",
            "bars",
            bars=[
                {"label": "Privacy", "value": 0.9, "tone": "danger"},
                {"label": "Fiabilite", "value": 0.72, "tone": "warning"},
                {"label": "RAG", "value": 0.64, "tone": "info"},
                {"label": "Outils", "value": 0.48, "tone": "neutral"},
            ],
        ),
        TabSection(
            "Erreurs recentes",
            "list",
            items=[
                SectionItem(
                    "WF-TOOL-04 - timeout etape 3",
                    "il y a 22 min",
                    badge="Erreur",
                    badge_tone="danger",
                ),
                SectionItem(
                    "WF-GW-03 - retry depasse", "il y a 1 h", badge="Erreur", badge_tone="warning"
                ),
                SectionItem(
                    "WF-RAG-02 - condition manquante",
                    "il y a 3 h",
                    badge="Avert",
                    badge_tone="warning",
                ),
            ],
            cta="Voir toutes les erreurs",
        ),
        TabSection(
            "Actions rapides",
            "actions",
            actions=["Nouveau workflow", "Importer une regle", "Voir le graphe", "Exporter"],
        ),
    ]
    return CatalogTab(
        "Workflows actifs",
        kpis=kpis,
        columns=columns,
        rows=rows,
        detail=detail,
        sections=sections,
    )


# --- Actions --------------------------------------------------------------


def _tab_actions() -> CatalogTab:
    kpis = [
        TabKpi("Actions en attente", "27", delta="+3.0%", delta_good=False, tone="warn"),
        TabKpi("Actions executees 24h", "184", delta="+6.0%", delta_good=True, tone="good"),
        TabKpi("Approbations requises", "31", tone="warn"),
        TabKpi("Habilitations disponibles", "9", sub="operateurs"),
        TabKpi("Taux de succes", "97.6", unit="%", delta="+0.4 pp", delta_good=True, tone="good"),
        TabKpi("Actions annulees", "4", delta="-2.0%", delta_good=True, tone="warn"),
    ]
    columns = [
        TabColumn("id", "ID", "mono"),
        TabColumn("type", "Type d'action", "text"),
        TabColumn("criticality", "Criticite", "badge"),
        TabColumn("requester", "Demandeur", "text"),
        TabColumn("owner", "Owner", "owner"),
        TabColumn("approval", "Approbation", "badge"),
        TabColumn("status", "Statut", "badge"),
    ]
    rows = [
        TabRow(
            "ACT-44213",
            {
                "id": "ACT-44213",
                "type": "Isoler workload support",
                "criticality": _badge("Critique", "danger"),
                "requester": "SOC Bot",
                "owner": _SARAH,
                "approval": _badge("Dual control", "warning"),
                "status": _badge("En attente", "warning"),
            },
        ),
        TabRow(
            "ACT-44210",
            {
                "id": "ACT-44210",
                "type": "Rollback gateway v2.2.15",
                "criticality": _badge("Eleve", "warning"),
                "requester": "PB-11",
                "owner": _KARIM,
                "approval": _badge("Auto", "info"),
                "status": _badge("Executee", "success"),
            },
        ),
        TabRow(
            "ACT-44207",
            {
                "id": "ACT-44207",
                "type": "Purge cache embeddings",
                "criticality": _badge("Moyen", "info"),
                "requester": "M. Dupont",
                "owner": _MARC,
                "approval": _badge("Approuvee", "success"),
                "status": _badge("Executee", "success"),
            },
        ),
        TabRow(
            "ACT-44203",
            {
                "id": "ACT-44203",
                "type": "Revoquer cle API tierce",
                "criticality": _badge("Critique", "danger"),
                "requester": "SecOps",
                "owner": _SARAH,
                "approval": _badge("Dual control", "warning"),
                "status": _badge("En attente", "warning"),
            },
        ),
        TabRow(
            "ACT-44198",
            {
                "id": "ACT-44198",
                "type": "Redemarrer worker retrieval",
                "criticality": _badge("Moyen", "info"),
                "requester": "PB-18",
                "owner": _NICOLAS,
                "approval": _badge("Auto", "info"),
                "status": _badge("Executee", "success"),
            },
        ),
        TabRow(
            "ACT-44190",
            {
                "id": "ACT-44190",
                "type": "Forcer recalibrage refus",
                "criticality": _badge("Eleve", "warning"),
                "requester": "PB-21",
                "owner": _LEA,
                "approval": _badge("Rejetee", "danger"),
                "status": _badge("Annulee", "danger"),
            },
        ),
    ]
    detail = TabDetail(
        eyebrow="Action",
        title="ACT-44213",
        status_label="En attente",
        status_tone="warning",
        summary="Isoler le workload support suite a INC-2024-2285, en attente de dual control.",
        fields=[
            DetailField("Type", "Isolation reseau"),
            DetailField("Criticite", "Critique", "danger"),
            DetailField("Demandeur", "SOC Bot"),
            DetailField("Cible", "ns/support, pods 4"),
            DetailField("Fenetre", "immediate"),
            DetailField("Owner", "Sarah Levy"),
        ],
        lists=[
            DetailList(
                "Verifications de securite (pre-execution)",
                [
                    {"label": "Perimetre confirme", "badge": "OK", "tone": "success"},
                    {"label": "Sauvegarde disponible", "badge": "OK", "tone": "success"},
                    {"label": "Impact estime borne", "badge": "OK", "tone": "success"},
                ],
            ),
            DetailList(
                "Dual control",
                [
                    {"label": "Sarah Levy", "badge": "Validee", "tone": "success"},
                    {"label": "Lea Moreau", "badge": "En attente", "tone": "warning"},
                ],
            ),
        ],
        actions=["Approuver", "Rejeter", "Executer", "Planifier"],
    )
    sections = [
        TabSection(
            "Actions par criticite",
            "bars",
            bars=[
                {"label": "Critique", "value": 0.85, "tone": "danger"},
                {"label": "Eleve", "value": 0.6, "tone": "warning"},
                {"label": "Moyen", "value": 0.4, "tone": "info"},
                {"label": "Faible", "value": 0.2, "tone": "neutral"},
            ],
        ),
        TabSection(
            "Approbations en attente",
            "list",
            items=[
                SectionItem(
                    "ACT-44213 - isolation", "dual control", badge="P0", badge_tone="danger"
                ),
                SectionItem(
                    "ACT-44203 - revocation cle", "dual control", badge="P0", badge_tone="danger"
                ),
                SectionItem("ACT-44188 - quarantaine", "simple", badge="P2", badge_tone="info"),
            ],
            cta="Voir les approbations",
        ),
        TabSection(
            "Executions recentes",
            "activity",
            items=[
                SectionItem("ACT-44210 rollback gateway reussi", "il y a 1 h"),
                SectionItem("ACT-44207 purge cache reussie", "il y a 2 h"),
                SectionItem("ACT-44190 annulee (rejet dual control)", "il y a 4 h"),
                SectionItem("ACT-44198 redemarrage worker reussi", "il y a 5 h"),
            ],
            cta="Voir toutes les executions",
        ),
        TabSection(
            "Actions rapides",
            "actions",
            actions=["Nouvelle action", "Gerer les habilitations", "Voir le journal", "Exporter"],
        ),
    ]
    return CatalogTab(
        "File d'actions gouvernees",
        kpis=kpis,
        columns=columns,
        rows=rows,
        detail=detail,
        sections=sections,
    )


# --- Post-mortems ---------------------------------------------------------


def _tab_postmortems() -> CatalogTab:
    kpis = [
        TabKpi("Post-mortems ouverts", "8", tone="warn"),
        TabKpi("Post-mortems retardes", "3", delta="+1.0%", delta_good=False, tone="bad"),
        TabKpi("Completes (30j)", "34", delta="+12.0%", delta_good=True, tone="good"),
        TabKpi("Actions correctives", "112", delta="+5.0%", delta_good=True),
        TabKpi("Temps moyen de cloture", "7j 3h", delta="-8.0%", delta_good=True, tone="good"),
        TabKpi("Recidives", "6", delta="-2.0%", delta_good=True, tone="warn"),
    ]
    columns = [
        TabColumn("id", "ID", "mono"),
        TabColumn("incident", "Incident", "mono"),
        TabColumn("title", "Sujet", "text"),
        TabColumn("severity", "Severite", "badge"),
        TabColumn("owner", "Owner", "owner"),
        TabColumn("due", "Echeance", "text", "right"),
        TabColumn("status", "Statut", "badge"),
    ]
    rows = [
        TabRow(
            "PM-2024-231",
            {
                "id": "PM-2024-231",
                "incident": "INC-2024-2188",
                "title": "Hallucination RAG recurrente",
                "severity": _badge("Critique", "danger"),
                "owner": _AMELIE,
                "due": "22 jun 2026",
                "status": _badge("En cours", "warning"),
            },
        ),
        TabRow(
            "PM-2024-229",
            {
                "id": "PM-2024-229",
                "incident": "INC-2024-2150",
                "title": "Fuite PII en reponse",
                "severity": _badge("Critique", "danger"),
                "owner": _SARAH,
                "due": "19 jun 2026",
                "status": _badge("Retarde", "danger"),
            },
        ),
        TabRow(
            "PM-2024-226",
            {
                "id": "PM-2024-226",
                "incident": "INC-2024-2102",
                "title": "Panne gateway prolongee",
                "severity": _badge("Eleve", "warning"),
                "owner": _KARIM,
                "due": "25 jun 2026",
                "status": _badge("En cours", "warning"),
            },
        ),
        TabRow(
            "PM-2024-221",
            {
                "id": "PM-2024-221",
                "incident": "INC-2024-2044",
                "title": "Refus excessifs apres deploiement",
                "severity": _badge("Moyen", "info"),
                "owner": _LEA,
                "due": "12 jun 2026",
                "status": _badge("Valide", "success"),
            },
        ),
        TabRow(
            "PM-2024-218",
            {
                "id": "PM-2024-218",
                "incident": "INC-2024-2001",
                "title": "Degradation embeddings",
                "severity": _badge("Moyen", "info"),
                "owner": _MARC,
                "due": "08 jun 2026",
                "status": _badge("Valide", "success"),
            },
        ),
        TabRow(
            "PM-2024-214",
            {
                "id": "PM-2024-214",
                "incident": "INC-2024-1960",
                "title": "Echec outil card_block",
                "severity": _badge("Eleve", "warning"),
                "owner": _NICOLAS,
                "due": "03 jun 2026",
                "status": _badge("Valide", "success"),
            },
        ),
    ]
    detail = TabDetail(
        eyebrow="Post-mortem",
        title="PM-2024-231",
        status_label="En cours",
        status_tone="warning",
        summary="Hallucination RAG recurrente sur le scoring credit, cause mere en ancrage.",
        fields=[
            DetailField("Incident", "INC-2024-2188"),
            DetailField("Severite", "Critique", "danger"),
            DetailField("Owner", "Amelie Dubois"),
            DetailField("Echeance", "22 jun 2026", "warning"),
            DetailField("Actions correctives", "5"),
            DetailField("Recidive", "Oui (2)", "danger"),
        ],
        lists=[
            DetailList(
                "Causes meres",
                [
                    {
                        "label": "Chunking trop large du corpus",
                        "badge": "Confirmee",
                        "tone": "danger",
                    },
                    {"label": "Reranker desactive en prod", "badge": "Confirmee", "tone": "danger"},
                    {
                        "label": "Seuil de confiance trop bas",
                        "badge": "Probable",
                        "tone": "warning",
                    },
                ],
            ),
            DetailList(
                "Actions assignees",
                [
                    {"label": "Reduire la taille de chunk", "badge": "En cours", "tone": "warning"},
                    {"label": "Reactiver le reranker", "badge": "A faire", "tone": "neutral"},
                ],
            ),
        ],
        actions=["Editer", "Assigner une action", "Valider", "Exporter"],
    )
    sections = [
        TabSection(
            "Repartition par severite",
            "donut",
            donut_value=0.0,
            donut_label="8 ouverts",
            items=[
                SectionItem("Critique", value="2", badge_tone="danger"),
                SectionItem("Eleve", value="3", badge_tone="warning"),
                SectionItem("Moyen", value="3", badge_tone="info"),
            ],
        ),
        TabSection(
            "Actions correctives par statut",
            "bars",
            bars=[
                {"label": "A faire", "value": 0.35, "tone": "neutral"},
                {"label": "En cours", "value": 0.45, "tone": "warning"},
                {"label": "Terminees", "value": 0.8, "tone": "success"},
            ],
        ),
        TabSection(
            "Recidives",
            "list",
            items=[
                SectionItem(
                    "Hallucination RAG", "2 recidives", badge="PM-231", badge_tone="danger"
                ),
                SectionItem("Latence gateway", "1 recidive", badge="PM-226", badge_tone="warning"),
                SectionItem("Refus excessifs", "1 recidive", badge="PM-221", badge_tone="warning"),
            ],
            cta="Voir les recidives",
        ),
        TabSection(
            "Activites recentes",
            "activity",
            items=[
                SectionItem("PM-2024-231 cause mere confirmee", "il y a 2 h"),
                SectionItem("PM-2024-221 valide par Lea Moreau", "hier"),
                SectionItem("PM-2024-229 marque retarde", "hier"),
            ],
            cta="Voir toutes les activites",
        ),
    ]
    return CatalogTab(
        "Post-mortems",
        kpis=kpis,
        columns=columns,
        rows=rows,
        detail=detail,
        sections=sections,
    )


# --- Problemes connus -----------------------------------------------------


def _tab_problemes() -> CatalogTab:
    kpis = [
        TabKpi("Problemes ouverts", "47", tone="warn"),
        TabKpi("Workarounds actifs", "31", tone="good"),
        TabKpi("Recurrences", "56", delta="+4.0%", delta_good=False, tone="warn"),
        TabKpi("Dette technique critique", "12", delta="+1.0%", delta_good=False, tone="bad"),
        TabKpi("Composants impactes", "68", delta="+3.0%", delta_good=False, tone="warn"),
        TabKpi("Demandes d'escalade", "9", delta="-1.0%", delta_good=True, tone="warn"),
    ]
    columns = [
        TabColumn("id", "ID", "mono"),
        TabColumn("title", "Titre", "text"),
        TabColumn("family", "Famille", "text"),
        TabColumn("component", "Composant", "text"),
        TabColumn("incidents", "Incidents", "num", "right"),
        TabColumn("impact", "Impact", "badge"),
        TabColumn("status", "Statut", "badge"),
    ]
    rows = [
        TabRow(
            "PRB-1024",
            {
                "id": "PRB-1024",
                "title": "Hallucinations - RAG",
                "family": "Qualite",
                "component": "Agent RAG",
                "incidents": "18",
                "impact": _badge("Eleve", "warning"),
                "status": _badge("Ouvert", "warning"),
            },
        ),
        TabRow(
            "PRB-1019",
            {
                "id": "PRB-1019",
                "title": "Fuite PII intermittente",
                "family": "Securite",
                "component": "Guardrails",
                "incidents": "9",
                "impact": _badge("Critique", "danger"),
                "status": _badge("Ouvert", "danger"),
            },
        ),
        TabRow(
            "PRB-1015",
            {
                "id": "PRB-1015",
                "title": "Latence gateway sous charge",
                "family": "Fiabilite",
                "component": "Gateway",
                "incidents": "14",
                "impact": _badge("Eleve", "warning"),
                "status": _badge("Workaround", "info"),
            },
        ),
        TabRow(
            "PRB-1011",
            {
                "id": "PRB-1011",
                "title": "Echec outil card_block",
                "family": "Outils",
                "component": "Tools",
                "incidents": "7",
                "impact": _badge("Moyen", "info"),
                "status": _badge("Workaround", "info"),
            },
        ),
        TabRow(
            "PRB-1007",
            {
                "id": "PRB-1007",
                "title": "Derive embeddings Vertex",
                "family": "Retrieval",
                "component": "Embeddings",
                "incidents": "5",
                "impact": _badge("Moyen", "info"),
                "status": _badge("Surveille", "neutral"),
            },
        ),
        TabRow(
            "PRB-1002",
            {
                "id": "PRB-1002",
                "title": "Refus excessifs post-deploiement",
                "family": "Qualite",
                "component": "Agent",
                "incidents": "6",
                "impact": _badge("Eleve", "warning"),
                "status": _badge("Resolu", "success"),
            },
        ),
    ]
    detail = TabDetail(
        eyebrow="Probleme connu",
        title="PRB-1024 Hallucinations - RAG",
        status_label="Ouvert",
        status_tone="warning",
        summary="Hallucinations recurrentes sur reponses ancrees, workaround de reranking actif.",
        fields=[
            DetailField("Famille", "Qualite"),
            DetailField("Composant", "Agent RAG"),
            DetailField("Recurrence", "18 incidents"),
            DetailField("Premiere detection", "12 avr 2026"),
            DetailField("Impact", "Eleve", "warning"),
            DetailField("Owner", "Amelie Dubois"),
        ],
        lists=[
            DetailList(
                "Workaround actif",
                [
                    {
                        "label": "Reranking force + seuil releve",
                        "badge": "Actif",
                        "tone": "success",
                    },
                ],
            ),
            DetailList(
                "Incidents lies (3)",
                [
                    {"label": "INC-2024-2291"},
                    {"label": "INC-2024-2240"},
                    {"label": "INC-2024-2188"},
                ],
            ),
        ],
        actions=["Editer", "Lier un incident", "Escalader", "Cloturer"],
    )
    sections = [
        TabSection(
            "Par famille",
            "bars",
            bars=[
                {"label": "Qualite", "value": 0.8, "tone": "warning"},
                {"label": "Securite", "value": 0.55, "tone": "danger"},
                {"label": "Fiabilite", "value": 0.62, "tone": "info"},
                {"label": "Outils", "value": 0.4, "tone": "neutral"},
            ],
        ),
        TabSection(
            "Dette technique critique",
            "list",
            items=[
                SectionItem(
                    "PRB-1019 - fuite PII", "non corrige", badge="Critique", badge_tone="danger"
                ),
                SectionItem(
                    "PRB-1024 - hallucinations", "workaround", badge="Eleve", badge_tone="warning"
                ),
                SectionItem(
                    "PRB-1015 - latence gateway", "workaround", badge="Eleve", badge_tone="warning"
                ),
            ],
            cta="Voir la dette technique",
        ),
        TabSection(
            "Detections recentes",
            "activity",
            items=[
                SectionItem("PRB-1024 recurrence sur INC-2024-2291", "il y a 12 min"),
                SectionItem("PRB-1019 nouvelle detection", "il y a 1 h"),
                SectionItem("PRB-1002 marque resolu", "hier"),
            ],
            cta="Voir toutes les detections",
        ),
        TabSection(
            "Actions rapides",
            "actions",
            actions=["Nouveau probleme", "Lier un incident", "Voir les relations", "Exporter"],
        ),
    ]
    return CatalogTab(
        "Registre des problemes connus",
        kpis=kpis,
        columns=columns,
        rows=rows,
        detail=detail,
        sections=sections,
    )


# --- Rapports -------------------------------------------------------------


def _tab_rapports() -> CatalogTab:
    kpis = [
        TabKpi("Rapports generes", "118", delta="+6.0%", delta_good=True, tone="good"),
        TabKpi("Rapports envoyes", "214", delta="+4.0%", delta_good=True),
        TabKpi("SLA reporting", "94", unit="%", delta="+1.0 pp", delta_good=True, tone="good"),
        TabKpi("MTTR", "28m 20s", delta="-4.0%", delta_good=True, tone="good"),
        TabKpi("Cout d'incident", "42 180", unit=" EUR", tone="warn"),
        TabKpi("Post-mortems lies", "37", tone="good"),
    ]
    columns = [
        TabColumn("id", "ID", "mono"),
        TabColumn("title", "Rapport", "text"),
        TabColumn("scope", "Portee", "text"),
        TabColumn("period", "Periode", "text"),
        TabColumn("incidents", "Incidents", "num", "right"),
        TabColumn("owner", "Owner", "owner"),
        TabColumn("status", "Statut", "badge"),
    ]
    rows = [
        TabRow(
            "REP-2026-06",
            {
                "id": "REP-2026-06",
                "title": "Resume mensuel incidents",
                "scope": "Global",
                "period": "01-31 mai 2026",
                "incidents": "42",
                "owner": _LEA,
                "status": _badge("Pret", "success"),
            },
        ),
        TabRow(
            "REP-2026-06-PRIV",
            {
                "id": "REP-2026-06-PRIV",
                "title": "Rapport privacy & PII",
                "scope": "Securite",
                "period": "01-31 mai 2026",
                "incidents": "9",
                "owner": _SARAH,
                "status": _badge("Pret", "success"),
            },
        ),
        TabRow(
            "REP-2026-06-SLA",
            {
                "id": "REP-2026-06-SLA",
                "title": "Conformite SLA reponse",
                "scope": "Fiabilite",
                "period": "01-31 mai 2026",
                "incidents": "27",
                "owner": _KARIM,
                "status": _badge("En cours", "warning"),
            },
        ),
        TabRow(
            "REP-2026-05",
            {
                "id": "REP-2026-05",
                "title": "Resume mensuel incidents",
                "scope": "Global",
                "period": "01-30 avr 2026",
                "incidents": "51",
                "owner": _LEA,
                "status": _badge("Envoye", "info"),
            },
        ),
        TabRow(
            "REP-2026-Q1",
            {
                "id": "REP-2026-Q1",
                "title": "Bilan trimestriel fiabilite",
                "scope": "Direction",
                "period": "T1 2026",
                "incidents": "138",
                "owner": _AMELIE,
                "status": _badge("Envoye", "info"),
            },
        ),
        TabRow(
            "REP-2026-AUDIT",
            {
                "id": "REP-2026-AUDIT",
                "title": "Extrait pour audit DORA",
                "scope": "Conformite",
                "period": "01 jan - 31 mai 2026",
                "incidents": "284",
                "owner": _MARC,
                "status": _badge("Pret", "success"),
            },
        ),
    ]
    detail = TabDetail(
        eyebrow="Rapport",
        title="REP-2026-06 Resume mensuel",
        status_label="Pret",
        status_tone="success",
        summary="Synthese mensuelle des incidents, MTTR, cout et post-mortems pour mai 2026.",
        fields=[
            DetailField("Periode", "01-31 mai 2026"),
            DetailField("Portee", "Global"),
            DetailField("Incidents", "42"),
            DetailField("MTTR", "28m 20s"),
            DetailField("Cout estime", "42 180 EUR", "warning"),
            DetailField("Owner", "Lea Moreau"),
        ],
        lists=[
            DetailList(
                "Sections",
                [
                    {"label": "Synthese executive"},
                    {"label": "Incidents majeurs"},
                    {"label": "MTTD / MTTR"},
                    {"label": "Post-mortems & CAPA"},
                ],
            ),
            DetailList(
                "Destinataires",
                [
                    {"label": "Comite reliability"},
                    {"label": "Direction des risques"},
                ],
            ),
        ],
        actions=["Generer", "Telecharger", "Envoyer", "Planifier"],
    )
    sections = [
        TabSection(
            "Tendances des incidents",
            "chart",
            series=[
                {"label": "Critique", "color": "#ef4444", "points": [9, 7, 8, 6, 6]},
                {"label": "Eleve", "color": "#f59e0b", "points": [14, 12, 13, 11, 9]},
                {"label": "Moyen", "color": "#3b82f6", "points": [18, 16, 15, 14, 11]},
            ],
            cta="Voir les tendances",
        ),
        TabSection(
            "Impact par service",
            "bars",
            bars=[
                {"label": "Agent RAG", "value": 0.9, "tone": "danger"},
                {"label": "Gateway", "value": 0.65, "tone": "warning"},
                {"label": "Guardrails", "value": 0.55, "tone": "warning"},
                {"label": "Retrieval", "value": 0.35, "tone": "info"},
            ],
        ),
        TabSection(
            "Succes des playbooks par type",
            "donut",
            donut_value=0.963,
            donut_label="214 exec",
            items=[
                SectionItem("Hallucination", value="97 %", badge_tone="success"),
                SectionItem("PII / securite", value="94 %", badge_tone="success"),
                SectionItem("Fiabilite", value="91 %", badge_tone="warning"),
            ],
        ),
        TabSection(
            "Rapports recents",
            "activity",
            items=[
                SectionItem("REP-2026-06 genere", "il y a 1 h"),
                SectionItem("REP-2026-06-PRIV genere", "il y a 3 h"),
                SectionItem("REP-2026-05 envoye au comite", "hier"),
            ],
            cta="Voir tous les rapports",
        ),
    ]
    return CatalogTab(
        "Inventaire des rapports",
        kpis=kpis,
        columns=columns,
        rows=rows,
        detail=detail,
        sections=sections,
    )


def _build_fr_tabs() -> dict[str, CatalogTab]:
    """Return the deterministic French per-tab payloads (the source of truth)."""
    return {
        "incidents": _tab_incidents(),
        "playbooks": _tab_playbooks(),
        "orchestration": _tab_orchestration(),
        "actions": _tab_actions(),
        "postmortems": _tab_postmortems(),
        "problemes": _tab_problemes(),
        "rapports": _tab_rapports(),
    }


# Generic translation layer: the catalogue fixture is authored in French; for
# DE / EN every string leaf of the assembled tab tree is mapped through ``_TR``.
# Unmapped strings (codes, owner names, colours, technical proper nouns) fall
# through verbatim, so an incomplete entry is a French label, never a crash.
_LANG_IDX = {"fr": 0, "de": 1, "en": 2}

_TR: dict[str, tuple[str, str]] = {
    # --- KPI labels / posture ------------------------------------------------
    "Incidents ouverts": ("Offene Vorfaelle", "Open incidents"),
    "Incidents critiques": ("Kritische Vorfaelle", "Critical incidents"),
    "Incidents majeurs": ("Schwere Vorfaelle", "Major incidents"),
    "Playbooks actifs": ("Aktive Playbooks", "Active playbooks"),
    "Playbooks bloques": ("Blockierte Playbooks", "Blocked playbooks"),
    "SLA respecte": ("SLA eingehalten", "SLA met"),
    "SLA a risque": ("SLA gefaehrdet", "SLA at risk"),
    "Taux de succes": ("Erfolgsrate", "Success rate"),
    "Taux succes": ("Erfolgsrate", "Success rate"),
    "Temps moyen": ("Durchschnittszeit", "Average time"),
    "Temps moyen de cloture": ("Durchschnittliche Abschlusszeit", "Average closure time"),
    "Temps de cycle (p50)": ("Zykluszeit (p50)", "Cycle time (p50)"),
    "Temps de cycle p50": ("Zykluszeit p50", "Cycle time p50"),
    "Latence p50": ("Latenz p50", "Latency p50"),
    "Cout estime": ("Geschaetzte Kosten", "Estimated cost"),
    "Cout d'incident": ("Vorfallkosten", "Incident cost"),
    "Cout incident": ("Vorfallkosten", "Incident cost"),
    "Impact estime borne": ("Geschaetzte Auswirkung begrenzt", "Estimated impact bounded"),
    "Executions 24h": ("Ausfuehrungen 24h", "Executions 24h"),
    "Executions en cours": ("Laufende Ausfuehrungen", "Running executions"),
    "Executions recentes": ("Letzte Ausfuehrungen", "Recent executions"),
    "Actions executees 24h": ("Ausgefuehrte Aktionen 24h", "Actions executed 24h"),
    "Actions en attente": ("Ausstehende Aktionen", "Pending actions"),
    "Actions en sortie": ("Ausgehende Aktionen", "Outbound actions"),
    "Actions assignees": ("Zugewiesene Aktionen", "Assigned actions"),
    "Actions annulees": ("Stornierte Aktionen", "Cancelled actions"),
    "Approbations en attente": ("Ausstehende Freigaben", "Pending approvals"),
    "Approbations requises": ("Erforderliche Freigaben", "Required approvals"),
    "Exceptions actives": ("Aktive Ausnahmen", "Active exceptions"),
    "Post-mortems ouverts": ("Offene Post-mortems", "Open post-mortems"),
    "Post-mortems retardes": ("Verzoegerte Post-mortems", "Delayed post-mortems"),
    "Post-mortems lies": ("Verknuepfte Post-mortems", "Linked post-mortems"),
    "Problemes ouverts": ("Offene Probleme", "Open problems"),
    "Rapports generes": ("Erstellte Berichte", "Reports generated"),
    "Rapports envoyes": ("Gesendete Berichte", "Reports sent"),
    "Completes (30j)": ("Abgeschlossen (30T)", "Completed (30d)"),
    "Resolu (24h)": ("Geloest (24h)", "Resolved (24h)"),
    "Terminees": ("Abgeschlossen", "Completed"),
    "Workflows actifs": ("Aktive Workflows", "Active workflows"),
    "Workflows en cours": ("Laufende Workflows", "Running workflows"),
    "Recidives": ("Rueckfaelle", "Recurrences"),
    "Recurrences": ("Wiederholungen", "Recurrences"),
    # --- column headers ------------------------------------------------------
    "Incident": ("Vorfall", "Incident"),
    "Severite": ("Schweregrad", "Severity"),
    "Service": ("Service", "Service"),
    "Owner": ("Owner", "Owner"),
    "Age": ("Alter", "Age"),
    "Statut": ("Status", "Status"),
    "Titre": ("Titel", "Title"),
    "Type": ("Typ", "Type"),
    "Type d'action": ("Aktionstyp", "Action type"),
    "Criticite": ("Kritikalitaet", "Criticality"),
    "Composant": ("Komponente", "Component"),
    "Composants impactes": ("Betroffene Komponenten", "Impacted components"),
    "Famille": ("Familie", "Family"),
    "Cible": ("Ziel", "Target"),
    "Direction": ("Richtung", "Direction"),
    "Demandeur": ("Antragsteller", "Requester"),
    "Destinataires": ("Empfaenger", "Recipients"),
    "Echeance": ("Frist", "Due date"),
    "Derniere execution": ("Letzte Ausfuehrung", "Last run"),
    "Premiere detection": ("Erste Erkennung", "First detection"),
    "Detecte": ("Erkannt", "Detected"),
    "Conditions": ("Bedingungen", "Conditions"),
    "Periode": ("Zeitraum", "Period"),
    "Fenetre": ("Fenster", "Window"),
    "Sujet": ("Thema", "Subject"),
    "Portee": ("Geltungsbereich", "Scope"),
    "Impact": ("Auswirkung", "Impact"),
    "Playbook lie": ("Verknuepftes Playbook", "Linked playbook"),
    "Playbook": ("Playbook", "Playbook"),
    "Declencheur": ("Ausloeser", "Trigger"),
    "Action": ("Aktion", "Action"),
    "Probable": ("Wahrscheinlich", "Probable"),
    # --- status / badge vocabulary ------------------------------------------
    "Critique": ("Kritisch", "Critical"),
    "Eleve": ("Hoch", "High"),
    "Moyen": ("Mittel", "Medium"),
    "Faible": ("Niedrig", "Low"),
    "Ouvert": ("Offen", "Open"),
    "En analyse": ("In Analyse", "Analyzing"),
    "En cours": ("Laufend", "In progress"),
    "En revue": ("In Pruefung", "In review"),
    "En attente": ("Ausstehend", "Pending"),
    "Mitige": ("Eingedaemmt", "Mitigated"),
    "Resolu": ("Geloest", "Resolved"),
    "Degrade": ("Beeintraechtigt", "Degraded"),
    "Bloque": ("Blockiert", "Blocked"),
    "Actif": ("Aktiv", "Active"),
    "Pret": ("Bereit", "Ready"),
    "Nouveau": ("Neu", "New"),
    "Surveille": ("Ueberwacht", "Monitored"),
    "Suspendu": ("Ausgesetzt", "Suspended"),
    "Retarde": ("Verzoegert", "Delayed"),
    "Confirmee": ("Bestaetigt", "Confirmed"),
    "Confirme": ("Bestaetigt", "Confirmed"),
    "Perimetre confirme": ("Geltungsbereich bestaetigt", "Scope confirmed"),
    "Probleme connu": ("Bekanntes Problem", "Known problem"),
    "Approuvee": ("Genehmigt", "Approved"),
    "Rejetee": ("Abgelehnt", "Rejected"),
    "Annulee": ("Storniert", "Cancelled"),
    "Executee": ("Ausgefuehrt", "Executed"),
    "Envoye": ("Gesendet", "Sent"),
    "Valide": ("Validiert", "Validated"),
    "Validee": ("Validiert", "Validated"),
    "Revue": ("Pruefung", "Review"),
    "en revue": ("in Pruefung", "in review"),
    "Recidive": ("Rueckfall", "Recurrence"),
    "Recurrence": ("Wiederholung", "Recurrence"),
    "Avert": ("Warnung", "Warning"),
    "Auto": ("Auto", "Auto"),
    "Global": ("Global", "Global"),
    "Oui (2)": ("Ja (2)", "Yes (2)"),
    "non corrige": ("nicht behoben", "not fixed"),
    # --- section titles / panels --------------------------------------------
    "File d'incidents en temps reel": ("Echtzeit-Vorfallwarteschlange", "Real-time incident queue"),
    "File d'actions gouvernees": ("Warteschlange gesteuerter Aktionen", "Governed actions queue"),
    "Demandes d'escalade": ("Eskalationsanfragen", "Escalation requests"),
    "Detections recentes": ("Letzte Erkennungen", "Recent detections"),
    "Erreurs recentes": ("Letzte Fehler", "Recent errors"),
    "Erreurs d'orchestration": ("Orchestrierungsfehler", "Orchestration errors"),
    "Activite recente": ("Letzte Aktivitaet", "Recent activity"),
    "Activites recentes": ("Letzte Aktivitaeten", "Recent activities"),
    "Actions rapides": ("Schnellaktionen", "Quick actions"),
    "Actions correctives": ("Korrekturmassnahmen", "Corrective actions"),
    "Actions correctives par statut": (
        "Korrekturmassnahmen nach Status",
        "Corrective actions by status",
    ),
    "Actions par criticite": ("Aktionen nach Kritikalitaet", "Actions by criticality"),
    "Causes meres": ("Grundursachen", "Root causes"),
    "Bibliotheque de playbooks": ("Playbook-Bibliothek", "Playbook library"),
    "Versions du playbook": ("Playbook-Versionen", "Playbook versions"),
    "Cles d'automatisation": ("Automatisierungsschluessel", "Automation keys"),
    "Regles de routage": ("Routing-Regeln", "Routing rules"),
    "Registre des problemes connus": ("Register bekannter Probleme", "Known problems register"),
    "Inventaire des rapports": ("Berichtsinventar", "Reports inventory"),
    "Rapports recents": ("Letzte Berichte", "Recent reports"),
    "Workflows par famille": ("Workflows nach Familie", "Workflows by family"),
    "Couverture par type d'incident": (
        "Abdeckung nach Vorfalltyp",
        "Coverage by incident type",
    ),
    "Repartition par severite": ("Verteilung nach Schweregrad", "Breakdown by severity"),
    "Impact par service": ("Auswirkung nach Service", "Impact by service"),
    "Succes des playbooks par type": (
        "Playbook-Erfolg nach Typ",
        "Playbook success by type",
    ),
    "Tendances des incidents": ("Vorfalltrends", "Incident trends"),
    "Synthese executive": ("Executive Summary", "Executive summary"),
    "Synthese mensuelle des incidents, MTTR, cout et post-mortems pour mai 2026.": (
        "Monatliche Zusammenfassung der Vorfaelle, MTTR, Kosten und Post-mortems fuer Mai 2026.",
        "Monthly summary of incidents, MTTR, cost and post-mortems for May 2026.",
    ),
    "Verifications de securite (pre-execution)": (
        "Sicherheitspruefungen (vor Ausfuehrung)",
        "Security checks (pre-execution)",
    ),
    "Habilitations disponibles": ("Verfuegbare Berechtigungen", "Available permissions"),
    "Preuves liees": ("Verknuepfte Nachweise", "Linked evidence"),
    "Incidents lies (3)": ("Verknuepfte Vorfaelle (3)", "Linked incidents (3)"),
    "Post-mortems & CAPA": ("Post-mortems & CAPA", "Post-mortems & CAPA"),
    "Etapes (6)": ("Schritte (6)", "Steps (6)"),
    "Etapes": ("Schritte", "Steps"),
    "Sections": ("Abschnitte", "Sections"),
    "Par famille": ("Nach Familie", "By family"),
    # --- CTAs / actions ------------------------------------------------------
    "Declarer un incident": ("Vorfall melden", "Declare an incident"),
    "Lancer un playbook": ("Playbook starten", "Launch a playbook"),
    "Ouvrir le playbook": ("Playbook oeffnen", "Open the playbook"),
    "Ouvrir le tableau de triage": ("Triage-Board oeffnen", "Open the triage board"),
    "Assigner une action": ("Aktion zuweisen", "Assign an action"),
    "Nouvelle action": ("Neue Aktion", "New action"),
    "Nouveau workflow": ("Neuer Workflow", "New workflow"),
    "Nouveau probleme": ("Neues Problem", "New problem"),
    "Editer": ("Bearbeiten", "Edit"),
    "Editer le workflow": ("Workflow bearbeiten", "Edit the workflow"),
    "Dupliquer": ("Duplizieren", "Duplicate"),
    "Importer une regle": ("Regel importieren", "Import a rule"),
    "Exporter": ("Exportieren", "Export"),
    "Exporter le journal": ("Protokoll exportieren", "Export the log"),
    "Generer": ("Generieren", "Generate"),
    "Planifier": ("Planen", "Schedule"),
    "Telecharger": ("Herunterladen", "Download"),
    "Acquitter": ("Bestaetigen", "Acknowledge"),
    "Approuver": ("Genehmigen", "Approve"),
    "Rejeter": ("Ablehnen", "Reject"),
    "Escalader": ("Eskalieren", "Escalate"),
    "Executer": ("Ausfuehren", "Execute"),
    "Cloturer": ("Abschliessen", "Close"),
    "Suspendre": ("Aussetzen", "Suspend"),
    "Valider": ("Validieren", "Validate"),
    "Envoyer": ("Senden", "Send"),
    "Tester a blanc": ("Trockenlauf testen", "Dry-run test"),
    "Lier un incident": ("Vorfall verknuepfen", "Link an incident"),
    "Gerer les habilitations": ("Berechtigungen verwalten", "Manage permissions"),
    "Voir l'historique": ("Verlauf anzeigen", "View history"),
    "Voir le graphe": ("Graph anzeigen", "View graph"),
    "Voir le journal": ("Protokoll anzeigen", "View log"),
    "Voir la dette technique": ("Technische Schuld anzeigen", "View technical debt"),
    "Voir les approbations": ("Freigaben anzeigen", "View approvals"),
    "Voir les exceptions": ("Ausnahmen anzeigen", "View exceptions"),
    "Voir les latences": ("Latenzen anzeigen", "View latencies"),
    "Voir les recidives": ("Rueckfaelle anzeigen", "View recurrences"),
    "Voir les relations": ("Beziehungen anzeigen", "View relations"),
    "Voir les tendances": ("Trends anzeigen", "View trends"),
    "Voir tous les rapports": ("Alle Berichte anzeigen", "View all reports"),
    "Voir toute l'activite": ("Gesamte Aktivitaet anzeigen", "View all activity"),
    "Voir toutes les activites": ("Alle Aktivitaeten anzeigen", "View all activities"),
    "Voir toutes les detections": ("Alle Erkennungen anzeigen", "View all detections"),
    "Voir toutes les erreurs": ("Alle Fehler anzeigen", "View all errors"),
    "Voir toutes les executions": ("Alle Ausfuehrungen anzeigen", "View all executions"),
    # --- incident / playbook prose ------------------------------------------
    "Hallucination RAG sur scoring credit": (
        "RAG-Halluzination beim Kredit-Scoring",
        "RAG hallucination on credit scoring",
    ),
    "Hallucination RAG recurrente": (
        "Wiederkehrende RAG-Halluzination",
        "Recurring RAG hallucination",
    ),
    "Hallucination RAG recurrente sur le scoring credit, cause mere en ancrage.": (
        "Wiederkehrende RAG-Halluzination beim Kredit-Scoring, Grundursache im Grounding.",
        "Recurring RAG hallucination on credit scoring, root cause in grounding.",
    ),
    "Hallucination detectee sur une reponse de scoring credit, playbook RAG declenche.": (
        "Halluzination bei einer Kredit-Scoring-Antwort erkannt, RAG-Playbook ausgeloest.",
        "Hallucination detected on a credit-scoring answer, RAG playbook triggered.",
    ),
    "Hallucinations recurrentes sur reponses ancrees, workaround de reranking actif.": (
        "Wiederkehrende Halluzinationen bei verankerten Antworten, Reranking-Workaround aktiv.",
        "Recurring hallucinations on grounded answers, reranking workaround active.",
    ),
    "Hallucination": ("Halluzination", "Hallucination"),
    "Hallucination RAG": ("RAG-Halluzination", "RAG hallucination"),
    "Hallucinations - RAG": ("Halluzinationen - RAG", "Hallucinations - RAG"),
    "Latence elevee passerelle LLM": ("Hohe Latenz LLM-Gateway", "High latency LLM gateway"),
    "Latence gateway": ("Gateway-Latenz", "Gateway latency"),
    "Latence gateway sous charge": ("Gateway-Latenz unter Last", "Gateway latency under load"),
    "Fuite PII potentielle en reponse": (
        "Moegliches PII-Leck in Antwort",
        "Potential PII leak in response",
    ),
    "Fuite PII en reponse": ("PII-Leck in Antwort", "PII leak in response"),
    "Fuite PII intermittente": ("Intermittierendes PII-Leck", "Intermittent PII leak"),
    "Fuite PII - confinement": ("PII-Leck - Eindaemmung", "PII leak - containment"),
    "Echec d'outil card_block": ("Tool-Fehler card_block", "Tool failure card_block"),
    "Echec outil card_block": ("Tool-Fehler card_block", "Tool failure card_block"),
    "Erreur d'outil": ("Tool-Fehler", "Tool error"),
    "Reprise outil en echec": ("Wiederholung fehlgeschlagenes Tool", "Retry failed tool"),
    "Outil en echec - reprise": ("Fehlgeschlagenes Tool - Wiederholung", "Failed tool - retry"),
    "Degradation embeddings": ("Embedding-Verschlechterung", "Embedding degradation"),
    "Degradation embeddings Vertex": (
        "Vertex-Embedding-Verschlechterung",
        "Vertex embedding degradation",
    ),
    "Derive embeddings Vertex": ("Vertex-Embedding-Drift", "Vertex embedding drift"),
    "Purge cache embeddings": ("Embedding-Cache leeren", "Purge embedding cache"),
    "Refus excessifs": ("Uebermaessige Ablehnungen", "Excessive refusals"),
    "Refus excessifs apres deploiement": (
        "Uebermaessige Ablehnungen nach Deployment",
        "Excessive refusals after deployment",
    ),
    "Refus excessifs post-deploiement": (
        "Uebermaessige Ablehnungen nach Deployment",
        "Excessive refusals post-deployment",
    ),
    "Refus excessif - recalibrage": (
        "Uebermaessige Ablehnung - Neukalibrierung",
        "Excessive refusal - recalibration",
    ),
    "Pic de refus": ("Ablehnungsspitze", "Refusal spike"),
    "Pic de refus injustifies": (
        "Spitze ungerechtfertigter Ablehnungen",
        "Spike of unjustified refusals",
    ),
    "Forcer recalibrage refus": (
        "Ablehnungs-Neukalibrierung erzwingen",
        "Force refusal recalibration",
    ),
    "Seuil de confiance trop bas": ("Konfidenzschwelle zu niedrig", "Confidence threshold too low"),
    "Seuil latence": ("Latenzschwelle", "Latency threshold"),
    "Reactiver le reranker": ("Reranker reaktivieren", "Re-enable the reranker"),
    "Reranker desactive en prod": ("Reranker in Prod deaktiviert", "Reranker disabled in prod"),
    "Reranking force + seuil releve": (
        "Reranking erzwungen + Schwelle erhoeht",
        "Reranking forced + threshold raised",
    ),
    "Reduire la taille de chunk": ("Chunk-Groesse reduzieren", "Reduce chunk size"),
    "Chunking trop large du corpus": (
        "Zu grosses Chunking des Korpus",
        "Chunking too large for the corpus",
    ),
    "Redemarrer worker retrieval": (
        "Retrieval-Worker neu starten",
        "Restart retrieval worker",
    ),
    "Enrichissement signal RAG": ("RAG-Signalanreicherung", "RAG signal enrichment"),
    "Signal PII": ("PII-Signal", "PII signal"),
    "Signal firewall": ("Firewall-Signal", "Firewall signal"),
    "Signal hallucination": ("Halluzinationssignal", "Hallucination signal"),
    "PII detectee": ("PII erkannt", "PII detected"),
    "Confinement reponse": ("Antwort-Eindaemmung", "Response containment"),
    "Confinement et regeneration ancree d'une reponse hallucinee, capture de preuves.": (
        "Eindaemmung und verankerte Regenerierung einer halluzinierten Antwort, Nachweiserfassung.",
        "Containment and grounded regeneration of a hallucinated answer, evidence capture.",
    ),
    "Collecte de preuve & cloture": ("Nachweiserfassung & Abschluss", "Evidence capture & closure"),
    "Escalade & notification astreinte": (
        "Eskalation & Bereitschaftsbenachrichtigung",
        "Escalation & on-call notification",
    ),
    "Routage incident critique privacy": (
        "Routing kritischer Privacy-Vorfall",
        "Critical privacy incident routing",
    ),
    "Route les incidents critiques privacy vers SecOps avec confinement immediat.": (
        "Leitet kritische Privacy-Vorfaelle mit sofortiger Eindaemmung an SecOps.",
        "Routes critical privacy incidents to SecOps with immediate containment.",
    ),
    "Severite critique": ("Kritischer Schweregrad", "Critical severity"),
    "Severite critique + domaine privacy": (
        "Kritischer Schweregrad + Privacy-Domaene",
        "Critical severity + privacy domain",
    ),
    "Isoler workload support": ("Support-Workload isolieren", "Isolate support workload"),
    "Isoler le workload support suite a INC-2024-2285, en attente de dual control.": (
        "Support-Workload nach INC-2024-2285 isolieren, wartet auf Dual Control.",
        "Isolate the support workload after INC-2024-2285, pending dual control.",
    ),
    "Isolation reseau": ("Netzwerkisolierung", "Network isolation"),
    "Revoquer cle API tierce": (
        "Drittanbieter-API-Schluessel widerrufen",
        "Revoke third-party API key",
    ),
    "Rollback gateway v2.2.15": ("Gateway-Rollback v2.2.15", "Gateway rollback v2.2.15"),
    "Auto-remediation gateway": ("Gateway-Auto-Behebung", "Gateway auto-remediation"),
    "Mitigation automatique": ("Automatische Eindaemmung", "Automatic mitigation"),
    "Ouverture ticket P0": ("P0-Ticket eroeffnen", "Open P0 ticket"),
    "Panne gateway prolongee": ("Laengerer Gateway-Ausfall", "Prolonged gateway outage"),
    "Latence gateway - rollback": ("Gateway-Latenz - Rollback", "Gateway latency - rollback"),
    "Dette technique critique": ("Kritische technische Schuld", "Critical technical debt"),
    "Conformite": ("Konformitaet", "Compliance"),
    "Conformite SLA reponse": ("Antwort-SLA-Konformitaet", "Response SLA compliance"),
    "Securite": ("Sicherheit", "Security"),
    "Qualite": ("Qualitaet", "Quality"),
    "Fiabilite": ("Zuverlaessigkeit", "Reliability"),
    "Disponibilite": ("Verfuegbarkeit", "Availability"),
    "Direction des risques": ("Risikoabteilung", "Risk management"),
    "Comite reliability": ("Reliability-Komitee", "Reliability committee"),
    "Bilan trimestriel fiabilite": (
        "Quartalsbericht Zuverlaessigkeit",
        "Quarterly reliability review",
    ),
    "Resume mensuel incidents": ("Monatliche Vorfallzusammenfassung", "Monthly incident summary"),
    "Synthese mensuelle des incidents": (
        "Monatliche Vorfallzusammenfassung",
        "Monthly incident summary",
    ),
    "Rapport privacy & PII": ("Privacy- & PII-Bericht", "Privacy & PII report"),
    "Rapport": ("Bericht", "Report"),
    "SLA reporting": ("SLA-Reporting", "SLA reporting"),
    "Extrait pour audit DORA": ("Auszug fuer DORA-Audit", "Extract for DORA audit"),
    "Approbation": ("Freigabe", "Approval"),
    "Sauvegarde disponible": ("Backup verfuegbar", "Backup available"),
    "Workarounds actifs": ("Aktive Workarounds", "Active workarounds"),
    "Workaround actif": ("Workaround aktiv", "Workaround active"),
    "Dual control": ("Dual Control", "Dual control"),
    "dual control": ("Dual Control", "dual control"),
    "Fin de mitigation": ("Ende der Eindaemmung", "End of mitigation"),
    "A faire": ("Zu erledigen", "To do"),
    # --- orchestration step labels (numbered) -------------------------------
    "1. Detection de signal": ("1. Signalerkennung", "1. Signal detection"),
    "2. Validation & correlation": ("2. Validierung & Korrelation", "2. Validation & correlation"),
    "3. Triage & enrichissement": ("3. Triage & Anreicherung", "3. Triage & enrichment"),
    "4. Mitigation": ("4. Eindaemmung", "4. Mitigation"),
    "5. Preuve & capture": ("5. Nachweis & Erfassung", "5. Evidence & capture"),
    "6. Cloture": ("6. Abschluss", "6. Closure"),
    # --- activity-log entries (code prefix kept, French clause translated) ----
    "ACT-44188 - quarantaine": ("ACT-44188 - Quarantaene", "ACT-44188 - quarantine"),
    "ACT-44190 annulee (rejet dual control)": (
        "ACT-44190 storniert (Dual-Control-Ablehnung)",
        "ACT-44190 cancelled (dual control rejection)",
    ),
    "ACT-44198 redemarrage worker reussi": (
        "ACT-44198 Worker-Neustart erfolgreich",
        "ACT-44198 worker restart successful",
    ),
    "ACT-44203 - revocation cle": ("ACT-44203 - Schluesselwiderruf", "ACT-44203 - key revocation"),
    "ACT-44207 purge cache reussie": (
        "ACT-44207 Cache-Bereinigung erfolgreich",
        "ACT-44207 cache purge successful",
    ),
    "ACT-44210 rollback gateway reussi": (
        "ACT-44210 Gateway-Rollback erfolgreich",
        "ACT-44210 gateway rollback successful",
    ),
    "ACT-44213 - isolation": ("ACT-44213 - Isolierung", "ACT-44213 - isolation"),
    "INC-2024-2269 resolu par Marc Dupont": (
        "INC-2024-2269 geloest von Marc Dupont",
        "INC-2024-2269 resolved by Marc Dupont",
    ),
    "INC-2024-2288 mitige (rollback gateway)": (
        "INC-2024-2288 eingedaemmt (Gateway-Rollback)",
        "INC-2024-2288 mitigated (gateway rollback)",
    ),
    "INC-2024-2291 escalade en critique": (
        "INC-2024-2291 auf kritisch eskaliert",
        "INC-2024-2291 escalated to critical",
    ),
    "PB-04 declenche sur INC-2024-2291": (
        "PB-04 ausgeloest auf INC-2024-2291",
        "PB-04 triggered on INC-2024-2291",
    ),
    "PB-04 execute sur INC-2024-2291": (
        "PB-04 ausgefuehrt auf INC-2024-2291",
        "PB-04 executed on INC-2024-2291",
    ),
    "PB-07 confinement PII reussi": (
        "PB-07 PII-Eindaemmung erfolgreich",
        "PB-07 PII containment successful",
    ),
    "PB-09 - quarantaine": ("PB-09 - Quarantaene", "PB-09 - quarantine"),
    "PB-11 rollback gateway reussi": (
        "PB-11 Gateway-Rollback erfolgreich",
        "PB-11 gateway rollback successful",
    ),
    "PB-14 - isolation": ("PB-14 - Isolierung", "PB-14 - isolation"),
    "PB-21 - recalibrage": ("PB-21 - Neukalibrierung", "PB-21 - recalibration"),
    "PB-21 suspendu (echec etape 3)": (
        "PB-21 ausgesetzt (Schritt 3 fehlgeschlagen)",
        "PB-21 suspended (step 3 failed)",
    ),
    "PM-2024-221 valide par Lea Moreau": (
        "PM-2024-221 validiert von Lea Moreau",
        "PM-2024-221 validated by Lea Moreau",
    ),
    "PM-2024-229 marque retarde": (
        "PM-2024-229 als verzoegert markiert",
        "PM-2024-229 marked delayed",
    ),
    "PM-2024-231 cause mere confirmee": (
        "PM-2024-231 Grundursache bestaetigt",
        "PM-2024-231 root cause confirmed",
    ),
    "PRB-1002 marque resolu": ("PRB-1002 als geloest markiert", "PRB-1002 marked resolved"),
    "PRB-1015 - latence gateway": ("PRB-1015 - Gateway-Latenz", "PRB-1015 - gateway latency"),
    "PRB-1019 - fuite PII": ("PRB-1019 - PII-Leck", "PRB-1019 - PII leak"),
    "PRB-1019 nouvelle detection": ("PRB-1019 neue Erkennung", "PRB-1019 new detection"),
    "PRB-1024 - hallucinations": ("PRB-1024 - Halluzinationen", "PRB-1024 - hallucinations"),
    "PRB-1024 Hallucinations - RAG": (
        "PRB-1024 Halluzinationen - RAG",
        "PRB-1024 hallucinations - RAG",
    ),
    "PRB-1024 recurrence sur INC-2024-2291": (
        "PRB-1024 Wiederholung auf INC-2024-2291",
        "PRB-1024 recurrence on INC-2024-2291",
    ),
    "Prompt injection - isolation": (
        "Prompt-Injection - Isolierung",
        "Prompt injection - isolation",
    ),
    "REP-2026-05 envoye au comite": (
        "REP-2026-05 an Komitee gesendet",
        "REP-2026-05 sent to committee",
    ),
    "REP-2026-06 genere": ("REP-2026-06 erstellt", "REP-2026-06 generated"),
    "REP-2026-06-PRIV genere": ("REP-2026-06-PRIV erstellt", "REP-2026-06-PRIV generated"),
    "REP-2026-06 Resume mensuel": (
        "REP-2026-06 Monatszusammenfassung",
        "REP-2026-06 monthly summary",
    ),
    "RAG Hallucination - P0": ("RAG-Halluzination - P0", "RAG hallucination - P0"),
    "PB-04 RAG Hallucination": ("PB-04 RAG-Halluzination", "PB-04 RAG hallucination"),
    # --- relative-time / misc ------------------------------------------------
    "dans 18 min": ("in 18 Min", "in 18 min"),
    "il y a 1 h": ("vor 1 Std", "1 h ago"),
    "il y a 2 h": ("vor 2 Std", "2 h ago"),
    "il y a 3 h": ("vor 3 Std", "3 h ago"),
    "il y a 4 h": ("vor 4 Std", "4 h ago"),
    "il y a 5 h": ("vor 5 Std", "5 h ago"),
    "il y a 4 min": ("vor 4 Min", "4 min ago"),
    "il y a 11 min": ("vor 11 Min", "11 min ago"),
    "il y a 12 min": ("vor 12 Min", "12 min ago"),
    "il y a 22 min": ("vor 22 Min", "22 min ago"),
    "il y a 2 j": ("vor 2 T", "2 d ago"),
    "il y a 18 j": ("vor 18 T", "18 d ago"),
    "il y a 41 j": ("vor 41 T", "41 d ago"),
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
    """Return the per-tab payloads for the Incidents command bar in ``lang``.

    The fixture is authored in French (the source of truth); for ``de`` / ``en``
    each string leaf is mapped through ``_TR`` (unmapped strings fall through
    verbatim), so the operational catalogues are localized end to end.
    """
    tabs = _build_fr_tabs()
    idx = _LANG_IDX.get(lang, 0)
    if idx == 0:
        return tabs
    return {key: cast("CatalogTab", _localize(tab, idx - 1)) for key, tab in tabs.items()}
