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
from tessera.observability.knowledge import _LANG_IDX, _norm_lang
from tessera.settings import LLMProfile, get_settings

__all__ = ["compute_agent_console"]

# Localized free-text (fr, de, en). Proper nouns (Tessera, Prompt/Sources labels
# that double as tab keys are localized below) handled explicitly.
_TR: dict[str, tuple[str, str, str]] = {
    "ep_title": ("Évaluation automatique", "Automatische Bewertung", "Automatic evaluation"),
    "ep_note": (
        "Dernier run d'évaluation — la console ne ré-évalue pas chaque tour.",
        "Letzter Bewertungslauf - die Konsole bewertet nicht jeden Tour neu.",
        "Latest evaluation run - the console does not re-evaluate each turn.",
    ),
    "ep_cta": ("Voir les évaluations", "Bewertungen ansehen", "View evaluations"),
    "m_faith": ("Fidélité", "Treue", "Faithfulness"),
    "m_ground": ("Ancrage", "Verankerung", "Grounding"),
    "m_hallu": ("Hallucination", "Halluzination", "Hallucination"),
    "tool_allowed": ("Autorisé", "Erlaubt", "Allowed"),
    "tools_title": (
        "Outils disponibles ({n})",
        "Verfuegbare Tools ({n})",
        "Available tools ({n})",
    ),
    "gd_deny_detail": (
        "Patterns deny chargés depuis la policy runtime.",
        "Deny-Patterns aus der Laufzeit-Policy geladen.",
        "Deny patterns loaded from the runtime policy.",
    ),
    "gd_pii_detail": (
        "Patterns PII chargés depuis la policy runtime.",
        "PII-Patterns aus der Laufzeit-Policy geladen.",
        "PII patterns loaded from the runtime policy.",
    ),
    "gd_title": (
        "Garde-fous chargés ({n})",
        "Geladene Guardrails ({n})",
        "Loaded guardrails ({n})",
    ),
    "lbl_guard": ("Garde-fous", "Guardrails", "Guardrails"),
    "tab_tools": ("Outils", "Tools", "Tools"),
    "tab_eval": ("Évaluation", "Bewertung", "Evaluation"),
    "footer_started": (
        "Session ouverte à {t}",
        "Sitzung geoeffnet um {t}",
        "Session opened at {t}",
    ),
    "lang_name": ("Français", "Deutsch", "English"),
    "placeholder": (
        "Posez votre question à l'assistant...",
        "Stellen Sie Ihre Frage an den Assistenten...",
        "Ask the assistant your question...",
    ),
    "fb_useful": ("Utile", "Nuetzlich", "Useful"),
    "fb_notuseful": ("Pas utile", "Nicht nuetzlich", "Not useful"),
    "fa_replay": ("Rejouer cette session", "Diese Sitzung wiederholen", "Replay this session"),
    "fa_compare": (
        "Comparer à la version actuelle",
        "Mit aktueller Version vergleichen",
        "Compare to current version",
    ),
    "fa_export": ("Exporter la session", "Sitzung exportieren", "Export session"),
    "fa_close": ("Clôturer la session", "Sitzung schliessen", "Close session"),
    "timeline_incidents": ("Timeline incidents", "Vorfall-Timeline", "Incident timeline"),
    "new_session": ("Nouvelle session", "Neue Sitzung", "New session"),
    "replay": ("Relire à T", "Bei T abspielen", "Replay at T"),
    "title": ("Conversation de test", "Testkonversation", "Test conversation"),
    "subtitle": (
        "Interagissez avec l'assistant et observez en détail les traces, "
        "sources, outils et garde-fous.",
        "Interagieren Sie mit dem Assistenten und beobachten Sie Traces, Quellen, "
        "Tools und Guardrails im Detail.",
        "Interact with the assistant and observe traces, sources, tools and "
        "guardrails in detail.",
    ),
}


def _t(key: str, lang: str) -> str:
    return _TR[key][_LANG_IDX.get(lang, 0)]


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


