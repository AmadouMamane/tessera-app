"""CONFIGURER platform guardrail catalogue (configurer/garde-fous).

A first-class catalogue block, like the model catalogue and Sources & memoire:
the **guardrail profiles** agents bind (``standard`` / ``strict`` …), each shown
with the real composition of the shared guard policy, the audit posture, and the
consuming agents + re-gate blast radius. Distinct from the per-agent Garde-fous
page (rule state / toggles): this is the reusable-block catalogue view.

Real sources (nothing invented):
  * ``tessera.guard.decisions.load_policy`` over ``guard/policy.yaml`` — the deny
    patterns, PII patterns, transforms and per-tool rules (the composition);
  * ``tessera.guard.audit.verify_audit_chain`` — logged-decision count + chain
    integrity (the journalisation posture);
  * ``catalogue_consumers("guardrails")`` — the binding blocks + consuming agents.

Free-text is localized (fr/de/en); enum keys (status) stay stable.
"""

from __future__ import annotations

from tessera.guard.decisions import Policy, load_policy
from tessera.guard.ledger_store import verify_active_ledger
from tessera.observability.knowledge import _LANG_IDX, _norm_lang

__all__ = ["available_guardrail_ids", "build_guardrail_catalogue"]

_LANG = _LANG_IDX

_TR: dict[str, tuple[str, str, str]] = {
    "subtitle": (
        "Les profils de garde-fous que les agents lient (policy + audit réels).",
        "Die Guardrail-Profile, die Agenten binden (reale Policy + Audit).",
        "The guardrail profiles agents bind (real policy + audit).",
    ),
    "kpi_blocks": ("Profils au catalogue", "Profile im Katalog", "Catalogued profiles"),
    "kpi_deny": ("Motifs de blocage", "Blockiermuster", "Deny patterns"),
    "kpi_pii": ("Motifs PII", "PII-Muster", "PII patterns"),
    "kpi_tools": ("Outils encadrés", "Eingeschraenkte Tools", "Guarded tools"),
    "kpi_version": ("Version policy", "Policy-Version", "Policy version"),
    "kpi_decisions": (
        "Décisions journalisées",
        "Protokollierte Entscheidungen",
        "Logged decisions",
    ),
    "col_block": ("Profil", "Profil", "Profile"),
    "col_scope": ("Portée", "Geltungsbereich", "Scope"),
    "col_composition": ("Composition", "Zusammensetzung", "Composition"),
    "col_status": ("Statut", "Status", "Status"),
    "col_usedby": ("Utilisé par", "Verwendet von", "Used by"),
    "st_active": ("Actif", "Aktiv", "Active"),
    "scope_shared": ("Policy partagée", "Geteilte Policy", "Shared policy"),
    "comp_value": (
        "{deny} blocages / {pii} PII / {tools} outils",
        "{deny} Block. / {pii} PII / {tools} Tools",
        "{deny} deny / {pii} PII / {tools} tools",
    ),
    "sec_composition": ("Composition", "Zusammensetzung", "Composition"),
    "sec_coverage": ("Couverture outils", "Tool-Abdeckung", "Tool coverage"),
    "sec_logging": ("Journalisation", "Protokollierung", "Logging"),
    "l_deny": (
        "Motifs de blocage (prompt injection)",
        "Blockiermuster (Prompt Injection)",
        "Deny patterns (prompt injection)",
    ),
    "l_transforms": ("Transformations", "Transformationen", "Transforms"),
    "l_pii": ("Motifs PII (rédaction)", "PII-Muster (Redaktion)", "PII patterns (redaction)"),
    "l_tools": ("Outils encadrés", "Eingeschraenkte Tools", "Guarded tools"),
    "l_version": ("Version policy", "Policy-Version", "Policy version"),
    "l_source": ("Source de config", "Konfigurationsquelle", "Config source"),
    "l_tools_allowed": ("Outils autorisés", "Erlaubte Tools", "Allowed tools"),
    "l_tools_confirm": (
        "Confirmation requise",
        "Bestaetigung erforderlich",
        "Confirmation required",
    ),
    "l_tools_denied": ("Outils refusés", "Abgelehnte Tools", "Denied tools"),
    "l_decisions": ("Décisions journalisées", "Protokollierte Entscheidungen", "Logged decisions"),
    "l_chain": ("Chaîne d'audit", "Audit-Kette", "Audit chain"),
    "chain_ok": ("Intacte", "Intakt", "Intact"),
    "chain_broken": ("Rompue (entrée {n})", "Gebrochen (Eintrag {n})", "Broken (entry {n})"),
    "ub_title": ("Utilisé par", "Verwendet von", "Used by"),
    "ub_none": ("Aucun agent", "Kein Agent", "No agent"),
    "ub_regate": ("{n} à re-valider", "{n} neu zu validieren", "{n} to re-validate"),
    "ub_revalidate": (
        "Re-valider les consommateurs",
        "Konsumenten neu validieren",
        "Re-validate consumers",
    ),
    "ub_note": (
        "Durcir un profil de garde-fous re-gate ses agents consommateurs "
        "(define -> consommateurs -> re-valider). La pastille = verdict eval-gate actuel.",
        "Ein Guardrail-Profil zu verschaerfen re-gated seine Agenten. Der Punkt = "
        "aktuelles Eval-Gate-Verdikt.",
        "Hardening a guardrail profile re-gates its consuming agents "
        "(define -> consumers -> re-validate). The dot = current eval-gate verdict.",
    ),
    "note": (
        "Catalogue dérivé de la policy guard réelle (guard/policy.yaml) et du "
        "journal d'audit. La composition est partagée par tous les profils.",
        "Katalog aus der realen Guard-Policy (guard/policy.yaml) + Audit-Log. Die "
        "Zusammensetzung ist fuer alle Profile gleich.",
        "Catalogue derived from the real guard policy (guard/policy.yaml) + audit "
        "log. The composition is shared across profiles.",
    ),
    "src_policy": (
        "guard/policy.yaml (Git / ingestion)",
        "guard/policy.yaml (Git / Ingestion)",
        "guard/policy.yaml (Git / ingestion)",
    ),
}


