"""Agent Session History ("Historique des sessions") payload (reference image 30).

The Historique page analyses conversation sessions, their quality and their
compliance: an inner tab strip (overview, sessions, messages, evaluations,
traces, users, content, errors, exports), a KPI strip (total sessions, messages
exchanged, answers generated, success rate, response time, tokens), a filterable
sessions table (user, agent, start, messages, score, status, response time,
tokens), a chart row (session trend, sessions by category, score distribution,
success-rate gauge), two secondary panels (watchlist, quick actions) and a
per-session detail panel with a Summary / Messages / Evaluation / Activity tab
set, agent configuration, session evaluation and technical information.

The numbers are real: each session is one failure-catalogue case run by the
smallest local model (llama3.2:3b), read from eval/reports/ via
:mod:`tessera.observability.eval_data`. Response times and token counts come
from the instrumented harness. Free-text data is verbatim French with ASCII-only
punctuation.
"""

from __future__ import annotations

from datetime import datetime
from statistics import median

from tessera.observability.eval_data import SessionRow, load_eval_snapshot

__all__ = ["compute_agent_historique"]

_TOPIC = "Assistant Tessera"
_OPERATOR = "Tessera Eval"
_GOOD_RATE = 0.7
_MILLION = 1_000_000
_THOUSAND = 1_000


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


def _row(
    sid: str,
    user: str,
    agent: str,
    start: str,
    messages: str,
    score: str,
    score_tone: str,
    status: str,
    status_tone: str,
    latency: str,
    tokens: str,
) -> dict[str, object]:
    return {
        "sid": sid,
        "user": user,
        "agent": agent,
        "start": start,
        "messages": messages,
        "score": score,
        "score_tone": score_tone,
        "status": status,
        "status_tone": status_tone,
        "latency": latency,
        "tokens": tokens,
    }


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


