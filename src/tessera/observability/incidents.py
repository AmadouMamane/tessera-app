"""Incidents & playbooks cockpit overview (page #10, ADR 0010).

Assembles the "Incidents & playbooks" overview the dashboard renders: the current
posture (open / critical incidents, MTTA / MTTR, auto-resolution), the triage
queue with the playbook recommended for each incident, the running playbook with
its step timeline, the automation rules, and the 7-day impact charts.

The AI-specific *playbook* catalogue and trigger logic live in
:mod:`tessera.observability.playbooks`; this module is the presentation layer
that composes a single, self-contained payload for the page.

The page has a REAL incident feed and a demonstration lifecycle subsystem:

* **REAL:** the incident queue is derived live — one incident per guard-rule
  family with denies in the window (clustered from the audit **ledger** through
  the read-seam, with real counts, last-seen times and a 7-day deny series),
  plus a low-faithfulness cluster from the captured replay bundles
  (``original_score`` below threshold). The posture KPIs (open/critical), the
  recent feed, the domain donut and the control cases (top failed-eval
  categories) all derive from those sources. Lifecycle metrics with no store
  (MTTA / MTTR / auto-resolution / SLA) render ``—``, never invented numbers.
* **DEMONSTRATION (``incidents`` synthetic signal):** the running-playbook
  timeline, response journal, automations, impact charts and post-mortems
  describe an incident-lifecycle subsystem this build does not implement; they
  stay a deterministic fixture, flagged in the frontend.
"""

from __future__ import annotations

import zlib
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta

from tessera.guard.ledger_store import read_ledger_entries
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


# Guard-rule family -> (severity, domain) for the real incident clusters.
_RULE_META: list[tuple[str, str, str]] = [
    ("prompt_injection", "critique", "securite"),
    ("pii", "critique", "privacy"),
    ("memory.", "eleve", "privacy"),
    ("tool.", "eleve", "securite"),
]
_LOW_SCORE_THRESHOLD = 0.80
_SLA_TONE = {"critique": "crit", "eleve": "warn", "moyen": "ok"}


def _rule_meta(rule: str) -> tuple[str, str]:
    for prefix, severity, domain in _RULE_META:
        if rule.startswith(prefix):
            return severity, domain
    return "moyen", "observabilite"


def _inc_id(key: str) -> str:
    """Deterministic INC-nnn id for a cluster key (stable across restarts)."""
    return f"INC-{zlib.crc32(key.encode('utf-8')) % 900 + 100}"