def _t(key: str, lang: str) -> str:
    return _TR[key][_LANG.get(lang, 0)]


def _fmt_int(value: int) -> str:
    return f"{value:,}".replace(",", " ")


class _Composition:
    """Real counts read once from the shared guard policy."""

    __slots__ = (
        "confirm",
        "deny",
        "denied",
        "pii",
        "tools",
        "tools_allowed",
        "transforms",
        "version",
    )

    def __init__(self, policy: Policy) -> None:
        self.version = policy.version
        self.deny = len(policy.prompt_injection_deny)
        self.transforms = len(policy.prompt_injection_transforms)
        self.pii = len(policy.pii_patterns)
        self.tools = len(policy.tools)
        self.tools_allowed = sum(1 for t in policy.tools.values() if t.allow)
        self.confirm = sum(1 for t in policy.tools.values() if t.requires_confirmation)
        self.denied = sum(1 for t in policy.tools.values() if not t.allow)


def available_guardrail_ids() -> set[str]:
    """Known guardrail block ids (from the registry bindings)."""
    return {str(item.get("item", "")) for item in _consumer_items("all")}


def _consumer_items(agent_scope: str) -> list[dict[str, object]]:
    try:
        from tessera.observability.catalogue_consumers import catalogue_consumers

        data = catalogue_consumers("guardrails", agent_scope=agent_scope)
    except Exception:  # registry/release unavailable
        return []
    items = data.get("items")
    return [i for i in items if isinstance(i, dict)] if isinstance(items, list) else []


def _consumers_of(item: dict[str, object]) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    raw = item.get("consumers")
    for con in raw if isinstance(raw, list) else []:
        if not isinstance(con, dict):
            continue
        rel_raw = con.get("release")
        rel = rel_raw if isinstance(rel_raw, dict) else {}
        out.append(
            {
                "agent_id": str(con.get("agent_id", "")),
                "name": str(con.get("name", con.get("agent_id", ""))),
                "tone": str(rel.get("verdict_tone", "muted")),
                "label": str(rel.get("verdict_label", "")),
                "passed": bool(rel.get("passed", False)),
            }
        )
    return out


