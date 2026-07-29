"""Integrations cockpit overview (page #19, configurer/integrations).

Distinct from **Connecteurs** (the infrastructure topology: LLM, pgvector, guard,
GCP), this surfaces the agent's *real* business integrations — the LLM-callable
tools in :mod:`tessera.agent.tools` that reach the banking back ends
(account balance, card block, transaction search, loan simulation, ticket
escalation). It is **not** an invented SaaS catalogue (Salesforce/Snowflake/...).

Each tool is crossed with two real sources:
  * the compiled guard policy (``policy.yaml`` via :func:`load_policy`): per-tool
    ``allow`` / ``requires_confirmation`` / ``max_calls_per_turn`` / argument
    rules — the contract the firewall actually enforces;
  * the JSON-Lines guard audit log (``GuardSettings.audit_file``): the real number
    of ``tool.<name>.allow`` decisions, denials and last invocation.

The implementations are honest demo stubs (the docstrings say so), so the
"environment" reads **Demo** and there is no fabricated latency/cost. Read-only by
design (tools + policy are code/PR-owned), like Prompts: the functional axis is
wired search / filter / sort / row-select / nav + export, not a fake mutation.

Free-text is localized fr/de/en (French keeps accents, German transliterates
ae/oe/ue/ss); enum keys (category/status/criticality) stay stable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from tessera.guard.decisions import Policy, ToolPolicy, load_policy
from tessera.guard.ledger_store import (
    integrations_tool_scan,
    ledger_source,
    read_ledger_entries,
)
from tessera.observability.knowledge import _LANG_IDX, _norm_lang
from tessera.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

__all__ = ["compute_integrations_overview"]

_MINUTE = 60.0
_HOUR = 3600.0
_DAY = 86_400.0

# Real tool metadata: id + category (the filter/donut axis) and schema names.
# Names mirror the modules in tessera/agent/tools/. Localized name/system/desc
# live in _TOOL_TR keyed by id.
_TOOLS: list[dict[str, str]] = [
    {
        "id": "account_balance",
        "category": "lecture",
        "request": "AccountBalanceRequest",
        "response": "AccountBalance",
    },
    {
        "id": "transaction_search",
        "category": "lecture",
        "request": "TransactionSearchRequest",
        "response": "TransactionSearchResult",
    },
    {
        "id": "loan_simulate",
        "category": "simulation",
        "request": "LoanSimulationRequest",
        "response": "LoanSimulation",
    },
    {
        "id": "card_block",
        "category": "action",
        "request": "CardBlockRequest",
        "response": "CardBlock",
    },
    {
        "id": "ticket_escalate",
        "category": "escalade",
        "request": "TicketRequest",
        "response": "Ticket",
    },
]

# Localized tool name / target system / description (fr, de, en).
_TOOL_TR: dict[str, dict[str, tuple[str, str, str]]] = {
    "account_balance": {
        "name": ("Solde de compte", "Kontostand", "Account balance"),
        "system": ("Core banking", "Core Banking", "Core banking"),
        "desc": (
            "Solde disponible du compte (lecture core-banking).",
            "Verfuegbarer Kontostand (Core-Banking-Lesezugriff).",
            "Available account balance (core-banking read).",
        ),
    },
    "transaction_search": {
        "name": ("Recherche de transactions", "Transaktionssuche", "Transaction search"),
        "system": ("Registre des transactions", "Transaktionsregister", "Transaction ledger"),
        "desc": (
            "Recherche dans l'historique des transactions du client.",
            "Suche im Transaktionsverlauf des Kunden.",
            "Search the customer's transaction history.",
        ),
    },
    "loan_simulate": {
        "name": ("Simulation de crédit", "Kreditsimulation", "Loan simulation"),
        "system": ("Moteur de crédit", "Kredit-Engine", "Loan engine"),
        "desc": (
            "Simulation d'un crédit : mensualités, TAEG, coût total.",
            "Kreditsimulation: Raten, effektiver Jahreszins, Gesamtkosten.",
            "Loan simulation: instalments, APR, total cost.",
        ),
    },
    "card_block": {
        "name": ("Blocage de carte", "Kartensperre", "Card block"),
        "system": ("Gestion des cartes", "Kartenverwaltung", "Card management"),
        "desc": (
            "Opposition / blocage d'une carte - action sensible, confirmée.",
            "Sperrung einer Karte - sensible Aktion, bestaetigt.",
            "Block a card - sensitive action, confirmed.",
        ),
    },
    "ticket_escalate": {
        "name": ("Escalade ticket", "Ticket-Eskalation", "Ticket escalation"),
        "system": ("Ticketing / CRM", "Ticketing / CRM", "Ticketing / CRM"),
        "desc": (
            "Escalade vers un agent humain (création de ticket).",
            "Eskalation an einen menschlichen Agenten (Ticketerstellung).",
            "Escalation to a human agent (ticket creation).",
        ),
    },
}

# Shared localized labels + fixed values (fr, de, en).
_TR: dict[str, tuple[str, str, str]] = {
    "env_demo": ("Démo", "Demo", "Demo"),
    "env_demo_full": (
        "Démo (implémentation simulée)",
        "Demo (simulierte Implementierung)",
        "Demo (simulated implementation)",
    ),
    "rt_now": ("à l'instant", "gerade eben", "just now"),
    "rt_min": ("il y a {n} min", "vor {n} Min", "{n} min ago"),
    "rt_hours": ("il y a {n} h", "vor {n} Std", "{n}h ago"),
    "cl_target": ("Système cible", "Zielsystem", "Target system"),
    "cl_in": ("Schéma d'entrée", "Eingabeschema", "Input schema"),
    "cl_out": ("Schéma de sortie", "Ausgabeschema", "Output schema"),
    "cl_allowed": ("Autorisé", "Erlaubt", "Allowed"),
    "cl_confirm": ("Confirmation requise", "Bestaetigung erforderlich", "Confirmation required"),
    "cl_maxcalls": ("Appels max / tour", "Max. Aufrufe / Runde", "Max calls / turn"),
    "cl_args": ("Arguments contrôlés", "Gepruefte Argumente", "Checked arguments"),
    "v_yes": ("Oui", "Ja", "Yes"),
    "v_no": ("Non", "Nein", "No"),
    "sl_fw": ("Pare-feu", "Firewall", "Firewall"),
    "sl_rule": ("Règle de politique", "Policy-Regel", "Policy rule"),
    "sl_argval": ("Validation des arguments", "Argumentvalidierung", "Argument validation"),
    "sl_onviol": ("Sur violation", "Bei Verstoss", "On violation"),
    "sl_denied": ("Refus journalisés", "Protokollierte Ablehnungen", "Logged denials"),
    "sv_deny_logged": ("Refus + journalisé", "Ablehnung + protokolliert", "Denied + logged"),
    "ud_24h": ("{n} sur 24h", "{n} in 24h", "{n} over 24h"),
    "ud_denials": ("refus journalisés", "protokollierte Ablehnungen", "logged denials"),
    "ud_perturn": ("par tour", "pro Runde", "per turn"),
    "ks_tools": ("outils de l'agent", "Agent-Tools", "agent tools"),
    "ks_allowed": ("autorisés par la politique", "durch die Policy erlaubt", "allowed by policy"),
    "ks_confirm": ("confirmation requise", "Bestaetigung erforderlich", "confirmation required"),
    "ks_calls": ("appels journalisés", "protokollierte Aufrufe", "logged calls"),
    "ks_blocked": ("refus journalisés", "protokollierte Ablehnungen", "logged denials"),
    "ks_idle": ("jamais sollicités", "nie aufgerufen", "never called"),
    "f_source": (
        "agent/tools + policy.yaml + journal d'audit",
        "agent/tools + policy.yaml + Audit-Log",
        "agent/tools + policy.yaml + audit log",
    ),
    "owner_tool": ("Agent Tessera", "Agent Tessera", "Agent Tessera"),
    "owner_row": ("Agent", "Agent", "Agent"),
}

_CATEGORY_COLOR = {
    "lecture": "#60a5fa",
    "simulation": "#a78bfa",
    "action": "#f87171",
    "escalade": "#fbbf24",
}


def _t(key: str, lang: str) -> str:
    return _TR[key][_LANG_IDX.get(lang, 0)]


def _tool_t(tool_id: str, field_key: str, lang: str) -> str:
    return _TOOL_TR[tool_id][field_key][_LANG_IDX.get(lang, 0)]


@dataclass
class _ToolStat:
    decisions: int = 0
    denials: int = 0
    c24: int = 0
    last: datetime | None = None


@dataclass
class _Scan:
    per_tool: dict[str, _ToolStat] = field(default_factory=dict)

    def stat(self, name: str) -> _ToolStat:
        return self.per_tool.setdefault(name, _ToolStat())


def _parse_dt(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _record(scan: _Scan, decision: dict[str, object], now: datetime) -> None:
    """Fold one ``tool.<name>.allow`` decision into the per-tool stats."""
    rule = str(decision.get("policy_rule", ""))
    if not (rule.startswith("tool.") and rule.endswith(".allow")):
        return
    name = rule[len("tool.") : -len(".allow")]
    stat = scan.stat(name)
    stat.decisions += 1
    if str(decision.get("decision")) == "deny":
        stat.denials += 1
    when = _parse_dt(decision.get("occurred_at"))
    if when is None:
        return
    if stat.last is None or when > stat.last:
        stat.last = when
    if (now - when).total_seconds() < _DAY:
        stat.c24 += 1


def _scan_audit(path: Path, now: datetime) -> _Scan:
    """Aggregate per-tool decision stats from the guard audit trail.

    Postgres: one bounded ``GROUP BY`` over the unnested ``tool.<name>.allow`` decisions
    (:func:`integrations_tool_scan`) — one row per tool, never the chain. File source: the flat
    journal has no index, so it keeps the Python fold; both build a byte-identical ``_Scan``
    (verified against the real Postgres engine over synthetic edge cases).
    """
    if ledger_source() == "postgres":
        scan = _Scan()
        for name, n_dec, n_den, n_c24, last_seen in integrations_tool_scan(now - timedelta(days=1)):
            stat = scan.stat(name)
            stat.decisions = n_dec
            stat.denials = n_den
            stat.c24 = n_c24
            stat.last = _parse_dt(last_seen)
        return scan

    scan = _Scan()
    for obj in read_ledger_entries(path):
        if obj.get("type") != "tessera.guard.audit":
            continue
        decisions = obj.get("decisions")
        if not isinstance(decisions, list):
            continue
        for decision in decisions:
            if isinstance(decision, dict):
                _record(scan, decision, now)
    return scan


def _kpi(key: str, value: str, sub: str, series: Sequence[float]) -> dict[str, object]:
    return {"key": key, "value": value, "sub": sub, "series": list(series)}


def _fmt_int(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def _rel(when: datetime | None, now: datetime, lang: str) -> str:
    if when is None:
        return "-"
    secs = (now - when).total_seconds()
    if secs < _MINUTE:
        return _t("rt_now", lang)
    if secs < _HOUR:
        return _t("rt_min", lang).format(n=int(secs // _MINUTE))
    if secs < _DAY:
        return _t("rt_hours", lang).format(n=int(secs // _HOUR))
    return when.strftime("%d/%m/%Y %H:%M")


def _status(tp: ToolPolicy, stat: _ToolStat) -> str:
    """Map the guard policy + activity to the table's status enum."""
    if not tp.allow:
        return "error"  # blocked by policy
    if tp.requires_confirmation:
        return "warning"  # allowed but gated by confirmation
    if stat.decisions == 0:
        return "disabled"  # allowed but never exercised
    return "active"


