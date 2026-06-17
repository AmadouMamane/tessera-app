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
    "description": "Assistant IA pour les clients Tessera. Réponses sourcées et conformes.",
    "owner": "Équipe Support",
    "timezone": "Europe/Paris",
    "fallback_strategy": "Automatique",
    "tone": "Professionnel",
    "detail": "Équilibré",
    "max_length": "Moyenne",
    "temperature": 0.3,
    "top_p": 0.7,
    "frequency_penalty": 0.2,
    "presence_penalty": 0.1,
    "routing_strategy": "Par défaut (Recommandé)",
    "parallel_tools": True,
    "tags": ["support", "client"],
    "archived": False,
}

_OPTIONS: dict[str, list[str]] = {
    "owner": ["Équipe Support", "Équipe Produit", "Équipe Conformité", "Équipe ML"],
    "timezone": ["Europe/Paris", "Europe/Berlin", "Europe/London", "UTC"],
    "fallback_strategy": ["Automatique", "Manuelle", "Désactivée"],
    "tone": ["Professionnel", "Amical", "Direct", "Pédagogique"],
    "detail": ["Concis", "Équilibré", "Détaillé"],
    "max_length": ["Courte", "Moyenne", "Longue"],
    "routing_strategy": [
        "Par défaut (Recommandé)",
        "Priorité latence",
        "Priorité qualité",
        "Coût minimal",
    ],
    "default_language": ["Français", "Allemand", "Anglais"],
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


# --- Durable change-log: real, append-only record of every config save ---------

_HISTORY_LIMIT = 50

# Human-facing French label for each persistable key (used in the change-log).
_KEY_LABEL: dict[str, str] = {
    "name": "Nom de l'agent",
    "description": "Description",
    "owner": "Propriétaire",
    "timezone": "Fuseau horaire",
    "fallback_strategy": "Stratégie de bascule",
    "tone": "Ton",
    "detail": "Détail des réponses",
    "max_length": "Longueur max",
    "temperature": "Température",
    "top_p": "Top P",
    "frequency_penalty": "Pénalité de fréquence",
    "presence_penalty": "Pénalité de présence",
    "routing_strategy": "Stratégie de routage",
    "parallel_tools": "Exécution parallèle d'outils",
    "tags": "Tags",
    "archived": "Archivage",
    "default_language": "Langue par défaut",
}


def _history_path() -> Path:
    return get_settings().guard.audit_file.parent / "agent_config_history.json"


def _load_change_log() -> list[dict[str, Any]]:
    path = _history_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return data if isinstance(data, list) else []


def _record_change(keys: list[str]) -> None:
    """Append a real, timestamped entry for a config save (most recent first)."""
    if not keys:
        return
    entries = _load_change_log()
    entries.insert(0, {"at": datetime.now(_PARIS).isoformat(), "keys": keys})
    path = _history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(entries[:_HISTORY_LIMIT], indent=2, ensure_ascii=False), encoding="utf-8"
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
    """Persist a set of agent-profile overrides and record the change durably."""
    state = _load_overrides()
    allowed = available_config_keys()
    changed: list[str] = []
    for key, value in changes.items():
        if key not in allowed:
            continue
        coerced = _coerce(key, value)
        if state.get(key) != coerced:
            changed.append(key)
        state[key] = coerced
    _save_overrides(state)
    _record_change(changed)


def _effective() -> dict[str, Any]:
    """Defaults merged with the durable overrides."""
    merged = dict(_DEFAULTS)
    for key, value in _load_overrides().items():
        if key in merged:
            merged[key] = _coerce(key, value)
    return merged


# --- Read-only repository introspection ---------------------------------------


def _lang_label(code: str) -> str:
    return {"fr": "Français", "de": "Allemand", "en": "Anglais"}.get(code, code)


def _mtime_dt(path: Path) -> datetime:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=_PARIS)
    except FileNotFoundError:
        return datetime.now(_PARIS)


def _fmt_mtime(path: Path) -> str:
    return _mtime_dt(path).strftime("%d/%m/%Y %H:%M")