def compute_agent_historique() -> dict[str, object]:
    """Return the Historique payload from the real llama3.2:3b session run."""
    snap = load_eval_snapshot()
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
        _kpi(
            "sessions",
            "Sessions totales",
            _fr_int(total),
            f"{len(snap.categories)} categories - {n_lang} langues",
            "muted",
            "violet",
            [_bucket_count(b) for b in b7],
        ),
        _kpi(
            "messages",
            "Messages echanges",
            _fr_int(total * 2),
            "1 entrant + 1 sortant par session",
            "muted",
            "blue",
            [_bucket_count(b) * 2 for b in b7],
        ),
        _kpi(
            "answers",
            "Reponses generees",
            _fr_int(total),
            "1 reponse par session",
            "muted",
            "green",
            [_bucket_count(b) for b in b7],
        ),
        _kpi(
            "success",
            "Taux de reussite",
            f"{pass_rate * 100:.1f} %".replace(".", ","),
            f"{passed}/{total} cas reussis",
            "good" if pass_rate >= _GOOD_RATE else "bad",
            "green",
            [_bucket_passrate(b) for b in b7],
        ),
        _kpi(
            "latency",
            "Temps de reponse (p50)",
            _secs(p50),
            f"p95 {_secs(p95)}",
            "muted",
            "amber",
            [_bucket_p50(b) for b in b7],
        ),
        _kpi(
            "tokens",
            "Tokens consommes",
            _compact(tok_total),
            f"{_compact(tok_in)} entree / {_compact(tok_out)} sortie",
            "muted",
            "violet",
            [_bucket_tokens(b) for b in b7],
        ),
    ]

    filters: dict[str, object] = {
        "search": "Rechercher une session, cas, categorie...",
        "selects": [
            {"label": "Categorie", "value": "Toutes"},
            {"label": "Langue", "value": "Toutes"},
            {"label": "Statut", "value": "Tous"},
            {"label": "Score", "value": "Tous"},
        ],
        "more": "Plus de filtres",
    }

    columns = [
        "Session ID",
        "Utilisateur",
        "Agent",
        "Debut de session",
        "Messages",
        "Score",
        "Statut",
        "Temps de reponse (p50)",
        "Tokens",
    ]
    recent = sorted(snap.sessions, key=lambda s: s.started_at, reverse=True)
    page = recent[:12]
    rows: list[dict[str, object]] = [
        _row(
            f"{s.case_id} / {s.language}",
            _OPERATOR,
            _TOPIC,
            _start_label(s),
            "2",
            "10,0" if s.passed else "0,0",
            "good" if s.passed else "bad",
            "Reussie" if s.passed else "Echec",
            "good" if s.passed else "bad",
            _secs(s.duration_ms),
            _fr_int(s.total_tokens),
        )
        for s in page
    ]

    b10 = _bucketize(chrono, 10)
    trend: dict[str, object] = {
        "title": "Evolution des sessions (sur le run)",
        "control": "Par tranche",
        "series": [_bucket_count(b) for b in b10],
        "prev": [sum(1 for s in b if s.passed) for b in b10],
        "legend": "Sessions",
        "legend_prev": "Sessions reussies",
    }

    top_cats = sorted(snap.categories, key=lambda c: -c.total)[:5]
    max_cat = top_cats[0].total if top_cats else 1
    by_agent: dict[str, object] = {
        "title": "Sessions par categorie (Top 5)",
        "cta": "Voir toutes les categories",
        "items": [
            {
                "label": c.label,
                "value": _fr_int(c.total),
                "pct": round(100 * c.total / max_cat),
                "share": f"{100 * c.total / total:.1f}%".replace(".", ","),
            }
            for c in top_cats
        ],
    }

    escalated = sum(1 for s in snap.sessions if not s.passed and s.needs_escalation)
    blocked = failed - escalated

    def _share(part: int) -> str:
        return f"{100 * part / total:.1f}%".replace(".", ",") if total else "0%"

    scores: dict[str, object] = {
        "title": "Repartition des sessions",
        "center": _fr_int(total),
        "center_label": "Sessions",
        "segments": [
            {
                "label": "Reussies",
                "value": _fr_int(passed),
                "share": _share(passed),
                "pct": round(100 * passed / total) if total else 0,
                "tone": "green",
            },
            {
                "label": "Echecs (escalade)",
                "value": _fr_int(escalated),
                "share": _share(escalated),
                "pct": round(100 * escalated / total) if total else 0,
                "tone": "amber",
            },
            {
                "label": "Echecs (geres)",
                "value": _fr_int(blocked),
                "share": _share(blocked),
                "pct": round(100 * blocked / total) if total else 0,
                "tone": "red",
            },
        ],
    }

    success: dict[str, object] = {
        "title": "Taux de reussite",
        "gauge": round(pass_rate * 100),
        "value": f"{pass_rate * 100:.1f}%".replace(".", ","),
        "note": "Reussie" if pass_rate >= _GOOD_RATE else "A surveiller",
        "cta": "Voir le detail",
    }

    worst = snap.categories_by_pass_rate()[:3]
    watch_tones = ["crit", "crit", "warn"]
    n_failing = sum(1 for c in snap.categories if c.pass_rate < _GOOD_RATE)
    watch: dict[str, object] = {
        "title": "A surveiller",
        "cta": f"Voir toutes les alertes ({n_failing})",
        "items": [
            {
                "title": f"{c.label} - {c.failed} echecs sur {c.total}",
                "detail": f"{_secs(p50)} p50 - {n_lang} langues",
                "tone": tone,
            }
            for c, tone in zip(worst, watch_tones, strict=False)
        ],
    }

    quick: dict[str, object] = {
        "title": "Actions rapides",
        "items": [
            "Voir les sessions en echec",
            "Analyser les scores",
            "Exporter (CSV / Parquet)",
            "Analyser une session",
        ],
    }

    focus = max(snap.sessions, key=lambda s: s.duration_ms)
    detail: dict[str, object] = {
        "sid": f"{focus.case_id} / {focus.language}",
        "id": f"@_session_{focus.case_id}",
        "tabs": ["Resume", "Messages (2)", "Evaluation", "Activite"],
        "fields": [
            {"label": "Utilisateur", "value": _OPERATOR},
            {"label": "Agent", "value": _TOPIC},
            {"label": "Duree totale", "value": _secs(focus.duration_ms)},
            {"label": "Messages", "value": "2"},
            {
                "label": "Score",
                "value": "10,0 / 10" if focus.passed else "0,0 / 10",
                "tone": "good" if focus.passed else "bad",
            },
            {
                "label": "Statut",
                "value": "Reussie" if focus.passed else "Echec",
                "tone": "good" if focus.passed else "bad",
            },
            {"label": "Temps de reponse (p50)", "value": _secs(focus.duration_ms)},
            {"label": "Tokens", "value": _fr_int(focus.total_tokens)},
            {"label": "Modele", "value": snap.model},
            {"label": "Categorie", "value": focus.label},
        ],
        "config_title": "Configuration de l'agent",
        "config_value": _TOPIC,
        "config_version": snap.catalogue_version,
        "eval_title": "Evaluation de la session",
        "eval_cta": "Voir tous les criteres",
        "eval": [
            {
                "label": "Score global",
                "value": "10" if focus.passed else "0",
                "scale": "/10",
                "lead": True,
            },
            {
                "label": "Reussite",
                "value": "Oui" if focus.passed else "Non",
                "scale": "",
                "lead": False,
            },
            {
                "label": "Escalade requise",
                "value": "Oui" if focus.needs_escalation else "Non",
                "scale": "",
                "lead": False,
            },
            {
                "label": "Outils invoques",
                "value": str(len(focus.tools)),
                "scale": "",
                "lead": False,
            },
            {
                "label": "Tokens (entree / sortie)",
                "value": f"{focus.input_tokens} / {focus.output_tokens}",
                "scale": "",
                "lead": False,
            },
        ],
        "info_title": "Informations techniques",
        "info": [
            {"label": "Session ID", "value": f"{focus.case_id} / {focus.language}"},
            {"label": "Cas", "value": focus.case_id},
            {"label": "Categorie", "value": focus.category},
            {"label": "Langue", "value": focus.language},
            {"label": "Modele", "value": snap.model},
            {"label": "Version catalogue", "value": snap.catalogue_version},
        ],
    }

    return {
        "title": "Historique des sessions",
        "subtitle": "Analysez les sessions de conversation, leur qualite et leur conformite.",
        "actions": {"export": "Exporter", "compare": "Comparer", "create": "Creer un rapport"},
        "subtabs": [
            "Vue d'ensemble",
            "Sessions",
            "Messages",
            "Evaluations",
            "Traces & outils",
            "Utilisateurs",
            "Contenu & sources",
            "Erreurs",
            "Exports",
        ],
        "kpis": kpis,
        "filters": filters,
        "table": {
            "columns": columns,
            "rows": rows,
            "count": f"1-{len(rows)} sur {_fr_int(total)} sessions",
            "pages": (total + len(rows) - 1) // len(rows) if rows else 1,
        },
        "trend": trend,
        "by_agent": by_agent,
        "scores": scores,
        "success": success,
        "watch": watch,
        "quick": quick,
        "detail": detail,
    }
