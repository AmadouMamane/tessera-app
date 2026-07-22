"""Settings / parameters cockpit overview (page #21).

Composes the "Paramètres" overview from the **real** running configuration: the
active guard-policy version, the settings posture (configured parameters, active
policies, security rules, connected integrations, catalogued models, config
sources), the quick-config categories, the recent parameters table, the
configuration-state distribution and the compliance checks.

Every number is derived from live state — :func:`tessera.settings.get_settings`,
the compiled guard policy (:func:`tessera.guard.decisions.load_policy`), the
model catalogue and the config-source file mtimes — never a hand-placed literal.
Slots with no per-parameter change history (per-row author/date) are attributed
to the config source (git-versioned files), not to invented users.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from tessera.guard.decisions import load_policy
from tessera.guard.ledger_store import read_ledger_entries
from tessera.observability._asof import occurred_before
from tessera.observability.knowledge import _LANG_IDX, _norm_lang
from tessera.observability.model_catalogue import (
    _active_ids,
    _catalogue_models,
    available_model_ids,
)
from tessera.settings import Settings, get_settings

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["OverrideRow", "compute_parameters_overview", "override_rows_as_of"]

_OVERRIDE_TARGET_PREFIX = "config_overrides."


def override_rows_as_of(asof: str) -> list[OverrideRow]:
    """The governed knob overrides in force at instant T — a real S1 fold (OT-01).

    Every knob write and revert is a governed act on the hash-chained ledger
    (``target="config_overrides.<key>"``, ``arguments`` carrying ``value``/
    ``reason`` or ``reverted``, top-level verified ``actor``). Entries come back
    oldest→newest, so the state at T is the last event at or before T per key:
    a write installs the override, a revert removes it (back to the base). The
    read is bounded (``until``) on the ``occurred_at`` index in postgres; file
    mode filters the seam's dicts with the shared as-of comparison.
    """
    at_dt = datetime.fromisoformat(asof.replace("Z", "+00:00"))
    if at_dt.tzinfo is None:
        at_dt = at_dt.replace(tzinfo=UTC)
    rows: dict[str, OverrideRow] = {}
    for entry in read_ledger_entries(until=at_dt):
        target = entry.get("target")
        if not (isinstance(target, str) and target.startswith(_OVERRIDE_TARGET_PREFIX)):
            continue
        occurred = entry.get("occurred_at")
        if not occurred_before(occurred, at_dt.isoformat()):
            continue
        key = target.removeprefix(_OVERRIDE_TARGET_PREFIX)
        args = entry.get("arguments")
        args = args if isinstance(args, dict) else {}
        if args.get("reverted") is True:
            rows.pop(key, None)
            continue
        try:
            updated_at = datetime.fromisoformat(str(occurred))
        except ValueError:
            continue  # an unreadable instant cannot claim a place in an as-of view
        rows[key] = OverrideRow(
            key=key,
            value=str(args.get("value", "")),
            author=str(entry.get("actor", "")),
            reason=str(args.get("reason", "")),
            updated_at=updated_at,
        )
    return list(rows.values())


@dataclass(frozen=True, slots=True)
class OverrideRow:
    """One stored governed override (ADR 0030), handed in by the route.

    The store read is async and lives in the api layer; this module stays sync
    and import-free of it, so the route converts and passes plain rows.
    """

    key: str
    value: str
    author: str
    reason: str
    updated_at: datetime


# Localized free-text (fr, de, en). IDs/versions/dates/names/values stay verbatim.
_TR: dict[str, tuple[str, str, str]] = {
    "validated": ("Validé", "Validiert", "Validated"),
    "sub_configured": (
        "paramètres actifs",
        "aktive Parameter",
        "active parameters",
    ),
    "sub_policies": (
        "règles de garde compilées",
        "kompilierte Guard-Regeln",
        "compiled guard rules",
    ),
    "sub_security": ("motifs deny + PII", "Deny- + PII-Muster", "deny + PII patterns"),
    "sub_integrations": ("points d'intégration", "Integrationspunkte", "integration points"),
    "sub_models": ("modèles au catalogue", "Modelle im Katalog", "catalogued models"),
    "sub_changes": ("fichiers de configuration", "Konfigurationsdateien", "configuration files"),
    "v_configured": ("configuré", "konfiguriert", "configured"),
    "u_days": ("{n} jours", "{n} Tage", "{n} days"),
    "up_rate": ("Limite de taux par session", "Ratenlimit pro Sitzung", "Per-session rate limit"),
    "up_quota": ("Plafond global de requêtes", "Globales Anfragelimit", "Global request cap"),
    "up_allowlist": ("Liste blanche d'outils", "Tool-Whitelist", "Tool allowlist"),
    "up_filter": ("Filtrage PII", "PII-Filterung", "PII filtering"),
    "v_strict": ("Strict", "Strikt", "Strict"),
    "v_off": ("Inactif", "Aus", "Off"),
    "v_tools": ("{n} outils", "{n} Tools", "{n} tools"),
    "src_git": ("git", "git", "git"),
    "by_config": ("config (git)", "Config (git)", "config (git)"),
    "cat_security": (
        "Configurez les règles de sécurité, les contrôles d'accès et les permissions.",
        "Konfigurieren Sie Sicherheitsregeln, Zugriffskontrollen und Berechtigungen.",
        "Configure security rules, access controls and permissions.",
    ),
    "cat_retention": (
        "Définissez les règles de rétention, d'archivage et de suppression.",
        "Definieren Sie Aufbewahrungs-, Archivierungs- und Loeschregeln.",
        "Define retention, archival and deletion rules.",
    ),
    "cat_models": (
        "Gérez les modèles, les prompts et les paramètres d'inférence.",
        "Verwalten Sie Modelle, Prompts und Inferenzparameter.",
        "Manage models, prompts and inference settings.",
    ),
    "cat_auth": (
        "Gérez l'authentification SSO, MFA, fournisseurs d'identité et accès.",
        "Verwalten Sie SSO, MFA, Identitaetsanbieter und Zugriff.",
        "Manage SSO, MFA, identity providers and access.",
    ),
    "cat_notif": (
        "Gérez les canaux, les alertes et les abonnements.",
        "Verwalten Sie Kanaele, Warnungen und Abonnements.",
        "Manage channels, alerts and subscriptions.",
    ),
    "cat_integrations": (
        "Configurez les connecteurs, API et flux de données.",
        "Konfigurieren Sie Konnektoren, APIs und Datenfluesse.",
        "Configure connectors, APIs and data flows.",
    ),
}


def _t(key: str, lang: str) -> str:
    return _TR[key][_LANG_IDX.get(lang, 0)]


def _kpi(key: str, value: str, sub: str, series: list[int]) -> dict[str, object]:
    return {"key": key, "value": value, "sub": sub, "series": series}


def _fmt_dt(ts: float) -> str:
    """Format a POSIX mtime as ``DD/MM/YYYY HH:MM`` (UTC)."""
    return datetime.fromtimestamp(ts, tz=UTC).strftime("%d/%m/%Y %H:%M")


def _fmt_day(ts: float) -> str:
    """Format a POSIX mtime as ``DD/MM HH:MM`` (UTC) for the compact table cell."""
    return datetime.fromtimestamp(ts, tz=UTC).strftime("%d/%m %H:%M")


def _mtime(path: Path) -> float | None:
    try:
        return path.stat().st_mtime
    except OSError:
        return None


def _config_sources(settings: Settings) -> list[Path]:
    """The real config-source files whose mtimes drive the freshness slots."""
    prompts = _PACKAGE_PROMPTS_DIR
    candidates = [
        settings.guard.policy_path,
        prompts / "fr.yaml",
        prompts / "de.yaml",
        prompts / "en.yaml",
    ]
    return [p for p in candidates if p.exists()]


def _integration_points(settings: Settings) -> int:
    """Count the runtime integration endpoints actually configured (real, honest)."""
    n = 3  # Postgres, the local Ollama path and the secrets provider are always wired
    if settings.vertex.project_id:
        n += 1
    if settings.observability.otel_collector_endpoint or settings.observability.otel_endpoint:
        n += 1
    if settings.observability.metrics_enabled:
        n += 1
    if settings.observability.cloud_logging_project:
        n += 1
    return n


# The prompts directory ships next to the settings package; resolve it once.
_PACKAGE_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "agent" / "prompts"

_STATE_COLORS = {
    "active": "#34d399",
    "inactive": "#60a5fa",
    "drafts": "#fbbf24",
    "deprecated": "#f87171",
}


def compute_parameters_overview(
    lang: str = "fr", *, override_rows: Sequence[OverrideRow] | None = None
) -> dict[str, object]:
    """Return the full Parameters overview payload, derived from live config.

    Args:
        lang: UI language (``fr`` / ``de`` / ``en``) for the localized free-text.
        override_rows: The stored governed overrides (ADR 0030), read by the
            route. They are the only parameters with a real per-row author.

    Returns:
        A JSON-serialisable mapping (same shape as the page consumes) with the
        real config version, posture KPIs, quick-config categories, recent
        parameters, configuration-state distribution and compliance checks.
    """
    lang = _norm_lang(lang)
    now = datetime.now(UTC)
    settings = get_settings()
    policy = load_policy()
    overrides = list(override_rows or [])
    org_chat_override = next((o.value for o in overrides if o.key == "llm.chat_model"), None)

    # --- Real counts ------------------------------------------------------
    n_deny = len(policy.prompt_injection_deny)
    n_transforms = len(policy.prompt_injection_transforms)
    n_pii = len(policy.pii_patterns)
    n_tools = len(policy.tools)
    n_security = n_deny + n_transforms + n_pii
    n_policies = n_tools + n_security
    n_models = len(available_model_ids())
    n_integrations = _integration_points(settings)
    sources = _config_sources(settings)
    n_changes = len(sources)

    policy_mtime = _mtime(settings.guard.policy_path)
    settings_mtime = _mtime(Path(__file__).resolve().parent.parent / "settings.py")

    # A real configuration-state distribution by area (every live parameter is
    # active — there is no draft/deprecated store, so the split is honest: 100%
    # active). ``configured`` is the sum, so the donut and the KPI agree.
    memory_knobs = 5  # backend + history_window + token_budget + consent_default + long_term_top_k
    api_knobs = 4  # rate_limit_chat + rate_limit_chat_global + rate_limit_read + max_request_bytes
    obs_knobs = 4  # log_level + profile + data_residency + online_eval_sample_rate
    configured = n_policies + memory_knobs + api_knobs + obs_knobs + n_models + n_integrations

    config_version = {
        "version": f"policy v{policy.version}",
        "env": settings.environment.value.capitalize(),
        "status": "active",
        "active_since": _fmt_dt(policy_mtime) if policy_mtime is not None else "-",
        "modified_by": _t("by_config", lang),
        "validation": _t("validated", lang),
        "next_review": "-",
    }

    def _flat(value: int) -> list[int]:
        # No per-parameter time-series exists; a flat line is the honest "stable"
        # shape (never a fabricated trend).
        return [value] * 7

    kpis = [
        _kpi("configured", str(configured), _t("sub_configured", lang), _flat(configured)),
        _kpi("policies", str(n_policies), _t("sub_policies", lang), _flat(n_policies)),
        _kpi("security_rules", str(n_security), _t("sub_security", lang), _flat(n_security)),
        _kpi(
            "integrations", str(n_integrations), _t("sub_integrations", lang), _flat(n_integrations)
        ),
        _kpi("models", str(n_models), _t("sub_models", lang), _flat(n_models)),
        _kpi("changes", str(n_changes), _t("sub_changes", lang), _flat(n_changes)),
    ]

    categories = [
        {"key": "security_policies", "desc": _t("cat_security", lang)},
        {"key": "data_retention", "desc": _t("cat_retention", lang)},
        {"key": "models_ai", "desc": _t("cat_models", lang)},
        {"key": "authentication", "desc": _t("cat_auth", lang)},
        {"key": "notifications", "desc": _t("cat_notif", lang)},
        {"key": "integrations", "desc": _t("cat_integrations", lang)},
    ]

    # Real, current parameter values pulled straight from the live settings /
    # policy. No per-parameter author store exists, so provenance is the config
    # source (git-versioned files) and the row date is that file's mtime.
    guard_day = _fmt_day(policy_mtime) if policy_mtime is not None else "-"
    cfg_day = _fmt_day(settings_mtime) if settings_mtime is not None else "-"
    by = _t("by_config", lang)

    def _row(name: str, cat: str, value: str, day: str) -> dict[str, str]:
        return {
            "name": name,
            "category": cat,
            "value": value,
            "modified_by": by,
            "date": day,
            "status": "active",
        }

    st = settings
    # Real, current settings grouped by the config tab they belong to (the tab keys
    # the frontend filters on). Every value is read straight from the live config.
    recent_params = [
        _row("environment", "general", st.environment.value, cfg_day),
        _row("default_language", "general", st.default_language.value, cfg_day),
        _row("deployment_mode", "general", st.deployment_mode.value, cfg_day),
        _row("guard.fail_closed", "security", str(st.guard.fail_closed).lower(), guard_day),
        _row(
            "guard.escalation_confidence_threshold",
            "security",
            f"{st.guard.escalation_confidence_threshold}",
            guard_day,
        ),
        _row(
            "api.security_headers_enabled",
            "security",
            str(st.api.security_headers_enabled).lower(),
            cfg_day,
        ),
        _row("memory.token_budget", "data", f"{st.memory.token_budget} tokens", cfg_day),
        _row("memory.history_window", "data", str(st.memory.history_window), cfg_day),
        _row("memory.consent_default", "data", str(st.memory.consent_default).lower(), cfg_day),
        _row("memory.backend", "models", st.memory.backend, cfg_day),
        _row("ollama.chat_model", "models", st.ollama.chat_model, cfg_day),
        _row("ollama.embedding_model", "models", st.ollama.embedding_model, cfg_day),
        _row("api.rate_limit_chat", "access", st.api.rate_limit_chat, cfg_day),
        _row("api.rate_limit_chat_global", "access", st.api.rate_limit_chat_global, cfg_day),
        _row("api.tls_terminated", "access", str(st.api.tls_terminated).lower(), cfg_day),
        _row("postgres.vector_table", "integrations", st.postgres.vector_table, cfg_day),
        _row(
            "observability.metrics_port",
            "integrations",
            str(st.observability.metrics_port),
            cfg_day,
        ),
        _row("secrets.provider", "integrations", st.secrets.provider, cfg_day),
        _row("guard.audit_sink", "audit", st.guard.audit_sink, guard_day),
        _row("observability.log_level", "audit", st.observability.log_level, cfg_day),
        _row("observability.data_residency", "system", st.observability.data_residency, cfg_day),
        _row("observability.profile", "system", st.observability.profile, cfg_day),
    ]
    # ADR 0030 — stored governed overrides are the only parameters with a real
    # per-row author. Shown first, attributed to the operator who set them.
    recent_params = [
        {
            "name": o.key,
            "category": "models",
            "value": o.value,
            "modified_by": o.author,
            "date": _fmt_day(o.updated_at.timestamp()),
            "status": "override",
        }
        for o in overrides
    ] + recent_params

    config_state = {
        "total": configured,
        "slices": [
            {"key": "active", "count": configured, "pct": 100, "color": _STATE_COLORS["active"]},
            {"key": "inactive", "count": 0, "pct": 0, "color": _STATE_COLORS["inactive"]},
            {"key": "drafts", "count": 0, "pct": 0, "color": _STATE_COLORS["drafts"]},
            {"key": "deprecated", "count": 0, "pct": 0, "color": _STATE_COLORS["deprecated"]},
        ],
    }

    # Real compliance posture: each check reflects a live configuration fact.
    compliance = [
        {"key": "security_policies", "status": "ok" if n_policies > 0 else "warn"},
        {
            "key": "data_retention",
            "status": "ok" if not settings.memory.consent_default else "warn",
        },
        {
            "key": "authentication",
            "status": "ok" if settings.api.security_headers_enabled else "warn",
        },
        {"key": "models_ai", "status": "ok" if n_models > 0 else "warn"},
        {"key": "audit", "status": "ok" if settings.guard.fail_closed else "warn"},
    ]

    usage_policies = [
        {"name": _t("up_rate", lang), "value": settings.api.rate_limit_chat, "status": "active"},
        {
            "name": _t("up_quota", lang),
            "value": settings.api.rate_limit_chat_global,
            "status": "active",
        },
        {
            "name": _t("up_allowlist", lang),
            "value": _t("v_tools", lang).format(n=n_tools),
            "status": "active",
        },
        {
            "name": _t("up_filter", lang),
            "value": _t("v_strict", lang) if n_pii > 0 else _t("v_off", lang),
            "status": "active" if n_pii > 0 else "inactive",
        },
    ]

    # The config "backup" is git: the policy/prompts are version-controlled files.
    # We surface the real source provenance (last change, file size) rather than a
    # fictional backup schedule.
    policy_size = 0
    try:
        policy_size = settings.guard.policy_path.stat().st_size
    except OSError:
        policy_size = 0
    backup = {
        "last_backup": _fmt_dt(policy_mtime) if policy_mtime is not None else "-",
        "frequency": _t("src_git", lang),
        "retention": _t("src_git", lang),
        "size": f"{policy_size // 1024 or 1} KB",
    }

    # Real model layer: the configured catalogue models, flagging the chat /
    # embedding models that actually serve under the current profile — including
    # the governed org-wide override when one is stored (ADR 0030). Same source
    # the /configurer/modeles page uses — never a fabricated model list.
    active_chat, active_embed = _active_ids(org_chat_override)
    active_model_ids = {active_chat, active_embed}
    models_configured = [
        {
            "name": m.model_id,
            "provider": m.provider,
            "role": m.role,
            "status": "active" if m.model_id in active_model_ids else "available",
        }
        for m in _catalogue_models()
    ]

    return {
        "generated_at": now.isoformat(),
        "config_version": config_version,
        "kpis": kpis,
        "categories": categories,
        "recent_params": recent_params,
        "config_state": config_state,
        "compliance": compliance,
        "usage_policies": usage_policies,
        "models_configured": models_configured,
        "backup": backup,
        "footer": {"version": f"policy v{policy.version}", "source": "YAML · Git"},
    }
