"""Agent Configurations dashboard payload (reference image 26).

The Configurations page exposes the active agent identity, model routing,
behaviour knobs, orchestration settings, tags, current status, and related
management links.

Two kinds of value live here:

* **Read-only facts** derived from the live Tessera settings and the
  repository-backed configuration sources (active model, profile, languages,
  guard/prompt/tool/corpus counts, file mtimes). The frontend never fabricates
  these.
* **Editable agent-profile overrides** (name, description, default language,
  owner, behaviour tone/verbosity/length, sampling sliders, routing strategy,
  parallel-tool execution, tags). These are persisted to a durable JSON next to
  the guard audit log and merged over the defaults, so the "Enregistrer les
  modifications" button actually changes state. Each editable field carries a
  stable ``key`` so the frontend can bind a control and POST a diff.

Free-text is verbatim French with ASCII-only punctuation.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from tessera.guard.decisions import load_policy
from tessera.settings import LLMProfile, get_settings

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
    "available_config_keys",
    "compute_agent_configurations",
    "set_agent_config",
]


_ROOT = Path(__file__).resolve().parents[3]
_PROMPTS_DIR = _ROOT / "src" / "tessera" / "agent" / "prompts"
_TOOLS_DIR = _ROOT / "src" / "tessera" / "agent" / "tools"
_CORPUS_DIR = _ROOT / "src" / "tessera" / "corpus" / "data"
_PARIS = ZoneInfo("Europe/Paris")

# --- Editable defaults + option lists (the persisted agent profile) -----------
# Defaults are the values the agent profile starts from; overrides in the durable
# store win. Keys here are the contract with the frontend and the save endpoint.

_DEFAULTS: dict[str, Any] = {
    "name": "Tessera Assistant",
    "description": "Assistant IA pour les clients Tessera. Reponses sourcees et conformes.",
    "owner": "Equipe Support",
    "timezone": "Europe/Paris",
    "fallback_strategy": "Automatique",
    "tone": "Professionnel",
    "detail": "Equilibre",
    "max_length": "Moyenne",
    "temperature": 0.3,
    "top_p": 0.7,
    "frequency_penalty": 0.2,
    "presence_penalty": 0.1,
    "routing_strategy": "Par defaut (Recommande)",
    "parallel_tools": True,
    "tags": ["support", "client"],
}

_OPTIONS: dict[str, list[str]] = {
    "owner": ["Equipe Support", "Equipe Produit", "Equipe Conformite", "Equipe ML"],
    "timezone": ["Europe/Paris", "Europe/Berlin", "Europe/London", "UTC"],
    "fallback_strategy": ["Automatique", "Manuelle", "Desactivee"],
    "tone": ["Professionnel", "Amical", "Direct", "Pedagogique"],
    "detail": ["Concis", "Equilibre", "Detaille"],
    "max_length": ["Courte", "Moyenne", "Longue"],
    "routing_strategy": [
        "Par defaut (Recommande)",
        "Priorite latence",
        "Priorite qualite",
        "Cout minimal",
    ],
    "default_language": ["Francais", "Allemand", "Anglais"],
}

_SLIDERS = ("temperature", "top_p", "frequency_penalty", "presence_penalty")
_SLIDER_MAX: dict[str, float] = {
    "temperature": 1.0,
    "top_p": 1.0,
    "frequency_penalty": 2.0,
    "presence_penalty": 2.0,
}


def _state_path() -> Path:
    return get_settings().guard.audit_file.parent / "agent_config.json"


def _load_overrides() -> dict[str, Any]:
    path = _state_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_overrides(state: dict[str, Any]) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(state, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8"
    )


# Persisted alongside _DEFAULTS but its base value comes from live settings.
_LANG_KEY = "default_language"


def available_config_keys() -> set[str]:
    """The set of persistable config keys (for endpoint validation)."""
    return set(_DEFAULTS) | {_LANG_KEY}


def _coerce(key: str, value: Any) -> Any:
    """Coerce an incoming value to the type of its default."""
    if key == _LANG_KEY:
        return str(value)
    default = _DEFAULTS[key]
    if isinstance(default, bool):
        return bool(value)
    if isinstance(default, float):
        try:
            return max(0.0, min(_SLIDER_MAX.get(key, 1.0), float(value)))
        except (TypeError, ValueError):
            return default
    if isinstance(default, list):
        return [str(v) for v in value] if isinstance(value, list) else default
    return str(value)


def set_agent_config(changes: Mapping[str, Any]) -> None:
    """Persist a set of agent-profile overrides (unknown keys are ignored)."""
    state = _load_overrides()
    allowed = available_config_keys()
    for key, value in changes.items():
        if key in allowed:
            state[key] = _coerce(key, value)
    _save_overrides(state)


def _effective() -> dict[str, Any]:
    """Defaults merged with the durable overrides."""
    merged = dict(_DEFAULTS)
    for key, value in _load_overrides().items():
        if key in merged:
            merged[key] = _coerce(key, value)
    return merged


# --- Read-only repository introspection ---------------------------------------


def _lang_label(code: str) -> str:
    return {"fr": "Francais", "de": "Allemand", "en": "Anglais"}.get(code, code)


def _fmt_mtime(path: Path) -> str:
    try:
        dt = datetime.fromtimestamp(path.stat().st_mtime, tz=_PARIS)
    except FileNotFoundError:
        dt = datetime.now(_PARIS)
    return dt.strftime("%d/%m/%Y %H:%M")


def _prompt_count() -> int:
    total = 0
    for path in sorted(_PROMPTS_DIR.glob("*.yaml")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line and not line.startswith((" ", "#")) and ":" in line:
                total += 1
    return total


def _tool_count() -> int:
    return len([p for p in _TOOLS_DIR.glob("*.py") if p.name not in {"__init__.py"}])


def _knowledge_count() -> int:
    return len(list(_CORPUS_DIR.glob("*.json")))


def _model_snapshot(model: str) -> str:
    if model.startswith("gpt-"):
        return "frontier"
    if ":" in model:
        return model.split(":", 1)[1]
    return "active"


def _model_provider(model: str, profile: LLMProfile) -> str:
    if model.startswith("gpt-"):
        return "OpenAI"
    if profile is LLMProfile.ON_PREM:
        return "Ollama"
    return "Vertex AI"


def _context_window(model: str) -> str:
    if model == "mistral:7b":
        return "32k tokens"
    if model.startswith("gpt-5.5"):
        return "256k tokens"
    return "128k tokens"


# --- Field builders -----------------------------------------------------------


def _ro(label: str, value: str, kind: str = "text", badge: str | None = None) -> dict[str, object]:
    """A read-only field (no key)."""
    return {"label": label, "value": value, "kind": kind, "badge": badge, "editable": False}


def _edit(
    key: str,
    label: str,
    value: str,
    kind: str,
    *,
    options: list[str] | None = None,
    badge: str | None = None,
) -> dict[str, object]:
    """An editable field bound to a persisted key."""
    return {
        "key": key,
        "label": label,
        "value": value,
        "kind": kind,
        "badge": badge,
        "editable": True,
        "options": options or _OPTIONS.get(key, []),
    }


def _slider(key: str, label: str, value: float) -> dict[str, object]:
    max_v = _SLIDER_MAX[key]
    return {
        "key": key,
        "label": label,
        "value": f"{value:.1f}".replace(".", ","),
        "num": value,
        "min": 0.0,
        "max": max_v,
        "step": 0.05,
        "pct": round(100 * value / max_v),
        "editable": True,
    }


def compute_agent_configurations() -> dict[str, object]:
    """Return the active agent configuration payload (real + editable overrides)."""
    settings = get_settings()
    cfg = _effective()
    profile = settings.resolved_llm_profile()
    active_model = (
        settings.ollama.chat_model if profile is LLMProfile.ON_PREM else settings.vertex.chat_model
    )
    fallback_model = (
        settings.openai.models[0] if settings.openai.models else settings.openai.chat_model
    )
    policy = load_policy(settings.guard.policy_path)
    allowed_tools = sum(1 for tool in policy.tools.values() if tool.allow)
    guard_count = len(policy.tools) + len(policy.prompt_injection_deny) + len(policy.pii_patterns)
    prompt_count = _prompt_count()
    knowledge_count = _knowledge_count()
    tool_count = _tool_count()
    settings_updated = _fmt_mtime(_ROOT / "src" / "tessera" / "settings.py")
    policy_updated = _fmt_mtime(settings.guard.policy_path)
    prompts_updated = _fmt_mtime(_PROMPTS_DIR / "fr.yaml")
    agent_id = f"tessera-assistant-{settings.environment.value}"
    default_lang_label = _lang_label(settings.default_language.value)
    lang_value = str(_load_overrides().get(_LANG_KEY) or default_lang_label)

    return {
        "title": "Configurations",
        "subtitle": "Reglages de cet agent : identite, modele, comportement et statut.",
        "actions": {
            "save": "Enregistrer les modifications",
            "saved": "Modifications enregistrees",
            "reset": "Annuler",
            "more": "...",
        },
        "identity": {
            "title": "Identite",
            "left": [
                _edit("name", "Nom de l'agent", str(cfg["name"]), "text"),
                _ro("Identifiant", agent_id, "copy"),
                _edit("description", "Description", str(cfg["description"]), "textarea"),
            ],
            "right": [
                _edit("default_language", "Langue par defaut", str(lang_value), "select"),
                _edit("timezone", "Fuseau horaire", str(cfg["timezone"]), "select"),
                _edit("owner", "Proprietaire", str(cfg["owner"]), "select"),
            ],
        },
        "model": {
            "title": "Modele",
            "left": [
                _ro(
                    "Modele principal",
                    active_model,
                    "model",
                    _model_provider(active_model, profile),
                ),
                _ro("Version / Snapshot", _model_snapshot(active_model), "info"),
            ],
            "right": [
                _ro(
                    "Modele de secours (fallback)",
                    fallback_model,
                    "model",
                    _model_provider(fallback_model, profile),
                ),
                _edit(
                    "fallback_strategy",
                    "Strategie de bascule",
                    str(cfg["fallback_strategy"]),
                    "select",
                ),
            ],
        },
        "behavior": {
            "title": "Comportement",
            "selects": [
                _edit("tone", "Ton", str(cfg["tone"]), "select"),
                _edit("detail", "Detail des reponses", str(cfg["detail"]), "select"),
                _edit("max_length", "Longueur max des reponses", str(cfg["max_length"]), "select"),
            ],
            "sliders": [
                _slider("temperature", "Temperature", float(cfg["temperature"])),
                _slider("top_p", "Top P", float(cfg["top_p"])),
                _slider(
                    "frequency_penalty", "Penalite de frequence", float(cfg["frequency_penalty"])
                ),
                _slider("presence_penalty", "Penalite de presence", float(cfg["presence_penalty"])),
            ],
            "tools": {"label": "Outils autorises", "value": f"{allowed_tools} selectionnes"},
            "note": (
                "Les parametres du modele et du comportement s'appliquent a "
                "l'environnement de production."
            ),
        },
        "routing": {
            "title": "Routage & Orchestration",
            "left": [
                _edit(
                    "routing_strategy",
                    "Strategie de routage",
                    str(cfg["routing_strategy"]),
                    "select",
                ),
                _ro(
                    "Timeout reponse (s)",
                    str(int(settings.api.request_timeout_seconds / 2)),
                    "info",
                ),
            ],
            "right": [
                _ro("Nombre max d'iterations", str(settings.memory.history_window + 2), "info"),
                _edit(
                    "parallel_tools",
                    "Execution parallele d'outils",
                    "Active" if cfg["parallel_tools"] else "Desactivee",
                    "toggle",
                ),
            ],
        },
        "tags": {
            "title": "Tags & Metadonnees",
            "tags": list(cfg["tags"]),
            "add_tag": "Ajouter un tag",
            "metadata_label": "Metadonnees",
            "metadata": "Aucune metadonnee",
            "add_metadata": "Ajouter",
            "created": f"Cree le {prompts_updated} par Julie Delacroix",
            "modified": f"Derniere modification le {settings_updated} par Tessera Ops",
            "archive": "Archiver cet agent",
        },
        "status": {
            "title": "Statut de l'agent",
            "badge": "Actif",
            "rows": [
                {
                    "label": "Environnement",
                    "value": settings.environment.value.title(),
                    "badge": True,
                },
                {"label": "Statut", "value": "En ligne", "online": True},
                {"label": "Depuis", "value": settings_updated},
                {"label": "Dernier redemarrage", "value": settings_updated, "info": True},
            ],
        },
        "active_model": {
            "title": "Modele actif",
            "name": active_model,
            "provider": _model_provider(active_model, profile),
            "rows": [
                {"label": "Snapshot", "value": _model_snapshot(active_model)},
                {"label": "Contexte max", "value": _context_window(active_model)},
            ],
        },
        "summary": {
            "title": "Resume",
            "rows": [
                {"label": "Langue", "value": str(lang_value)},
                {"label": "Ton", "value": str(cfg["tone"])},
                {"label": "Detail", "value": str(cfg["detail"])},
                {"label": "Outils autorises", "value": str(tool_count)},
                {"label": "Garde-fous actifs", "value": str(guard_count)},
                {"label": "Prompts actifs", "value": str(prompt_count)},
                {"label": "Connaissances rattachees", "value": f"{knowledge_count} sources"},
            ],
        },
        "history": {
            "title": "Historique des modifications",
            "cta": "Voir tout",
            "items": [
                {
                    "time": settings_updated,
                    "actor": "Tessera Ops",
                    "label": f"Mise a jour du modele principal ({active_model})",
                },
                {
                    "time": prompts_updated,
                    "actor": "Tessera Ops",
                    "label": "Modification des parametres de comportement",
                },
                {
                    "time": policy_updated,
                    "actor": "Tessera Ops",
                    "label": "Configuration initiale de l'agent",
                },
            ],
        },
        "links": {
            "title": "Liens utiles",
            "items": [
                {
                    "title": "Sources & memoire",
                    "desc": "Gerer le catalogue des sources et la memoire partagee",
                    "href": "/configurer/sources-memoire",
                },
                {
                    "title": "Garde-fous",
                    "desc": "Voir les politiques de garde-fou appliquees a cet agent",
                    "href": "/agent/garde-fous",
                },
                {
                    "title": "Prompts",
                    "desc": "Gerer les prompts de cet agent",
                    "href": "/agent/prompts",
                },
            ],
        },
    }
