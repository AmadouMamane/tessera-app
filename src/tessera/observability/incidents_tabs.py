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


def build_tabs() -> dict[str, CatalogTab]:
    """Return the deterministic per-tab payloads for the Incidents command bar."""
    return {
        "incidents": _tab_incidents(),
        "playbooks": _tab_playbooks(),
        "orchestration": _tab_orchestration(),
        "actions": _tab_actions(),
        "postmortems": _tab_postmortems(),
        "problemes": _tab_problemes(),
        "rapports": _tab_rapports(),
    }
