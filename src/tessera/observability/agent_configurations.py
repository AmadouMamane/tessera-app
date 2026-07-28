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
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from tessera.agent.identity import DEFAULT_AGENT_ID
from tessera.fsutil import atomic_write_text
from tessera.guard.decisions import load_policy
from tessera.settings import LLMProfile, get_settings

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
    "RUNTIME_TEMPERATURE_DEFAULT",
    "available_config_keys",
    "compute_agent_configurations",
    "resolve_escalation_threshold",
    "resolve_memory",
    "resolve_retrieval",
    "resolve_sampling",
    "resolve_style",
    "set_agent_config",
]


_ROOT = Path(__file__).resolve().parents[3]
_PROMPTS_DIR = _ROOT / "src" / "tessera" / "agent" / "prompts"
_TOOLS_DIR = _ROOT / "src" / "tessera" / "agent" / "tools"
_CORPUS_DIR = _ROOT / "src" / "tessera" / "corpus" / "data"
_PARIS = ZoneInfo("Europe/Paris")

_LANG_IDX = {"fr": 0, "de": 1, "en": 2}


def _loc(lang: str, fr: str, de: str, en: str) -> str:
    """Pick the locale variant of an inline string (fr / de / en)."""
    return (fr, de, en)[_LANG_IDX.get(lang, 0)]


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
    # ADR 0031 — the slider defaults are the RUNTIME truth, never a plausible
    # number: temperature 0.2 is what the reporter has always sent; the other
    # four default to unset (None = not sent, the backend's own default
    # serves). The former 0.3/0.7/0.2/0.1 were fabricated display values.
    "temperature": 0.2,
    "top_p": None,
    "top_k": None,
    "frequency_penalty": None,
    "presence_penalty": None,
    # ADR 0033 — unset means the org-wide settings value serves
    # (GuardSettings.escalation_confidence_threshold), never a copied number.
    "escalation_threshold": None,
    # ADR 0035 — unset means each lookup worker's historical default serves
    # (4 product / 6 regulation); reranking ON is the historical truth.
    "retrieval_top_k": None,
    "retrieval_rerank": True,
    # ADR 0036 — "Défaut org" = the settings-selected tier serves; the window
    # unset = the org history_window (never a copied number).
    "memory_backend": "Défaut org",
    "memory_window": None,
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
    # ADR 0036 — the three first-party tiers (ADR 0007); external adapters are
    # deliberately not offered (they may not be installed).
    "memory_backend": [
        "Défaut org",
        "Fenêtre (Tier 0)",
        "Résumé (Tier 1)",
        "Persistante (Tier 2)",
    ],
}

# Per-key translation of the editable option *values*. The canonical French
# string is the persisted identity (the durable store always holds it); display
# and the option list are localized, and ``_canonical_value`` maps any localized
# value posted by the UI back to the French canonical before persisting. Timezone
# values are technical identifiers and stay verbatim.
_VALUE_TR: dict[str, dict[str, tuple[str, str, str]]] = {
    "owner": {
        "Équipe Support": ("Équipe Support", "Support-Team", "Support team"),
        "Équipe Produit": ("Équipe Produit", "Produkt-Team", "Product team"),
        "Équipe Conformité": ("Équipe Conformité", "Compliance-Team", "Compliance team"),
        "Équipe ML": ("Équipe ML", "ML-Team", "ML team"),
    },
    "fallback_strategy": {
        "Automatique": ("Automatique", "Automatisch", "Automatic"),
        "Manuelle": ("Manuelle", "Manuell", "Manual"),
        "Désactivée": ("Désactivée", "Deaktiviert", "Disabled"),
    },
    "tone": {
        "Professionnel": ("Professionnel", "Professionell", "Professional"),
        "Amical": ("Amical", "Freundlich", "Friendly"),
        "Direct": ("Direct", "Direkt", "Direct"),
        "Pédagogique": ("Pédagogique", "Lehrreich", "Pedagogical"),
    },
    "detail": {
        "Concis": ("Concis", "Praegnant", "Concise"),
        "Équilibré": ("Équilibré", "Ausgewogen", "Balanced"),
        "Détaillé": ("Détaillé", "Detailliert", "Detailed"),
    },
    "max_length": {
        "Courte": ("Courte", "Kurz", "Short"),
        "Moyenne": ("Moyenne", "Mittel", "Medium"),
        "Longue": ("Longue", "Lang", "Long"),
    },
    "routing_strategy": {
        "Par défaut (Recommandé)": (
            "Par défaut (Recommandé)",
            "Standard (Empfohlen)",
            "Default (Recommended)",
        ),
        "Priorité latence": ("Priorité latence", "Latenz-Prioritaet", "Latency priority"),
        "Priorité qualité": ("Priorité qualité", "Qualitaets-Prioritaet", "Quality priority"),
        "Coût minimal": ("Coût minimal", "Minimale Kosten", "Minimal cost"),
    },
    "default_language": {
        "Français": ("Français", "Franzoesisch", "French"),
        "Allemand": ("Allemand", "Deutsch", "German"),
        "Anglais": ("Anglais", "Englisch", "English"),
    },
    "memory_backend": {
        "Défaut org": ("Défaut org", "Org-Standard", "Org default"),
        "Fenêtre (Tier 0)": ("Fenêtre (Tier 0)", "Fenster (Tier 0)", "Window (Tier 0)"),
        "Résumé (Tier 1)": ("Résumé (Tier 1)", "Zusammenfassung (Tier 1)", "Summary (Tier 1)"),
        "Persistante (Tier 2)": (
            "Persistante (Tier 2)",
            "Persistent (Tier 2)",
            "Persistent (Tier 2)",
        ),
    },
}

# ADR 0036 — canonical French tier value -> the memory factory's tier slug.
_MEMORY_TIER_SLUGS: dict[str, str] = {
    "Fenêtre (Tier 0)": "window",
    "Résumé (Tier 1)": "summary",
    "Persistante (Tier 2)": "persistent",
}


def _value_display(key: str, canonical: str, lang: str) -> str:
    """Localized display of an option value (canonical French in, locale out)."""
    table = _VALUE_TR.get(key)
    if not table:
        return canonical
    variants = table.get(canonical)
    return variants[_LANG_IDX.get(lang, 0)] if variants else canonical


def _value_options(key: str, lang: str) -> list[str]:
    """The option list for ``key``, localized for display."""
    return [_value_display(key, v, lang) for v in _OPTIONS.get(key, [])]


def _canonical_value(key: str, value: str) -> str:
    """Map a (possibly localized) option value back to its French canonical."""
    table = _VALUE_TR.get(key)
    if not table:
        return value
    for canonical, variants in table.items():
        if value == canonical or value in variants:
            return canonical
    return value


# Human labels for the LLM-callable tools governed by the guard policy (fr/de/en).
_TOOL_LABELS: dict[str, tuple[str, str, str]] = {
    "account_balance": ("Consultation de solde", "Saldoabfrage", "Balance lookup"),
    "card_block": ("Blocage de carte", "Kartensperre", "Card block"),
    "transaction_search": ("Recherche de transactions", "Transaktionssuche", "Transaction search"),
    "loan_simulate": ("Simulation de crédit", "Kreditsimulation", "Loan simulation"),
    "ticket_escalate": (
        "Escalade vers un conseiller",
        "Eskalation an Berater",
        "Escalate to an advisor",
    ),
}


def _tool_label(name: str, lang: str) -> str:
    variants = _TOOL_LABELS.get(name)
    return variants[_LANG_IDX.get(lang, 0)] if variants else name.replace("_", " ").title()


