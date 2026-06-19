"""Agent Console (Debug) payload (reference image agent-console-normative).

The endpoint exposes the operator-facing debug context for the live chat
console. Static-looking labels are still derived from source-of-truth files:
runtime settings, guard policy, prompt/corpus files, and durable eval/replay
telemetry. The chat itself streams through the same `/chat` route as the client
product console; debug details for each turn are attached to the SSE final
envelope by `tessera.api.routes.chat`.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from tessera.guard.decisions import load_policy
from tessera.observability.eval import scores as eval_scores
from tessera.settings import LLMProfile, get_settings

__all__ = ["compute_agent_console"]


_ROOT = Path(__file__).resolve().parents[3]
_PROMPTS_DIR = _ROOT / "src" / "tessera" / "agent" / "prompts"
_CORPUS_DIR = _ROOT / "src" / "tessera" / "corpus" / "data"
_PARIS = ZoneInfo("Europe/Paris")


def _mtime(path: Path) -> datetime:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=_PARIS)
    except FileNotFoundError:
        return datetime.now(_PARIS)


def _fmt_time(dt: datetime) -> str:
    return dt.strftime("%H:%M:%S")


def _version(path: Path, *, prefix: str = "v") -> str:
    digest = hashlib.sha256(path.read_bytes() if path.exists() else str(path).encode()).hexdigest()
    stamp = _mtime(path)
    return f"{prefix}{stamp.month}.{stamp.day}.{int(digest[:2], 16) % 10}"


def _active_model() -> tuple[str, str]:
    settings = get_settings()
    profile = settings.resolved_llm_profile()
    if profile is LLMProfile.ON_PREM:
        return settings.ollama.chat_model, "Ollama"
    return settings.vertex.chat_model, "Vertex AI"


def _score_rows(metric: str) -> list[float]:
    rows = eval_scores.recent_scores()
    values: list[float] = []
    for row in rows:
        if row.get("metric") != metric:
            continue
        raw = row.get("score")
        if isinstance(raw, int | float):
            values.append(float(raw))
    return values


def _latest_score(metric: str) -> float | None:
    values = _score_rows(metric)
    return values[-1] if values else None


def _evaluation_panel() -> dict[str, object]:
    """Latest *real* automated-eval metrics for this agent (honest, not per-turn).

    The console does not re-run the evaluation harness on each turn, so this
    block surfaces the metrics from the latest durable eval run (the same source
    that feeds the Évaluations page), each labelled distinctly. When a metric has
    no recorded score it renders an honest empty value (``None``) rather than a
    fabricated number.
    """
    metrics = (
        ("Fidélité", "faithfulness"),
        ("Ancrage", "grounding"),
        ("Hallucination", "hallucination"),
    )
    rows: list[dict[str, object]] = []
    for label, key in metrics:
        value = _latest_score(key)
        rows.append({"label": label, "value": None if value is None else f"{value:.2f}"})
    return {
        "title": "Évaluation automatique",
        "note": "Dernier run d'évaluation — la console ne ré-évalue pas chaque tour.",
        "cta": "Voir les évaluations",
        "available": any(row["value"] is not None for row in rows),
        "rows": rows,
    }


def _tools_panel() -> dict[str, object]:
    policy = load_policy(get_settings().guard.policy_path)
    rows = [
        {"name": name, "status": "Autorisé", "tone": "good", "latency": "policy"}
        for name, rule in policy.tools.items()
        if rule.allow
    ][:3]
    return {"title": f"Outils disponibles ({len(rows)})", "rows": rows}


def _guardrails_panel() -> dict[str, object]:
    policy = load_policy(get_settings().guard.policy_path)
    rows = [
        {
            "name": "Prompt Injection Deny",
            "status": str(len(policy.prompt_injection_deny)),
            "tone": "warn",
            "detail": "Patterns deny chargés depuis la policy runtime.",
        },
        {
            "name": "PII Output Guard",
            "status": str(len(policy.pii_patterns)),
            "tone": "warn",
            "detail": "Patterns PII chargés depuis la policy runtime.",
        },
    ]
    return {"title": f"Garde-fous chargés ({len(rows)})", "rows": rows}


def compute_agent_console() -> dict[str, object]:
    """Return the Console (Debug) payload from live settings and source files."""
    settings = get_settings()
    model, provider = _active_model()
    prompt_path = _PROMPTS_DIR / f"{settings.default_language.value}.yaml"
    policy_path = settings.guard.policy_path
    newest_corpus = max(
        (_mtime(path) for path in _CORPUS_DIR.glob("*.json")),
        default=_mtime(_CORPUS_DIR),
    )
    prompt_version = _version(prompt_path)
    sources_version = f"snapshot {len(list(_CORPUS_DIR.glob('*.json')))}.{newest_corpus.month}"
    guard_version = _version(policy_path)
    session_seed = f"{model}:{prompt_version}:{sources_version}:{guard_version}"
    session_id = f"sess_{hashlib.sha256(session_seed.encode()).hexdigest()[:8]}"
    now = datetime.now(_PARIS)

    return {
        # Context strip atop the central "Résumé de la réponse" column (normative
        # 05). The console is the debug/sandbox surface (ui-contract: env=debug),
        # so "Sandbox" is the real environment; the rest is derived from the live
        # settings + source files (model, prompt/corpus/policy versions).
        "context": {
            "session_id": session_id,
            "fields": [
                {"label": "Environnement", "value": "Sandbox"},
                {"label": "Modèle", "value": model},
                {"label": "Prompt", "value": prompt_version},
                {"label": "Sources", "value": sources_version},
                {"label": "Garde-fous", "value": guard_version},
            ],
        },
        "tabs": ["Sources", "Outils", "Garde-fous", "Évaluation"],
        # Response-specific panels (quality / sources used / trace) are NOT seeded:
        # before a turn there is no response to summarise, so the frontend renders
        # an honest awaiting state. Only the configuration panels below are real
        # pre-turn (loaded tools / guardrails from the policy) + the latest eval run.
        "tools": _tools_panel(),
        "guardrails": _guardrails_panel(),
        "evaluation": _evaluation_panel(),
        "footer": {
            "started": f"Session ouverte à {_fmt_time(now)}",
            "live": True,
            "context": "Plateforme Tessera",
            "language": "Français",
            "session_id": session_id,
        },
        "actions": {
            "input_placeholder": "Posez votre question à l'assistant...",
            "feedback": ["Utile", "Pas utile"],
            "footer_actions": [
                {"key": "replay", "label": "Rejouer cette session"},
                {"key": "compare", "label": "Comparer à la version actuelle"},
                {"key": "export", "label": "Exporter la session"},
                {"key": "close", "label": "Clôturer la session"},
            ],
            "timeline_incidents": "Timeline incidents",
            "new_session": "Nouvelle session",
            "replay": "Relire à T",
        },
        "title": "Conversation de test",
        "subtitle": (
            "Interagissez avec l'assistant et observez en détail les traces, "
            "sources, outils et garde-fous."
        ),
        "provider": provider,
    }
