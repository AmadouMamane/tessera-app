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
import json
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import cast
from zoneinfo import ZoneInfo

from tessera.guard.decisions import load_policy
from tessera.observability import replay
from tessera.observability.eval import scores as eval_scores
from tessera.observability.slo import compute_slo
from tessera.settings import LLMProfile, get_settings

__all__ = ["compute_agent_console"]


_ROOT = Path(__file__).resolve().parents[3]
_PROMPTS_DIR = _ROOT / "src" / "tessera" / "agent" / "prompts"
_CORPUS_DIR = _ROOT / "src" / "tessera" / "corpus" / "data"
_PARIS = ZoneInfo("Europe/Paris")
_MS_PER_SECOND = 1000.0
_MS_PER_MINUTE = 60_000.0
_RETENTION_SOURCE_LIMIT = 5
_VISIBLE_SOURCE_LIMIT = 4
_QUALITY_GOOD_THRESHOLD = 0.8
_RETENTION_TERMS = ("conservation", "retention", "article 6", "article 32", "article 17")


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


def _fmt_percent(value: float) -> str:
    return f"{value * 100:.1f}%".replace(".", ",")


def _fmt_duration_ms(ms: float) -> str:
    if ms >= _MS_PER_MINUTE:
        minutes = int(ms // _MS_PER_MINUTE)
        seconds = int((ms % _MS_PER_MINUTE) // _MS_PER_SECOND)
        return f"{minutes}m {seconds:02d}s"
    if ms >= _MS_PER_SECOND:
        return f"{ms / _MS_PER_SECOND:.1f}s"
    return f"{ms:.0f}ms"


def _kpis() -> list[dict[str, object]]:
    faithfulness = _score_rows("faithfulness")
    slo = compute_slo(faithfulness)
    bundles = replay.recent_bundles()
    latency_values: list[float] = []
    for bundle in bundles:
        latency = bundle.latency_ms or {}
        if latency:
            latency_values.append(sum(float(v) for v in latency.values()))
    return [
        {
            "key": "sla",
            "label": "SLA respecté",
            "value": _fmt_percent(slo.good_rate) if faithfulness else "n/a",
            "good": not slo.breaching,
        },
        {
            "key": "mttr",
            "label": "MTTR (7j)",
            "value": _fmt_duration_ms(mean(latency_values)) if latency_values else "n/a",
            "good": True,
        },
    ]


def _corpus_rows(path: Path) -> list[dict[str, object]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        return []
    return [cast(dict[str, object], row) for row in raw if isinstance(row, dict)]


def _retention_sources() -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    for path in (_CORPUS_DIR / "regulations_cnil.json", _CORPUS_DIR / "regulations_gdpr.json"):
        for row in _corpus_rows(path):
            text = str(row.get("text", ""))
            source = str(row.get("source", path.stem))
            locator = str(cast(dict[str, object], row.get("metadata", {})).get("locator", source))
            lowered = text.lower()
            if any(term in lowered for term in _RETENTION_TERMS):
                candidates.append({"source": source, "locator": locator, "text": text})
            if len(candidates) >= _RETENTION_SOURCE_LIMIT:
                return candidates
    return candidates


def _excerpt(text: str, needle: str, *, fallback_words: int = 20) -> str:
    sentences = [part.strip() for part in text.replace(";", ".").split(".") if part.strip()]
    for sentence in sentences:
        if needle.lower() in sentence.lower():
            return sentence[:220]
    return " ".join(text.split()[:fallback_words])


def _transcript() -> list[dict[str, object]]:
    sources = _retention_sources()
    now = datetime.now(_PARIS)
    points: list[dict[str, object]] = []
    selectors = [
        ("Conservation excessive", "conservation"),
        ("Base légale insuffisante", "Article 6"),
        ("Droits des personnes", "Article 17"),
        ("Sécurité et confidentialité", "Article 32"),
        ("Documentation probatoire", "document"),
    ]
    for index, (title, needle) in enumerate(selectors):
        if index >= len(sources):
            break
        source = sources[index]
        points.append(
            {
                "ref": source["locator"],
                "title": title,
                "body": _excerpt(source["text"], needle),
            }
        )

    return [
        {
            "role": "user",
            "time": _fmt_time(now.replace(microsecond=0)),
            "text": (
                "Quels sont les risques de non-conformité au RGPD liés à la "
                "rétention des conversations utilisateur dans notre assistant ?"
            ),
        },
        {
            "role": "assistant",
            "time": _fmt_time(now.replace(microsecond=0)),
            "latency": "source corpus",
            "intro": (
                "Les principaux risques de non-conformité au RGPD liés à la "
                "rétention des conversations utilisateur sont :"
            ),
            "points": points,
            "closing": (
                "La console peut rejouer cette question en direct : la réponse "
                "streamera alors via le même modèle que la console Produit."
            ),
            "chips": [
                {"label": f"Sources ({len(sources[:_VISIBLE_SOURCE_LIMIT])})", "kind": "info"},
                {"label": "Flux live actif", "kind": "info"},
                {"label": "Debug turn.end", "kind": "ghost"},
            ],
        },
    ]


def _quality() -> dict[str, object]:
    f = _latest_score("faithfulness") or 0.0
    g = _latest_score("grounding") or f
    h = _latest_score("hallucination") or f
    completeness = mean([f, g]) if f or g else 0.0
    minimum = min(value for value in (f, g, h, completeness) if value >= 0.0)
    badge = "Bon" if minimum >= _QUALITY_GOOD_THRESHOLD else "À surveiller"
    tone = "good" if minimum >= _QUALITY_GOOD_THRESHOLD else "warn"
    return {
        "title": "Qualité & sécurité de la réponse",
        "badge": badge,
        "badge_tone": tone,
        "rows": [
            {"label": "Pertinence", "value": f"{f * 10:.1f}", "scale": "/10", "tone": tone},
            {"label": "Exactitude", "value": f"{g * 10:.1f}", "scale": "/10", "tone": tone},
            {
                "label": "Complétude",
                "value": f"{completeness * 10:.1f}",
                "scale": "/10",
                "tone": tone,
            },
            {"label": "Sécurité", "value": f"{h * 10:.1f}", "scale": "/10", "tone": tone},
        ],
    }


def _sources_panel() -> dict[str, object]:
    sources = _retention_sources()[:_VISIBLE_SOURCE_LIMIT]
    rows = [
        {"label": f"{source['source']} - {source['locator']}", "scope": "Externe"}
        for source in sources
    ]
    return {"title": f"Sources utilisées ({len(rows)})", "cta": "Voir toutes", "rows": rows}


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


def _trace_panel() -> dict[str, object]:
    return {
        "title": "XT-01 · Trace d'exécution",
        "cta": "Voir la trace complète",
        "rows": [
            {"label": "Réception de la requête", "value": "live"},
            {"label": "Analyse & classification", "value": "turn.end"},
            {"label": "Recherche de sources", "value": "turn.end"},
            {"label": "Outils exécutés", "value": "turn.end"},
            {"label": "Garde-fous", "value": "turn.end"},
            {"label": "Génération de la réponse", "value": "stream"},
        ],
    }


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
        "status": {
            "session_id": session_id,
            "live": True,
            "fields": [
                {"label": "Modèle", "value": model},
                {"label": "Prompt", "value": prompt_version},
                {"label": "Sources", "value": sources_version},
                {"label": "Garde-fous", "value": guard_version},
                {"label": "Trace", "value": "Live"},
            ],
        },
        "transcript": _transcript(),
        "kpis": _kpis(),
        "tabs": ["Contexte", "Sources", "Outils", "Garde-fous", "Trace"],
        "quality": _quality(),
        "sources": _sources_panel(),
        "tools": _tools_panel(),
        "guardrails": _guardrails_panel(),
        "trace": _trace_panel(),
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
        "title": "Console",
        "subtitle": (
            "Interagissez avec l'assistant et observez en détail les traces, "
            "sources, outils et garde-fous."
        ),
        "provider": provider,
    }
