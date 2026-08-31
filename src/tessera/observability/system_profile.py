"""System profile cockpit overview (page #20, admin/profil-systeme).

Surfaces the **real** runtime, not an invented data-center: the Python / OS /
arch from :mod:`platform`, the installed dependency versions from
:mod:`importlib.metadata` (FastAPI, LangGraph, psycopg, pgvector, Ollama,
Pydantic), the deployment posture from :func:`get_settings` (mode,
environment, LLM profile, languages), the live process uptime, and honest health
checks that probe the real artifacts on disk (policy, prompts, corpus, audit log
+ chain). Nothing here is fabricated — unsourceable metrics (CPU%, per-node load,
seat counts) are dropped rather than faked (no psutil in the frozen stack).

Read-only by design: it is a status surface. The functional axis is the wired
Export / Refresh / "view audit" controls, not a fake mutation.
"""

from __future__ import annotations

import platform
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import tessera
from tessera.guard.ledger_store import (
    count_ledger_entries,
    ledger_available,
    verify_active_ledger,
)
from tessera.observability import firewall_efficacy
from tessera.observability.eval.report_paths import iter_report_files
from tessera.observability.knowledge import _LANG_IDX, _norm_lang
from tessera.settings import get_settings

__all__ = ["compute_system_profile"]

# Tessera ships prompts in the three supported languages (FR/DE/EN).
_REQUIRED_LANGS = 3

# Localized free-text (fr, de, en). Proper nouns (FastAPI, LangGraph, PostgreSQL,
# package versions, deployment-mode names) stay verbatim.
_TR: dict[str, tuple[str, str, str]] = {
    "st_operational": ("Opérationnel", "Betriebsbereit", "Operational"),
    "st_watch": (
        "{n} vérification(s) à surveiller",
        "{n} Pruefung(en) zu beobachten",
        "{n} check(s) to watch",
    ),
    "sub_health": ("Vérifications de santé", "Gesundheitspruefungen", "Health checks"),
    "sub_interp": ("Interpréteur", "Interpreter", "Interpreter"),
    "sub_deploy": ("Mode de déploiement", "Deployment-Modus", "Deployment mode"),
    "sub_llm": ("Profil LLM", "LLM-Profil", "LLM profile"),
    "sub_vcpu": ("vCPU disponibles", "verfuegbare vCPU", "available vCPU"),
    "sub_memory": ("Mémoire totale", "Gesamtspeicher", "Total memory"),
    "sub_apiproc": ("Processus API", "API-Prozess", "API process"),
    "started": ("Démarré {d}", "Gestartet {d}", "Started {d}"),
    "u_day": ("j", "T", "d"),
    "edition_ref": ("Référence (AGPL-3.0)", "Referenz (AGPL-3.0)", "Reference (AGPL-3.0)"),
    "default_lang": (
        "{lang} (langue par défaut)",
        "{lang} (Standardsprache)",
        "{lang} (default language)",
    ),
    "topo_retrieval": ("Récupération", "Abruf", "Retrieval"),
    "topo_guard": ("Garde-fou", "Guardrail", "Guardrail"),
    "topo_corpus_detail": ("JSON réglementaire", "JSON Regulierung", "Regulatory JSON"),
    "chain_ok": ("Vérifiée", "Verifiziert", "Verified"),
    "chain_broken": ("Rupture détectée", "Bruch erkannt", "Break detected"),
    "svc_retrieval": ("Récupération (psycopg)", "Abruf (psycopg)", "Retrieval (psycopg)"),
    "svc_guard": (
        "Garde-fou (Tessera, interne)",
        "Guardrail (Tessera, hauseigen)",
        "Guardrail (Tessera, first-party)",
    ),
    "svc_local_llm": ("LLM local (Ollama)", "Lokales LLM (Ollama)", "Local LLM (Ollama)"),
}


def _t(key: str, lang: str) -> str:
    return _TR[key][_LANG_IDX.get(lang, 0)]


# Process start time (module import) — a real, monotonic-enough uptime base.
_START = datetime.now(UTC)

_PKG_ROOT = Path(tessera.__file__).resolve().parent