def _evaluation_panel(lang: str) -> dict[str, object]:
    """Latest *real* automated-eval metrics for this agent (honest, not per-turn).

    The console does not re-run the evaluation harness on each turn, so this
    block surfaces the metrics from the latest durable eval run (the same source
    that feeds the Évaluations page), each labelled distinctly. When a metric has
    no recorded score it renders an honest empty value (``None``) rather than a
    fabricated number.
    """
    metrics = (
        (_t("m_faith", lang), "faithfulness"),
        (_t("m_ground", lang), "grounding"),
        (_t("m_hallu", lang), "hallucination"),
    )
    rows: list[dict[str, object]] = []
    for label, key in metrics:
        value = _latest_score(key)
        rows.append({"label": label, "value": None if value is None else f"{value:.2f}"})
    return {
        "title": _t("ep_title", lang),
        "note": _t("ep_note", lang),
        "cta": _t("ep_cta", lang),
        "available": any(row["value"] is not None for row in rows),
        "rows": rows,
    }


def _tools_panel(lang: str) -> dict[str, object]:
    policy = load_policy(get_settings().guard.policy_path)
    rows = [
        {"name": name, "status": _t("tool_allowed", lang), "tone": "good", "latency": "policy"}
        for name, rule in policy.tools.items()
        if rule.allow
    ][:3]
    return {"title": _t("tools_title", lang).format(n=len(rows)), "rows": rows}


def _guardrails_panel(lang: str) -> dict[str, object]:
    policy = load_policy(get_settings().guard.policy_path)
    rows = [
        {
            "name": "Prompt Injection Deny",
            "status": str(len(policy.prompt_injection_deny)),
            "tone": "warn",
            "detail": _t("gd_deny_detail", lang),
        },
        {
            "name": "PII Output Guard",
            "status": str(len(policy.pii_patterns)),
            "tone": "warn",
            "detail": _t("gd_pii_detail", lang),
        },
    ]
    return {"title": _t("gd_title", lang).format(n=len(rows)), "rows": rows}


def compute_agent_console(lang: str = "fr") -> dict[str, object]:
    """Return the Console (Debug) payload from live settings and source files."""
    lang = _norm_lang(lang)
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
        # Provenance strip atop the central "Résumé de la réponse" column
        # (normative 05): the lineage versions the answer was produced with —
        # prompt bundle, corpus snapshot, guard policy. The environment ("Sandbox")
        # and the model are deliberately NOT echoed here: the top sandbox bar owns
        # the live model selection and the Debug tab echoes the effective config,
        # so repeating a *static* model here was both redundant and stale.
        "context": {
            "session_id": session_id,
            "fields": [
                {"label": "Prompt", "value": prompt_version},
                {"label": "Sources", "value": sources_version},
                {"label": _t("lbl_guard", lang), "value": guard_version},
            ],
        },
        # Stable keys: the frontend gates panel content on these exact strings and
        # maps them to localized labels for display. Do NOT localize here.
        "tabs": ["Sources", "Outils", "Garde-fous", "Évaluation"],
        # Response-specific panels (quality / sources used / trace) are NOT seeded:
        # before a turn there is no response to summarise, so the frontend renders
        # an honest awaiting state. Only the configuration panels below are real
        # pre-turn (loaded tools / guardrails from the policy) + the latest eval run.
        "tools": _tools_panel(lang),
        "guardrails": _guardrails_panel(lang),
        "evaluation": _evaluation_panel(lang),
        "footer": {
            "started": _t("footer_started", lang).format(t=_fmt_time(now)),
            "live": True,
            "context": "Plateforme Tessera",
            "language": _t("lang_name", lang),
            "session_id": session_id,
        },
        "actions": {
            "input_placeholder": _t("placeholder", lang),
            "feedback": [_t("fb_useful", lang), _t("fb_notuseful", lang)],
            "footer_actions": [
                {"key": "replay", "label": _t("fa_replay", lang)},
                {"key": "compare", "label": _t("fa_compare", lang)},
                {"key": "export", "label": _t("fa_export", lang)},
                {"key": "close", "label": _t("fa_close", lang)},
            ],
            "timeline_incidents": _t("timeline_incidents", lang),
            "new_session": _t("new_session", lang),
            "replay": _t("replay", lang),
        },
        "title": _t("title", lang),
        "subtitle": _t("subtitle", lang),
        "provider": provider,
    }
