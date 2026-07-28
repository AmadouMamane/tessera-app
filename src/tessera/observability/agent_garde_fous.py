"""Real Garde-fous data: guard rules from policy.yaml + the live audit trail.

This dashboard is backed by the running guard layer, not a fixture:

* The **rules** are derived from the canonical guard policy
  (``src/tessera/guard/policy.yaml``): the prompt-injection deny patterns, the
  PII redaction patterns, the per-tool allow/confirmation rules and the memory
  governance checks. Each rule's mode, severity and configuration counts are
  read from the compiled :class:`~tessera.guard.decisions.Policy`.
* The **runtime stats** (decisions logged, blocks, last firing, 24h deltas) are
  aggregated from the tamper-evident audit log
  (``GuardSettings.audit_file``), the same trail ``guard_explain`` reads.
* The **audit-chain integrity** is verified with
  :func:`tessera.guard.audit.verify_audit_chain`.

Per-rule enable/disable state is persisted to a durable JSON next to the audit
log and mutated by the rule-state endpoint. Display labels are localized
(fr/de/en); logic keys (tones, severities, modes) stay stable. Free-text is
ASCII-only per the source-file convention (accents are allowed; confusable
punctuation is not).
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

from tessera.guard.decisions import Policy, load_policy
from tessera.guard.ledger_store import read_ledger_entries, verify_active_ledger_checkpointed
from tessera.settings import get_settings

if TYPE_CHECKING:
    from pathlib import Path

    from tessera.guard.audit import ChainStatus

__all__ = [
    "available_rules",
    "build_agent_garde_fous",
    "set_rule_state",
]

_LANG_IDX: dict[str, int] = {"fr": 0, "de": 1, "en": 2}
_DAY_SECS = 86_400
_HIGH_COVERAGE = 90
_MID_COVERAGE = 70


def _norm_lang(lang: str) -> str:
    return lang if lang in _LANG_IDX else "fr"


def _t(triple: tuple[str, str, str], lang: str) -> str:
    return triple[_LANG_IDX[_norm_lang(lang)]]


# --- Rule catalogue -----------------------------------------------------------
# Each rule keys off the ``policy_rule`` identifier the guard actually emits into
# the audit log, so the firing stats below attribute correctly. Names, category,
# severity and mode are editorial mappings of what each policy mechanism does;
# the counts that flesh them out are read live from policy.yaml.


@dataclass(frozen=True, slots=True)
class _RuleDef:
    key: str  # policy_rule id as emitted into the audit log
    name: tuple[str, str, str]
    category: str  # category key (see _CATEGORY)
    severity: str  # severity tone key
    mode: str  # mode tone key
    description: tuple[str, str, str]


_CATEGORY: dict[str, tuple[str, str, str]] = {
    "securite": ("Sécurité", "Sicherheit", "Security"),
    "confidentialite": ("Confidentialité", "Vertraulichkeit", "Confidentiality"),
    "outils": ("Outils", "Werkzeuge", "Tools"),
    "memoire": ("Mémoire", "Speicher", "Memory"),
}

_SEVERITY: dict[str, tuple[str, str, str]] = {
    "crit": ("Critique", "Kritisch", "Critical"),
    "high": ("Élevée", "Hoch", "High"),
    "mod": ("Modérée", "Mittel", "Moderate"),
    "low": ("Faible", "Niedrig", "Low"),
}

_MODE: dict[str, tuple[str, str, str]] = {
    "block": ("Blocage", "Blockieren", "Block"),
    "limit": ("Limitation", "Begrenzung", "Limit"),
    "warn": ("Avertissement", "Warnung", "Warn"),
    "allow": ("Autorisation", "Freigabe", "Allow"),
    "confirm": ("Confirmation", "Bestätigung", "Confirm"),
}

_RULES: tuple[_RuleDef, ...] = (
    _RuleDef(
        key="prompt_injection.deny_patterns",
        name=(
            "Prompt injection - Blocage",
            "Prompt-Injection - Blockieren",
            "Prompt injection - Block",
        ),
        category="securite",
        severity="crit",
        mode="block",
        description=(
            "Détecte les tentatives de détournement d'instructions (jailbreak, "
            "usurpation de rôle, injection via balises ou encodage) et refuse le "
            "tour avant que le LLM ne voie le contenu hostile.",
            "Erkennt Versuche, Anweisungen zu unterlaufen (Jailbreak, "
            "Rollenuebernahme, Injektion ueber Tags oder Kodierung) und lehnt "
            "den Zug ab, bevor das LLM den feindlichen Inhalt sieht.",
            "Detects attempts to hijack instructions (jailbreak, role "
            "impersonation, tag- or encoding-based injection) and refuses the "
            "turn before the LLM ever sees the hostile content.",
        ),
    ),
    _RuleDef(
        key="pii.redact_patterns",
        name=(
            "PII - Redaction",
            "PII - Schwaerzung",
            "PII - Redaction",
        ),
        category="confidentialite",
        severity="crit",
        mode="limit",
        description=(
            "Masque les données personnelles (email, IBAN, numéro de carte, "
            "téléphones FR/DE) dans les entrées et sorties d'outils ainsi que "
            "dans les arguments renvoyés au LLM.",
            "Maskiert personenbezogene Daten (E-Mail, IBAN, Kartennummer, "
            "Telefon FR/DE) in Werkzeug-Ein- und -Ausgaben sowie in den an das "
            "LLM zurueckgegebenen Argumenten.",
            "Masks personal data (email, IBAN, card number, FR/DE phone "
            "numbers) in tool inputs and outputs and in the arguments echoed "
            "back to the LLM.",
        ),
    ),
    _RuleDef(
        key="tool.card_block.allow",
        name=(
            "Outil - Blocage de carte",
            "Werkzeug - Karte sperren",
            "Tool - Card block",
        ),
        category="outils",
        severity="high",
        mode="confirm",
        description=(
            "Action sensible : le blocage d'une carte exige une confirmation "
            "explicite de l'utilisateur et valide le motif et les quatre "
            "derniers chiffres avant exécution.",
            "Sensible Aktion: das Sperren einer Karte erfordert eine "
            "ausdrueckliche Bestaetigung und prueft Grund und letzte vier "
            "Ziffern vor der Ausfuehrung.",
            "Sensitive action: blocking a card requires explicit user "
            "confirmation and validates the reason and last four digits before "
            "executing.",
        ),
    ),
    _RuleDef(
        key="tool.account_balance.allow",
        name=(
            "Outil - Solde de compte",
            "Werkzeug - Kontostand",
            "Tool - Account balance",
        ),
        category="outils",
        severity="mod",
        mode="allow",
        description=(
            "Autorise la lecture du solde après validation de l'identifiant "
            "client, masqué dans le journal d'audit.",
            "Erlaubt das Lesen des Kontostands nach Pruefung der Kundennummer, "
            "im Audit-Protokoll maskiert.",
            "Allows reading the balance after validating the customer id, "
            "redacted in the audit log.",
        ),
    ),
    _RuleDef(
        key="tool.transaction_search.allow",
        name=(
            "Outil - Recherche de transactions",
            "Werkzeug - Transaktionssuche",
            "Tool - Transaction search",
        ),
        category="outils",
        severity="mod",
        mode="allow",
        description=(
            "Autorise la recherche de transactions du client avec validation de "
            "l'identifiant et plafonnement du nombre d'appels par tour.",
            "Erlaubt die Suche nach Kundentransaktionen mit Pruefung der "
            "Kennung und Begrenzung der Aufrufe pro Zug.",
            "Allows searching the customer's transactions with id validation "
            "and a per-turn call cap.",
        ),
    ),
    _RuleDef(
        key="tool.loan_simulate.allow",
        name=(
            "Outil - Simulation de prêt",
            "Werkzeug - Kreditsimulation",
            "Tool - Loan simulation",
        ),
        category="outils",
        severity="low",
        mode="allow",
        description=(
            "Autorise les simulations de prêt en rejetant les montants aberrants "
            "(plafond 10 M EUR) et les durées hors de l'intervalle 1-30 ans.",
            "Erlaubt Kreditsimulationen und weist abwegige Betraege (Limit "
            "10 Mio. EUR) und Laufzeiten ausserhalb von 1-30 Jahren ab.",
            "Allows loan simulations while rejecting aberrant amounts (10M EUR "
            "cap) and terms outside the 1-30 year range.",
        ),
    ),
    _RuleDef(
        key="tool.ticket_escalate.allow",
        name=(
            "Outil - Escalade vers un humain",
            "Werkzeug - Eskalation an Mensch",
            "Tool - Human escalation",
        ),
        category="outils",
        severity="low",
        mode="allow",
        description=(
            "Autorise l'escalade vers un agent humain en masquant l'extrait de "
            "conversation dans le journal d'audit.",
            "Erlaubt die Eskalation an einen menschlichen Agenten und maskiert "
            "den Gespraechsausschnitt im Audit-Protokoll.",
            "Allows escalation to a human agent while redacting the transcript "
            "excerpt from the audit log.",
        ),
    ),
    _RuleDef(
        key="memory.write.governance",
        name=(
            "Mémoire - Écriture (gouvernance)",
            "Speicher - Schreiben (Governance)",
            "Memory - Write (governance)",
        ),
        category="memoire",
        severity="high",
        mode="limit",
        description=(
            "Filtre les écritures mémoire : dépistage PII, consentement et TTL "
            "avant toute persistance d'un fait cross-session.",
            "Filtert Speicher-Schreibvorgaenge: PII-Screening, Einwilligung und "
            "TTL vor jeder sitzungsuebergreifenden Persistenz.",
            "Filters memory writes: PII screening, consent and TTL before any "
            "cross-session fact is persisted.",
        ),
    ),
    _RuleDef(
        key="memory.read.governance",
        name=(
            "Mémoire - Lecture (gouvernance)",
            "Speicher - Lesen (Governance)",
            "Memory - Read (governance)",
        ),
        category="memoire",
        severity="mod",
        mode="limit",
        description=(
            "Filtre les lectures mémoire : dépistage PII et contrôle d'accès par "
            "sujet avant de restituer un souvenir à l'agent.",
            "Filtert Speicher-Lesevorgaenge: PII-Screening und subjektbezogene "
            "Zugriffskontrolle, bevor eine Erinnerung an den Agenten geht.",
            "Filters memory reads: PII screening and per-subject access control "
            "before returning a memory to the agent.",
        ),
    ),
)


# --- Runtime stats from the audit trail ---------------------------------------


@dataclass(slots=True)
class _RuleStat:
    """Per-rule firing aggregates read from the audit log."""

    decisions: int = 0
    denials: int = 0
    last_fired: datetime | None = None
    c24: int = 0  # decisions in the last 24h
    cprev: int = 0  # decisions in the prior 24h (24-48h ago)


@dataclass(slots=True)
class _AuditScan:
    """Whole-log aggregates plus per-rule stats."""

    total: int = 0
    denials: int = 0
    total_24h: int = 0
    denials_24h: int = 0
    per_rule: dict[str, _RuleStat] = field(default_factory=lambda: defaultdict(_RuleStat))


def _parse_dt(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _scan_audit(path: Path, now: datetime) -> _AuditScan:
    """Aggregate per-rule and global decision stats from the JSON-Lines log."""
    scan = _AuditScan()
    for obj in read_ledger_entries(path):
        if obj.get("type") != "tessera.guard.audit":
            continue
        decisions = obj.get("decisions")
        if not isinstance(decisions, list):
            continue
        for decision in decisions:
            if isinstance(decision, dict):
                _record_decision(scan, decision, now)
    return scan


def _record_decision(scan: _AuditScan, decision: dict[str, object], now: datetime) -> None:
    rule = str(decision.get("policy_rule", "unknown"))
    kind = str(decision.get("decision", "unknown"))
    when = _parse_dt(decision.get("occurred_at"))
    is_deny = kind == "deny"
    age = (now - when).total_seconds() if when is not None else None

    scan.total += 1
    if is_deny:
        scan.denials += 1
    if age is not None and age < _DAY_SECS:
        scan.total_24h += 1
        if is_deny:
            scan.denials_24h += 1

    stat = scan.per_rule[rule]
    stat.decisions += 1
    if is_deny:
        stat.denials += 1
    if when is not None and (stat.last_fired is None or when > stat.last_fired):
        stat.last_fired = when
    if age is not None:
        if age < _DAY_SECS:
            stat.c24 += 1
        elif age < 2 * _DAY_SECS:
            stat.cprev += 1


# --- Durable enable/disable state ---------------------------------------------


def _state_path() -> Path:
    return get_settings().guard.audit_file.parent / "garde_fous_state.json"


def _load_state() -> dict[str, dict[str, bool]]:
    path = _state_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_state(state: dict[str, dict[str, bool]]) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def set_rule_state(key: str, *, enabled: bool) -> None:
    """Persist an enable/disable change for one rule key."""
    state = _load_state()
    entry = state.get(key, {"enabled": True})
    entry["enabled"] = enabled
    state[key] = entry
    _save_state(state)


def available_rules() -> set[str]:
    """The set of known rule keys (for endpoint validation)."""
    return {rule.key for rule in _RULES}


# --- Formatting helpers -------------------------------------------------------


def _fmt_int(value: int) -> str:
    """Group thousands with an ASCII space (12540 -> '12 540')."""
    return f"{value:,}".replace(",", " ")


def _fmt_pct(value: float, decimals: int = 1) -> str:
    return f"{value:.{decimals}f}".replace(".", ",") + " %"


def _rel_age(when: datetime | None, now: datetime, lang: str) -> str:
    if when is None:
        return "-"
    secs = (now - when).total_seconds()
    lng = _norm_lang(lang)
    hour = 3600
    if secs < hour:
        n = max(1, int(secs // 60))
        return {"fr": f"il y a {n} min", "de": f"vor {n} Min", "en": f"{n}m ago"}[lng]
    if secs < _DAY_SECS:
        n = int(secs // hour)
        return {"fr": f"il y a {n} h", "de": f"vor {n} Std", "en": f"{n}h ago"}[lng]
    n = int(secs // _DAY_SECS)
    return {"fr": f"il y a {n} j", "de": f"vor {n} T", "en": f"{n}d ago"}[lng]


# --- Config block per rule (real, from the compiled policy) -------------------

_CFG: dict[str, tuple[str, str, str]] = {
    "deny_patterns": ("Motifs de refus", "Ablehnungsmuster", "Deny patterns"),
    "transforms": ("Transformations", "Transformationen", "Transforms"),
    "languages": ("Langues couvertes", "Abgedeckte Sprachen", "Covered languages"),
    "action_refuse": ("Action", "Aktion", "Action"),
    "redact_patterns": ("Motifs de redaction", "Schwaerzungsmuster", "Redaction patterns"),
    "scope": ("Portee", "Geltungsbereich", "Scope"),
    "logging": ("Journalisation", "Protokollierung", "Logging"),
    "allowed": ("Autorise", "Erlaubt", "Allowed"),
    "confirm_required": (
        "Confirmation requise",
        "Bestaetigung erforderlich",
        "Confirmation required",
    ),
    "max_calls": ("Appels max / tour", "Max. Aufrufe / Zug", "Max calls / turn"),
    "args_validated": ("Arguments valides", "Validierte Argumente", "Validated arguments"),
    "args_redacted": (
        "Arguments masques (audit)",
        "Maskierte Argumente (Audit)",
        "Redacted args (audit)",
    ),
    "pii_screen": ("Depistage PII", "PII-Screening", "PII screening"),
    "consent": ("Consentement", "Einwilligung", "Consent"),
    "residency": ("Résidence des données", "Datenresidenz", "Data residency"),
}

_YES = ("Oui", "Ja", "Yes")
_NO = ("Non", "Nein", "No")
_ENABLED = ("Activée", "Aktiviert", "Enabled")
_REQUIRED = ("Requise", "Erforderlich", "Required")
_REFUSE_TURN = ("Refus du tour", "Zug ablehnen", "Refuse the turn")
_MASK = ("Masquage", "Maskierung", "Masking")
_IO_SCOPE = (
    "Entrées et sorties d'outils",
    "Werkzeug-Ein- und -Ausgaben",
    "Tool inputs and outputs",
)


def _config_rows(rule: _RuleDef, policy: Policy, lang: str) -> list[dict[str, str]]:
    """Real technical configuration for ``rule`` from the compiled policy."""
    if rule.key == "prompt_injection.deny_patterns":
        return [
            {
                "label": _t(_CFG["deny_patterns"], lang),
                "value": str(len(policy.prompt_injection_deny)),
            },
            {
                "label": _t(_CFG["transforms"], lang),
                "value": str(len(policy.prompt_injection_transforms)),
            },
            {"label": _t(_CFG["languages"], lang), "value": "FR / DE / EN"},
            {"label": _t(_CFG["action_refuse"], lang), "value": _t(_REFUSE_TURN, lang)},
            {"label": _t(_CFG["logging"], lang), "value": _t(_ENABLED, lang)},
        ]
    if rule.key == "pii.redact_patterns":
        return [
            {"label": _t(_CFG["redact_patterns"], lang), "value": str(len(policy.pii_patterns))},
            {"label": _t(_CFG["scope"], lang), "value": _t(_IO_SCOPE, lang)},
            {"label": _t(_CFG["action_refuse"], lang), "value": _t(_MASK, lang)},
            {"label": _t(_CFG["logging"], lang), "value": _t(_ENABLED, lang)},
        ]
    if rule.key.startswith("tool."):
        tool_name = rule.key.split(".", 2)[1]
        tp = policy.tool(tool_name)
        n_redacted = sum(1 for a in tp.arguments.values() if a.redact_in_audit)
        return [
            {"label": _t(_CFG["allowed"], lang), "value": _t(_YES if tp.allow else _NO, lang)},
            {
                "label": _t(_CFG["confirm_required"], lang),
                "value": _t(_YES if tp.requires_confirmation else _NO, lang),
            },
            {"label": _t(_CFG["max_calls"], lang), "value": str(tp.max_calls_per_turn)},
            {"label": _t(_CFG["args_validated"], lang), "value": str(len(tp.arguments))},
            {"label": _t(_CFG["args_redacted"], lang), "value": str(n_redacted)},
        ]
    # memory governance
    residency = get_settings().observability.data_residency.upper()
    return [
        {"label": _t(_CFG["pii_screen"], lang), "value": _t(_ENABLED, lang)},
        {"label": _t(_CFG["consent"], lang), "value": _t(_REQUIRED, lang)},
        {"label": _t(_CFG["logging"], lang), "value": _t(_ENABLED, lang)},
        {"label": _t(_CFG["residency"], lang), "value": residency},
    ]


# --- Chrome strings -----------------------------------------------------------

_STR: dict[str, tuple[str, str, str]] = {
    "title": ("Garde-fous", "Schutzregeln", "Guardrails"),
    "subtitle": (
        "Règles et protections appliquées aux réponses de l'assistant (live policy + audit).",
        "Regeln und Schutzmassnahmen fuer die Antworten des Assistenten (live Policy + Audit).",
        "Rules and protections applied to the assistant's answers (live policy + audit).",
    ),
    "act_asof": ("Voir à date (as-of)", "Stand anzeigen (as-of)", "View as-of"),
    "act_create": ("Créer un garde-fou", "Schutzregel erstellen", "Create a guardrail"),
    "snap_tag": ("SNAPSHOT ACTIF", "AKTIVER SNAPSHOT", "ACTIVE SNAPSHOT"),
    "snap_label": ("Garde-fous à date", "Schutzregeln (Stand)", "Guardrails as-of"),
    "snap_updated": ("Dernière mise à jour", "Letzte Aktualisierung", "Last updated"),
    "snap_version": ("Version de la politique", "Policy-Version", "Policy version"),
    "snap_decisions": (
        "Décisions journalisées",
        "Protokollierte Entscheidungen",
        "Logged decisions",
    ),
    "snap_coverage": ("Règles actives", "Aktive Regeln", "Active rules"),
    "snap_asof": ("Voir à date", "Stand anzeigen", "View as-of"),
    "snap_compare": (
        "Comparer au snapshot précédent",
        "Mit vorherigem Snapshot vergleichen",
        "Compare to previous snapshot",
    ),
    "kpi_rules": ("Règles actives", "Aktive Regeln", "Active rules"),
    "kpi_categories": ("Catégories couvertes", "Abgedeckte Kategorien", "Covered categories"),
    "kpi_block": ("Taux de blocage", "Blockierrate", "Block rate"),
    "kpi_incidents": ("Incidents bloqués", "Blockierte Vorfaelle", "Blocked incidents"),
    "kpi_falsepos": ("Taux de faux positifs", "Falsch-Positiv-Rate", "False-positive rate"),
    "kpi_decisions": (
        "Décisions journalisées",
        "Protokollierte Entscheidungen",
        "Logged decisions",
    ),
    "f_search": ("Rechercher une regle...", "Regel suchen...", "Search a rule..."),
    "f_category": ("Catégorie", "Kategorie", "Category"),
    "f_status": ("Statut", "Status", "Status"),
    "f_severity": ("Sévérité", "Schweregrad", "Severity"),
    "f_all_f": ("Toutes", "Alle", "All"),
    "f_all_m": ("Tous", "Alle", "All"),
    "f_more": ("Filtres", "Filter", "Filters"),
    "col_name": ("Nom de la regle", "Regelname", "Rule name"),
    "col_category": ("Catégorie", "Kategorie", "Category"),
    "col_severity": ("Sévérité", "Schweregrad", "Severity"),
    "col_status": ("Statut", "Status", "Status"),
    "col_mode": ("Mode", "Modus", "Mode"),
    "col_activity": ("Part d'activite", "Aktivitaetsanteil", "Activity share"),
    "col_updated": ("Source", "Quelle", "Source"),
    "col_lastfired": ("Dernier déclenchement", "Letzte Ausloesung", "Last fired"),
    "st_active": ("Active", "Aktiv", "Active"),
    "st_off": ("Désactivée", "Deaktiviert", "Disabled"),
    "src_policy": ("policy.yaml", "policy.yaml", "policy.yaml"),
    "src_governance": ("gouvernance mémoire", "Speicher-Governance", "memory governance"),
    "never": ("Jamais déclenchée", "Nie ausgeloest", "Never fired"),
    "watch_title": ("À surveiller", "Zu beobachten", "Watchlist"),
    "watch_cta": ("Voir le journal d'audit", "Audit-Protokoll ansehen", "View the audit log"),
    "quick_title": ("Actions rapides", "Schnellaktionen", "Quick actions"),
    "q_policy": ("Modifier la politique", "Policy bearbeiten", "Edit the policy"),
    "q_audit": ("Voir le journal d'audit", "Audit-Protokoll ansehen", "View the audit log"),
    "q_policies": ("Politiques de conformite", "Compliance-Richtlinien", "Compliance policies"),
    "q_catalog": ("Catalogue de signaux", "Signalkatalog", "Signal catalogue"),
    "cov_title": ("Couverture par catégorie", "Abdeckung nach Kategorie", "Coverage by category"),
    "reasons_title": ("Top raisons de blocage", "Top Blockiergründe", "Top block reasons"),
    "detail_eyebrow": ("Détails du garde-fou", "Details der Schutzregel", "Guardrail details"),
    "tab_summary": ("Résumé", "Zusammenfassung", "Summary"),
    "tab_config": ("Configuration", "Konfiguration", "Configuration"),
    "tab_tests": ("Journalisation", "Protokollierung", "Logging"),
    "fld_category": ("Catégorie", "Kategorie", "Category"),
    "fld_severity": ("Sévérité", "Schweregrad", "Severity"),
    "fld_mode": ("Mode", "Modus", "Mode"),
    "fld_decisions": (
        "Décisions journalisées",
        "Protokollierte Entscheidungen",
        "Logged decisions",
    ),
    "fld_blocks": ("Blocages", "Blockierungen", "Blocks"),
    "fld_blockrate": ("Taux de blocage", "Blockierrate", "Block rate"),
    "fld_activity": ("Part d'activite", "Aktivitaetsanteil", "Activity share"),
    "fld_lastfired": ("Dernier déclenchement", "Letzte Ausloesung", "Last fired"),
    "cfg_title": ("Configuration technique", "Technische Konfiguration", "Technical configuration"),
    "cfg_cta": ("Voir policy.yaml", "policy.yaml ansehen", "View policy.yaml"),
    "log_title": ("Journalisation & intégrité", "Protokoll & Integritaet", "Logging & integrity"),
    "log_cta": ("Ouvrir le journal", "Protokoll oeffnen", "Open the log"),
    "log_chain": ("Chaîne d'audit", "Audit-Kette", "Audit chain"),
    "log_entries": ("Entrées vérifiées", "Verifizierte Eintraege", "Verified entries"),
    "log_verified": ("Verifiee", "Verifiziert", "Verified"),
    "log_broken": ("Rompue", "Gebrochen", "Broken"),
    "toggle_label": ("Active dans la politique", "In der Policy aktiv", "Active in the policy"),
    "realtime": ("Temps reel", "Echtzeit", "Realtime"),
    "good": ("Bonne", "Gut", "Good"),
    "mid": ("Moyenne", "Mittel", "Fair"),
    "low_cov": ("Faible", "Niedrig", "Low"),
}

# Watch-item templates (filled with real numbers in _assemble).
_W_CAMPAIGN: dict[str, str] = {
    "fr": "Campagne d'évaluation : {n} tours d'injection bloqués",
    "de": "Evaluierungskampagne: {n} Injektions-Zuege blockiert",
    "en": "Evaluation campaign: {n} injection turns blocked",
}
_W_TOPRULE: dict[str, str] = {
    "fr": "{name} : {n} déclenchements sur 24h",
    "de": "{name}: {n} Ausloesungen in 24h",
    "en": "{name}: {n} firings in 24h",
}
_W_CHAIN_OK: dict[str, str] = {
    "fr": "Chaîne d'audit vérifiée - {n} entrées intactes",
    "de": "Audit-Kette verifiziert - {n} Eintraege intakt",
    "en": "Audit chain verified - {n} entries intact",
}
_W_CHAIN_KO: dict[str, str] = {
    "fr": "Chaîne d'audit rompue à l'entrée {n}",
    "de": "Audit-Kette bei Eintrag {n} gebrochen",
    "en": "Audit chain broken at entry {n}",
}


def _coverage_tone(pct: float) -> str:
    if pct >= _HIGH_COVERAGE:
        return "green"
    if pct >= _MID_COVERAGE:
        return "amber"
    return "red"


# --- Public builder -----------------------------------------------------------


async def build_agent_garde_fous(lang: str = "fr") -> dict[str, object]:
    """Assemble the Garde-fous payload from the live policy + audit trail."""
    settings = get_settings()
    now = datetime.now(UTC)
    policy = load_policy()
    scan = _scan_audit(settings.guard.audit_file, now)
    # Health-dot integrity for the panel: the cheap checkpointed verdict, not the full ~2s
    # opposability re-walk (which stays on État à date / audit-integrity).
    chain = verify_active_ledger_checkpointed()
    policy_mtime = _policy_mtime(settings.guard.policy_path)
    return _assemble(policy, scan, chain, _load_state(), policy_mtime, lang, now)


def _policy_mtime(path: Path) -> datetime:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    except OSError:
        return datetime.now(UTC)


def _enabled(state: dict[str, dict[str, bool]], key: str) -> bool:
    return bool(state.get(key, {"enabled": True}).get("enabled", True))


def _build_row(
    rule: _RuleDef,
    stat: _RuleStat,
    *,
    enabled: bool,
    total: int,
    version: int,
    now: datetime,
    lang: str,
) -> dict[str, object]:
    activity = round(100 * stat.decisions / total) if total else 0
    last = _rel_age(stat.last_fired, now, lang) if stat.last_fired else _t(_STR["never"], lang)
    source = _STR["src_governance"] if rule.key.startswith("memory.") else _STR["src_policy"]
    return {
        "key": rule.key,
        "name": _t(rule.name, lang),
        "category": _t(_CATEGORY[rule.category], lang),
        "category_key": rule.category,
        "severity": _t(_SEVERITY[rule.severity], lang),
        "sev_tone": rule.severity,
        "status": _t(_STR["st_active" if enabled else "st_off"], lang),
        "status_tone": "good" if enabled else "off",
        "mode": _t(_MODE[rule.mode], lang),
        "mode_tone": rule.mode,
        "coverage": activity,
        "decisions": stat.decisions,
        "updated": _t(source, lang),
        "author": f"v{version}",
        "test_status": last,
        "test_tone": "good" if stat.last_fired is not None else "off",
    }


def _build_kpis(
    scan: _AuditScan,
    *,
    n_active: int,
    n_total: int,
    n_cats_covered: int,
    n_cats: int,
    lang: str,
) -> list[dict[str, object]]:
    block_pct = 100 * scan.denials / scan.total if scan.total else 0.0
    block_24 = 100 * scan.denials_24h / scan.total_24h if scan.total_24h else 0.0
    return [
        {
            "key": "rules",
            "label": _t(_STR["kpi_rules"], lang),
            "value": str(n_active),
            "delta": f"{n_total} {_pack(lang)}",
            "good": True,
        },
        {
            "key": "categories",
            "label": _t(_STR["kpi_categories"], lang),
            "value": f"{n_cats_covered} / {n_cats}",
            "delta": "-",
            "good": True,
        },
        {
            "key": "block",
            "label": _t(_STR["kpi_block"], lang),
            "value": _fmt_pct(block_pct),
            "delta": f"24h : {_fmt_pct(block_24)}",
            "good": True,
        },
        {
            "key": "incidents",
            "label": _t(_STR["kpi_incidents"], lang),
            "value": _fmt_int(scan.denials),
            "delta": f"+{_fmt_int(scan.denials_24h)} (24h)",
            "good": True,
        },
        {
            "key": "falsepos",
            "label": _t(_STR["kpi_falsepos"], lang),
            "value": "-",
            "delta": "-",
            "good": True,
        },
        {
            "key": "decisions",
            "label": _t(_STR["kpi_decisions"], lang),
            "value": _fmt_int(scan.total),
            "delta": f"+{_fmt_int(scan.total_24h)} (24h)",
            "good": True,
        },
    ]


def _pack(lang: str) -> str:
    return {"fr": "au total", "de": "insgesamt", "en": "total"}[_norm_lang(lang)]


def _build_snapshot(
    *,
    policy: Policy,
    scan: _AuditScan,
    n_active: int,
    n_total: int,
    policy_mtime: datetime,
    now: datetime,
    lang: str,
) -> dict[str, object]:
    cov = round(100 * n_active / n_total) if n_total else 0
    tone_key = "good" if cov >= _HIGH_COVERAGE else "mid" if cov >= _MID_COVERAGE else "low_cov"
    return {
        "tag": _t(_STR["snap_tag"], lang),
        "label": _t(_STR["snap_label"], lang),
        "updated_label": _t(_STR["snap_updated"], lang),
        "updated": policy_mtime.strftime("%d/%m/%Y %H:%M"),
        "updated_rel": _rel_age(policy_mtime, now, lang),
        "version_label": _t(_STR["snap_version"], lang),
        "version": f"v{policy.version}",
        "version_status": _t(_STR["st_active"], lang),
        "evalset_label": _t(_STR["snap_decisions"], lang),
        "evalset": _fmt_int(scan.total),
        "coverage_label": _t(_STR["snap_coverage"], lang),
        "coverage": cov,
        "coverage_tone": _t(_STR[tone_key], lang),
        "asof": _t(_STR["snap_asof"], lang),
        "compare": _t(_STR["snap_compare"], lang),
    }


def _build_watch(
    scan: _AuditScan,
    chain: ChainStatus,
    rows: list[dict[str, object]],
    lang: str,
) -> dict[str, object]:
    lng = _norm_lang(lang)
    items: list[dict[str, str]] = []

    inj = scan.per_rule.get("prompt_injection.deny_patterns")
    if inj and inj.denials:
        items.append(
            {
                "title": _W_CAMPAIGN[lng].format(n=_fmt_int(inj.denials)),
                "detail": "",
                "tone": "warn",
            }
        )

    # Busiest rule over the last 24h.
    top = max(rows, key=lambda r: cast("int", r["decisions"]), default=None)
    if top and scan.per_rule.get(str(top["key"]), _RuleStat()).c24:
        c24 = scan.per_rule[str(top["key"])].c24
        items.append(
            {
                "title": _W_TOPRULE[lng].format(name=top["name"], n=_fmt_int(c24)),
                "detail": "",
                "tone": "info",
            }
        )

    if chain.verified:
        items.append(
            {
                "title": _W_CHAIN_OK[lng].format(n=_fmt_int(chain.length)),
                "detail": "",
                "tone": "info",
            }
        )
    else:
        items.append(
            {"title": _W_CHAIN_KO[lng].format(n=chain.broken_at), "detail": "", "tone": "crit"}
        )

    return {
        "title": _t(_STR["watch_title"], lang),
        "cta": _t(_STR["watch_cta"], lang),
        "items": items,
    }


def _build_coverage(
    per_cat_total: dict[str, int], per_cat_active: dict[str, int], lang: str
) -> dict[str, object]:
    items: list[dict[str, object]] = []
    for cat, total in sorted(per_cat_total.items(), key=lambda kv: -kv[1]):
        pct = round(100 * per_cat_active.get(cat, 0) / total) if total else 0
        items.append({"label": _t(_CATEGORY[cat], lang), "pct": pct, "tone": _coverage_tone(pct)})
    return {"title": _t(_STR["cov_title"], lang), "items": items}


# Humanized labels for the policy_rule keys carried by guard decisions.
_REASON_LABELS: dict[str, tuple[str, str, str]] = {
    "prompt_injection.deny_patterns": (
        "Injection de prompt",
        "Prompt-Injektion",
        "Prompt injection",
    ),
    "pii.patterns": ("Donnée personnelle (PII)", "Personenbezogene Daten", "Personal data (PII)"),
    "tools.allow": ("Outil non autorisé", "Nicht erlaubtes Werkzeug", "Disallowed tool"),
}


def _reason_label(rule: str, lang: str) -> str:
    if rule in _REASON_LABELS:
        return _t(_REASON_LABELS[rule], lang)
    return rule.replace("_", " ").replace(".", " · ").capitalize()


def _build_reasons(scan: _AuditScan, lang: str) -> dict[str, object]:
    """Top block reasons, from the real per-rule denial counts in the S1 journal."""
    ranked = sorted(
        ((rule, st.denials) for rule, st in scan.per_rule.items() if st.denials > 0),
        key=lambda kv: -kv[1],
    )
    top = scan.denials or 1
    items = [
        {
            "label": _reason_label(rule, lang),
            "pct": round(100 * n / top),
            "count": _fmt_int(n),
            "tone": "red" if n >= top / 2 else "amber",
        }
        for rule, n in ranked[:6]
    ]
    return {"title": _t(_STR["reasons_title"], lang), "items": items}


# Mode d'application + Overrides — i18n triples (logic keys stay stable).
_MODE_TITLE: tuple[str, str, str] = (
    "Mode d'application",
    "Durchsetzungsmodus",
    "Enforcement mode",
)
_MODE_SUB: tuple[str, str, str] = (
    "Répartition des règles par mécanisme (dérivé de policy.yaml).",
    "Verteilung der Regeln nach Mechanismus (aus policy.yaml).",
    "Rule distribution by mechanism (derived from policy.yaml).",
)
_OVR_TITLE: tuple[str, str, str] = ("Dérogations (overrides)", "Ausnahmen (Overrides)", "Overrides")
_OVR_SUB: tuple[str, str, str] = (
    "Règles désactivées manuellement pour cet agent (journal d'état réel).",
    "Manuell deaktivierte Regeln für diesen Agenten (realer Zustand).",
    "Rules manually disabled for this agent (real state store).",
)
_OVR_EMPTY: tuple[str, str, str] = (
    "Aucune dérogation manuelle — toutes les règles sont au réglage par défaut.",
    "Keine manuelle Ausnahme — alle Regeln auf Standard.",
    "No manual override — every rule is at its default.",
)
_OVR_OFF: tuple[str, str, str] = ("Désactivée", "Deaktiviert", "Disabled")


def _build_mode_distribution(
    state: dict[str, dict[str, bool]], scan: _AuditScan, lang: str
) -> dict[str, object]:
    """Enforcement-mode distribution, derived from the real policy mechanisms.

    Each guardrail rule maps to a policy enforcement mode (block / limit /
    confirm / allow); the counts come from the live rule set and the per-rule
    decision volume from the S1 journal. No fabricated values.
    """
    n_total = len(_RULES) or 1
    items: list[dict[str, object]] = []
    for mode in ("block", "limit", "confirm", "allow"):
        rules = [r for r in _RULES if r.mode == mode]
        if not rules:
            continue
        active = sum(1 for r in rules if _enabled(state, r.key))
        decisions = sum(scan.per_rule.get(r.key, _RuleStat()).decisions for r in rules)
        items.append(
            {
                "label": _t(_MODE[mode], lang),
                "mode": mode,
                "count": len(rules),
                "active": active,
                "decisions": decisions,
                "pct": round(100 * len(rules) / n_total),
            }
        )
    return {
        "title": _t(_MODE_TITLE, lang),
        "subtitle": _t(_MODE_SUB, lang),
        "items": items,
        "total": len(_RULES),
    }


def _build_overrides(state: dict[str, dict[str, bool]], lang: str) -> dict[str, object]:
    """Manual overrides = rules disabled in the durable state store (real source).

    The override panel binds to the same `set_rule_state` store the toggle
    writes to. When nothing is overridden it renders an honest empty state
    rather than a fabricated list.
    """
    items: list[dict[str, object]] = []
    for rule in _RULES:
        if not _enabled(state, rule.key):
            items.append(
                {
                    "key": rule.key,
                    "name": _t(rule.name, lang),
                    "category": _t(_CATEGORY[rule.category], lang),
                    "mode": _t(_MODE[rule.mode], lang),
                    "status": _t(_OVR_OFF, lang),
                }
            )
    return {
        "title": _t(_OVR_TITLE, lang),
        "subtitle": _t(_OVR_SUB, lang),
        "items": items,
        "count": len(items),
        "empty": _t(_OVR_EMPTY, lang),
    }


def _build_detail(
    rule: _RuleDef,
    stat: _RuleStat,
    *,
    enabled: bool,
    policy: Policy,
    chain: ChainStatus,
    total: int,
    policy_mtime: datetime,
    now: datetime,
    lang: str,
) -> dict[str, object]:
    activity = round(100 * stat.decisions / total) if total else 0
    block_rate = 100 * stat.denials / stat.decisions if stat.decisions else 0.0
    last = _rel_age(stat.last_fired, now, lang) if stat.last_fired else _t(_STR["never"], lang)
    chain_label = _t(_STR["log_verified" if chain.verified else "log_broken"], lang)
    return {
        "key": rule.key,
        "name": _t(rule.name, lang),
        "id": rule.key,
        "status": _t(_STR["st_active" if enabled else "st_off"], lang),
        "status_tone": "good" if enabled else "off",
        "enabled": enabled,
        "tabs": [
            _t(_STR["tab_summary"], lang),
            _t(_STR["tab_config"], lang),
            _t(_STR["tab_tests"], lang),
        ],
        "description": _t(rule.description, lang),
        "fields": [
            {"label": _t(_STR["fld_category"], lang), "value": _t(_CATEGORY[rule.category], lang)},
            {
                "label": _t(_STR["fld_severity"], lang),
                "value": _t(_SEVERITY[rule.severity], lang),
                "tone": rule.severity,
            },
            {"label": _t(_STR["fld_mode"], lang), "value": _t(_MODE[rule.mode], lang)},
            {"label": _t(_STR["fld_decisions"], lang), "value": _fmt_int(stat.decisions)},
            {"label": _t(_STR["fld_blocks"], lang), "value": _fmt_int(stat.denials)},
            {"label": _t(_STR["fld_blockrate"], lang), "value": _fmt_pct(block_rate)},
            {"label": _t(_STR["fld_activity"], lang), "value": f"{activity}%"},
            {
                "label": _t(_STR["fld_lastfired"], lang),
                "value": last,
                "tone": "good" if stat.last_fired is not None else None,
            },
        ],
        "config_title": _t(_STR["cfg_title"], lang),
        "config_cta": _t(_STR["cfg_cta"], lang),
        "config": _config_rows(rule, policy, lang),
        "rbac_title": _t(_STR["log_title"], lang),
        "rbac_cta": _t(_STR["log_cta"], lang),
        "rbac": [
            {"role": _t(_STR["fld_decisions"], lang), "access": _fmt_int(stat.decisions)},
            {"role": _t(_STR["fld_blocks"], lang), "access": _fmt_int(stat.denials)},
            {"role": _t(_STR["fld_lastfired"], lang), "access": last},
            {"role": _t(_STR["log_chain"], lang), "access": chain_label},
            {"role": _t(_STR["log_entries"], lang), "access": _fmt_int(chain.length)},
        ],
        "rbac_more": "",
        "toggle_label": _t(_STR["toggle_label"], lang),
        "policy_updated": policy_mtime.strftime("%d/%m/%Y %H:%M"),
    }


def _assemble(
    policy: Policy,
    scan: _AuditScan,
    chain: ChainStatus,
    state: dict[str, dict[str, bool]],
    policy_mtime: datetime,
    lang: str,
    now: datetime | None = None,
) -> dict[str, object]:
    """Pure assembly of the Garde-fous payload (no I/O) - unit-testable."""
    lang = _norm_lang(lang)
    now = now or datetime.now(UTC)

    per_cat_total: dict[str, int] = {cat: 0 for cat in _CATEGORY}
    per_cat_active: dict[str, int] = {cat: 0 for cat in _CATEGORY}
    rows: list[dict[str, object]] = []
    details: list[dict[str, object]] = []
    n_active = 0
    for rule in _RULES:
        stat = scan.per_rule.get(rule.key, _RuleStat())
        enabled = _enabled(state, rule.key)
        per_cat_total[rule.category] += 1
        if enabled:
            per_cat_active[rule.category] += 1
            n_active += 1
        rows.append(
            _build_row(
                rule,
                stat,
                enabled=enabled,
                total=scan.total,
                version=policy.version,
                now=now,
                lang=lang,
            )
        )
        details.append(
            _build_detail(
                rule,
                stat,
                enabled=enabled,
                policy=policy,
                chain=chain,
                total=scan.total,
                policy_mtime=policy_mtime,
                now=now,
                lang=lang,
            )
        )

    rows.sort(key=lambda r: -cast("int", r["decisions"]))
    n_total = len(_RULES)
    n_cats = len(_CATEGORY)
    n_cats_covered = sum(1 for cat in _CATEGORY if per_cat_active.get(cat, 0) > 0)

    return {
        "title": _t(_STR["title"], lang),
        "subtitle": _t(_STR["subtitle"], lang),
        "actions": {"asof": _t(_STR["act_asof"], lang), "create": _t(_STR["act_create"], lang)},
        "snapshot": _build_snapshot(
            policy=policy,
            scan=scan,
            n_active=n_active,
            n_total=n_total,
            policy_mtime=policy_mtime,
            now=now,
            lang=lang,
        ),
        "kpis": _build_kpis(
            scan,
            n_active=n_active,
            n_total=n_total,
            n_cats_covered=n_cats_covered,
            n_cats=n_cats,
            lang=lang,
        ),
        "filters": {
            "search": _t(_STR["f_search"], lang),
            "selects": [
                {"label": _t(_STR["f_category"], lang), "value": _t(_STR["f_all_f"], lang)},
                {"label": _t(_STR["f_status"], lang), "value": _t(_STR["f_all_m"], lang)},
                {"label": _t(_STR["f_severity"], lang), "value": _t(_STR["f_all_f"], lang)},
            ],
            "more": _t(_STR["f_more"], lang),
        },
        "table": {
            "columns": [
                _t(_STR["col_name"], lang),
                _t(_STR["col_category"], lang),
                _t(_STR["col_severity"], lang),
                _t(_STR["col_status"], lang),
                _t(_STR["col_mode"], lang),
                _t(_STR["col_activity"], lang),
                _t(_STR["col_updated"], lang),
                _t(_STR["col_lastfired"], lang),
            ],
            "rows": rows,
            "count": str(len(rows)),
            "pages": 1,
        },
        "watch": _build_watch(scan, chain, rows, lang),
        "quick": {
            "title": _t(_STR["quick_title"], lang),
            "items": [
                {"label": _t(_STR["q_policy"], lang), "href": "/configurer/garde-fous"},
                {"label": _t(_STR["q_audit"], lang), "href": "/prouver/audit-logs"},
                {"label": _t(_STR["q_policies"], lang), "href": "/configurer/politiques"},
                {"label": _t(_STR["q_catalog"], lang), "href": "/configurer/signal-catalog"},
            ],
        },
        "coverage": _build_coverage(per_cat_total, per_cat_active, lang),
        "reasons": _build_reasons(scan, lang),
        "mode_distribution": _build_mode_distribution(state, scan, lang),
        "overrides": _build_overrides(state, lang),
        "details": details,
    }