def build_guardrail_catalogue(lang: str = "fr", *, agent_scope: str = "all") -> dict[str, object]:
    """Assemble the platform guardrail-catalogue payload from real policy + audit."""
    lang = _norm_lang(lang)
    comp = _Composition(load_policy())
    chain = verify_active_ledger()
    items = _consumer_items(agent_scope)

    rows = [_block_row(item, comp, chain, lang) for item in items]
    return {
        "subtitle": _t("subtitle", lang),
        "kpis": _kpis(rows, comp, chain, lang),
        "columns": [
            _t("col_block", lang),
            _t("col_scope", lang),
            _t("col_composition", lang),
            _t("col_status", lang),
            _t("col_usedby", lang),
        ],
        "blocks": rows,
        "note": _t("note", lang),
    }


def _block_row(
    item: dict[str, object], comp: _Composition, chain: object, lang: str
) -> dict[str, object]:
    block_id = str(item.get("item", ""))
    consumers = _consumers_of(item)
    regate = sum(1 for c in consumers if not c.get("passed", False))
    composition = _t("comp_value", lang).format(deny=comp.deny, pii=comp.pii, tools=comp.tools)
    return {
        "id": block_id,
        "name": block_id,
        "scope": _t("scope_shared", lang),
        "composition": composition,
        "status": "active",
        "status_label": _t("st_active", lang),
        "used_by": str(len(consumers)),
        "used_by_count": len(consumers),
        "consumer_ids": [str(c["agent_id"]) for c in consumers],
        "detail": _block_detail(block_id, comp, chain, consumers, regate, lang),
    }


def _chain_label(chain: object, lang: str) -> str:
    verified = bool(getattr(chain, "verified", True))
    if verified:
        return _t("chain_ok", lang)
    broken = getattr(chain, "broken_at", None)
    return _t("chain_broken", lang).format(n=broken if broken is not None else "?")


def _block_detail(
    block_id: str,
    comp: _Composition,
    chain: object,
    consumers: list[dict[str, object]],
    regate: int,
    lang: str,
) -> dict[str, object]:
    length = int(getattr(chain, "length", 0))
    return {
        "id": block_id,
        "name": block_id,
        "status": "active",
        "sections": [
            {
                "key": "composition",
                "title": _t("sec_composition", lang),
                "rows": [
                    {"label": _t("l_deny", lang), "value": str(comp.deny)},
                    {"label": _t("l_transforms", lang), "value": str(comp.transforms)},
                    {"label": _t("l_pii", lang), "value": str(comp.pii)},
                    {"label": _t("l_tools", lang), "value": str(comp.tools)},
                    {"label": _t("l_version", lang), "value": f"v{comp.version}"},
                    {"label": _t("l_source", lang), "value": _t("src_policy", lang)},
                ],
            },
            {
                "key": "coverage",
                "title": _t("sec_coverage", lang),
                "rows": [
                    {"label": _t("l_tools_allowed", lang), "value": str(comp.tools_allowed)},
                    {"label": _t("l_tools_confirm", lang), "value": str(comp.confirm)},
                    {"label": _t("l_tools_denied", lang), "value": str(comp.denied)},
                ],
            },
            {
                "key": "logging",
                "title": _t("sec_logging", lang),
                "rows": [
                    {"label": _t("l_decisions", lang), "value": _fmt_int(length)},
                    {"label": _t("l_chain", lang), "value": _chain_label(chain, lang)},
                ],
            },
        ],
        "consumers": {
            "title": _t("ub_title", lang),
            "count": len(consumers),
            "regate_count": regate,
            "regate_label": _t("ub_regate", lang).format(n=regate) if regate else "",
            "revalidate_label": _t("ub_revalidate", lang),
            "empty": _t("ub_none", lang),
            "note": _t("ub_note", lang),
            "items": consumers,
        },
    }


def _kpi(key: str, label: str, value: str) -> dict[str, object]:
    return {"key": key, "label": label, "value": value}


def _kpis(
    rows: list[dict[str, object]], comp: _Composition, chain: object, lang: str
) -> list[dict[str, object]]:
    length = int(getattr(chain, "length", 0))
    return [
        _kpi("blocks", _t("kpi_blocks", lang), str(len(rows))),
        _kpi("deny", _t("kpi_deny", lang), str(comp.deny)),
        _kpi("pii", _t("kpi_pii", lang), str(comp.pii)),
        _kpi("tools", _t("kpi_tools", lang), str(comp.tools)),
        _kpi("version", _t("kpi_version", lang), f"v{comp.version}"),
        _kpi("decisions", _t("kpi_decisions", lang), _fmt_int(length)),
    ]