def _criticality(tp: ToolPolicy, category: str) -> str:
    if tp.requires_confirmation or category == "action":
        return "high"
    if category in {"simulation", "escalade"}:
        return "medium"
    return "low"


def _detail(
    meta: dict[str, str], tp: ToolPolicy, stat: _ToolStat, now: datetime, lang: str
) -> dict[str, object]:
    allowed = stat.decisions - stat.denials
    rate = f"{round(allowed / stat.decisions * 100)}%" if stat.decisions else "-"
    tid = meta["id"]
    return {
        "id": tid,
        "name": _tool_t(tid, "name", lang),
        "status": _status(tp, stat),
        "response_time": "-",  # demo stubs: not instrumented
        "success_rate": rate,
        "last_sync": _rel(stat.last, now, lang),
        "description": _tool_t(tid, "desc", lang),
        "owner": _t("owner_tool", lang),
        "environment": _t("env_demo_full", lang),
        "region": "local",
        "criticality": _criticality(tp, meta["category"]),
        # Usage = real audit counts (relabelled read/write/cost slots).
        "usage": {
            "read": {
                "value": _fmt_int(stat.decisions),
                "delta": _t("ud_24h", lang).format(n=stat.c24),
            },
            "write": {"value": _fmt_int(stat.denials), "delta": _t("ud_denials", lang)},
            "cost": {"value": str(tp.max_calls_per_turn), "delta": _t("ud_perturn", lang)},
        },
        # Config = the real guard contract.
        "config_rows": [
            {"label": _t("cl_target", lang), "value": _tool_t(tid, "system", lang)},
            {"label": _t("cl_in", lang), "value": meta["request"]},
            {"label": _t("cl_out", lang), "value": meta["response"]},
            {"label": _t("cl_allowed", lang), "value": _t("v_yes" if tp.allow else "v_no", lang)},
            {
                "label": _t("cl_confirm", lang),
                "value": _t("v_yes" if tp.requires_confirmation else "v_no", lang),
            },
            {"label": _t("cl_maxcalls", lang), "value": str(tp.max_calls_per_turn)},
            {"label": _t("cl_args", lang), "value": str(len(tp.arguments))},
        ],
        # Security = how the firewall enforces it.
        "security_rows": [
            {"label": _t("sl_fw", lang), "value": "tessera.guard (first-party)"},
            {"label": _t("sl_rule", lang), "value": f"tool.{tid}.allow"},
            {"label": _t("sl_argval", lang), "value": "Pydantic strict (extra=forbid)"},
            {"label": _t("sl_onviol", lang), "value": _t("sv_deny_logged", lang)},
            {"label": _t("sl_denied", lang), "value": _fmt_int(stat.denials)},
        ],
    }