_SLIDERS = ("temperature", "top_p", "top_k", "frequency_penalty", "presence_penalty")
# ADR 0033/0035 — float knobs beyond the sampling family (same coercion, own
# homes: the escalation threshold drives the reviewer, the retrieval depth
# drives the lookup workers — neither rides a backend sampling call).
_FLOAT_KNOBS = (*_SLIDERS, "escalation_threshold", "retrieval_top_k", "memory_window")
_SLIDER_MAX: dict[str, float] = {
    "temperature": 1.0,
    "top_p": 1.0,
    "top_k": 100.0,
    "frequency_penalty": 2.0,
    "presence_penalty": 2.0,
    "escalation_threshold": 1.0,
    "retrieval_top_k": 10.0,
    "memory_window": 20.0,
}
_SLIDER_MIN: dict[str, float] = {"retrieval_top_k": 1.0, "memory_window": 2.0}
# ADR 0032/0035/0036 — integer-valued knobs: whole-number steps, coerced on save.
_INT_KNOBS = ("top_k", "retrieval_top_k", "memory_window")
_SLIDER_STEP: dict[str, float] = {"top_k": 1.0, "retrieval_top_k": 1.0, "memory_window": 1.0}
_SLIDER_STEP_DEFAULT = 0.05


def _state_path() -> Path:
    return get_settings().guard.audit_file.parent / "agent_config.json"


def _load_all_overrides() -> dict[str, Any]:
    """Read the whole durable override store, keyed by agent_id.

    Backward-compat: a legacy *flat* file (config keys at the top level, written
    before the multi-agent split) is read as the default agent's overrides.
    """
    path = _state_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    # Legacy flat shape -> nest under the default agent.
    if data and any(k in available_config_keys() for k in data):
        return {DEFAULT_AGENT_ID: data}
    return data


def _load_overrides(agent_id: str = DEFAULT_AGENT_ID) -> dict[str, Any]:
    bucket = _load_all_overrides().get(agent_id, {})
    return bucket if isinstance(bucket, dict) else {}


def _save_overrides(state: dict[str, Any], agent_id: str = DEFAULT_AGENT_ID) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    store = _load_all_overrides()
    store[agent_id] = state
    atomic_write_text(path, json.dumps(store, indent=2, sort_keys=True, ensure_ascii=False))


# --- Durable change-log: real, append-only record of every config save ---------

_HISTORY_LIMIT = 50

# Human-facing label for each persistable key, per locale (used in the change-log).
_KEY_LABEL: dict[str, tuple[str, str, str]] = {
    "name": ("Nom de l'agent", "Agent-Name", "Agent name"),
    "description": ("Description", "Beschreibung", "Description"),
    "owner": ("Propriétaire", "Eigentuemer", "Owner"),
    "timezone": ("Fuseau horaire", "Zeitzone", "Timezone"),
    "fallback_strategy": ("Stratégie de bascule", "Fallback-Strategie", "Fallback strategy"),
    "tone": ("Ton", "Ton", "Tone"),
    "detail": ("Détail des réponses", "Antwortdetailgrad", "Answer detail"),
    "max_length": ("Longueur max", "Maximale Laenge", "Max length"),
    "temperature": ("Température", "Temperatur", "Temperature"),
    "top_p": ("Top P", "Top P", "Top P"),
    "top_k": ("Top K", "Top K", "Top K"),
    "escalation_threshold": ("Seuil d'escalade", "Eskalationsschwelle", "Escalation threshold"),
    "retrieval_top_k": ("Profondeur de recherche", "Suchtiefe", "Search depth"),
    "retrieval_rerank": ("Reranking (RRF)", "Reranking (RRF)", "Reranking (RRF)"),
    "memory_backend": ("Mémoire (tier)", "Speicher (Tier)", "Memory (tier)"),
    "memory_window": ("Fenêtre de mémoire", "Speicherfenster", "Memory window"),
    "frequency_penalty": ("Pénalité de fréquence", "Frequenzstrafe", "Frequency penalty"),
    "presence_penalty": ("Pénalité de présence", "Praesenzstrafe", "Presence penalty"),
    "routing_strategy": ("Stratégie de routage", "Routing-Strategie", "Routing strategy"),
    "parallel_tools": (
        "Exécution parallèle d'outils",
        "Parallele Tool-Ausfuehrung",
        "Parallel tool execution",
    ),
    "tags": ("Tags", "Tags", "Tags"),
    "archived": ("Archivage", "Archivierung", "Archiving"),
    "default_language": ("Langue par défaut", "Standardsprache", "Default language"),
}


def _key_label(key: str, lang: str) -> str:
    variants = _KEY_LABEL.get(key)
    return variants[_LANG_IDX.get(lang, 0)] if variants else key


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


def _record_change(
    keys: list[str], agent_id: str = DEFAULT_AGENT_ID, *, author: str | None = None
) -> None:
    """Append a real, timestamped entry for a config save (most recent first).

    ``author`` names the verified principal who saved (ADR 0024); ``None`` is
    honest absence, never a default that names somebody.
    """
    if not keys:
        return
    entries = _load_change_log()
    entry: dict[str, Any] = {
        "at": datetime.now(_PARIS).isoformat(),
        "agent_id": agent_id,
        "keys": keys,
    }
    if author is not None:
        entry["author"] = author
    entries.insert(0, entry)
    path = _history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json.dumps(entries[:_HISTORY_LIMIT], indent=2, ensure_ascii=False))


# Persisted alongside _DEFAULTS but its base value comes from live settings.
_LANG_KEY = "default_language"


def available_config_keys() -> set[str]:
    """The set of persistable config keys (for endpoint validation)."""
    return set(_DEFAULTS) | {_LANG_KEY}


def _coerce_slider(key: str, value: Any) -> float | None:
    """Coerce one sampling slider value (ADR 0031).

    ``None`` means "unset": the parameter is not sent to the LLM and the
    backend default serves. A number is clamped to the slider range.
    """
    if value is None:
        return None
    try:
        clamped = max(_SLIDER_MIN.get(key, 0.0), min(_SLIDER_MAX.get(key, 1.0), float(value)))
    except (TypeError, ValueError):
        default = _DEFAULTS[key]
        return float(default) if isinstance(default, int | float) else None
    # ADR 0032/0035 — integer knobs: the store keeps a whole number.
    return float(round(clamped)) if key in _INT_KNOBS else clamped


def _coerce(key: str, value: Any) -> Any:
    """Coerce an incoming value to the type of its default.

    Option values are normalized to their French canonical, so the durable store
    always holds the canonical identity regardless of the UI locale that posted.
    """
    if key == _LANG_KEY:
        return _canonical_value(key, str(value))
    if key in _FLOAT_KNOBS:
        return _coerce_slider(key, value)
    default = _DEFAULTS[key]
    if isinstance(default, bool):
        return bool(value)
    if isinstance(default, list):
        return [str(v) for v in value] if isinstance(value, list) else default
    return _canonical_value(key, str(value))


def set_agent_config(
    changes: Mapping[str, Any], agent_id: str = DEFAULT_AGENT_ID, *, author: str | None = None
) -> list[str]:
    """Persist agent-profile overrides for one agent and record the change durably.

    ``author`` is the verified session principal (ADR 0024) — the route passes
    it, and the durable change-log names them. ``None`` is honest absence (an
    internal caller with no session), never a name. Returns the keys that
    actually changed, so the route can emit the governance act for real changes
    only.
    """
    state = _load_overrides(agent_id)
    allowed = available_config_keys()
    changed: list[str] = []
    for key, value in changes.items():
        if key not in allowed:
            continue
        coerced = _coerce(key, value)
        if state.get(key) != coerced:
            changed.append(key)
        state[key] = coerced
    _save_overrides(state, agent_id)
    _record_change(changed, agent_id, author=author)
    return changed


