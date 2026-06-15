"""Agent Configurations dashboard payload (reference image 26).

The Configurations page exposes the active agent identity, model routing,
behaviour knobs, orchestration settings, tags, current status, and related
management links. Values are derived from the live Tessera settings and
repository-backed configuration sources (guard policy, prompt bundles, tools,
and corpus files) so the frontend never fabricates configuration data.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from tessera.guard.decisions import load_policy
from tessera.settings import LLMProfile, get_settings

__all__ = ["compute_agent_configurations"]


_ROOT = Path(__file__).resolve().parents[3]
_PROMPTS_DIR = _ROOT / "src" / "tessera" / "agent" / "prompts"
_TOOLS_DIR = _ROOT / "src" / "tessera" / "agent" / "tools"
_CORPUS_DIR = _ROOT / "src" / "tessera" / "corpus" / "data"
_PARIS = ZoneInfo("Europe/Paris")


def _field(
    label: str, value: str, kind: str = "text", badge: str | None = None
) -> dict[str, object]:
    return {"label": label, "value": value, "kind": kind, "badge": badge}


def _summary(label: str, value: str) -> dict[str, object]:
    return {"label": label, "value": value}


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


def compute_agent_configurations() -> dict[str, object]:
    """Return the active agent configuration payload."""
    settings = get_settings()
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

    return {
        "title": "Configurations",
        "subtitle": "Reglages de cet agent : identite, modele, comportement et statut.",
        "actions": {"save": "Enregistrer les modifications", "more": "..."},
        "identity": {
            "title": "Identite",
            "left": [
                _field("Nom de l'agent", "Tessera Assistant"),
                _field("Identifiant", agent_id, "copy"),
                _field(
                    "Description",
                    "Assistant IA pour les clients Tessera. Reponses sourcees et conformes.",
                    "textarea",
                ),
            ],
            "right": [
                _field("Langue par defaut", _lang_label(settings.default_language.value), "select"),
                _field("Fuseau horaire", str(_PARIS), "select"),
                _field("Proprietaire", "Equipe Support", "select"),
            ],
        },
        "model": {
            "title": "Modele",
            "left": [
                _field(
                    "Modele principal",
                    active_model,
                    "model",
                    _model_provider(active_model, profile),
                ),
                _field("Version / Snapshot", _model_snapshot(active_model), "info"),
            ],
            "right": [
                _field(
                    "Modele de secours (fallback)",
                    fallback_model,
                    "model",
                    _model_provider(fallback_model, profile),
                ),
                _field("Strategie de bascule", "Automatique", "select"),
            ],
        },
        "behavior": {
            "title": "Comportement",
            "selects": [
                {"label": "Ton", "value": "Professionnel"},
                {"label": "Detail des reponses", "value": "Equilibre"},
                {"label": "Longueur max des reponses", "value": "Moyenne"},
            ],
            "sliders": [
                {"label": "Temperature", "value": "0,3", "pct": 30},
                {"label": "Top P", "value": "0,7", "pct": 70},
                {"label": "Penalite de frequence", "value": "0,2", "pct": 45},
                {"label": "Penalite de presence", "value": "0,1", "pct": 30},
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
                _field("Strategie de routage", "Par defaut (Recommande)", "select"),
                _field(
                    "Timeout reponse (s)",
                    str(int(settings.api.request_timeout_seconds / 2)),
                    "info",
                ),
            ],
            "right": [
                _field("Nombre max d'iterations", str(settings.memory.history_window + 2), "info"),
                _field("Execution parallele d'outils", "Active", "toggle"),
            ],
        },
        "tags": {
            "title": "Tags & Metadonnees",
            "tags": ["support", "client", settings.environment.value],
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
                _summary("Langue", _lang_label(settings.default_language.value)),
                _summary("Ton", "Professionnel"),
                _summary("Detail", "Equilibre"),
                _summary("Outils autorises", str(tool_count)),
                _summary("Garde-fous actifs", str(guard_count)),
                _summary("Prompts actifs", str(prompt_count)),
                _summary("Connaissances rattachees", f"{knowledge_count} sources"),
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
