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
"environment" reads **Démo** and there is no fabricated latency/cost. Read-only by
design (tools + policy are code/PR-owned), like Prompts: the functional axis is
wired search / filter / sort / row-select / nav + export, not a fake mutation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from tessera.guard.decisions import Policy, ToolPolicy, load_policy
from tessera.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

__all__ = ["compute_integrations_overview"]

_MINUTE = 60.0
_HOUR = 3600.0
_DAY = 86_400.0

# Real tool metadata: the banking system each integrates with, a category (the
# filter/donut axis) and a one-line description. Names mirror the modules in
# tessera/agent/tools/. ASCII-only source (accents in literals are fine).
_TOOLS: list[dict[str, str]] = [
    {
        "id": "account_balance",
        "name": "Solde de compte",
        "system": "Core banking",
        "category": "lecture",
        "request": "AccountBalanceRequest",
        "response": "AccountBalance",
        "description": "Solde disponible du compte (lecture core-banking).",
    },
    {
        "id": "transaction_search",
        "name": "Recherche de transactions",
        "system": "Registre des transactions",
        "category": "lecture",
        "request": "TransactionSearchRequest",
        "response": "TransactionSearchResult",
        "description": "Recherche dans l'historique des transactions du client.",
    },
    {
        "id": "loan_simulate",
        "name": "Simulation de crédit",
        "system": "Moteur de crédit",
        "category": "simulation",
        "request": "LoanSimulationRequest",
        "response": "LoanSimulation",
        "description": "Simulation d'un crédit : mensualités, TAEG, coût total.",
    },
    {
        "id": "card_block",
        "name": "Blocage de carte",
        "system": "Gestion des cartes",
        "category": "action",
        "request": "CardBlockRequest",
        "response": "CardBlock",
        "description": "Opposition / blocage d'une carte - action sensible, confirmée.",
    },
    {
        "id": "ticket_escalate",
        "name": "Escalade ticket",
        "system": "Ticketing / CRM",
        "category": "escalade",
        "request": "TicketRequest",
        "response": "Ticket",
        "description": "Escalade vers un agent humain (création de ticket).",
    },
]

_CATEGORY_COLOR = {
    "lecture": "#60a5fa",
    "simulation": "#a78bfa",
    "action": "#f87171",
    "escalade": "#fbbf24",
}


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
    """Aggregate per-tool decision stats from the guard audit log."""
    scan = _Scan()
    if not path.exists():
        return scan
    with path.open("r", encoding="utf-8") as fp:
        for raw in fp:
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                obj = json.loads(stripped)
            except json.JSONDecodeError:
                continue
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


def _rel(when: datetime | None, now: datetime) -> str:
    if when is None:
        return "-"
    secs = (now - when).total_seconds()
    if secs < _MINUTE:
        return "à l'instant"
    if secs < _HOUR:
        return f"il y a {int(secs // _MINUTE)} min"
    if secs < _DAY:
        return f"il y a {int(secs // _HOUR)} h"
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
    meta: dict[str, str], tp: ToolPolicy, stat: _ToolStat, now: datetime
) -> dict[str, object]:
    allowed = stat.decisions - stat.denials
    rate = f"{round(allowed / stat.decisions * 100)}%" if stat.decisions else "-"
    return {
        "id": meta["id"],
        "name": meta["name"],
        "status": _status(tp, stat),
        "response_time": "-",  # demo stubs: not instrumented
        "success_rate": rate,
        "last_sync": _rel(stat.last, now),
        "description": meta["description"],
        "owner": "Agent Tessera",
        "environment": "Démo (implémentation simulée)",
        "region": "local",
        "criticality": _criticality(tp, meta["category"]),
        # Usage = real audit counts (relabelled read/write/cost slots).
        "usage": {
            "read": {"value": _fmt_int(stat.decisions), "delta": f"{stat.c24} sur 24h"},
            "write": {"value": _fmt_int(stat.denials), "delta": "refus journalisés"},
            "cost": {"value": str(tp.max_calls_per_turn), "delta": "par tour"},
        },
        # Config = the real guard contract.
        "config_rows": [
            {"label": "Système cible", "value": meta["system"]},
            {"label": "Schéma d'entrée", "value": meta["request"]},
            {"label": "Schéma de sortie", "value": meta["response"]},
            {"label": "Autorisé", "value": "Oui" if tp.allow else "Non"},
            {
                "label": "Confirmation requise",
                "value": "Oui" if tp.requires_confirmation else "Non",
            },
            {"label": "Appels max / tour", "value": str(tp.max_calls_per_turn)},
            {"label": "Arguments contrôlés", "value": str(len(tp.arguments))},
        ],
        # Security = how the firewall enforces it.
        "security_rows": [
            {"label": "Pare-feu", "value": "mcp-firewall"},
            {"label": "Règle de politique", "value": f"tool.{meta['id']}.allow"},
            {"label": "Validation des arguments", "value": "Pydantic strict (extra=forbid)"},
            {"label": "Sur violation", "value": "Refus + journalisé"},
            {"label": "Refus journalisés", "value": _fmt_int(stat.denials)},
        ],
    }


def compute_integrations_overview() -> dict[str, object]:
    """Return the full Integrations overview, built from the real agent tools.

    Returns:
        A JSON-serialisable mapping with posture KPIs (tools, allowed, gated by
        confirmation, real audited calls, denials, idle tools), the tool table,
        the selected-tool detail (guard contract + real audit usage) and the
        category / per-tool call distributions.
    """
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
                "name": meta["name"],
                "type": meta["category"],
                "status": _status(tp, stat),
                "environment": "Démo",
                "owner": "Agent",
                "calls": _fmt_int(stat.decisions),
                "success_rate": (
                    f"{round(allowed / stat.decisions * 100)}%" if stat.decisions else "-"
                ),
                "response_time": "-",
                "last_sync": _rel(stat.last, now),
                "detail": _detail(meta, tp, stat, now),
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
        _kpi("tools", str(len(_TOOLS)), "outils de l'agent", maxcalls_per_tool),
        _kpi("allowed", str(allowed_tools), "autorises par la politique", maxcalls_per_tool),
        _kpi("confirmation", str(confirm_tools), "confirmation requise", maxcalls_per_tool),
        _kpi("calls", _fmt_int(total_calls), "appels journalises", calls_per_tool),
        _kpi("blocked", _fmt_int(total_denials), "refus journalises", calls_per_tool),
        _kpi("idle", str(idle_tools), "jamais sollicites", calls_per_tool),
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
            "label": m["name"],
            "value": _fmt_int(scan.stat(m["id"]).decisions),
            "pct": round(scan.stat(m["id"]).decisions / total_calls * 100) if total_calls else 0,
            "color": _CATEGORY_COLOR.get(m["category"], "#64748b"),
        }
        for m in sorted(_TOOLS, key=lambda x: -scan.stat(x["id"]).decisions)
    ]

    top_integrations = [
        {
            "name": m["name"],
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
        "footer": {"total": len(_TOOLS), "source": "agent/tools + policy.yaml + journal d'audit"},
    }