def _registry_base(agent_id: str) -> dict[str, Any]:
    """Identity bindings the registry pins for ``agent_id`` (override _DEFAULTS).

    The registry is the source of truth for who an agent *is* (name, owner,
    description, tags, default language); editable overrides layer on top. Unknown
    agents (e.g. before the registry is populated) fall back to plain defaults.
    """
    try:
        from tessera.agent.registry import get_agent

        agent = get_agent(agent_id)
    except (KeyError, OSError, ValueError):
        return {}
    return {
        "name": agent.name,
        "description": agent.description,
        "owner": agent.owner,
        "tags": list(agent.tags),
    }


def _registry_default_language(agent_id: str, settings: Any) -> str:
    """The agent's bound default-language code, else the global setting."""
    try:
        from tessera.agent.registry import get_agent

        return get_agent(agent_id).default_language
    except (KeyError, OSError, ValueError):
        return str(settings.default_language.value)


def _effective(agent_id: str = DEFAULT_AGENT_ID) -> dict[str, Any]:
    """Defaults <- registry bindings <- durable per-agent overrides."""
    merged = dict(_DEFAULTS)
    for key, value in _registry_base(agent_id).items():
        if key in merged:
            merged[key] = value
    for key, value in _load_overrides(agent_id).items():
        if key in merged:
            merged[key] = _coerce(key, value)
    return merged


#: The temperature the reporter has always sent when nothing overrides it —
#: the runtime truth the sliders now display and resolve to (ADR 0031).
RUNTIME_TEMPERATURE_DEFAULT: float = 0.2

# --- ADR 0032 — the behaviour selects are effective by construction ------------

#: Canonical French option value -> ASCII slug, the locale-stable key suffix of
#: the style directives in the prompt bundles (``tone_directive_<slug>`` …).
_STYLE_SLUGS: dict[str, str] = {
    "Professionnel": "professionnel",
    "Amical": "amical",
    "Direct": "direct",
    "Pédagogique": "pedagogique",
    "Concis": "concis",
    "Équilibré": "equilibre",
    "Détaillé": "detaille",
    "Courte": "courte",
    "Moyenne": "moyenne",
    "Longue": "longue",
}

#: Declared hard cap per max-length option (ADR 0032 §3): passed to the backend
#: as ``max_output_tokens`` — all three backends apply it. ``Moyenne`` is the
#: number the Vertex settings default has always sent (the historical runtime
#: truth on the frontier path); the directive in the prompt does the styling,
#: the cap is the backstop.
_LENGTH_BUDGET_TOKENS: dict[str, int] = {"Courte": 512, "Moyenne": 2048, "Longue": 8192}

_STYLE_DEFAULTS: dict[str, str] = {"tone": "professionnel", "detail": "equilibre"}
_LENGTH_DEFAULT = "moyenne"


def resolve_style(agent_id: str = DEFAULT_AGENT_ID) -> tuple[dict[str, str], int]:
    """``(style slugs, max_output_tokens)`` for one turn (ADR 0032).

    Resolved once per turn at the routing seam, from the same effective
    configuration the Configurations page displays. ``style`` maps
    ``tone`` / ``detail`` / ``length`` to the ASCII slug of the prompt-bundle
    directive; the int is the declared hard cap for the backend call.
    Fail-open: a corrupt store yields the defaults, loudly — the chat path
    never goes down for a knob.
    """
    try:
        cfg = _effective(agent_id)
    except Exception as exc:
        sys.stderr.write(f"tessera.observability.agent_configurations: resolve_style: {exc}\n")
        return (
            {**_STYLE_DEFAULTS, "length": _LENGTH_DEFAULT},
            _LENGTH_BUDGET_TOKENS["Moyenne"],
        )
    tone = _STYLE_SLUGS.get(str(cfg.get("tone")), _STYLE_DEFAULTS["tone"])
    detail = _STYLE_SLUGS.get(str(cfg.get("detail")), _STYLE_DEFAULTS["detail"])
    length_canonical = str(cfg.get("max_length"))
    length = _STYLE_SLUGS.get(length_canonical, _LENGTH_DEFAULT)
    budget = _LENGTH_BUDGET_TOKENS.get(length_canonical, _LENGTH_BUDGET_TOKENS["Moyenne"])
    return {"tone": tone, "detail": detail, "length": length}, budget


def resolve_retrieval(agent_id: str = DEFAULT_AGENT_ID) -> dict[str, object]:
    """The per-turn retrieval knobs for the lookup workers (ADR 0035).

    ``rerank`` is always present (True is the historical truth); ``top_k`` is
    present only when SET — an absent depth means each worker's own historical
    default serves (4 product / 6 regulation), never one invented number for
    both. Fail-open to the historical behaviour, loudly.
    """
    try:
        cfg = _effective(agent_id)
    except Exception as exc:
        sys.stderr.write(f"tessera.observability.agent_configurations: resolve_retrieval: {exc}\n")
        return {"rerank": True}
    resolved: dict[str, object] = {"rerank": bool(cfg.get("retrieval_rerank", True))}
    raw = cfg.get("retrieval_top_k")
    if isinstance(raw, int | float) and not isinstance(raw, bool):
        resolved["top_k"] = int(raw)
    return resolved


def resolve_memory(agent_id: str = DEFAULT_AGENT_ID) -> dict[str, object]:
    """The per-turn memory knobs for the reporter (ADR 0036).

    ``tier`` is present only when the agent picked a first-party tier
    ("Défaut org" is honest absence — the settings-selected backend serves);
    ``window`` only when set. An empty dict means the org singleton serves,
    exactly the historical behaviour. Fail-open to it, loudly.
    """
    try:
        cfg = _effective(agent_id)
    except Exception as exc:
        sys.stderr.write(f"tessera.observability.agent_configurations: resolve_memory: {exc}\n")
        return {}
    resolved: dict[str, object] = {}
    tier = _MEMORY_TIER_SLUGS.get(str(cfg.get("memory_backend")))
    if tier is not None:
        resolved["tier"] = tier
    raw = cfg.get("memory_window")
    if isinstance(raw, int | float) and not isinstance(raw, bool):
        resolved["window"] = int(raw)
    return resolved


def resolve_escalation_threshold(agent_id: str = DEFAULT_AGENT_ID) -> float:
    """The per-turn escalation-confidence threshold (ADR 0033).

    Resolved once per turn at the routing seam, from the same effective
    configuration the Configurations page displays. Unset means the org-wide
    settings value serves (``GuardSettings.escalation_confidence_threshold``);
    a stored override is this agent's own bar. Fail-open to the org default,
    loudly — the chat path never goes down for a knob.
    """
    org_default = float(get_settings().guard.escalation_confidence_threshold)
    try:
        raw = _effective(agent_id).get("escalation_threshold")
    except Exception as exc:
        sys.stderr.write(
            f"tessera.observability.agent_configurations: resolve_escalation_threshold: {exc}\n"
        )
        return org_default
    if isinstance(raw, int | float) and not isinstance(raw, bool):
        return float(raw)
    return org_default


