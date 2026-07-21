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

from tessera.agent.identity import DEFAULT_AGENT_ID
from tessera.observability.eval_data import SessionRow, load_agent_or_global_snapshot

if TYPE_CHECKING:
    from tessera.observability.eval_data import EvalSnapshot

__all__ = ["compute_agent_historique"]

_TOPIC = "Assistant Tessera"
_OPERATOR = "Tessera Eval"
_GOOD_RATE = 0.7
_MILLION = 1_000_000
_THOUSAND = 1_000
_RESPONSE_LIMIT = 280

_LANG_IDX = {"fr": 0, "de": 1, "en": 2}

# Display name of a content language (code) per UI locale.
_LANG_LABELS: dict[str, tuple[str, str, str]] = {
    "fr": ("Français", "Franzoesisch", "French"),
    "de": ("Allemand", "Deutsch", "German"),
    "en": ("Anglais", "Englisch", "English"),
}


def _loc(lang: str, fr: str, de: str, en: str) -> str:
    """Pick the locale variant of an inline string (fr / de / en)."""
    return (fr, de, en)[_LANG_IDX.get(lang, 0)]


def _lang_label(code: str, lang: str) -> str:
    """Localized display name for a content-language code."""
    variants = _LANG_LABELS.get(code)
    return variants[_LANG_IDX.get(lang, 0)] if variants else code


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


def _oneline(text: str) -> str:
    """Collapse whitespace; never truncate.

    A field shown clipped but with a hover reveal must carry its FULL text — a
    length cut baked here would make the reveal show the same clipped string.
    Bodies (responses) keep :func:`_truncate` (preview + detail panel); short
    identifiers (the question/title) use this.
    """
    return " ".join(text.split())


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


def _row(session: SessionRow, lang: str) -> dict[str, object]:
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
        "status": _loc(lang, "Réussie", "Erfolgreich", "Passed")
        if passed
        else _loc(lang, "Échec", "Fehlgeschlagen", "Failed"),
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
        "question": _oneline(session.title),
        "response": _truncate(session.response),
    }


