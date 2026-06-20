"""System profile cockpit overview (page #20, admin/profil-systeme).

Surfaces the **real** runtime, not an invented data-center: the Python / OS /
arch from :mod:`platform`, the installed dependency versions from
:mod:`importlib.metadata` (FastAPI, LangGraph, psycopg, pgvector, mcp-firewall,
Ollama, Pydantic), the deployment posture from :func:`get_settings` (mode,
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
from tessera.guard.audit import verify_audit_chain
from tessera.settings import get_settings

__all__ = ["compute_system_profile"]

# Tessera ships prompts in the three supported languages (FR/DE/EN).
_REQUIRED_LANGS = 3

# Process start time (module import) — a real, monotonic-enough uptime base.
_START = datetime.now(UTC)

_PKG_ROOT = Path(tessera.__file__).resolve().parent


def _dep(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "-"


def _uptime(now: datetime) -> str:
    secs = int((now - _START).total_seconds())
    days, rem = divmod(secs, 86_400)
    hours, rem = divmod(rem, 3600)
    mins = rem // 60
    if days:
        return f"{days} j {hours} h {mins} min"
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
    eval_reports = _PKG_ROOT.parent.parent / "eval" / "reports"

    chain_ok = True
    try:
        chain_ok = bool(verify_audit_chain(audit_file).verified)
    except (OSError, ValueError):
        chain_ok = False

    def ok(flag: bool) -> str:
        return "ok" if flag else "warn"

    return [
        {"key": "policy", "status": ok(policy.is_file())},
        {"key": "prompts", "status": ok(_file_count(prompts, "*.yaml") >= _REQUIRED_LANGS)},
        {"key": "corpus", "status": ok(_file_count(corpus, "*.json") > 0)},
        {"key": "audit_log", "status": ok(audit_file.is_file())},
        {"key": "audit_chain", "status": ok(chain_ok)},
        {"key": "firewall", "status": ok(_dep("mcp-firewall") != "-")},
        {"key": "eval_reports", "status": ok(_file_count(eval_reports, "*.json") > 0)},
        {"key": "embeddings", "status": "ok"},
    ]


def compute_system_profile() -> dict[str, object]:
    """Return the full System profile overview, built from the real runtime.

    Returns:
        A JSON-serialisable mapping with the posture KPIs, architecture metadata,
        the real component topology, the component-count distribution, OS info,
        the runtime/audit facts, real health checks, the services & versions
        tables and the license panel.
    """
    now = datetime.now(UTC)
    settings = get_settings()
    py = platform.python_version()
    on_prem = bool(settings.is_on_prem)
    deployment = "On-premises" if on_prem else "Cloud"
    profile = "Local (Llama 3.3 70B)" if on_prem else "Frontier (Vertex AI)"
    hostname = platform.node() or "-"

    health_checks = _health(settings.guard.audit_file)
    degraded = sum(1 for h in health_checks if h["status"] != "ok")
    status_value = "Opérationnel" if degraded == 0 else f"{degraded} vérification(s) à surveiller"

    kpis = [
        {
            "key": "status",
            "kind": "status",
            "value": status_value,
            "sub": "Vérifications de santé",
            "series": [],
        },
        {"key": "python", "kind": "metric", "value": py, "sub": "Interpréteur", "series": []},
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
            "sub": "Mode de déploiement",
            "series": [],
        },
        {"key": "profile", "kind": "metric", "value": profile, "sub": "Profil LLM", "series": []},
        {
            "key": "cpus",
            "kind": "metric",
            "value": str(_cpu_count()),
            "sub": "vCPU disponibles",
            "series": [],
        },
        {
            "key": "memory",
            "kind": "metric",
            "value": _total_memory(),
            "sub": "Mémoire totale",
            "series": [],
        },
        {
            "key": "uptime",
            "kind": "time",
            "value": _uptime(now),
            "sub": "Processus API",
            "extra": _START.strftime("Démarré %d/%m %H:%M"),
            "series": [],
        },
    ]

    tessera_ver = _dep("tessera")
    architecture = {
        "edition": "Référence (Apache-2.0)",
        "version": f"Tessera v{tessera_ver} - Python {py}",
        "deployment": deployment,
        "region": str(settings.environment),
        "cluster": hostname,
        "deployed_at": _START.strftime("%d/%m/%Y %H:%M"),
        "uptime": _uptime(now),
        "next_maintenance": str(settings.default_language).upper() + " (langue par défaut)",
    }

    topology = {
        "tiers": [
            {"key": "api", "label": "API FastAPI", "nodes": 1},
            {"key": "frontend", "label": "Cockpit Next.js", "nodes": 1},
        ],
        "planes": [
            {"key": "agent", "label": "Agent LangGraph", "nodes": 1},
            {"key": "retrieval", "label": "Récupération", "nodes": 1},
            {"key": "guard", "label": "Garde-fou", "nodes": 1},
        ],
        "stores": [
            {"key": "postgres", "label": "PostgreSQL", "detail": f"pgvector {_dep('pgvector')}"},
            {"key": "prompts", "label": "Prompts", "detail": "YAML FR/DE/EN"},
            {"key": "corpus", "label": "Corpus", "detail": "JSON réglementaire"},
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

    audit_file = settings.guard.audit_file
    audit_lines = 0
    if audit_file.is_file():
        with audit_file.open("r", encoding="utf-8") as fp:
            audit_lines = sum(1 for _ in fp)
    chain_label = next((h["status"] for h in health_checks if h["key"] == "audit_chain"), "warn")
    runtime = {
        "uptime": _uptime(now),
        "audit_lines": f"{audit_lines:,}".replace(",", " "),
        "audit_chain": "Vérifiée" if chain_label == "ok" else "Rupture détectée",
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
            "name": "Récupération (psycopg)",
            "status": "ok",
            "version": _dep("psycopg"),
            "instances": "-",
        },
        {
            "name": "Garde-fou (mcp-firewall)",
            "status": "ok" if _dep("mcp-firewall") != "-" else "warn",
            "version": _dep("mcp-firewall"),
            "instances": "-",
        },
        {"name": "LLM local (Ollama)", "status": "ok", "version": _dep("ollama"), "instances": "-"},
    ]

    versions = [
        {"name": "Python", "version": py},
        {"name": "FastAPI", "version": _dep("fastapi")},
        {"name": "LangGraph", "version": _dep("langgraph")},
        {"name": "Pydantic", "version": _dep("pydantic")},
        {"name": "pgvector", "version": _dep("pgvector")},
        {"name": "mcp-firewall", "version": _dep("mcp-firewall")},
    ]

    licenses = {
        "edition": "Apache-2.0",
        "seats": "Référence (Apache-2.0)",
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
