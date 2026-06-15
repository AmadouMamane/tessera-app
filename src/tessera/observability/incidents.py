"""Incidents & playbooks cockpit overview (page #10, ADR 0010).

Assembles the "Incidents & playbooks" overview the dashboard renders: the current
posture (open / critical incidents, MTTA / MTTR, auto-resolution), the triage
queue with the playbook recommended for each incident, the running playbook with
its step timeline, the automation rules, and the 7-day impact charts.

The AI-specific *playbook* catalogue and trigger logic live in
:mod:`tessera.observability.playbooks`; this module is the presentation layer
that composes a single, self-contained payload for the page. The dataset is a
deterministic reference fixture (this build ships without a live incident store);
values are stable across calls so the page never "dances" on refetch.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime

from tessera.observability.incidents_tabs import build_tabs

__all__ = ["compute_incidents_overview"]

# Severity / domain accent colours, shared by the donut, bars and dots so the
# whole page reads with one palette.
_DOMAIN_COLOR = {
    "privacy": "#f472b6",
    "qualite_rag": "#f97316",
    "securite": "#60a5fa",
    "observabilite": "#a78bfa",
    "conformite": "#34d399",
}


def _kpi(
    key: str, value: str, delta_label: str, good_is_up: bool, series: list[int]
) -> dict[str, object]:
    return {
        "key": key,
        "value": value,
        "delta_label": delta_label,
        "good_is_up": good_is_up,
        "series": series,
    }


def compute_incidents_overview() -> dict[str, object]:
    """Return the full Incidents & playbooks overview payload.

    Returns:
        A JSON-serialisable mapping with the current posture KPIs, the triage
        queue, the playbook catalogue, the running playbook timeline, the
        automation rules and the 7-day impact series — everything the page
        renders, in one document.
    """
    now = datetime.now(UTC)

    kpis = [
        _kpi("open", "14", "+3", False, [9, 10, 8, 11, 12, 13, 14]),
        _kpi("critical", "4", "+1", False, [2, 3, 2, 3, 3, 4, 4]),
        _kpi("mtta", "3m20", "-45 s", True, [5, 4, 5, 4, 4, 3, 3]),
        _kpi("mttr", "28 min", "-6 min", True, [42, 40, 38, 35, 33, 30, 28]),
        _kpi("playbooks", "19", "+4", True, [13, 14, 15, 16, 17, 18, 19]),
        _kpi("autoresolve", "61%", "+8 pts", True, [48, 50, 53, 55, 57, 59, 61]),
        _kpi("sla_risk", "6", "+2", False, [3, 3, 4, 4, 5, 5, 6]),
        _kpi("evidence", "82", "+12", True, [58, 62, 67, 71, 74, 78, 82]),
    ]

    priority_incidents = [
        {
            "id": "INC-231",
            "severity": "critique",
            "trigger": "Jailbreak / RAG",
            "domain": "qualite_rag",
            "status": "ouvert",
            "owner": "M. Engineer",
            "sla": "18 min",
            "sla_tone": "crit",
            "playbook": "Hallucination — RAG",
            "role": "Operator+",
        },
        {
            "id": "INC-232",
            "severity": "critique",
            "trigger": "Fuite PII — mémoire",
            "domain": "privacy",
            "status": "ouvert",
            "owner": "A. Privacy",
            "sla": "24 min",
            "sla_tone": "crit",
            "playbook": "Purge mémoire PII",
            "role": "Operator+",
        },
        {
            "id": "INC-225",
            "severity": "eleve",
            "trigger": "Prompt injection",
            "domain": "securite",
            "status": "encours",
            "owner": "S. SysAdmin",
            "sla": "42 min",
            "sla_tone": "warn",
            "playbook": "Prompt injection containment",
            "role": "Operator+",
        },
        {
            "id": "INC-229",
            "severity": "eleve",
            "trigger": "Grounding faible",
            "domain": "qualite_rag",
            "status": "ouvert",
            "owner": "M. Engineer",
            "sla": "1 h 02",
            "sla_tone": "warn",
            "playbook": "Hallucination — RAG",
            "role": "Operator+",
        },
        {
            "id": "INC-227",
            "severity": "moyen",
            "trigger": "Réponse langue dégradée",
            "domain": "qualite_rag",
            "status": "ouvert",
            "owner": "DevRel",
            "sla": "2 h 10",
            "sla_tone": "ok",
            "playbook": "Freeze release & rollback",
            "role": "Operator+",
        },
        {
            "id": "INC-210",
            "severity": "moyen",
            "trigger": "Conformité Art. 50",
            "domain": "conformite",
            "status": "ouvert",
            "owner": "A. Compliance",
            "sla": "1 h 45",
            "sla_tone": "warn",
            "playbook": "Disclosure remediation",
            "role": "Operator+",
        },
    ]

    playbook_catalog = [
        {
            "name": "Hallucination — RAG",
            "desc": "Détecter & réduire les hallucinations RAG",
            "runs": 18,
        },
        {
            "name": "Prompt injection containment",
            "desc": "Confiner une injection de prompt",
            "runs": 12,
        },
        {"name": "Purge mémoire PII", "desc": "Effacer la PII en mémoire (RGPD)", "runs": 9},
        {
            "name": "Freeze release & rollback",
            "desc": "Geler la release et revenir en arrière",
            "runs": 13,
        },
        {"name": "Incident conformité", "desc": "Art. 50 / RGPD — remédiation", "runs": 7},
    ]

    recent_incidents = [
        {"id": "INC-231", "label": "Hallucination — RAG", "severity": "critique", "time": "11:23"},
        {"id": "INC-232", "label": "Fuite PII — mémoire", "severity": "critique", "time": "11:23"},
        {"id": "INC-227", "label": "Prompt injection", "severity": "eleve", "time": "11:21"},
        {"id": "INC-219", "label": "Réponse langue dégradée", "severity": "moyen", "time": "11:18"},
    ]

    sla_escalations = [
        {"id": "INC-231", "remaining": "22 min restantes", "tone": "crit"},
        {"id": "INC-232", "remaining": "28 min restantes", "tone": "crit"},
        {"id": "INC-225", "remaining": "54 min restantes", "tone": "warn"},
        {"id": "INC-227", "remaining": "1 h 05 restantes", "tone": "ok"},
    ]

    domain_distribution = [
        {"key": "privacy", "count": 4, "pct": 29, "color": _DOMAIN_COLOR["privacy"]},
        {"key": "qualite_rag", "count": 3, "pct": 21, "color": _DOMAIN_COLOR["qualite_rag"]},
        {"key": "securite", "count": 3, "pct": 21, "color": _DOMAIN_COLOR["securite"]},
        {"key": "observabilite", "count": 2, "pct": 14, "color": _DOMAIN_COLOR["observabilite"]},
        {"key": "conformite", "count": 2, "pct": 14, "color": _DOMAIN_COLOR["conformite"]},
    ]

    control_cases = [
        {"id": "CC-012", "label": "Fuite PII & mémoire", "assoc": 2},
        {"id": "CC-007", "label": "Hallucination systématique", "assoc": 1},
        {"id": "CC-004", "label": "Conformité Art. 50", "assoc": 1},
    ]

    running_playbook = {
        "name": "Prompt injection containment",
        "incident": "INC-231",
        "owner": "S. SysAdmin",
        "role": "Operator+",
        "proofs": 3,
        "elapsed": "00:07:31",
        "steps": [
            {"key": "detection", "label": "Détection", "time": "11:44:22", "state": "done"},
            {"key": "containment", "label": "Containment", "time": "11:48:48", "state": "current"},
            {"key": "investigation", "label": "Investigation", "time": "", "state": "todo"},
            {"key": "remediation", "label": "Remediation", "time": "", "state": "todo"},
            {"key": "verification", "label": "Vérification", "time": "", "state": "todo"},
            {"key": "closure", "label": "Clôture", "time": "", "state": "todo"},
        ],
    }

    response_journal = [
        {
            "time": "11:47:31",
            "incident": "INC-231",
            "action": "Containment — règles MAJ",
            "actor": "M. Engineer",
        },
        {
            "time": "11:46:12",
            "incident": "INC-225",
            "action": "Qualification — sévérité",
            "actor": "S. SysAdmin",
        },
        {
            "time": "11:45:02",
            "incident": "INC-232",
            "action": "Purge mémoire — lancée",
            "actor": "A. Privacy",
        },
        {
            "time": "11:44:22",
            "incident": "INC-231",
            "action": "Playbook lancé",
            "actor": "Auto-page",
        },
        {
            "time": "11:42:50",
            "incident": "INC-228",
            "action": "Escalade — Admin+",
            "actor": "Auto-escalade",
        },
    ]

    automations = [
        {"rule": "Auto-page critique", "status": "actif", "last": "11:53:41", "role": "Operator+"},
        {
            "rule": "Auto-triage (mémoire)",
            "status": "actif",
            "last": "11:51:08",
            "role": "Operator+",
        },
        {"rule": "Auto-escalade SLA", "status": "actif", "last": "10:59:11", "role": "Operator+"},
        {
            "rule": "Auto-ouverture playbook",
            "status": "actif",
            "last": "11:48:17",
            "role": "Compliance+",
        },
        {"rule": "Auto-redaction PII", "status": "dryrun", "last": "11:48:17", "role": "Admin+"},
    ]

    mttr_series = {
        "labels": ["01/05", "03/05", "05/05", "07/05", "09/05", "11/05", "13/05"],
        "mtta": [5, 4, 5, 4, 4, 3, 3],
        "mttr": [42, 40, 38, 35, 33, 30, 28],
    }

    resolution_by_playbook = [
        {"name": "Hallucination — RAG", "pct": 73, "ratio": "10/14", "color": "#f97316"},
        {"name": "Purge mémoire PII", "pct": 89, "ratio": "8/9", "color": "#34d399"},
        {"name": "Prompt injection containment", "pct": 83, "ratio": "10/12", "color": "#60a5fa"},
        {"name": "Freeze release & rollback", "pct": 75, "ratio": "9/12", "color": "#a78bfa"},
        {"name": "Incident conformité", "pct": 71, "ratio": "5/7", "color": "#fbbf24"},
    ]

    postmortems = [
        {
            "id": "INC-224",
            "label": "Hallucination — RAG",
            "rca": "Chunking trop large — reranker ajusté",
            "resolved": "Résolu 12:05 · J-2",
        },
        {
            "id": "INC-221",
            "label": "Fuite PII — mémoire",
            "rca": "TTL mémoire manquant — purge auto.",
            "resolved": "Résolu 16:40 · J-2",
        },
        {
            "id": "INC-223",
            "label": "Prompt injection",
            "rca": "Motif jailbreak — règle ajoutée",
            "resolved": "Résolu 11:03 · J-3",
        },
        {
            "id": "INC-216",
            "label": "Sortie langue dégradée",
            "rca": "Routage langue — seuil revu",
            "resolved": "Résolu 09:18 · J-4",
        },
    ]

    return {
        "generated_at": now.isoformat(),
        "period_days": 7,
        "updated_at": "11:54:01",
        "kpis": kpis,
        "priority_incidents": priority_incidents,
        "playbook_catalog": playbook_catalog,
        "recent_incidents": recent_incidents,
        "recent_more": 9,
        "sla_escalations": sla_escalations,
        "domain_distribution": domain_distribution,
        "donut_total": 14,
        "control_cases": control_cases,
        "running_playbook": running_playbook,
        "response_journal": response_journal,
        "automations": automations,
        "mttr_series": mttr_series,
        "resolution_by_playbook": resolution_by_playbook,
        "incidents_by_domain": domain_distribution,
        "postmortems": postmortems,
        "footer": {
            "critical": 14,
            "at_risk": 6,
            "playbooks": 19,
            "proofs": 82,
            "source": "YAML · Git",
            "sync": "il y a 2 min",
        },
        # Per-tab operational catalogues (Incidents, Playbooks, Orchestration,
        # Actions, Post-mortems, Problemes connus, Rapports), rendered generically.
        "tabs": {key: asdict(tab) for key, tab in build_tabs().items()},
    }