def resolve_sampling(agent_id: str = DEFAULT_AGENT_ID) -> dict[str, float]:
    """The per-turn sampling the reporter passes to the backend (ADR 0031).

    Resolved once per turn at the routing seam, from the agent's effective
    configuration — the same read the Configurations page displays, so the
    slider value and the served value cannot diverge. Returns only the SET
    parameters; ``temperature`` is always present (default 0.2). Fail-open:
    a corrupt store yields the runtime defaults, loudly — the chat path never
    goes down for a knob.
    """
    try:
        cfg = _effective(agent_id)
    except Exception as exc:
        sys.stderr.write(f"tessera.observability.agent_configurations: resolve_sampling: {exc}\n")
        return {"temperature": RUNTIME_TEMPERATURE_DEFAULT}
    sampling: dict[str, float] = {}
    for key in _SLIDERS:
        value = cfg.get(key)
        if isinstance(value, int | float) and not isinstance(value, bool):
            sampling[key] = float(value)
    sampling.setdefault("temperature", RUNTIME_TEMPERATURE_DEFAULT)
    return sampling


# --- Read-only repository introspection ---------------------------------------


def _lang_label(code: str, lang: str = "fr") -> str:
    """Localized display name for a content-language code (canonical FR for codes)."""
    canonical = {"fr": "Français", "de": "Allemand", "en": "Anglais"}.get(code, code)
    return _value_display("default_language", canonical, lang)


def _mtime_dt(path: Path) -> datetime:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=_PARIS)
    except FileNotFoundError:
        return datetime.now(_PARIS)


def _fmt_mtime(path: Path) -> str:
    return _mtime_dt(path).strftime("%d/%m/%Y %H:%M")


def _build_history(
    policy_path: Path,
    lang: str = "fr",
    agent_id: str = DEFAULT_AGENT_ID,
    until: datetime | None = None,
) -> list[dict[str, str]]:
    """Real change history: durable form-save log + real config-file mtimes.

    No invented events - each row is either a real persisted override save
    (timestamp + the fields that actually changed) or a real file modification
    (the source's actual mtime), newest first. Form saves are scoped to
    ``agent_id`` (OT-01 is a per-object trace); the repo-file mtimes stay,
    because settings/policy/prompts/corpus are provenance for every agent.
    ``until`` set = the as-of reading: events after T leave the list (an mtime
    row is the file's LAST update event — if that instant is after T the event
    does not exist yet at T and the row honestly disappears).
    """
    console = _loc(lang, "Console", "Konsole", "Console")
    repo = _loc(lang, "Dépôt (Git)", "Repository (Git)", "Repository (Git)")
    events: list[tuple[datetime, str, str]] = []
    for entry in _load_change_log():
        # Pre-attribution entries carry no agent_id; they were all saves of the
        # single default agent, so they stay visible on it and on it only.
        if str(entry.get("agent_id") or DEFAULT_AGENT_ID) != agent_id:
            continue
        try:
            when = datetime.fromisoformat(str(entry.get("at")))
        except (TypeError, ValueError):
            # best-effort: skip a change-log row with a bad timestamp — non-gating read (0015)
            continue
        keys = [str(k) for k in entry.get("keys", [])]
        labels = ", ".join(_key_label(k, lang) for k in keys) or _loc(
            lang, "configuration", "Konfiguration", "configuration"
        )
        n = len(keys)
        if lang == "de":
            summary = f"{n} Feld{'er' if n > 1 else ''} geaendert: {labels}"
        elif lang == "en":
            summary = f"{n} field{'s' if n > 1 else ''} changed: {labels}"
        else:
            plural = "s" if n > 1 else ""
            summary = f"{n} champ{plural} modifié{plural} : {labels}"
        # ADR 0024/0031 — a save that changes runtime behaviour names its author.
        # Entries from before attribution have no author; honest absence stays silent.
        author = entry.get("author")
        if isinstance(author, str) and author:
            summary += _loc(lang, f" — par {author}", f" - von {author}", f" - by {author}")
        events.append((when, console, summary))
    sources = [
        (
            _ROOT / "src" / "tessera" / "settings.py",
            _loc(
                lang,
                "Paramètres système (settings.py)",
                "Systemeinstellungen (settings.py)",
                "System settings (settings.py)",
            ),
        ),
        (
            policy_path,
            _loc(
                lang,
                "Politique garde-fous (policy.yaml)",
                "Schutzregel-Richtlinie (policy.yaml)",
                "Guardrail policy (policy.yaml)",
            ),
        ),
        (
            _PROMPTS_DIR / "fr.yaml",
            _loc(lang, "Prompts (fr.yaml)", "Prompts (fr.yaml)", "Prompts (fr.yaml)"),
        ),
    ]
    newest_corpus = max(_CORPUS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, default=None)
    if newest_corpus is not None:
        sources.append((newest_corpus, f"Corpus ({newest_corpus.name})"))
    updated = _loc(lang, "mis à jour", "aktualisiert", "updated")
    for path, label in sources:
        if path.exists():
            events.append((_mtime_dt(path), repo, f"{label} {updated}"))
    if until is not None:
        events = [e for e in events if e[0] <= until]
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
    lang: str = "fr",
    *,
    options: list[str] | None = None,
    badge: str | None = None,
) -> dict[str, object]:
    """An editable field bound to a persisted key.

    ``value`` is the canonical (French) stored value; it and the option list are
    localized for display. The frontend posts the localized value back and the
    save endpoint re-canonicalizes it, so the durable store stays stable.
    """
    return {
        "key": key,
        "label": label,
        "value": _value_display(key, value, lang),
        "kind": kind,
        "badge": badge,
        "editable": True,
        "options": options or _value_options(key, lang),
    }


def _slider(
    key: str,
    label: str,
    value: float | None,
    *,
    overridden: bool = False,
    applied: bool = True,
    lang: str = "fr",
) -> dict[str, object]:
    """One sampling slider, honest about its value's provenance (ADR 0031).

    ``value=None`` means UNSET: the parameter is not sent and the backend
    default serves — displayed as such, never as an invented number.
    ``overridden`` says whether a durable override produced the value;
    ``applied`` says whether the serving backend forwards this parameter at all.
    """
    max_v = _SLIDER_MAX[key]
    min_v = _SLIDER_MIN.get(key, 0.0)
    step = _SLIDER_STEP.get(key, _SLIDER_STEP_DEFAULT)
    if value is None:
        display = _loc(lang, "Défaut backend", "Backend-Standard", "Backend default")
        return {
            "key": key,
            "label": label,
            "value": display,
            "min": min_v,
            "max": max_v,
            "step": step,
            "pct": 0,
            "editable": True,
            "unset": True,
            "overridden": False,
            "applied": applied,
        }
    return {
        "key": key,
        "label": label,
        "value": f"{value:.2f}".rstrip("0").rstrip(".").replace(".", ",") or "0",
        "num": value,
        "min": min_v,
        "max": max_v,
        "step": step,
        "pct": round(100 * value / max_v),
        "editable": True,
        "unset": False,
        "overridden": overridden,
        "applied": applied,
    }


def _definition_block(agent_slug: str, lang: str = "fr") -> dict[str, object]:
    """The read-only *definition* (catalogue) this agent binds to.

    Sourced from the governed registry package (``agents.yaml``) — never typed
    free-text. This is the ``define`` half of define/choose/govern: the agent
    *chooses* and *tunes* this definition via the editable instance sections.
    """
    from tessera.agent.registry import get_agent

    try:
        agent = get_agent(agent_slug)
    except KeyError:
        agent = get_agent(DEFAULT_AGENT_ID)
    return {
        "title": _loc(
            lang, "Définition (catalogue)", "Definition (Katalog)", "Definition (catalogue)"
        ),
        "subtitle": _loc(lang, "lecture seule", "schreibgeschuetzt", "read-only"),
        "link": {
            "label": _loc(
                lang,
                "Voir la définition dans CONFIGURER → Paramètres",
                "Definition unter KONFIGURIEREN → Parameter anzeigen",
                "View the definition in CONFIGURE → Parameters",
            ),
            "href": "/configurer/parametres",
        },
        "rows": [
            {
                "label": _loc(lang, "Nom de la définition", "Definitionsname", "Definition name"),
                "value": agent.name,
            },
            {"label": _loc(lang, "Propriétaire", "Eigentuemer", "Owner"), "value": agent.owner},
            {
                "label": _loc(
                    lang, "Modèle de définition", "Definitionsmodell", "Definition model"
                ),
                "value": agent.model,
            },
            {
                "label": _loc(lang, "Langue par défaut", "Standardsprache", "Default language"),
                "value": _lang_label(agent.default_language, lang),
            },
            {
                "label": _loc(
                    lang, "Politique de garde-fous", "Schutzregel-Richtlinie", "Guardrail policy"
                ),
                "value": agent.guardrails,
            },
            {
                "label": _loc(lang, "Jeu d'évaluation", "Evaluierungsset", "Evaluation set"),
                "value": agent.eval_set,
            },
        ],
    }


