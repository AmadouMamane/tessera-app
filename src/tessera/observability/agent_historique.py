"""Agent Session History ("Historique des sessions") payload (reference image 30).

The Historique page analyses conversation sessions, their quality and their
compliance: an inner tab strip, a KPI strip (total sessions, messages exchanged,
answers generated, success rate, response time, tokens), a filterable + sortable
+ paginated sessions table (user, agent, start, messages, score, status,
response time, tokens), a chart row (session trend, sessions by category, score
distribution, success-rate gauge), two secondary panels (watchlist, quick
actions) and a per-session detail panel driven by the selected row (Summary /
Messages / Evaluation / Activity).

The numbers are real: each session is one failure-catalogue case run by the
smallest local model (llama3.2:3b), read from ``eval/reports/`` via
:mod:`tessera.observability.eval_data`. Response times and token counts come
from the instrumented harness; the detail Messages tab shows the real question
and the model's actual answer. Free-text data is verbatim French (accented).

The page is read-only on the eval run (an immutable artifact): the functional
axis is the wired filters / sort / pagination / row-selection and the real CSV
export + cross-page navigation, all verified end to end. There is no UI mutation
of the run itself.
"""

from __future__ import annotations

from datetime import datetime
from statistics import median
from typing import TYPE_CHECKING

from tessera.observability.eval_data import SessionRow, load_eval_snapshot

if TYPE_CHECKING:
    from tessera.observability.eval_data import EvalSnapshot

__all__ = ["compute_agent_historique"]

_TOPIC = "Assistant Tessera"
_OPERATOR = "Tessera Eval"
_GOOD_RATE = 0.7
_MILLION = 1_000_000
_THOUSAND = 1_000
_RESPONSE_LIMIT = 280

_LANG_LABELS: dict[str, str] = {"fr": "Français", "de": "Allemand", "en": "Anglais"}


def _fr_int(value: int) -> str:
    """Thousands separated by a thin space: 258243 -> '258 243'."""
    return f"{value:,}".replace(",", " ")


def _compact(value: int) -> str:
    """Compact magnitude: 258243 -> '258,2k', 1_200_000 -> '1,2M'."""
    if value >= _MILLION:
        return f"{value / 1_000_000:.1f}M".replace(".", ",")
    if value >= _THOUSAND:
        return f"{value / 1_000:.1f}k".replace(".", ",")
    return str(value)


def _secs(ms: float) -> str:
    """Milliseconds -> French seconds: 3243 -> '3,2 s'."""
    return f"{ms / 1000:.1f} s".replace(".", ",")


def _truncate(text: str, limit: int = _RESPONSE_LIMIT) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "..."


def _kpi(
    key: str, label: str, value: str, delta: str, delta_tone: str, tone: str, series: list[int]
) -> dict[str, object]:
    return {
        "key": key,
        "label": label,
        "value": value,
        "delta": delta,
        "delta_tone": delta_tone,
        "tone": tone,
        "series": series,
    }


def _bucketize(items: list[SessionRow], n: int) -> list[list[SessionRow]]:
    """Split a chronological list into n contiguous buckets."""
    if not items or n <= 0:
        return []
    size = len(items) / n
    return [items[round(i * size) : round((i + 1) * size)] for i in range(n)]


def _bucket_count(bucket: list[SessionRow]) -> int:
    return len(bucket)


def _bucket_passrate(bucket: list[SessionRow]) -> int:
    return round(100 * sum(1 for s in bucket if s.passed) / len(bucket)) if bucket else 0


def _bucket_p50(bucket: list[SessionRow]) -> int:
    values = [s.duration_ms for s in bucket if s.duration_ms > 0]
    return round(median(values)) if values else 0


def _bucket_tokens(bucket: list[SessionRow]) -> int:
    return sum(s.total_tokens for s in bucket)


def _start_label(session: SessionRow) -> str:
    try:
        return datetime.fromisoformat(session.started_at).strftime("%d/%m/%Y %H:%M:%S")
    except (ValueError, TypeError):
        return session.started_at