def _parse_when(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _scan_low_score() -> tuple[int, datetime | None]:
    """Count the real low-faithfulness turns in the captured replay bundles."""
    count = 0
    last: datetime | None = None
    try:
        from tessera.observability.replay import recent_bundles

        bundles = recent_bundles()
    except Exception:
        return 0, None
    for bundle in bundles:
        score = getattr(bundle, "original_score", None)
        if score is None or score >= _LOW_SCORE_THRESHOLD:
            continue
        count += 1
        when = _parse_when(getattr(bundle, "captured_at", None))
        if when and (last is None or when > last):
            last = when
    return count, last


@dataclass
class _Cluster:
    """One real incident cluster: a guard-rule family with denies in the window."""

    rule: str
    severity: str
    domain: str
    count: int = 0
    last: datetime = field(default_factory=lambda: datetime.min.replace(tzinfo=UTC))


class _RealIncidents:
    """The live incident feed: deny clusters + the low-faithfulness cluster."""

    def __init__(self, now: datetime) -> None:
        window = now - timedelta(days=7)
        day_keys = [(now - timedelta(days=d)).date().isoformat() for d in range(6, -1, -1)]
        self.day_denies: dict[str, int] = dict.fromkeys(day_keys, 0)
        clusters: dict[str, _Cluster] = {}
        self.n_events = 0
        self.events: list[tuple[datetime, str, str]] = []  # (when, rule, severity)
        try:
            entries = read_ledger_entries()
        except Exception:
            entries = []
        for entry in entries:
            if entry.get("type") != "tessera.guard.audit":
                continue
            decisions = entry.get("decisions")
            if not isinstance(decisions, list):
                continue
            for dec in decisions:
                if not isinstance(dec, dict) or dec.get("decision") != "deny":
                    continue
                when = _parse_when(dec.get("occurred_at")) or _parse_when(entry.get("occurred_at"))
                if when is None or when < window:
                    continue
                rule = str(dec.get("policy_rule", "") or "guard.autre")
                severity, domain = _rule_meta(rule)
                self.n_events += 1
                self.events.append((when, rule, severity))
                day = when.date().isoformat()
                if day in self.day_denies:
                    self.day_denies[day] += 1
                cl = clusters.setdefault(
                    rule, _Cluster(rule=rule, severity=severity, domain=domain)
                )
                cl.count += 1
                cl.last = max(when, cl.last)
        self.low_score, self.low_last = _scan_low_score()
        self.clusters = sorted(clusters.values(), key=lambda c: (-c.count, c.rule))

    def trigger_label(self, rule: str, lang: str) -> str:
        if rule.startswith("prompt_injection"):
            return "Prompt injection"
        if rule.startswith("pii"):
            return _loc(lang, "Fuite PII — mémoire", "PII-Leck — Speicher", "PII leak — memory")
        if rule.startswith("memory."):
            return _loc(
                lang,
                "Gouvernance mémoire — refus",
                "Speicher-Governance — Ablehnung",
                "Memory governance — deny",
            )
        if rule.startswith("tool."):
            name = rule.split(".")[1] if "." in rule else rule
            return _loc(
                lang,
                f"Outil refusé — {name}",
                f"Tool abgelehnt — {name}",
                f"Tool denied — {name}",
            )
        return _loc(lang, "Guard — autre règle", "Guard — andere Regel", "Guard — other rule")

    def playbook_for(self, rule: str, lang: str) -> str:
        if rule.startswith("prompt_injection"):
            return "Prompt injection containment"
        if rule.startswith(("pii", "memory.")):
            return _loc(lang, "Purge mémoire PII", "PII-Speicher leeren", "PII memory purge")
        return "—"


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
    core = _RealIncidents(now)

    # Recurring playbook names, localized once and reused across the page so the
    # triage queue, catalogue and resolution chart stay consistent.
    pb_pii = _loc(lang, "Purge mémoire PII", "PII-Speicher leeren", "PII memory purge")
    pb_conf = _loc(lang, "Incident conformité", "Konformitaetsvorfall", "Compliance incident")

    # REAL posture: clusters from the ledger + the low-faithfulness cluster; the
    # lifecycle metrics (MTTA/MTTR/auto-resolution/SLA/evidence packs) have no
    # store in this build -> honest dashes, never invented numbers.
    n_open = len(core.clusters) + (1 if core.low_score else 0)
    n_critical = sum(1 for c in core.clusters if c.severity == "critique")
    deny_series = list(core.day_denies.values())
    kpis = [
        _kpi("open", str(n_open), "0", False, deny_series or [0] * 7),
        _kpi("critical", str(n_critical), "0", False, [n_critical] * 7),
        _kpi("mtta", "—", "—", True, [0] * 7),
        _kpi("mttr", "—", "—", True, [0] * 7),
        _kpi("playbooks", "—", "—", True, [0] * 7),
        _kpi("autoresolve", "—", "—", True, [0] * 7),
        _kpi("sla_risk", "—", "—", False, [0] * 7),
        _kpi("evidence", "—", "—", True, [0] * 7),
    ]

    # REAL triage queue: one incident per guard-rule family with denies in the
    # window (real count + last-seen), plus the low-faithfulness cluster. There
    # is no lifecycle store: status is honestly "ouvert", owner/SLA are "—".
    priority_incidents = [
        {
            "id": _inc_id(c.rule),
            "severity": c.severity,
            "trigger": f"{core.trigger_label(c.rule, lang)} ({c.count})",
            "domain": c.domain,
            "status": "ouvert",
            "owner": "—",
            "sla": "—",
            "sla_tone": _SLA_TONE.get(c.severity, "ok"),
            "playbook": core.playbook_for(c.rule, lang),
            "role": "Operator+",
        }
        for c in core.clusters[:5]
    ]
    if core.low_score:
        priority_incidents.append(
            {
                "id": _inc_id("low_score"),
                "severity": "eleve",
                "trigger": _loc(
                    lang,
                    f"Fidélité faible — {core.low_score} tours",
                    f"Geringe Treue — {core.low_score} Turns",
                    f"Low faithfulness — {core.low_score} turns",
                ),
                "domain": "qualite_rag",
                "status": "ouvert",
                "owner": "—",
                "sla": "—",
                "sla_tone": "warn",
                "playbook": "Hallucination — RAG",
                "role": "Operator+",
            }
        )

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

    # REAL feed: the latest deny events from the ledger (rule label + real time).
    latest = sorted(core.events, key=lambda e: e[0], reverse=True)[:4]
    recent_incidents = [
        {
            "id": _inc_id(rule),
            "label": core.trigger_label(rule, lang),
            "severity": severity,
            "time": when.strftime("%H:%M"),
        }
        for when, rule, severity in latest
    ]
    if not recent_incidents and core.low_score and core.low_last:
        recent_incidents = [
            {
                "id": _inc_id("low_score"),
                "label": _loc(lang, "Fidélité faible", "Geringe Treue", "Low faithfulness"),
                "severity": "eleve",
                "time": core.low_last.strftime("%H:%M"),
            }
        ]

    def _remaining(value: str) -> str:
        return _loc(lang, f"{value} restantes", f"{value} verbleibend", f"{value} remaining")

    del _remaining  # no SLA store in this build: remaining renders an honest dash
    sla_escalations = [
        {
            "id": str(pi["id"]),
            "remaining": "—",
            "tone": str(pi["sla_tone"]),
        }
        for pi in priority_incidents[:4]
    ]

    # REAL distribution: incident clusters per domain (only non-empty domains).
    _domain_counts: dict[str, int] = {}
    for pi in priority_incidents:
        key = str(pi["domain"])
        _domain_counts[key] = _domain_counts.get(key, 0) + 1
    _domain_total = sum(_domain_counts.values()) or 1
    domain_distribution = [
        {
            "key": key,
            "count": count,
            "pct": round(count / _domain_total * 100),
            "color": _DOMAIN_COLOR.get(key, "#64748b"),
        }
        for key, count in sorted(_domain_counts.items(), key=lambda kv: -kv[1])
    ]

    # REAL control cases: the top failed-eval categories across the fleet
    # (the same real backlog the inbox and curation pages triage).
    _cat_label = {
        "hallucination": ("Hallucinations", "Halluzinationen", "Hallucinations"),
        "grounding": ("Ancrage / citations", "Verankerung / Zitate", "Grounding / citations"),
        "conformite": ("Conformité", "Konformitaet", "Compliance"),
        "pii_securite": ("PII & sécurité", "PII & Sicherheit", "PII & security"),
        "outils": ("Outils", "Tools", "Tools"),
        "multilingue": ("Multilingue", "Mehrsprachig", "Multilingual"),
        "autres": ("Autres", "Andere", "Other"),
    }
    try:
        from tessera.observability.curation_store import load_candidates

        _cc_counts: dict[str, int] = {}
        for cand in load_candidates():
            _cc_counts[cand.curation_category] = _cc_counts.get(cand.curation_category, 0) + 1
        control_cases = [
            {
                "id": f"CC-{key}",
                "label": _loc(lang, *_cat_label.get(key, (key, key, key))),
                "assoc": count,
            }
            for key, count in sorted(_cc_counts.items(), key=lambda kv: -kv[1])[:3]
        ]
    except Exception:
        control_cases = []

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
            "label": _loc(lang, "Fuite PII — mémoire", "PII-Leck — Speicher", "PII leak — memory"),
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
        "updated_at": now.strftime("%H:%M:%S"),
        "kpis": kpis,
        "priority_incidents": priority_incidents,
        "playbook_catalog": playbook_catalog,
        "recent_incidents": recent_incidents,
        "recent_more": max(0, core.n_events - len(recent_incidents)),
        "sla_escalations": sla_escalations,
        "domain_distribution": domain_distribution,
        "donut_total": len(priority_incidents),
        "control_cases": control_cases,
        "running_playbook": running_playbook,
        "response_journal": response_journal,
        "automations": automations,
        "mttr_series": mttr_series,
        "resolution_by_playbook": resolution_by_playbook,
        "incidents_by_domain": domain_distribution,
        "postmortems": postmortems,
        "footer": {
            "critical": n_critical,
            "at_risk": 0,
            "playbooks": len(playbook_catalog),
            "proofs": core.n_events,
            "source": "YAML · Git",
            "sync": _loc(lang, "il y a 2 min", "vor 2 Min", "2 min ago"),
        },
        # Per-tab operational catalogues (Incidents, Playbooks, Orchestration,
        # Actions, Post-mortems, Problemes connus, Rapports), rendered generically.
        "tabs": {key: asdict(tab) for key, tab in build_tabs(lang).items()},
    }