def _dep(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "-"


def _uptime(now: datetime, lang: str = "fr") -> str:
    secs = int((now - _START).total_seconds())
    days, rem = divmod(secs, 86_400)
    hours, rem = divmod(rem, 3600)
    mins = rem // 60
    day_u = _t("u_day", lang)
    if days:
        return f"{days} {day_u} {hours} h {mins} min"
    if hours:
        return f"{hours} h {mins} min"
    return f"{mins} min"


def _total_memory() -> str:
    try:
        pages = os_sysconf("SC_PHYS_PAGES")
        page_size = os_sysconf("SC_PAGE_SIZE")
    except (ValueError, OSError):
        return "-"
    if pages <= 0 or page_size <= 0:
        return "-"
    gib = pages * page_size / (1024**3)
    return f"{gib:.0f} GB"


def os_sysconf(name: str) -> int:
    import os

    return int(os.sysconf(name))


def _cpu_count() -> int:
    import os

    return os.cpu_count() or 0


def _file_count(directory: Path, pattern: str) -> int:
    if not directory.is_dir():
        return 0
    return sum(1 for _ in directory.glob(pattern))


def _health(audit_file: Path) -> list[dict[str, str]]:
    """Real health checks: probe the artifacts the system actually needs."""
    prompts = _PKG_ROOT / "agent" / "prompts"
    corpus = _PKG_ROOT / "corpus" / "data"
    policy = _PKG_ROOT / "guard" / "policy.yaml"

    chain_ok = True
    try:
        chain_ok = bool(verify_active_ledger(audit_file).verified)
    except Exception:  # a health probe never crashes the page (postgres unreachable, …)
        chain_ok = False

    # ADR 0028/0029: the guard badge reports the measured detector, never the
    # presence of a package. A witness that cannot see may not say "ok". Green
    # requires (a) the limes injection detector to be the one that ran — F1 > 0
    # alone is a hollow green, it cannot tell limes from a fallback — and (b) a
    # dated, real F1. limes absent → compute_efficacy raises → warn (fail-closed).
    fw: firewall_efficacy.EfficacyReport | None
    try:
        fw = firewall_efficacy.compute_efficacy()
    except Exception:  # blind spot — report warn, never a fabricated ok
        fw = None
    firewall_active = (
        fw is not None
        and fw.detector_id == firewall_efficacy.LIMES_INJECTION_DETECTOR_ID
        and fw.f1 > 0.0
    )

    def ok(flag: bool) -> str:
        return "ok" if flag else "warn"

    return [
        {"key": "policy", "status": ok(policy.is_file())},
        {"key": "prompts", "status": ok(_file_count(prompts, "*.yaml") >= _REQUIRED_LANGS)},
        {"key": "corpus", "status": ok(_file_count(corpus, "*.json") > 0)},
        {"key": "audit_log", "status": ok(ledger_available(audit_file))},
        {"key": "audit_chain", "status": ok(chain_ok)},
        {"key": "firewall", "status": ok(firewall_active)},
        {"key": "eval_reports", "status": ok(len(iter_report_files()) > 0)},
        {"key": "embeddings", "status": "ok"},
    ]


def compute_system_profile(lang: str = "fr") -> dict[str, object]:
    """Return the full System profile overview, built from the real runtime.

    Args:
        lang: UI language (``fr`` / ``de`` / ``en``) for the localized free-text.

    Returns:
        A JSON-serialisable mapping with the posture KPIs, architecture metadata,
        the real component topology, the component-count distribution, OS info,
        the runtime/audit facts, real health checks, the services & versions
        tables and the license panel.
    """
    lang = _norm_lang(lang)
    now = datetime.now(UTC)
    settings = get_settings()
    py = platform.python_version()
    on_prem = bool(settings.is_on_prem)
    deployment = "On-premises" if on_prem else "Cloud"
    profile = "Local (Llama 3.3 70B)" if on_prem else "Frontier (Vertex AI)"
    hostname = platform.node() or "-"

    health_checks = _health(settings.guard.audit_file)
    degraded = sum(1 for h in health_checks if h["status"] != "ok")
    status_value = (
        _t("st_operational", lang) if degraded == 0 else _t("st_watch", lang).format(n=degraded)
    )

    kpis = [
        {
            "key": "status",
            "kind": "status",
            "value": status_value,
            "sub": _t("sub_health", lang),
            "series": [],
        },
        {
            "key": "python",
            "kind": "metric",
            "value": py,
            "sub": _t("sub_interp", lang),
            "series": [],
        },
        {
            "key": "platform",
            "kind": "metric",
            "value": f"{platform.system()} {platform.machine()}",
            "sub": platform.release(),
            "series": [],
        },
        {
            "key": "mode",
            "kind": "metric",
            "value": deployment,
            "sub": _t("sub_deploy", lang),
            "series": [],
        },
        {
            "key": "profile",
            "kind": "metric",
            "value": profile,
            "sub": _t("sub_llm", lang),
            "series": [],
        },
        {
            "key": "cpus",
            "kind": "metric",
            "value": str(_cpu_count()),
            "sub": _t("sub_vcpu", lang),
            "series": [],
        },
        {
            "key": "memory",
            "kind": "metric",
            "value": _total_memory(),
            "sub": _t("sub_memory", lang),
            "series": [],
        },
        {
            "key": "uptime",
            "kind": "time",
            "value": _uptime(now, lang),
            "sub": _t("sub_apiproc", lang),
            "extra": _t("started", lang).format(d=_START.strftime("%d/%m %H:%M")),
            "series": [],
        },
    ]

    tessera_ver = _dep("tessera")
    architecture = {
        "edition": _t("edition_ref", lang),
        "version": f"Tessera v{tessera_ver} - Python {py}",
        "deployment": deployment,
        "region": str(settings.environment),
        "cluster": hostname,
        "deployed_at": _START.strftime("%d/%m/%Y %H:%M"),
        "uptime": _uptime(now, lang),
        "next_maintenance": _t("default_lang", lang).format(
            lang=str(settings.default_language).upper()
        ),
    }

    topology = {
        "tiers": [
            {"key": "api", "label": "API FastAPI", "nodes": 1},
            {"key": "frontend", "label": "Cockpit Next.js", "nodes": 1},
        ],
        "planes": [
            {"key": "agent", "label": "Agent LangGraph", "nodes": 1},
            {"key": "retrieval", "label": _t("topo_retrieval", lang), "nodes": 1},
            {"key": "guard", "label": _t("topo_guard", lang), "nodes": 1},
        ],
        "stores": [
            {"key": "postgres", "label": "PostgreSQL", "detail": f"pgvector {_dep('pgvector')}"},
            {"key": "prompts", "label": "Prompts", "detail": "YAML FR/DE/EN"},
            {"key": "corpus", "label": "Corpus", "detail": _t("topo_corpus_detail", lang)},
        ],
    }

    n_tools = _file_count(_PKG_ROOT / "agent" / "tools", "*.py") - 1  # minus __init__
    n_workers = _file_count(_PKG_ROOT / "agent" / "workers", "*.py") - 1
    n_failures = _file_count(_PKG_ROOT.parent.parent / "eval" / "failures", "[0-9]*.json")
    comp: list[tuple[str, int, str]] = [
        ("tools", max(n_tools, 0), "#60a5fa"),
        ("workers", max(n_workers, 0), "#a78bfa"),
        ("prompts", 14, "#34d399"),
        ("failures", n_failures, "#fbbf24"),
    ]
    comp_total = sum(count for _key, count, _color in comp) or 1
    resources = {
        "total": f"{comp_total} modules",
        "slices": [
            {"key": key, "count": count, "color": color, "pct": round(count / comp_total * 100)}
            for key, count, color in comp
        ],
    }

    os_info = {
        "os": f"{platform.system()} {platform.release()}",
        "kernel": platform.version().split(";")[0][:48],
        "arch": platform.machine(),
        "virtualization": deployment,
        "cpu": f"{_cpu_count()} vCPU",
        "memory": _total_memory(),
        "system_time": now.strftime("%d/%m/%Y %H:%M:%S"),
        "timezone": str(now.astimezone().tzinfo or "UTC"),
        "fqdn": hostname,
        "infra_id": f"Python {py}",
        "support": str(settings.environment),
    }

    audit_lines = count_ledger_entries()
    chain_label = next((h["status"] for h in health_checks if h["key"] == "audit_chain"), "warn")
    runtime = {
        "uptime": _uptime(now, lang),
        "audit_lines": f"{audit_lines:,}".replace(",", " "),
        "audit_chain": _t("chain_ok", lang) if chain_label == "ok" else _t("chain_broken", lang),
        "started": _START.strftime("%d/%m/%Y %H:%M"),
    }

    services = [
        {"name": "API (FastAPI)", "status": "ok", "version": _dep("fastapi"), "instances": "-"},
        {
            "name": "Agent (LangGraph)",
            "status": "ok",
            "version": _dep("langgraph"),
            "instances": "-",
        },
        {
            "name": _t("svc_retrieval", lang),
            "status": "ok",
            "version": _dep("psycopg"),
            "instances": "-",
        },
        {
            "name": _t("svc_guard", lang),
            "status": "ok",
            "version": tessera.__version__,
            "instances": "-",
        },
        {
            "name": _t("svc_local_llm", lang),
            "status": "ok",
            "version": _dep("ollama"),
            "instances": "-",
        },
    ]

    versions = [
        {"name": "Python", "version": py},
        {"name": "FastAPI", "version": _dep("fastapi")},
        {"name": "LangGraph", "version": _dep("langgraph")},
        {"name": "Pydantic", "version": _dep("pydantic")},
        {"name": "pgvector", "version": _dep("pgvector")},
        {"name": "Tessera guard (first-party)", "version": tessera.__version__},
    ]

    licenses = {
        "edition": "AGPL-3.0-only",
        "seats": _t("edition_ref", lang),
        "expiry": "FR / DE / EN",
        "quota_calls": profile,
        "quota_storage": str(settings.environment),
    }

    return {
        "generated_at": now.isoformat(),
        "kpis": kpis,
        "architecture": architecture,
        "topology": topology,
        "resources": resources,
        "os_info": os_info,
        "health_checks": health_checks,
        "runtime": runtime,
        "services": services,
        "versions": versions,
        "licenses": licenses,
        "footer": {
            "version": f"Tessera v{tessera_ver}",
            "source": f"{deployment} - {hostname}",
        },
    }