def _row(session: SessionRow) -> dict[str, object]:
    """A fully self-describing session row (display cells + raw keys + Q/A).

    Carrying the stable keys (``category_key``/``lang``/``status_tone``) and the
    raw numbers lets the frontend filter/sort on keys (i18n-safe) and build the
    whole detail panel from the selected row without a second round-trip.
    """
    passed = session.passed
    return {
        "sid": f"{session.case_id} / {session.language}",
        "user": _OPERATOR,
        "agent": _TOPIC,
        "start": _start_label(session),
        "start_ts": session.started_at,
        "messages": "2",
        "score": "10,0" if passed else "0,0",
        "score_num": 10 if passed else 0,
        "score_tone": "good" if passed else "bad",
        "status": "Réussie" if passed else "Échec",
        "status_tone": "good" if passed else "bad",
        "latency": _secs(session.duration_ms),
        "latency_ms": round(session.duration_ms),
        "tokens": _fr_int(session.total_tokens),
        "tokens_num": session.total_tokens,
        # raw fields for filtering + the detail panel
        "case_id": session.case_id,
        "category_key": session.category,
        "category_label": session.label,
        "lang": session.language,
        "passed": passed,
        "escalation": session.needs_escalation,
        "tools_count": len(session.tools),
        "input_tokens": session.input_tokens,
        "output_tokens": session.output_tokens,
        "question": _truncate(session.title, 160),
        "response": _truncate(session.response),
    }