def compute_integrations_overview(lang: str = "fr") -> dict[str, object]:
    """Return the full Integrations overview, built from the real agent tools.

    Args:
        lang: UI language (``fr`` / ``de`` / ``en``) for the localized free-text.

    Returns:
        A JSON-serialisable mapping with posture KPIs (tools, allowed, gated by
        confirmation, real audited calls, denials, idle tools), the tool table,
        the selected-tool detail (guard contract + real audit usage) and the
        category / per-tool call distributions.
    """
    lang = _norm_lang(lang)
    now = datetime.now(UTC)
    settings = get_settings()
    policy: Policy = load_policy()
    scan = _scan_audit(settings.guard.audit_file, now)

    rows: list[dict[str, object]] = []
    for meta in _TOOLS:
        tp = policy.tool(meta["id"])
        stat = scan.stat(meta["id"])
        allowed = stat.decisions - stat.denials
        rows.append(
            {
                "id": meta["id"],
                "name": _tool_t(meta["id"], "name", lang),
                "type": meta["category"],
                "status": _status(tp, stat),
                "environment": _t("env_demo", lang),
                "owner": _t("owner_row", lang),
                "calls": _fmt_int(stat.decisions),
                "success_rate": (
                    f"{round(allowed / stat.decisions * 100)}%" if stat.decisions else "-"
                ),
                "response_time": "-",
                "last_sync": _rel(stat.last, now, lang),
                "detail": _detail(meta, tp, stat, now, lang),
            }
        )

    total_calls = sum(scan.stat(m["id"]).decisions for m in _TOOLS)
    total_denials = sum(scan.stat(m["id"]).denials for m in _TOOLS)
    allowed_tools = sum(1 for m in _TOOLS if policy.tool(m["id"]).allow)
    confirm_tools = sum(1 for m in _TOOLS if policy.tool(m["id"]).requires_confirmation)
    idle_tools = sum(1 for m in _TOOLS if scan.stat(m["id"]).decisions == 0)
    calls_per_tool = [scan.stat(m["id"]).decisions for m in _TOOLS]
    maxcalls_per_tool = [policy.tool(m["id"]).max_calls_per_turn for m in _TOOLS]

    kpis = [
        _kpi("tools", str(len(_TOOLS)), _t("ks_tools", lang), maxcalls_per_tool),
        _kpi("allowed", str(allowed_tools), _t("ks_allowed", lang), maxcalls_per_tool),
        _kpi("confirmation", str(confirm_tools), _t("ks_confirm", lang), maxcalls_per_tool),
        _kpi("calls", _fmt_int(total_calls), _t("ks_calls", lang), calls_per_tool),
        _kpi("blocked", _fmt_int(total_denials), _t("ks_blocked", lang), calls_per_tool),
        _kpi("idle", str(idle_tools), _t("ks_idle", lang), calls_per_tool),
    ]

    # Category distribution (donut).
    cat_counts: dict[str, int] = {}
    for m in _TOOLS:
        cat_counts[m["category"]] = cat_counts.get(m["category"], 0) + 1
    by_type = [
        {
            "key": cat,
            "count": n,
            "pct": round(n / len(_TOOLS) * 100),
            "color": _CATEGORY_COLOR.get(cat, "#64748b"),
        }
        for cat, n in sorted(cat_counts.items(), key=lambda kv: -kv[1])
    ]

    # Per-tool call distribution (replaces the fabricated by-environment panel).
    by_env = [
        {
            "key": m["id"],
            "label": _tool_t(m["id"], "name", lang),
            "value": _fmt_int(scan.stat(m["id"]).decisions),
            "pct": round(scan.stat(m["id"]).decisions / total_calls * 100) if total_calls else 0,
            "color": _CATEGORY_COLOR.get(m["category"], "#64748b"),
        }
        for m in sorted(_TOOLS, key=lambda x: -scan.stat(x["id"]).decisions)
    ]

    top_integrations = [
        {
            "name": _tool_t(m["id"], "name", lang),
            "value": scan.stat(m["id"]).decisions,
            "label": _fmt_int(scan.stat(m["id"]).decisions),
        }
        for m in sorted(_TOOLS, key=lambda x: -scan.stat(x["id"]).decisions)
    ]

    return {
        "generated_at": now.isoformat(),
        "total_integrations": len(_TOOLS),
        "page_size": len(_TOOLS),
        "kpis": kpis,
        "integrations": rows,
        "selected": rows[0]["detail"],
        "by_type": by_type,
        "by_type_total": len(_TOOLS),
        "by_env": by_env,
        "top_integrations": top_integrations,
        "footer": {"total": len(_TOOLS), "source": _t("f_source", lang)},
    }
