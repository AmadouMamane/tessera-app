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

_LANG_IDX = {"fr": 0, "de": 1, "en": 2}


def _loc(lang: str, fr: str, de: str, en: str) -> str:
    """Pick the locale variant of an inline fixture string (fr / de / en)."""
    return (fr, de, en)[_LANG_IDX.get(lang, 0)]

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


def compute_incidents_overview(lang: str = "fr") -> dict[str, object]:
    """Return the full Incidents & playbooks overview payload.

    Args:
        lang: Locale (fr / de / en) for the free-text fixture fields the
            frontend renders verbatim (triggers, playbook names/descriptions,
            running-playbook steps, journal actions, automation rules,
            post-mortems). Severity / status / domain / KPI labels are localized
            in the frontend via next-intl keys; owner / actor names and IDs stay
            verbatim.

    Returns:
        A JSON-serialisable mapping with the current posture KPIs, the triage
        queue, the playbook catalogue, the running playbook timeline, the
        automation rules and the 7-day impact series — everything the page
        renders, in one document.
    """
    now = datetime.now(UTC)

    # Recurring playbook names, localized once and reused across the page so the
    # triage queue, catalogue and resolution chart stay consistent.
    pb_pii = _loc(lang, "Purge mémoire PII", "PII-Speicher leeren", "PII memory purge")
    pb_conf = _loc(lang, "Incident conformité", "Konformitaetsvorfall", "Compliance incident")

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

    trig_pii = _loc(lang, "Fuite PII — mémoire", "PII-Leck — Speicher", "PII leak — memory")
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
            "trigger": trig_pii,
            "domain": "privacy",
            "status": "ouvert",
            "owner": "A. Privacy",
            "sla": "24 min",
            "sla_tone": "crit",
            "playbook": pb_pii,
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
            "trigger": _loc(lang, "Grounding faible", "Schwaches Grounding", "Weak grounding"),
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
            "trigger": _loc(
                lang,
                "Réponse langue dégradée",
                "Verschlechterte Sprachantwort",
                "Degraded language response",
            ),
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
            "trigger": _loc(
                lang, "Conformité Art. 50", "Konformitaet Art. 50", "Compliance Art. 50"
            ),
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
            "desc": _loc(
                lang,
                "Détecter & réduire les hallucinations RAG",
                "RAG-Halluzinationen erkennen & reduzieren",
                "Detect & reduce RAG hallucinations",
            ),
            "runs": 18,
        },
        {
            "name": "Prompt injection containment",
            "desc": _loc(
                lang,
                "Confiner une injection de prompt",
                "Eine Prompt-Injection eindaemmen",
                "Contain a prompt injection",
            ),
            "runs": 12,
        },
        {
            "name": pb_pii,
            "desc": _loc(
                lang,
                "Effacer la PII en mémoire (RGPD)",
                "PII im Speicher loeschen (DSGVO)",
                "Erase PII from memory (GDPR)",
            ),
            "runs": 9,
        },
        {
            "name": "Freeze release & rollback",
            "desc": _loc(
                lang,
                "Geler la release et revenir en arrière",
                "Release einfrieren und zuruecksetzen",
                "Freeze the release and roll back",
            ),
            "runs": 13,
        },
        {
            "name": pb_conf,
            "desc": _loc(
                lang,
                "Art. 50 / RGPD — remédiation",
                "Art. 50 / DSGVO — Behebung",
                "Art. 50 / GDPR — remediation",
            ),
            "runs": 7,
        },
    ]

    recent_incidents = [
        {"id": "INC-231", "label": "Hallucination — RAG", "severity": "critique", "time": "11:23"},
        {"id": "INC-232", "label": trig_pii, "severity": "critique", "time": "11:23"},
        {"id": "INC-227", "label": "Prompt injection", "severity": "eleve", "time": "11:21"},
        {
            "id": "INC-219",
            "label": _loc(
                lang,
                "Réponse langue dégradée",
                "Verschlechterte Sprachantwort",
                "Degraded language response",
            ),
            "severity": "moyen",
            "time": "11:18",
        },
    ]

    def _remaining(value: str) -> str:
        return _loc(lang, f"{value} restantes", f"{value} verbleibend", f"{value} remaining")

    sla_escalations = [
        {"id": "INC-231", "remaining": _remaining("22 min"), "tone": "crit"},
        {"id": "INC-232", "remaining": _remaining("28 min"), "tone": "crit"},
        {"id": "INC-225", "remaining": _remaining("54 min"), "tone": "warn"},
        {"id": "INC-227", "remaining": _remaining("1 h 05"), "tone": "ok"},
    ]

    domain_distribution = [
        {"key": "privacy", "count": 4, "pct": 29, "color": _DOMAIN_COLOR["privacy"]},
        {"key": "qualite_rag", "count": 3, "pct": 21, "color": _DOMAIN_COLOR["qualite_rag"]},
        {"key": "securite", "count": 3, "pct": 21, "color": _DOMAIN_COLOR["securite"]},
        {"key": "observabilite", "count": 2, "pct": 14, "color": _DOMAIN_COLOR["observabilite"]},
        {"key": "conformite", "count": 2, "pct": 14, "color": _DOMAIN_COLOR["conformite"]},
    ]

    control_cases = [
        {
            "id": "CC-012",
            "label": _loc(lang, "Fuite PII & mémoire", "PII-Leck & Speicher", "PII leak & memory"),
            "assoc": 2,
        },
        {
            "id": "CC-007",
            "label": _loc(
                lang,
                "Hallucination systématique",
                "Systematische Halluzination",
                "Systematic hallucination",
            ),
            "assoc": 1,
        },
        {
            "id": "CC-004",
            "label": _loc(lang, "Conformité Art. 50", "Konformitaet Art. 50", "Compliance Art. 50"),
            "assoc": 1,
        },
    ]

    running_playbook = {
        "name": "Prompt injection containment",
        "incident": "INC-231",
        "owner": "S. SysAdmin",
        "role": "Operator+",
        "proofs": 3,
        "elapsed": "00:07:31",
        "steps": [
            {
                "key": "detection",
                "label": _loc(lang, "Détection", "Erkennung", "Detection"),
                "time": "11:44:22",
                "state": "done",
            },
            {
                "key": "containment",
                "label": _loc(lang, "Containment", "Eindaemmung", "Containment"),
                "time": "11:48:48",
                "state": "current",
            },
            {
                "key": "investigation",
                "label": _loc(lang, "Investigation", "Untersuchung", "Investigation"),
                "time": "",
                "state": "todo",
            },
            {
                "key": "remediation",
                "label": _loc(lang, "Remediation", "Behebung", "Remediation"),
                "time": "",
                "state": "todo",
            },
            {
                "key": "verification",
                "label": _loc(lang, "Vérification", "Verifizierung", "Verification"),
                "time": "",
                "state": "todo",
            },
            {
                "key": "closure",
                "label": _loc(lang, "Clôture", "Abschluss", "Closure"),
                "time": "",
                "state": "todo",
            },
        ],
    }

    response_journal = [
        {
            "time": "11:47:31",
            "incident": "INC-231",
            "action": _loc(
                lang,
                "Containment — règles MAJ",
                "Eindaemmung — Regeln aktualisiert",
                "Containment — rules updated",
            ),
            "actor": "M. Engineer",
        },
        {
            "time": "11:46:12",
            "incident": "INC-225",
            "action": _loc(
                lang,
                "Qualification — sévérité",
                "Qualifizierung — Schweregrad",
                "Triage — severity",
            ),
            "actor": "S. SysAdmin",
        },
        {
            "time": "11:45:02",
            "incident": "INC-232",
            "action": _loc(
                lang,
                "Purge mémoire — lancée",
                "Speicherbereinigung — gestartet",
                "Memory purge — started",
            ),
            "actor": "A. Privacy",
        },
        {
            "time": "11:44:22",
            "incident": "INC-231",
            "action": _loc(lang, "Playbook lancé", "Playbook gestartet", "Playbook launched"),
            "actor": "Auto-page",
        },
        {
            "time": "11:42:50",
            "incident": "INC-228",
            "action": _loc(lang, "Escalade — Admin+", "Eskalation — Admin+", "Escalation — Admin+"),
            "actor": "Auto-escalade",
        },
    ]

    automations = [
        {
            "rule": _loc(lang, "Auto-page critique", "Auto-Page kritisch", "Auto-page critical"),
            "status": "actif",
            "last": "11:53:41",
            "role": "Operator+",
        },
        {
            "rule": _loc(
                lang, "Auto-triage (mémoire)", "Auto-Triage (Speicher)", "Auto-triage (memory)"
            ),
            "status": "actif",
            "last": "11:51:08",
            "role": "Operator+",
        },
        {
            "rule": _loc(lang, "Auto-escalade SLA", "Auto-Eskalation SLA", "Auto-escalation SLA"),
            "status": "actif",
            "last": "10:59:11",
            "role": "Operator+",
        },
        {
            "rule": _loc(
                lang,
                "Auto-ouverture playbook",
                "Auto-Oeffnung Playbook",
                "Auto-open playbook",
            ),
            "status": "actif",
            "last": "11:48:17",
            "role": "Compliance+",
        },
        {
            "rule": _loc(lang, "Auto-redaction PII", "Auto-Schwaerzung PII", "Auto-redaction PII"),
            "status": "dryrun",
            "last": "11:48:17",
            "role": "Admin+",
        },
    ]

    mttr_series = {
        "labels": ["01/05", "03/05", "05/05", "07/05", "09/05", "11/05", "13/05"],
        "mtta": [5, 4, 5, 4, 4, 3, 3],
        "mttr": [42, 40, 38, 35, 33, 30, 28],
    }

    resolution_by_playbook = [
        {"name": "Hallucination — RAG", "pct": 73, "ratio": "10/14", "color": "#f97316"},
        {"name": pb_pii, "pct": 89, "ratio": "8/9", "color": "#34d399"},
        {"name": "Prompt injection containment", "pct": 83, "ratio": "10/12", "color": "#60a5fa"},
        {"name": "Freeze release & rollback", "pct": 75, "ratio": "9/12", "color": "#a78bfa"},
        {"name": pb_conf, "pct": 71, "ratio": "5/7", "color": "#fbbf24"},
    ]

    def _resolved(time: str, day: str) -> str:
        return _loc(
            lang, f"Résolu {time} · {day}", f"Geloest {time} · {day}", f"Resolved {time} · {day}"
        )

    postmortems = [
        {
            "id": "INC-224",
            "label": "Hallucination — RAG",
            "rca": _loc(
                lang,
                "Chunking trop large — reranker ajusté",
                "Chunking zu gross — Reranker angepasst",
                "Chunking too large — reranker adjusted",
            ),
            "resolved": _resolved("12:05", "J-2"),
        },
        {
            "id": "INC-221",
            "label": trig_pii,
            "rca": _loc(
                lang,
                "TTL mémoire manquant — purge auto.",
                "Speicher-TTL fehlt — Auto-Bereinigung",
                "Missing memory TTL — auto purge",
            ),
            "resolved": _resolved("16:40", "J-2"),
        },
        {
            "id": "INC-223",
            "label": "Prompt injection",
            "rca": _loc(
                lang,
                "Motif jailbreak — règle ajoutée",
                "Jailbreak-Muster — Regel hinzugefuegt",
                "Jailbreak pattern — rule added",
            ),
            "resolved": _resolved("11:03", "J-3"),
        },
        {
            "id": "INC-216",
            "label": _loc(
                lang,
                "Sortie langue dégradée",
                "Verschlechterte Sprachausgabe",
                "Degraded language output",
            ),
            "rca": _loc(
                lang,
                "Routage langue — seuil revu",
                "Sprachrouting — Schwelle ueberarbeitet",
                "Language routing — threshold revised",
            ),
            "resolved": _resolved("09:18", "J-4"),
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
            "sync": _loc(lang, "il y a 2 min", "vor 2 Min", "2 min ago"),
        },
        # Per-tab operational catalogues (Incidents, Playbooks, Orchestration,
        # Actions, Post-mortems, Problemes connus, Rapports), rendered generically.
        "tabs": {key: asdict(tab) for key, tab in build_tabs(lang).items()},
    }