def _retrieval_block(
    cfg: dict[str, Any], overrides_now: dict[str, Any], lang: str
) -> dict[str, object]:
    """The "Recherche documentaire" panel (ADR 0035): depth slider + rerank toggle."""
    raw = cfg.get("retrieval_top_k")
    num = float(raw) if isinstance(raw, int | float) and not isinstance(raw, bool) else None
    slider = _slider(
        "retrieval_top_k",
        _loc(lang, "Profondeur de recherche", "Suchtiefe", "Search depth"),
        num,
        overridden=overrides_now.get("retrieval_top_k") is not None,
        applied=True,
        lang=lang,
    )
    if num is None:
        slider["unset_label"] = _loc(
            lang,
            "Défaut par recherche (4 produit / 6 réglementaire)",
            "Standard je Suche (4 Produkt / 6 Regulierung)",
            "Per-lookup default (4 product / 6 regulation)",
        )
    rerank_on = bool(cfg.get("retrieval_rerank", True))
    return {
        "title": _loc(lang, "Recherche documentaire", "Dokumentensuche", "Document retrieval"),
        "slider": slider,
        "toggle": {
            "key": "retrieval_rerank",
            "label": _loc(lang, "Reranking (RRF)", "Reranking (RRF)", "Reranking (RRF)"),
            "value": _loc(lang, "Activé", "Aktiviert", "Enabled")
            if rerank_on
            else _loc(lang, "Désactivé", "Deaktiviert", "Disabled"),
            "on": rerank_on,
            "kind": "toggle",
            "badge": None,
            "editable": True,
            "options": [],
        },
        "note": _loc(
            lang,
            "Nombre de documents remis à la synthèse par recherche, et reranking RRF "
            "(fusion lexicale + vectorielle, actif par défaut — vérité historique). "
            "Non défini = défaut historique par recherche. Résolu à chaque tour au "
            "même seam que le modèle — ADR 0035.",
            "Anzahl der pro Suche an die Synthese uebergebenen Dokumente und "
            "RRF-Reranking (lexikalische + vektorielle Fusion, standardmaessig aktiv "
            "- historische Wahrheit). Nicht gesetzt = historischer Standard je Suche. "
            "Pro Turn am selben Seam aufgeloest - ADR 0035.",
            "Documents handed to synthesis per lookup, and RRF reranking (lexical + "
            "vector fusion, on by default - the historical truth). Unset = the "
            "historical per-lookup default. Resolved every turn at the same seam - "
            "ADR 0035.",
        ),
    }


def _memory_block(
    cfg: dict[str, Any], overrides_now: dict[str, Any], settings: Any, lang: str
) -> dict[str, object]:
    """The "Mémoire" panel (ADR 0036): tier select + window slider."""
    org_tier = str(settings.memory.backend)
    org_window = int(settings.memory.history_window)
    select = _edit(
        "memory_backend",
        _loc(lang, "Mémoire (tier)", "Speicher (Tier)", "Memory (tier)"),
        str(cfg.get("memory_backend", "Défaut org")),
        "select",
        lang,
        badge=_loc(lang, f"org : {org_tier}", f"Org: {org_tier}", f"org: {org_tier}"),
    )
    raw = cfg.get("memory_window")
    num = float(raw) if isinstance(raw, int | float) and not isinstance(raw, bool) else None
    slider = _slider(
        "memory_window",
        _loc(lang, "Fenêtre de mémoire", "Speicherfenster", "Memory window"),
        num,
        overridden=overrides_now.get("memory_window") is not None,
        applied=True,
        lang=lang,
    )
    if num is None:
        slider["unset_label"] = _loc(
            lang,
            f"Défaut org ({org_window})",
            f"Org-Standard ({org_window})",
            f"Org default ({org_window})",
        )
    return {
        "title": _loc(lang, "Mémoire", "Speicher", "Memory"),
        "select": select,
        "slider": slider,
        "note": _loc(
            lang,
            "Tier de mémoire (ADR 0007 : fenêtre verbatim / résumé compacté / "
            "persistante inter-sessions) et taille de la fenêtre verbatim, par "
            "agent. Non défini = défaut org (settings). La transcription durable "
            "enregistre tout indépendamment de la fenêtre. Résolu à chaque tour "
            "au même seam — ADR 0036.",
            "Speicher-Tier (ADR 0007: Verbatim-Fenster / kompaktierte "
            "Zusammenfassung / sitzungsuebergreifend persistent) und Groesse des "
            "Verbatim-Fensters, pro Agent. Nicht gesetzt = Org-Standard "
            "(Settings). Das dauerhafte Transkript zeichnet unabhaengig vom "
            "Fenster alles auf. Pro Turn am selben Seam aufgeloest - ADR 0036.",
            "Memory tier (ADR 0007: verbatim window / compacted summary / "
            "cross-session persistent) and verbatim window size, per agent. "
            "Unset = the org default (settings). The durable transcript records "
            "everything regardless of the window. Resolved every turn at the "
            "same seam - ADR 0036.",
        ),
    }


def _escalation_block(
    cfg: dict[str, Any], overrides_now: dict[str, Any], settings: Any, lang: str
) -> dict[str, object]:
    """The "Escalade humaine" panel (ADR 0033): slider + the real formula."""
    org_default = float(settings.guard.escalation_confidence_threshold)
    raw = cfg.get("escalation_threshold")
    num = float(raw) if isinstance(raw, int | float) and not isinstance(raw, bool) else None
    slider = _slider(
        "escalation_threshold",
        _loc(lang, "Seuil d'escalade", "Eskalationsschwelle", "Escalation threshold"),
        num,
        overridden=overrides_now.get("escalation_threshold") is not None,
        applied=True,
        lang=lang,
    )
    if num is None:
        org_display = f"{org_default:.2f}"
        slider["unset_label"] = _loc(
            lang,
            f"Défaut org ({org_display.replace('.', ',')})",
            f"Org-Standard ({org_display.replace('.', ',')})",
            f"Org default ({org_display})",
        )
    return {
        "title": _loc(lang, "Escalade humaine", "Menschliche Eskalation", "Human escalation"),
        "slider": slider,
        "note": _loc(
            lang,
            "Sous ce seuil de confiance, l'agent transmet le tour à un conseiller "
            "humain. Confiance = fondement x 0,5 + couverture x 0,3 + garde-fous x 0,2 "
            "(reviewer déterministe). Non défini = défaut org "
            f"({f'{org_default:.2f}'.replace('.', ',')}, settings). Résolu à chaque "
            "tour au même seam que le modèle — ADR 0033.",
            "Unter dieser Konfidenzschwelle uebergibt der Agent den Turn an einen "
            "menschlichen Berater. Konfidenz = Fundierung x 0,5 + Abdeckung x 0,3 + "
            "Schutzregeln x 0,2 (deterministischer Reviewer). Nicht gesetzt = "
            f"Org-Standard ({f'{org_default:.2f}'.replace('.', ',')}, Settings). Pro "
            "Turn am selben Seam wie das Modell aufgeloest - ADR 0033.",
            "Below this confidence threshold the agent hands the turn to a human "
            "advisor. Confidence = grounding x 0.5 + coverage x 0.3 + guard x 0.2 "
            f"(deterministic reviewer). Unset = org default ({org_default:.2f}, "
            "settings). Resolved every turn at the same seam as the model - ADR 0033.",
        ),
    }