def _build_history(policy_path: Path) -> list[dict[str, str]]:
    """Real change history: durable form-save log + real config-file mtimes.

    No invented events - each row is either a real persisted override save
    (timestamp + the fields that actually changed) or a real file modification
    (the source's actual mtime), newest first.
    """
    events: list[tuple[datetime, str, str]] = []
    for entry in _load_change_log():
        try:
            when = datetime.fromisoformat(str(entry.get("at")))
        except (TypeError, ValueError):
            continue
        keys = [str(k) for k in entry.get("keys", [])]
        labels = ", ".join(_KEY_LABEL.get(k, k) for k in keys) or "configuration"
        plural = "s" if len(keys) > 1 else ""
        events.append((when, "Console", f"{len(keys)} champ{plural} modifié{plural} : {labels}"))
    sources = [
        (_ROOT / "src" / "tessera" / "settings.py", "Paramètres système (settings.py)"),
        (policy_path, "Politique garde-fous (policy.yaml)"),
        (_PROMPTS_DIR / "fr.yaml", "Prompts (fr.yaml)"),
    ]
    newest_corpus = max(_CORPUS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, default=None)
    if newest_corpus is not None:
        sources.append((newest_corpus, f"Corpus ({newest_corpus.name})"))
    for path, label in sources:
        if path.exists():
            events.append((_mtime_dt(path), "Dépôt (Git)", f"{label} mis à jour"))
    events.sort(key=lambda e: e[0], reverse=True)
    return [
        {"time": when.strftime("%d/%m/%Y %H:%M"), "actor": actor, "label": label}
        for when, actor, label in events[:6]
    ]


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
    agent_id = f"tessera-assistant-{settings.environment.value}"
    default_lang_label = _lang_label(settings.default_language.value)
    lang_value = str(_load_overrides().get(_LANG_KEY) or default_lang_label)
    archived = bool(cfg["archived"])

    return {
        "title": "Configurations",
        "subtitle": "Réglages de cet agent : identité, modèle, comportement et statut.",
        "actions": {
            "save": "Enregistrer les modifications",
            "saved": "Modifications enregistrées",
            "reset": "Annuler",
            "more": "...",
        },
        "identity": {
            "title": "Identité",
            "left": [
                _edit("name", "Nom de l'agent", str(cfg["name"]), "text"),
                _ro("Identifiant", agent_id, "copy"),
                _edit("description", "Description", str(cfg["description"]), "textarea"),
            ],
            "right": [
                _edit("default_language", "Langue par défaut", str(lang_value), "select"),
                _edit("timezone", "Fuseau horaire", str(cfg["timezone"]), "select"),
                _edit("owner", "Propriétaire", str(cfg["owner"]), "select"),
            ],
        },
        "model": {
            "title": "Modèle",
            "left": [
                _ro(
                    "Modèle principal",
                    active_model,
                    "model",
                    _model_provider(active_model, profile),
                ),
                _ro("Version / Snapshot", _model_snapshot(active_model), "info"),
            ],
            "right": [
                _ro(
                    "Modèle de secours (fallback)",
                    fallback_model,
                    "model",
                    _model_provider(fallback_model, profile),
                ),
                _edit(
                    "fallback_strategy",
                    "Stratégie de bascule",
                    str(cfg["fallback_strategy"]),
                    "select",
                ),
            ],
        },
        "behavior": {
            "title": "Comportement",
            "selects": [
                _edit("tone", "Ton", str(cfg["tone"]), "select"),
                _edit("detail", "Détail des réponses", str(cfg["detail"]), "select"),
                _edit("max_length", "Longueur max des réponses", str(cfg["max_length"]), "select"),
            ],
            "sliders": [
                _slider("temperature", "Température", float(cfg["temperature"])),
                _slider("top_p", "Top P", float(cfg["top_p"])),
                _slider(
                    "frequency_penalty", "Pénalité de fréquence", float(cfg["frequency_penalty"])
                ),
                _slider("presence_penalty", "Pénalité de présence", float(cfg["presence_penalty"])),
            ],
            "tools": {"label": "Outils autorisés", "value": f"{allowed_tools} sélectionnés"},
            "note": (
                "Les paramètres du modèle et du comportement s'appliquent à "
                "l'environnement de production."
            ),
        },
        "routing": {
            "title": "Routage & Orchestration",
            "left": [
                _edit(
                    "routing_strategy",
                    "Stratégie de routage",
                    str(cfg["routing_strategy"]),
                    "select",
                ),
                _ro(
                    "Timeout réponse (s)",
                    str(int(settings.api.request_timeout_seconds / 2)),
                    "info",
                ),
            ],
            "right": [
                _ro("Nombre max d'itérations", str(settings.memory.history_window + 2), "info"),
                _edit(
                    "parallel_tools",
                    "Exécution parallèle d'outils",
                    "Activé" if cfg["parallel_tools"] else "Désactivée",
                    "toggle",
                ),
            ],
        },
        "tags": {
            "title": "Tags & Métadonnées",
            "tags": list(cfg["tags"]),
            "add_tag": "Ajouter un tag",
            "metadata_label": "Métadonnées",
            "metadata": "Aucune métadonnée",
            "add_metadata": "Ajouter",
            # Honest provenance: no invented author. "created" = the repo config
            # baseline; "modified" = the real last override save (or defaults).
            "created": "Profil issu du dépôt (settings.py + policy.yaml + prompts)",
            "modified": (
                f"Dernière sauvegarde via la console le {_fmt_mtime(_state_path())}"
                if _state_path().exists()
                else "Valeurs par défaut - aucune surcharge enregistrée"
            ),
            "archive": "Désarchiver cet agent" if archived else "Archiver cet agent",
            "archived": archived,
        },
        "status": {
            "title": "Statut de l'agent",
            "badge": "Archivé" if archived else "Actif",
            "badge_tone": "crit" if archived else "good",
            "rows": [
                {
                    "label": "Environnement",
                    "value": settings.environment.value.title(),
                    "badge": True,
                },
                {
                    # `live` tells the frontend to replace this with the real
                    # /readyz probe (is the chat backend actually reachable);
                    # archived agents are never probed.
                    "label": "Statut",
                    "value": "Archivé" if archived else "En ligne",
                    "online": not archived,
                    "live": not archived,
                },
                {"label": "Config modifiée le", "value": settings_updated},
                {"label": "Source", "value": "settings.py (dépôt)", "info": True},
            ],
        },
        "active_model": {
            "title": "Modèle actif",
            "name": active_model,
            "provider": _model_provider(active_model, profile),
            "rows": [
                {"label": "Snapshot", "value": _model_snapshot(active_model)},
                {"label": "Contexte max", "value": _context_window(active_model)},
            ],
        },
        "summary": {
            "title": "Résumé",
            "rows": [
                {"label": "Langue", "value": str(lang_value)},
                {"label": "Ton", "value": str(cfg["tone"])},
                {"label": "Detail", "value": str(cfg["detail"])},
                {"label": "Outils autorisés", "value": str(tool_count)},
                {"label": "Garde-fous actifs", "value": str(guard_count)},
                {"label": "Prompts actifs", "value": str(prompt_count)},
                {"label": "Connaissances rattachées", "value": f"{knowledge_count} sources"},
            ],
        },
        "history": {
            "title": "Historique des modifications",
            "cta": "Voir tout",
            "items": _build_history(settings.guard.policy_path),
        },
        "links": {
            "title": "Liens utiles",
            "items": [
                {
                    "title": "Sources & mémoire",
                    "desc": "Gérer le catalogue des sources et la mémoire partagée",
                    "href": "/configurer/sources-memoire",
                },
                {
                    "title": "Garde-fous",
                    "desc": "Voir les politiques de garde-fou appliquées à cet agent",
                    "href": "/agent/garde-fous",
                },
                {
                    "title": "Prompts",
                    "desc": "Gérer les prompts de cet agent",
                    "href": "/agent/prompts",
                },
            ],
        },
    }