def _assemble(snap: EvalSnapshot) -> dict[str, object]:
    """Assemble the Historique payload from the eval snapshot (pure, I/O-free)."""
    chrono = sorted(snap.sessions, key=lambda s: s.started_at)
    total = snap.total
    passed = snap.passed
    failed = total - passed
    n_lang = len(snap.languages)
    pass_rate = snap.pass_rate
    p50 = snap.latency_percentile(50)
    p95 = snap.latency_percentile(95)
    tok_in, tok_out = snap.token_totals()
    tok_total = tok_in + tok_out

    b7 = _bucketize(chrono, 7)
    kpis: list[dict[str, object]] = [
        _kpi("sessions", "Sessions totales", _fr_int(total),
             f"{len(snap.categories)} catégories - {n_lang} langues", "muted", "violet",
             [_bucket_count(b) for b in b7]),
        _kpi("messages", "Messages échangés", _fr_int(total * 2),
             "1 entrant + 1 sortant par session", "muted", "blue",
             [_bucket_count(b) * 2 for b in b7]),
        _kpi("answers", "Réponses générées", _fr_int(total), "1 réponse par session", "muted",
             "green", [_bucket_count(b) for b in b7]),
        _kpi("success", "Taux de réussite", f"{pass_rate * 100:.1f} %".replace(".", ","),
             f"{passed}/{total} cas réussis", "good" if pass_rate >= _GOOD_RATE else "bad",
             "green", [_bucket_passrate(b) for b in b7]),
        _kpi("latency", "Temps de réponse (p50)", _secs(p50), f"p95 {_secs(p95)}", "muted",
             "amber", [_bucket_p50(b) for b in b7]),
        _kpi("tokens", "Tokens consommés", _compact(tok_total),
             f"{_compact(tok_in)} entrée / {_compact(tok_out)} sortie", "muted", "violet",
             [_bucket_tokens(b) for b in b7]),
    ]

    cat_options = [
        {"key": c.category, "label": c.label}
        for c in sorted(snap.categories, key=lambda c: c.label)
    ]
    lang_options = [
        {"key": code, "label": _LANG_LABELS.get(code, code)} for code, _ in snap.languages
    ]
    filters: dict[str, object] = {
        "search": "Rechercher une session, cas, catégorie...",
        "options": {
            "category": cat_options,
            "lang": lang_options,
            "status": [{"key": "good", "label": "Réussie"}, {"key": "bad", "label": "Échec"}],
            "score": [{"key": "high", "label": "Score >= 5"}, {"key": "low", "label": "Score < 5"}],
        },
    }

    columns = [
        "Session ID", "Utilisateur", "Agent", "Début de session", "Messages",
        "Score", "Statut", "Temps de réponse (p50)", "Tokens",
    ]
    recent = sorted(snap.sessions, key=lambda s: s.started_at, reverse=True)
    rows = [_row(s) for s in recent]

    b10 = _bucketize(chrono, 10)
    trend: dict[str, object] = {
        "title": "Évolution des sessions (sur le run)",
        "control": "Par tranche",
        "series": [_bucket_count(b) for b in b10],
        "prev": [sum(1 for s in b if s.passed) for b in b10],
        "legend": "Sessions",
        "legend_prev": "Sessions réussies",
    }

    top_cats = sorted(snap.categories, key=lambda c: -c.total)[:5]
    max_cat = top_cats[0].total if top_cats else 1
    by_agent: dict[str, object] = {
        "title": "Sessions par catégorie (Top 5)",
        "cta": "Voir toutes les catégories",
        "cta_href": "/agent/evaluations",
        "items": [
            {"label": c.label, "value": _fr_int(c.total), "pct": round(100 * c.total / max_cat),
             "share": f"{100 * c.total / total:.1f}%".replace(".", ",")}
            for c in top_cats
        ],
    }

    escalated = sum(1 for s in snap.sessions if not s.passed and s.needs_escalation)
    blocked = failed - escalated

    def _share(part: int) -> str:
        return f"{100 * part / total:.1f}%".replace(".", ",") if total else "0%"

    scores: dict[str, object] = {
        "title": "Répartition des sessions",
        "center": _fr_int(total),
        "center_label": "Sessions",
        "segments": [
            {"label": "Réussies", "value": _fr_int(passed), "share": _share(passed),
             "pct": round(100 * passed / total) if total else 0, "tone": "green"},
            {"label": "Échecs (escalade)", "value": _fr_int(escalated), "share": _share(escalated),
             "pct": round(100 * escalated / total) if total else 0, "tone": "amber"},
            {"label": "Échecs (gérés)", "value": _fr_int(blocked), "share": _share(blocked),
             "pct": round(100 * blocked / total) if total else 0, "tone": "red"},
        ],
    }

    success: dict[str, object] = {
        "title": "Taux de réussite",
        "gauge": round(pass_rate * 100),
        "value": f"{pass_rate * 100:.1f}%".replace(".", ","),
        "note": "Réussie" if pass_rate >= _GOOD_RATE else "À surveiller",
        "cta": "Voir le détail",
        "cta_href": "/agent/evaluations",
    }

    worst = snap.categories_by_pass_rate()[:3]
    watch_tones = ["crit", "crit", "warn"]
    n_failing = sum(1 for c in snap.categories if c.pass_rate < _GOOD_RATE)
    watch: dict[str, object] = {
        "title": "À surveiller",
        "cta": f"Voir toutes les alertes ({n_failing})",
        "cta_href": "/agent/a-traiter",
        "items": [
            {"title": f"{c.label} - {c.failed} échecs sur {c.total}",
             "detail": f"{_secs(p50)} p50 - {n_lang} langues", "tone": tone}
            for c, tone in zip(worst, watch_tones, strict=False)
        ],
    }

    quick: dict[str, object] = {
        "title": "Actions rapides",
        "items": [
            {"key": "failed", "label": "Voir les sessions en échec"},
            {"key": "scores", "label": "Analyser les scores"},
            {"key": "export", "label": "Exporter (CSV)"},
            {"key": "evaluate", "label": "Analyser une session"},
        ],
    }

    return {
        "title": "Historique des sessions",
        "subtitle": "Analysez les sessions de conversation, leur qualité et leur conformité.",
        "actions": {"export": "Exporter", "compare": "Comparer", "create": "Créer un rapport"},
        "subtabs": [
            "Vue d'ensemble", "Sessions", "Messages", "Evaluations", "Traces & outils",
            "Utilisateurs", "Contenu & sources", "Erreurs", "Exports",
        ],
        "meta": {"model": snap.model, "catalogue_version": snap.catalogue_version},
        "detail_labels": {
            "eyebrow": "Détails de la session",
            "tabs": ["Résumé", "Messages (2)", "Évaluation", "Activité"],
            "config_title": "Configuration de l'agent",
            "eval_title": "Évaluation de la session",
            "eval_cta": "Voir tous les critères",
            "info_title": "Informations techniques",
            "messages_title": "Échange de la session",
            "question_label": "Question",
            "response_label": "Réponse de l'agent",
            "activity_title": "Journal d'activité",
        },
        "kpis": kpis,
        "filters": filters,
        "table": {"columns": columns, "rows": rows, "total": total},
        "trend": trend,
        "by_agent": by_agent,
        "scores": scores,
        "success": success,
        "watch": watch,
        "quick": quick,
    }


def compute_agent_historique() -> dict[str, object]:
    """Return the Historique payload from the real llama3.2:3b session run."""
    return _assemble(load_eval_snapshot())