async def _serving_effectiveness(agent_slug: str) -> tuple[str, str, tuple[str, ...], str]:
    """``(effective_model, backend_name, applied slider keys, provenance)`` for one agent.

    The effective model is the ADR 0030 resolution (per-agent override > org
    override > frozen base) and ``provenance`` says which level produced it
    (``"agent"`` / ``"org"`` / ``"base"``); the serving backend and the sampling
    parameters it applies follow from the model (``SAMPLING_APPLIED`` — the
    declaration the unit tests verify against the backends themselves). Imports
    are lazy to keep this observability module import-light (the API layer
    imports us).
    """
    from tessera.api.config_overrides import resolve_chat_model_with_provenance
    from tessera.llm.router import SAMPLING_APPLIED, backend_for_model

    model, provenance = await resolve_chat_model_with_provenance(agent_slug)
    backend = backend_for_model(model if provenance != "base" else None)
    return model, backend.name, SAMPLING_APPLIED.get(backend.name, ()), provenance


def _parse_at(at: str | None) -> datetime | None:
    """The as-of bound if it parses as ISO, else ``None`` (read live, never raise)."""
    if not at:
        return None
    try:
        parsed = datetime.fromisoformat(at.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


async def compute_agent_configurations(
    agent_slug: str = DEFAULT_AGENT_ID, lang: str = "fr", at: str | None = None
) -> dict[str, object]:
    """Return the active agent configuration payload (real + editable overrides).

    ``agent_slug`` is the URL slug of the agent in scope; it scopes the in-page
    navigation links (``/agents/<agent_slug>/...``). It is distinct from the
    internal display id ``agent_id`` (``tessera-assistant-<env>``). ``lang``
    localizes the chrome and the editable option values for display; the durable
    store keeps the canonical French values.

    Async since ADR 0031: the behaviour block derives which sliders the serving
    backend applies from the agent's *effective* model (ADR 0030 override
    resolution — a durable read).

    ``at`` (ISO instant) bounds the OT-01 per-object history at T — the change
    log and provenance events after T leave the list; every other block stays
    live (the acting surface acts on the present; the rail says so).
    """
    settings = get_settings()
    cfg = _effective(agent_slug)
    serving_model, serving_backend, applied_keys, serving_prov = await _serving_effectiveness(
        agent_slug
    )
    overrides_now = _load_overrides(agent_slug)
    # Provenance of the effective model (ADR 0030 §3), said next to the value —
    # the base row and the runtime block must never show two different models.
    prov_label = {
        "agent": _loc(lang, "Override agent", "Agent-Override", "Agent override"),
        "org": _loc(lang, "Override org", "Org-Override", "Org override"),
    }.get(serving_prov, _loc(lang, "Base (config gelée)", "Basis (Konfig)", "Base (frozen config)"))

    def _sampling_slider(key: str, label: str) -> dict[str, object]:
        raw = cfg.get(key)
        num = float(raw) if isinstance(raw, int | float) and not isinstance(raw, bool) else None
        if key == "temperature" and num is None:
            num = RUNTIME_TEMPERATURE_DEFAULT
        return _slider(
            key,
            label,
            num,
            overridden=overrides_now.get(key) is not None,
            applied=key in applied_keys,
            lang=lang,
        )

    profile = settings.resolved_llm_profile()
    fallback_model = (
        settings.openai.models[0] if settings.openai.models else settings.openai.chat_model
    )
    policy = load_policy(settings.guard.policy_path)
    allowed_tool_names = [
        _tool_label(name, lang) for name, tool in policy.tools.items() if tool.allow
    ]
    allowed_tools = len(allowed_tool_names)
    guard_count = len(policy.tools) + len(policy.prompt_injection_deny) + len(policy.pii_patterns)
    prompt_count = _prompt_count()
    knowledge_count = _knowledge_count()
    tool_count = _tool_count()
    settings_updated = _fmt_mtime(_ROOT / "src" / "tessera" / "settings.py")
    # Identifiant = the agent's URL slug (the same id stamped on its data),
    # so the displayed identity matches /agents/<slug>/... and the registry.
    agent_id = agent_slug
    lang_canonical = _canonical_value(
        _LANG_KEY,
        str(
            _load_overrides(agent_slug).get(_LANG_KEY)
            or _lang_label(_registry_default_language(agent_slug, settings))
        ),
    )
    lang_value = _value_display(_LANG_KEY, lang_canonical, lang)
    parallel_on = bool(cfg["parallel_tools"])
    archived = bool(cfg["archived"])
    definition = _definition_block(agent_slug, lang)

    return {
        "title": _loc(lang, "Configurations", "Konfigurationen", "Configurations"),
        "subtitle": _loc(
            lang,
            "Réglages de cet agent : identité, modèle, comportement et statut.",
            "Einstellungen dieses Agenten: Identitaet, Modell, Verhalten und Status.",
            "Settings for this agent: identity, model, behaviour and status.",
        ),
        # define / choose / govern: the registry package (agents.yaml) is the
        # read-only *definition* this agent binds to; the sections below are the
        # editable *instance* overrides. In production every change is governed.
        "definition": definition,
        "governance_banner": _loc(
            lang,
            "Cette configuration s'applique uniquement à cet agent. Toute modification "
            "en environnement de production est gouvernée, versionnée et auditée.",
            "Diese Konfiguration gilt nur fuer diesen Agenten. Jede Aenderung in der "
            "Produktionsumgebung ist gesteuert, versioniert und auditiert.",
            "This configuration applies only to this agent. Any change in the production "
            "environment is governed, versioned and audited.",
        ),
        # In production, changes are load-bearing + regulated: the inline save is
        # replaced by a governed "propose change" flow (RBAC + versioned event +
        # audit via Release Control). Direct inline save stays for local/staging.
        "governed": get_settings().is_production(),
        "actions": {
            "save": _loc(
                lang, "Enregistrer les modifications", "Aenderungen speichern", "Save changes"
            ),
            "saved": _loc(
                lang, "Modifications enregistrées", "Aenderungen gespeichert", "Changes saved"
            ),
            "reset": _loc(lang, "Annuler", "Abbrechen", "Cancel"),
            "more": "...",
            "propose": _loc(
                lang, "Proposer un changement", "Aenderung vorschlagen", "Propose a change"
            ),
        },
        "identity": {
            "title": _loc(lang, "Identité", "Identitaet", "Identity"),
            "left": [
                _edit(
                    "name",
                    _loc(lang, "Nom de l'agent", "Agent-Name", "Agent name"),
                    str(cfg["name"]),
                    "text",
                    lang,
                ),
                _ro(_loc(lang, "Identifiant", "Kennung", "Identifier"), agent_id, "copy"),
                _edit(
                    "description",
                    _loc(lang, "Description", "Beschreibung", "Description"),
                    str(cfg["description"]),
                    "textarea",
                    lang,
                ),
            ],
            "right": [
                _edit(
                    "default_language",
                    _loc(lang, "Langue par défaut", "Standardsprache", "Default language"),
                    lang_canonical,
                    "select",
                    lang,
                ),
                _edit(
                    "timezone",
                    _loc(lang, "Fuseau horaire", "Zeitzone", "Timezone"),
                    str(cfg["timezone"]),
                    "select",
                    lang,
                ),
                _edit(
                    "owner",
                    _loc(lang, "Propriétaire", "Eigentuemer", "Owner"),
                    str(cfg["owner"]),
                    "select",
                    lang,
                ),
            ],
        },
        "model": {
            "title": _loc(lang, "Modèle", "Modell", "Model"),
            "left": [
                # ADR 0030 — the row shows the EFFECTIVE serving model (override
                # resolution included) with its provenance, never the frozen base
                # alone: the base and the runtime block must tell one story.
                _ro(
                    _loc(lang, "Modèle servi (effectif)", "Bedientes Modell", "Serving model"),
                    serving_model,
                    "model",
                    f"{_model_provider(serving_model, profile)} · {prov_label}",
                ),
                _ro(
                    _loc(lang, "Version / Snapshot", "Version / Snapshot", "Version / Snapshot"),
                    _model_snapshot(serving_model),
                    "info",
                ),
            ],
            "right": [
                _ro(
                    _loc(
                        lang,
                        "Modèle de secours (fallback)",
                        "Ersatzmodell (Fallback)",
                        "Fallback model",
                    ),
                    fallback_model,
                    "model",
                    _model_provider(fallback_model, profile),
                ),
                _edit(
                    "fallback_strategy",
                    _loc(lang, "Stratégie de bascule", "Fallback-Strategie", "Fallback strategy"),
                    str(cfg["fallback_strategy"]),
                    "select",
                    lang,
                ),
            ],
            # The model itself is read-only here: it is defined (and approved) in
            # the CONFIGURER model registry, never typed free-text on this page.
            "link": {
                "label": _loc(
                    lang,
                    "Gérer dans le registre des modèles",
                    "Im Modellregister verwalten",
                    "Manage in the model registry",
                ),
                "href": "/configurer/modeles",
            },
        },
        "behavior": {
            "title": _loc(lang, "Comportement", "Verhalten", "Behaviour"),
            # ADR 0032 — each select says HOW it takes effect, next to the
            # control: tone/detail are injected into the system prompt every
            # turn; max length is also a hard cap on the backend call.
            "selects": [
                _edit(
                    "tone",
                    _loc(lang, "Ton", "Ton", "Tone"),
                    str(cfg["tone"]),
                    "select",
                    lang,
                    badge=_loc(
                        lang, "Injecté au prompt", "In den Prompt injiziert", "Injected into prompt"
                    ),
                ),
                _edit(
                    "detail",
                    _loc(lang, "Détail des réponses", "Antwortdetailgrad", "Answer detail"),
                    str(cfg["detail"]),
                    "select",
                    lang,
                    badge=_loc(
                        lang, "Injecté au prompt", "In den Prompt injiziert", "Injected into prompt"
                    ),
                ),
                _edit(
                    "max_length",
                    _loc(
                        lang,
                        "Longueur max des réponses",
                        "Maximale Antwortlaenge",
                        "Max answer length",
                    ),
                    str(cfg["max_length"]),
                    "select",
                    lang,
                    badge="≤ {n} tokens".format(
                        n=_LENGTH_BUDGET_TOKENS.get(
                            str(cfg["max_length"]), _LENGTH_BUDGET_TOKENS["Moyenne"]
                        )
                    ),
                ),
            ],
            "sliders": [
                _sampling_slider(
                    "temperature", _loc(lang, "Température", "Temperatur", "Temperature")
                ),
                _sampling_slider("top_p", "Top P"),
                _sampling_slider("top_k", "Top K"),
                _sampling_slider(
                    "frequency_penalty",
                    _loc(lang, "Pénalité de fréquence", "Frequenzstrafe", "Frequency penalty"),
                ),
                _sampling_slider(
                    "presence_penalty",
                    _loc(lang, "Pénalité de présence", "Praesenzstrafe", "Presence penalty"),
                ),
            ],
            # ADR 0031 — the sliders are effective by construction: resolved per
            # turn at the routing seam and passed to the serving backend. This
            # block says WHICH backend serves this agent (from its ADR 0030
            # effective model) and which parameters that backend applies.
            "runtime": {
                "label": _loc(lang, "Effectivité runtime", "Laufzeitwirkung", "Runtime effect"),
                "model": serving_model,
                "backend": serving_backend,
                "applied": [k for k in _SLIDERS if k in applied_keys],
                "not_applied": [k for k in _SLIDERS if k not in applied_keys],
                "note": _loc(
                    lang,
                    f"Résolus à chaque tour et envoyés au backend {serving_backend} "
                    f"(modèle effectif : {serving_model}). Un curseur non appliqué "
                    "par ce backend est indiqué — jamais envoyé en silence. "
                    "Ton et détail sont injectés dans le prompt système ; la longueur "
                    "max est aussi appliquée en dur (max_output_tokens) — ADR 0032.",
                    f"Pro Turn aufgeloest und an das Backend {serving_backend} gesendet "
                    f"(effektives Modell: {serving_model}). Ein von diesem Backend nicht "
                    "angewendeter Regler wird angezeigt - nie stillschweigend gesendet. "
                    "Ton und Detail werden in den System-Prompt injiziert; die maximale "
                    "Laenge gilt zusaetzlich hart (max_output_tokens) - ADR 0032.",
                    f"Resolved every turn and sent to the {serving_backend} backend "
                    f"(effective model: {serving_model}). A slider this backend does not "
                    "apply is flagged - never silently sent. Tone and detail are injected "
                    "into the system prompt; max length is also enforced hard "
                    "(max_output_tokens) - ADR 0032.",
                ),
            },
            # ADR 0033 — the escalation threshold is an operable, governed
            # knob: unset serves the org settings value (said as such), set is
            # this agent's own bar, resolved per turn at the routing seam and
            # read by the reviewer from the state.
            "escalation": _escalation_block(cfg, overrides_now, settings, lang),
            # ADR 0035 — retrieval depth + reranking, per agent, same seam.
            "retrieval": _retrieval_block(cfg, overrides_now, lang),
            # ADR 0036 — memory tier + window, per agent, same seam.
            "memory": _memory_block(cfg, overrides_now, settings, lang),
            "tools": {
                "label": _loc(lang, "Outils autorisés", "Erlaubte Tools", "Allowed tools"),
                "value": _loc(
                    lang,
                    f"{allowed_tools} sélectionnés",
                    f"{allowed_tools} ausgewaehlt",
                    f"{allowed_tools} selected",
                ),
                "items": allowed_tool_names,
                "href": f"/agents/{agent_slug}/garde-fous",
            },
            "note": _loc(
                lang,
                "Les paramètres du modèle et du comportement s'appliquent à "
                "l'environnement de production.",
                "Die Modell- und Verhaltensparameter gelten fuer die " "Produktionsumgebung.",
                "The model and behaviour parameters apply to the production " "environment.",
            ),
        },
        "routing": {
            "title": _loc(
                lang,
                "Routage & Orchestration",
                "Routing & Orchestrierung",
                "Routing & Orchestration",
            ),
            "left": [
                _edit(
                    "routing_strategy",
                    _loc(lang, "Stratégie de routage", "Routing-Strategie", "Routing strategy"),
                    str(cfg["routing_strategy"]),
                    "select",
                    lang,
                ),
                _ro(
                    _loc(
                        lang, "Timeout réponse (s)", "Antwort-Timeout (s)", "Response timeout (s)"
                    ),
                    str(int(settings.api.request_timeout_seconds / 2)),
                    "info",
                ),
            ],
            "right": [
                _ro(
                    _loc(lang, "Nombre max d'itérations", "Max. Iterationen", "Max iterations"),
                    str(settings.memory.history_window + 2),
                    "info",
                ),
                {
                    "key": "parallel_tools",
                    "label": _loc(
                        lang,
                        "Exécution parallèle d'outils",
                        "Parallele Tool-Ausfuehrung",
                        "Parallel tool execution",
                    ),
                    "value": _loc(lang, "Activé", "Aktiviert", "Enabled")
                    if parallel_on
                    else _loc(lang, "Désactivée", "Deaktiviert", "Disabled"),
                    "on": parallel_on,
                    "kind": "toggle",
                    "badge": None,
                    "editable": True,
                    "options": [],
                },
            ],
        },
        "tags": {
            "title": _loc(lang, "Tags & Métadonnées", "Tags & Metadaten", "Tags & Metadata"),
            "tags": list(cfg["tags"]),
            "add_tag": _loc(lang, "Ajouter un tag", "Tag hinzufuegen", "Add a tag"),
            "metadata_label": _loc(lang, "Métadonnées", "Metadaten", "Metadata"),
            "metadata": _loc(lang, "Aucune métadonnée", "Keine Metadaten", "No metadata"),
            "add_metadata": _loc(lang, "Ajouter", "Hinzufuegen", "Add"),
            # Honest provenance: no invented author. "created" = the repo config
            # baseline; "modified" = the real last override save (or defaults).
            "created": _loc(
                lang,
                "Profil issu du dépôt (settings.py + policy.yaml + prompts)",
                "Profil aus dem Repository (settings.py + policy.yaml + Prompts)",
                "Profile from the repository (settings.py + policy.yaml + prompts)",
            ),
            "modified": (
                _loc(
                    lang,
                    f"Dernière sauvegarde via la console le {_fmt_mtime(_state_path())}",
                    f"Letzte Speicherung ueber die Konsole am {_fmt_mtime(_state_path())}",
                    f"Last saved via the console on {_fmt_mtime(_state_path())}",
                )
                if _state_path().exists()
                else _loc(
                    lang,
                    "Valeurs par défaut - aucune surcharge enregistrée",
                    "Standardwerte - keine Ueberschreibung gespeichert",
                    "Default values - no override saved",
                )
            ),
            "archive": _loc(
                lang, "Désarchiver cet agent", "Agent dearchivieren", "Unarchive this agent"
            )
            if archived
            else _loc(lang, "Archiver cet agent", "Agent archivieren", "Archive this agent"),
            "archived": archived,
        },
        "status": {
            "title": _loc(lang, "Statut de l'agent", "Agent-Status", "Agent status"),
            "badge": _loc(lang, "Archivé", "Archiviert", "Archived")
            if archived
            else _loc(lang, "Actif", "Aktiv", "Active"),
            "badge_tone": "crit" if archived else "good",
            "rows": [
                {
                    "label": _loc(lang, "Environnement", "Umgebung", "Environment"),
                    "value": settings.environment.value.title(),
                    "badge": True,
                },
                {
                    # `live` tells the frontend to replace this with the real
                    # /readyz probe (is the chat backend actually reachable);
                    # archived agents are never probed.
                    "label": _loc(lang, "Statut", "Status", "Status"),
                    "value": _loc(lang, "Archivé", "Archiviert", "Archived")
                    if archived
                    else _loc(lang, "En ligne", "Online", "Online"),
                    "online": not archived,
                    "live": not archived,
                },
                {
                    "label": _loc(
                        lang, "Config modifiée le", "Konfig geaendert am", "Config changed on"
                    ),
                    "value": settings_updated,
                },
                {
                    "label": _loc(lang, "Source", "Quelle", "Source"),
                    "value": _loc(
                        lang, "settings.py (dépôt)", "settings.py (Repo)", "settings.py (repo)"
                    ),
                    "info": True,
                },
            ],
        },
        "active_model": {
            "title": _loc(lang, "Modèle actif", "Aktives Modell", "Active model"),
            # Same rule as the Modèle section: the EFFECTIVE serving model with
            # its provenance — one story across every surface of this page.
            "name": serving_model,
            "provider": f"{_model_provider(serving_model, profile)} · {prov_label}",
            "rows": [
                {
                    "label": _loc(lang, "Snapshot", "Snapshot", "Snapshot"),
                    "value": _model_snapshot(serving_model),
                },
                {
                    "label": _loc(lang, "Contexte max", "Max. Kontext", "Max context"),
                    "value": _context_window(serving_model),
                },
            ],
        },
        "summary": {
            "title": _loc(lang, "Résumé", "Zusammenfassung", "Summary"),
            "rows": [
                {"label": _loc(lang, "Langue", "Sprache", "Language"), "value": str(lang_value)},
                {
                    "label": _loc(lang, "Ton", "Ton", "Tone"),
                    "value": _value_display("tone", str(cfg["tone"]), lang),
                },
                {
                    "label": _loc(lang, "Detail", "Detail", "Detail"),
                    "value": _value_display("detail", str(cfg["detail"]), lang),
                },
                {
                    "label": _loc(lang, "Outils autorisés", "Erlaubte Tools", "Allowed tools"),
                    "value": str(tool_count),
                },
                {
                    "label": _loc(
                        lang, "Garde-fous actifs", "Aktive Schutzregeln", "Active guardrails"
                    ),
                    "value": str(guard_count),
                },
                {
                    "label": _loc(lang, "Prompts actifs", "Aktive Prompts", "Active prompts"),
                    "value": str(prompt_count),
                },
                {
                    "label": _loc(
                        lang,
                        "Connaissances rattachées",
                        "Verknuepftes Wissen",
                        "Attached knowledge",
                    ),
                    "value": _loc(
                        lang,
                        f"{knowledge_count} sources",
                        f"{knowledge_count} Quellen",
                        f"{knowledge_count} sources",
                    ),
                },
            ],
        },
        "history": {
            "title": _loc(
                lang, "Historique des modifications", "Aenderungsverlauf", "Change history"
            ),
            "cta": _loc(lang, "Voir tout", "Alle anzeigen", "View all"),
            "items": _build_history(
                settings.guard.policy_path, lang, agent_slug, until=_parse_at(at)
            ),
        },
        "links": {
            "title": _loc(lang, "Liens utiles", "Nuetzliche Links", "Useful links"),
            "items": [
                {
                    "title": _loc(
                        lang, "Sources & mémoire", "Quellen & Speicher", "Sources & memory"
                    ),
                    "desc": _loc(
                        lang,
                        "Gérer le catalogue des sources et la mémoire partagée",
                        "Quellenkatalog und gemeinsamen Speicher verwalten",
                        "Manage the source catalogue and shared memory",
                    ),
                    "href": "/configurer/sources-memoire",
                },
                {
                    "title": _loc(lang, "Garde-fous", "Schutzregeln", "Guardrails"),
                    "desc": _loc(
                        lang,
                        "Voir les politiques de garde-fou appliquées à cet agent",
                        "Auf diesen Agenten angewandte Schutzregeln anzeigen",
                        "View the guardrail policies applied to this agent",
                    ),
                    "href": f"/agents/{agent_slug}/garde-fous",
                },
                {
                    "title": _loc(lang, "Prompts", "Prompts", "Prompts"),
                    "desc": _loc(
                        lang,
                        "Gérer les prompts de cet agent",
                        "Prompts dieses Agenten verwalten",
                        "Manage this agent's prompts",
                    ),
                    "href": f"/agents/{agent_slug}/prompts",
                },
            ],
        },
    }