def _assemble(
    snap: EvalSnapshot, agent_id: str = DEFAULT_AGENT_ID, lang: str = "fr"
) -> dict[str, object]:
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
        _kpi(
            "sessions",
            _loc(lang, "Sessions totales", "Sessions gesamt", "Total sessions"),
            _fr_int(total),
            _loc(
                lang,
                f"{len(snap.categories)} catégories - {n_lang} langues",
                f"{len(snap.categories)} Kategorien - {n_lang} Sprachen",
                f"{len(snap.categories)} categories - {n_lang} languages",
            ),
            "muted",
            "violet",
            [_bucket_count(b) for b in b7],
        ),
        _kpi(
            "messages",
            _loc(lang, "Messages échangés", "Ausgetauschte Nachrichten", "Messages exchanged"),
            _fr_int(total * 2),
            _loc(
                lang,
                "1 entrant + 1 sortant par session",
                "1 eingehend + 1 ausgehend pro Session",
                "1 inbound + 1 outbound per session",
            ),
            "muted",
            "blue",
            [_bucket_count(b) * 2 for b in b7],
        ),
        _kpi(
            "answers",
            _loc(lang, "Réponses générées", "Generierte Antworten", "Answers generated"),
            _fr_int(total),
            _loc(
                lang,
                "1 réponse par session",
                "1 Antwort pro Session",
                "1 answer per session",
            ),
            "muted",
            "green",
            [_bucket_count(b) for b in b7],
        ),
        _kpi(
            "success",
            _loc(lang, "Taux de réussite", "Erfolgsrate", "Pass rate"),
            f"{pass_rate * 100:.1f} %".replace(".", ","),
            _loc(
                lang,
                f"{passed}/{total} cas réussis",
                f"{passed}/{total} bestandene Faelle",
                f"{passed}/{total} cases passed",
            ),
            "good" if pass_rate >= _GOOD_RATE else "bad",
            "green",
            [_bucket_passrate(b) for b in b7],
        ),
        _kpi(
            "latency",
            _loc(lang, "Temps de réponse (p50)", "Antwortzeit (p50)", "Response time (p50)"),
            _secs(p50),
            f"p95 {_secs(p95)}",
            "muted",
            "amber",
            [_bucket_p50(b) for b in b7],
        ),
        _kpi(
            "tokens",
            _loc(lang, "Tokens consommés", "Verbrauchte Tokens", "Tokens consumed"),
            _compact(tok_total),
            _loc(
                lang,
                f"{_compact(tok_in)} entrée / {_compact(tok_out)} sortie",
                f"{_compact(tok_in)} Eingang / {_compact(tok_out)} Ausgang",
                f"{_compact(tok_in)} input / {_compact(tok_out)} output",
            ),
            "muted",
            "violet",
            [_bucket_tokens(b) for b in b7],
        ),
    ]

    cat_options = [
        {"key": c.category, "label": c.label}
        for c in sorted(snap.categories, key=lambda c: c.label)
    ]
    lang_options = [{"key": code, "label": _lang_label(code, lang)} for code, _ in snap.languages]
    filters: dict[str, object] = {
        "search": _loc(
            lang,
            "Rechercher une session, cas, catégorie...",
            "Session, Fall, Kategorie suchen...",
            "Search a session, case, category...",
        ),
        "options": {
            "category": cat_options,
            "lang": lang_options,
            "status": [
                {"key": "good", "label": _loc(lang, "Réussie", "Erfolgreich", "Passed")},
                {"key": "bad", "label": _loc(lang, "Échec", "Fehlgeschlagen", "Failed")},
            ],
            "score": [
                {"key": "high", "label": _loc(lang, "Score >= 5", "Score >= 5", "Score >= 5")},
                {"key": "low", "label": _loc(lang, "Score < 5", "Score < 5", "Score < 5")},
            ],
        },
    }

    columns = [
        _loc(lang, "Session ID", "Session-ID", "Session ID"),
        _loc(lang, "Utilisateur", "Benutzer", "User"),
        _loc(lang, "Agent", "Agent", "Agent"),
        _loc(lang, "Début de session", "Session-Beginn", "Session start"),
        _loc(lang, "Messages", "Nachrichten", "Messages"),
        _loc(lang, "Score", "Score", "Score"),
        _loc(lang, "Statut", "Status", "Status"),
        _loc(lang, "Temps de réponse (p50)", "Antwortzeit (p50)", "Response time (p50)"),
        _loc(lang, "Tokens", "Tokens", "Tokens"),
    ]
    recent = sorted(snap.sessions, key=lambda s: s.started_at, reverse=True)
    rows = [_row(s, lang) for s in recent]

    b10 = _bucketize(chrono, 10)
    trend: dict[str, object] = {
        "title": _loc(
            lang,
            "Évolution des sessions (sur le run)",
            "Session-Entwicklung (ueber den Lauf)",
            "Session trend (over the run)",
        ),
        "control": _loc(lang, "Par tranche", "Pro Abschnitt", "Per bucket"),
        "series": [_bucket_count(b) for b in b10],
        "prev": [sum(1 for s in b if s.passed) for b in b10],
        "legend": _loc(lang, "Sessions", "Sessions", "Sessions"),
        "legend_prev": _loc(lang, "Sessions réussies", "Erfolgreiche Sessions", "Passed sessions"),
    }

    top_cats = sorted(snap.categories, key=lambda c: -c.total)[:5]
    max_cat = top_cats[0].total if top_cats else 1
    by_agent: dict[str, object] = {
        "title": _loc(
            lang,
            "Sessions par catégorie (Top 5)",
            "Sessions nach Kategorie (Top 5)",
            "Sessions by category (Top 5)",
        ),
        "cta": _loc(
            lang,
            "Voir toutes les catégories",
            "Alle Kategorien anzeigen",
            "View all categories",
        ),
        "cta_href": f"/agents/{agent_id}/evaluations",
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
        "title": _loc(lang, "Répartition des sessions", "Session-Verteilung", "Session breakdown"),
        "center": _fr_int(total),
        "center_label": _loc(lang, "Sessions", "Sessions", "Sessions"),
        "segments": [
            {
                "label": _loc(lang, "Réussies", "Erfolgreich", "Passed"),
                "value": _fr_int(passed),
                "share": _share(passed),
                "pct": round(100 * passed / total) if total else 0,
                "tone": "green",
            },
            {
                "label": _loc(
                    lang, "Échecs (escalade)", "Fehler (Eskalation)", "Failures (escalated)"
                ),
                "value": _fr_int(escalated),
                "share": _share(escalated),
                "pct": round(100 * escalated / total) if total else 0,
                "tone": "amber",
            },
            {
                "label": _loc(lang, "Échecs (gérés)", "Fehler (behandelt)", "Failures (handled)"),
                "value": _fr_int(blocked),
                "share": _share(blocked),
                "pct": round(100 * blocked / total) if total else 0,
                "tone": "red",
            },
        ],
    }

    success: dict[str, object] = {
        "title": _loc(lang, "Taux de réussite", "Erfolgsrate", "Pass rate"),
        "gauge": round(pass_rate * 100),
        "value": f"{pass_rate * 100:.1f}%".replace(".", ","),
        "note": _loc(lang, "Réussie", "Erfolgreich", "Passing")
        if pass_rate >= _GOOD_RATE
        else _loc(lang, "À surveiller", "Zu beobachten", "To watch"),
        "cta": _loc(lang, "Voir le détail", "Details anzeigen", "View details"),
        "cta_href": f"/agents/{agent_id}/evaluations",
    }

    worst = snap.categories_by_pass_rate()[:3]
    watch_tones = ["crit", "crit", "warn"]
    n_failing = sum(1 for c in snap.categories if c.pass_rate < _GOOD_RATE)
    watch: dict[str, object] = {
        "title": _loc(lang, "À surveiller", "Zu beobachten", "To watch"),
        "cta": _loc(
            lang,
            f"Voir toutes les alertes ({n_failing})",
            f"Alle Warnungen anzeigen ({n_failing})",
            f"View all alerts ({n_failing})",
        ),
        "cta_href": "/a-traiter",
        "items": [
            {
                "title": _loc(
                    lang,
                    f"{c.label} - {c.failed} échecs sur {c.total}",
                    f"{c.label} - {c.failed} Fehler von {c.total}",
                    f"{c.label} - {c.failed} failures of {c.total}",
                ),
                "detail": _loc(
                    lang,
                    f"{_secs(p50)} p50 - {n_lang} langues",
                    f"{_secs(p50)} p50 - {n_lang} Sprachen",
                    f"{_secs(p50)} p50 - {n_lang} languages",
                ),
                "tone": tone,
            }
            for c, tone in zip(worst, watch_tones, strict=False)
        ],
    }

    quick: dict[str, object] = {
        "title": _loc(lang, "Actions rapides", "Schnellaktionen", "Quick actions"),
        "items": [
            {
                "key": "failed",
                "label": _loc(
                    lang,
                    "Voir les sessions en échec",
                    "Fehlgeschlagene Sessions anzeigen",
                    "View failed sessions",
                ),
            },
            {
                "key": "scores",
                "label": _loc(lang, "Analyser les scores", "Scores analysieren", "Analyze scores"),
            },
            {
                "key": "export",
                "label": _loc(lang, "Exporter (CSV)", "Exportieren (CSV)", "Export (CSV)"),
            },
            {
                "key": "evaluate",
                "label": _loc(
                    lang,
                    "Analyser une session",
                    "Eine Session analysieren",
                    "Analyze a session",
                ),
            },
        ],
    }

    return {
        "title": _loc(lang, "Historique des sessions", "Session-Verlauf", "Session history"),
        "subtitle": _loc(
            lang,
            "Analysez les sessions de conversation, leur qualité et leur conformité.",
            "Analysieren Sie Konversationssessions, ihre Qualitaet und Konformitaet.",
            "Analyze conversation sessions, their quality and their compliance.",
        ),
        "actions": {
            "export": _loc(lang, "Exporter", "Exportieren", "Export"),
            "compare": _loc(lang, "Comparer", "Vergleichen", "Compare"),
            "create": _loc(lang, "Créer un rapport", "Bericht erstellen", "Create a report"),
        },
        "subtabs": [
            _loc(lang, "Vue d'ensemble", "Uebersicht", "Overview"),
            _loc(lang, "Sessions", "Sessions", "Sessions"),
            _loc(lang, "Messages", "Nachrichten", "Messages"),
            _loc(lang, "Evaluations", "Evaluierungen", "Evaluations"),
            _loc(lang, "Traces & outils", "Traces & Tools", "Traces & tools"),
            _loc(lang, "Utilisateurs", "Benutzer", "Users"),
            _loc(lang, "Contenu & sources", "Inhalt & Quellen", "Content & sources"),
            _loc(lang, "Erreurs", "Fehler", "Errors"),
            _loc(lang, "Exports", "Exporte", "Exports"),
        ],
        "meta": {"model": snap.model, "catalogue_version": snap.catalogue_version},
        "detail_labels": {
            "eyebrow": _loc(lang, "Détails de la session", "Session-Details", "Session details"),
            "tabs": [
                _loc(lang, "Résumé", "Zusammenfassung", "Summary"),
                _loc(lang, "Messages (2)", "Nachrichten (2)", "Messages (2)"),
                _loc(lang, "Évaluation", "Evaluierung", "Evaluation"),
                _loc(lang, "Activité", "Aktivitaet", "Activity"),
            ],
            "config_title": _loc(
                lang, "Configuration de l'agent", "Agent-Konfiguration", "Agent configuration"
            ),
            "eval_title": _loc(
                lang, "Évaluation de la session", "Session-Evaluierung", "Session evaluation"
            ),
            "eval_cta": _loc(
                lang, "Voir tous les critères", "Alle Kriterien anzeigen", "View all criteria"
            ),
            "info_title": _loc(
                lang, "Informations techniques", "Technische Informationen", "Technical information"
            ),
            "messages_title": _loc(
                lang, "Échange de la session", "Session-Austausch", "Session exchange"
            ),
            "question_label": _loc(lang, "Question", "Frage", "Question"),
            "response_label": _loc(
                lang, "Réponse de l'agent", "Antwort des Agenten", "Agent response"
            ),
            "activity_title": _loc(
                lang, "Journal d'activité", "Aktivitaetsprotokoll", "Activity log"
            ),
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


def compute_agent_historique(
    agent_id: str = DEFAULT_AGENT_ID, lang: str = "fr"
) -> dict[str, object]:
    """Return the Historique payload from the real llama3.2:3b session run.

    ``lang`` (fr / de / en) localizes the chrome; the per-case data (category
    labels, the real question/answer text) stays verbatim from the eval run.
    """
    return _assemble(load_agent_or_global_snapshot(agent_id), agent_id, lang)
