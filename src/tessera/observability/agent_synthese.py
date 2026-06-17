"""Agent overview ("Synthese de l'agent") dashboard payload (reference image 25).

The Synthese page is the operator's at-a-glance cockpit for a single agent
instance: a KPI strip (conversations, turns, resolution, latency, failures,
sources, messages), the agent profile and capabilities, top evaluated topics,
detailed performance metrics, the current configuration, recent conversations,
a live activity feed, active system prompts, language mix, a change timeline,
alerts and quick configuration shortcuts.

Every panel is backed by a real artifact:

- conversations / turns / messages / activity feed / recent conversations come
  from the durable transcript (``conversation_messages``, see
  ``memory/transcript.py``);
- resolution / latency / failures / escalations / topics / performance / model
  come from the real llama3.2:3b failure-catalogue run via ``eval_data``;
- knowledge sources come from the live pgvector ``documents`` table;
- active prompts come from ``agent/prompts/{fr,de,en}.yaml``;
- capabilities come from the real LLM-callable tools under ``agent/tools/``;
- the profile (name/owner/model) comes from the persisted agent config;
- alerts include the live guard audit-chain integrity status; the timeline is
  built from real file mtimes (prompts, policy) and ingest/eval timestamps.

There is no per-channel or satisfaction store, so the formerly-fabricated
"Utilisation par canal" / "Satisfaction" slots were relabelled to real
distributions (language mix) and dropped. Values with no real source render an
honest ``-`` rather than an invented number. The page is FR-only (it never had
a ``lang`` parameter); free-text data is verbatim French.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from psycopg.rows import dict_row

from tessera.agent.identity import DEFAULT_AGENT_ID
from tessera.guard.audit import verify_audit_chain
from tessera.observability.agent_configurations import _effective
from tessera.observability.eval_data import EvalSnapshot, load_eval_snapshot
from tessera.retrieval.store import _connection
from tessera.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["compute_agent_synthese"]

_ROOT = Path(__file__).resolve().parents[3]
_PROMPTS_DIR = _ROOT / "src" / "tessera" / "agent" / "prompts"
_TOOLS_DIR = _ROOT / "src" / "tessera" / "agent" / "tools"
_POLICY_FILE = _ROOT / "src" / "tessera" / "guard" / "policy.yaml"
_PARIS = ZoneInfo("Europe/Paris")

_GOOD_PCT = 70.0
_GOOD_MEAN_MS = 4000
_GOOD_P95_MS = 8000
_ESCAL_WARN_PCT = 20.0
_SPARK_DAYS = 7
_MIN_SERIES = 2
_RECENT_CONVERSATIONS = 5
_RECENT_ACTIVITY = 8
_TOP_TOPICS = 6

_TONES = ("violet", "blue", "amber", "green", "cyan", "slate")

# Real LLM-callable tools -> human capability labels (verbatim French).
_TOOL_LABELS: dict[str, str] = {
    "account_balance": "Consultation de solde",
    "card_block": "Blocage de carte",
    "transaction_search": "Recherche de transactions",
    "loan_simulate": "Simulation de crédit",
    "ticket_escalate": "Escalade vers un conseiller",
}

_LANG_LABELS: dict[str, str] = {"fr": "Français", "de": "Allemand", "en": "Anglais"}


def _secs(ms: float) -> str:
    """Milliseconds -> French seconds: 3243 -> '3,2 s'."""
    return f"{ms / 1000:.1f} s".replace(".", ",")


def _fmt_dt(value: datetime | None) -> str:
    value = _aware(value)
    if value is None:
        return "-"
    return value.astimezone(_PARIS).strftime("%d/%m/%Y %H:%M")


def _aware(value: datetime | None) -> datetime | None:
    """Attach UTC to a naive datetime so comparisons/sorts never mix tzinfo."""
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _mtime(path: Path) -> datetime | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    except (FileNotFoundError, OSError):
        return None


def _newest_mtime(directory: Path, pattern: str) -> datetime | None:
    times = [t for p in directory.glob(pattern) if (t := _mtime(p)) is not None]
    return max(times) if times else None


def _fmt_int(n: int) -> str:
    """Group thousands with a space, French style: 1008 -> '1 008'."""
    return f"{n:,}".replace(",", " ")


def _turns_label(n: int) -> str:
    return f"{n} échange" if n <= 1 else f"{n} échanges"


def _truncate(text: str, limit: int = 64) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "..."


# --- live transcript -----------------------------------------------------------


async def _fetch_transcript(agent_id: str, period_days: int | None) -> dict[str, Any]:
    """Read the durable conversation transcript aggregates for one agent.

    Returns totals, per-day buckets (for the KPI sparklines), the most recent
    conversations (first question + turn count + escalation heuristic) and the
    latest individual messages (for the activity feed). Also surfaces the newest
    ingested knowledge source for the timeline.

    Every transcript-derived figure is scoped to ``agent_id`` (per-turn
    attribution), so a single agent's Synthese reflects its own slice — turns
    are counted at the turn grain (one ``user`` message = one turn). When
    ``period_days`` is set, figures are further restricted to that trailing
    window. The knowledge-base counts are agent- and period-agnostic.
    """
    # An interval literal cannot be a placeholder; period_days is a validated int.
    window = f"created_at >= now() - interval '{int(period_days)} days'" if period_days else "TRUE"
    where = f"agent_id = %s AND ({window})"
    async with _connection() as conn:
        conn.row_factory = dict_row
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT count(DISTINCT conversation_id) AS convs, count(*) AS msgs, "  # noqa: S608
                "count(*) FILTER (WHERE role = 'user') AS turns, "
                f"max(created_at) AS last_at FROM conversation_messages WHERE {where}",
                (agent_id,),
            )
            totals = await cur.fetchone() or {}

            await cur.execute(
                "SELECT date_trunc('day', created_at) AS day, "  # noqa: S608
                "count(DISTINCT conversation_id) AS convs, "
                "count(*) AS msgs, count(*) FILTER (WHERE role = 'user') AS turns "
                f"FROM conversation_messages WHERE {where} GROUP BY 1 ORDER BY 1",
                (agent_id,),
            )
            daily = list(await cur.fetchall())

            await cur.execute(
                "SELECT conversation_id, max(created_at) AS ended, "  # noqa: S608
                "count(*) FILTER (WHERE role = 'user') AS turns, "
                "(array_agg(content ORDER BY id) "
                "  FILTER (WHERE role = 'user'))[1] AS first_q, "
                "bool_or(role = 'assistant' AND ("
                "  content ILIKE '%%escalad%%' OR content ILIKE '%%conseiller%%' "
                "  OR content ILIKE '%%ticket%%' OR content ILIKE '%%transf%%')) AS escalated "
                f"FROM conversation_messages WHERE {where} GROUP BY conversation_id "
                "ORDER BY ended DESC LIMIT %s",
                (agent_id, _RECENT_CONVERSATIONS),
            )
            recent_convs = list(await cur.fetchall())

            await cur.execute(
                f"SELECT role, content, created_at FROM conversation_messages WHERE {where} "  # noqa: S608
                "ORDER BY id DESC LIMIT %s",
                (agent_id, _RECENT_ACTIVITY),
            )
            recent_msgs = list(await cur.fetchall())

            await cur.execute(
                "SELECT metadata->>'locator' AS locator, inserted_at "
                "FROM documents ORDER BY inserted_at DESC LIMIT 1"
            )
            newest_doc = await cur.fetchone() or {}

            await cur.execute("SELECT count(*) AS n FROM documents")
            doc_count = (await cur.fetchone() or {}).get("n", 0)

            await cur.execute("SELECT count(DISTINCT metadata->>'category') AS n FROM documents")
            cat_count = (await cur.fetchone() or {}).get("n", 0)

    return {
        "totals": totals,
        "daily": daily,
        "recent_convs": recent_convs,
        "recent_msgs": recent_msgs,
        "newest_doc": newest_doc,
        "doc_count": int(doc_count or 0),
        "cat_count": int(cat_count or 0),
    }


def _prompt_inventory() -> tuple[list[dict[str, Any]], datetime | None]:
    """Read prompt keys present per language from the live YAML files."""
    import yaml  # local import: only needed here

    per_key: dict[str, set[str]] = {}
    for path in sorted(_PROMPTS_DIR.glob("*.yaml")):
        lang = path.stem
        try:
            loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            continue
        if isinstance(loaded, dict):
            for key in loaded:
                per_key.setdefault(str(key), set()).add(lang)
    rows = [{"key": k, "langs": sorted(v)} for k, v in sorted(per_key.items())]
    return rows, _newest_mtime(_PROMPTS_DIR, "*.yaml")


def _tool_capabilities() -> list[str]:
    """List capabilities from the real LLM-callable tool modules on disk."""
    labels: list[str] = []
    for path in sorted(_TOOLS_DIR.glob("*.py")):
        if path.stem.startswith("_"):
            continue
        labels.append(_TOOL_LABELS.get(path.stem, path.stem.replace("_", " ").title()))
    return labels


# --- assembly ------------------------------------------------------------------


def _kpi(
    key: str, label: str, value: str, delta: str, good: bool, series: Sequence[int]
) -> dict[str, object]:
    return {
        "key": key,
        "label": label,
        "value": value,
        "delta": delta,
        "good": good,
        "series": list(series),
    }


def _delta_vs_prev(series: Sequence[int]) -> str:
    """Last-vs-previous bucket delta as a signed percentage, or '-'."""
    if len(series) < _MIN_SERIES or series[-2] == 0:
        return "-"
    pct = round(100 * (series[-1] - series[-2]) / series[-2])
    return f"{pct:+d}% vs jour précédent"


def _period_label(period_days: int | None) -> str:
    """Human window label for the meta strip."""
    if period_days is None:
        return "Tout l'historique"
    if period_days <= 1:
        return "24 dernières heures"
    return f"{period_days} derniers jours"


def _page(agent_id: str, page: str) -> str:
    """Build an agent-scoped cockpit link (mirrors the front-end ``agentPath``).

    The AGENT section is scoped to a selected agent, so every internal link is
    ``/agents/<agent_id>/<page>`` — never a literal single-agent path.
    """
    return f"/agents/{agent_id}/{page}"


def _assemble(
    snap: EvalSnapshot,
    tx: dict[str, Any],
    chain_ok: bool,
    agent_id: str = DEFAULT_AGENT_ID,
    period_days: int | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    """Assemble the Synthese payload from the eval snapshot + transcript.

    Pure and I/O-free so it can be unit-tested with synthetic inputs.
    """
    now = now or datetime.now(UTC)
    total = snap.total
    passed = snap.passed
    failed = total - passed
    pass_pct = round(snap.pass_rate * 100, 1)
    escal_pct = round(100 - pass_pct, 1) if total else 0.0
    p50 = snap.latency_percentile(50)
    p95 = snap.latency_percentile(95)
    durations = [s.duration_ms for s in snap.sessions if s.duration_ms > 0]
    mean_ms = sum(durations) / len(durations) if durations else 0.0

    # eval-derived sparklines (chronological buckets of the real run)
    chrono = sorted(snap.sessions, key=lambda s: s.started_at)
    seven = (
        [chrono[round(i * len(chrono) / 7) : round((i + 1) * len(chrono) / 7)] for i in range(7)]
        if chrono
        else []
    )
    res_series = [round(100 * sum(1 for s in b if s.passed) / len(b)) if b else 0 for b in seven]
    lat_series = [round(sum(s.duration_ms for s in b) / len(b)) if b else 0 for b in seven]
    err_series = [sum(1 for s in b if not s.passed) for b in seven]

    # transcript-derived series
    daily = tx["daily"]
    conv_series = [int(d["convs"]) for d in daily][-_SPARK_DAYS:]
    turn_series = [int(d["turns"]) for d in daily][-_SPARK_DAYS:]
    msg_series = [int(d["msgs"]) for d in daily][-_SPARK_DAYS:]
    totals = tx["totals"]
    n_convs = int(totals.get("convs") or 0)
    n_turns = int(totals.get("turns") or 0)
    n_msgs = int(totals.get("msgs") or 0)
    last_at = totals.get("last_at")
    cat_count = tx["cat_count"]
    doc_count = tx["doc_count"]

    # category chunk distribution for the sources sparkline (real per-category)
    cat_series = [c.total for c in sorted(snap.categories, key=lambda c: -c.total)][:_SPARK_DAYS]

    kpis: list[dict[str, object]] = [
        _kpi(
            "conversations",
            "Conversations",
            _fmt_int(n_convs),
            _delta_vs_prev(conv_series),
            True,
            conv_series,
        ),
        _kpi(
            "turns",
            "Tours utilisateur",
            _fmt_int(n_turns),
            _delta_vs_prev(turn_series),
            True,
            turn_series,
        ),
        _kpi(
            "resolution",
            "Taux de résolution",
            f"{pass_pct:.1f}%".replace(".", ","),
            f"{passed}/{total} cas réussis",
            pass_pct >= _GOOD_PCT,
            res_series,
        ),
        _kpi(
            "latency",
            "Temps de réponse moyen",
            _secs(mean_ms),
            f"p50 {_secs(p50)} - p95 {_secs(p95)}",
            mean_ms <= _GOOD_MEAN_MS,
            lat_series,
        ),
        _kpi(
            "errors",
            "Cas en échec",
            str(failed),
            f"sur {total} cas du catalogue",
            False,
            err_series,
        ),
        _kpi(
            "sources",
            "Sources de connaissances",
            str(cat_count),
            f"{doc_count} fragments indexés",
            True,
            cat_series,
        ),
        _kpi(
            "messages",
            "Messages échangés",
            _fmt_int(n_msgs),
            _delta_vs_prev(msg_series),
            True,
            msg_series,
        ),
    ]

    cfg = _effective()
    profile: dict[str, object] = {
        "name": str(cfg.get("name", "Tessera Assistant")),
        "status": "actif",
        "fields": [
            {"label": "Modèle principal", "value": snap.model},
            {"label": "Propriétaire", "value": str(cfg.get("owner", "-"))},
            {"label": "Langues", "value": f"{len(snap.languages)} (fr/de/en)"},
            {"label": "Connaissances", "value": f"{cat_count} sources / {doc_count} fragments"},
            {"label": "Conversations", "value": _fmt_int(n_convs)},
            {"label": "Dernière activité", "value": _fmt_dt(last_at)},
        ],
        "cta": "Voir la configuration active",
        "ctaHref": _page(agent_id, "configurations"),
    }

    capabilities: dict[str, object] = {
        "title": "Capacités principales",
        "items": _tool_capabilities(),
        "cta": "Gérer les capacités",
        "ctaHref": _page(agent_id, "configurations"),
    }

    top_cats = sorted(snap.categories, key=lambda c: -c.total)[:_TOP_TOPICS]
    topics: dict[str, object] = {
        "title": "Top catégories évaluées",
        "items": [
            {
                "label": cat.label,
                "pct": round(100 * cat.total / total) if total else 0,
                "tone": tone,
            }
            for cat, tone in zip(top_cats, _TONES, strict=False)
        ],
        "cta": "Voir toutes les catégories",
        "ctaHref": _page(agent_id, "evaluations"),
    }

    performance: dict[str, object] = {
        "title": "Performance détaillée",
        "rows": [
            {
                "label": "Taux de résolution",
                "value": f"{pass_pct:.1f}%".replace(".", ","),
                "delta": f"{passed}/{total}",
                "good": pass_pct >= _GOOD_PCT,
            },
            {
                "label": "Cas en échec",
                "value": f"{escal_pct:.1f}%".replace(".", ","),
                "delta": f"{failed}/{total}",
                "good": False,
            },
            {"label": "Escalades", "value": str(snap.escalations), "delta": "cas", "good": True},
            {
                "label": "Invocations d'outils",
                "value": str(snap.tool_invocations),
                "delta": "cas",
                "good": True,
            },
            {
                "label": "Langues couvertes",
                "value": str(len(snap.languages)),
                "delta": "fr/de/en",
                "good": True,
            },
            {"label": "Temps de réponse P50", "value": _secs(p50), "delta": "median", "good": True},
            {
                "label": "Temps de réponse P95",
                "value": _secs(p95),
                "delta": "queue",
                "good": p95 <= _GOOD_P95_MS,
            },
        ],
        "cta": "Voir le détail",
        "ctaHref": _page(agent_id, "evaluations"),
    }

    config: dict[str, object] = {
        "title": "Configuration courante",
        "rows": [
            {"label": "Modèle", "value": snap.model},
            {"label": "Jeu d'évaluation", "value": snap.catalogue_version},
            {"label": "Cas évalués", "value": str(total)},
            {"label": "Catégories", "value": str(len(snap.categories))},
            {"label": "Langue par défaut", "value": str(cfg.get("default_language", "Francais"))},
        ],
        "cta": "Modifier la configuration",
        "ctaHref": _page(agent_id, "configurations"),
    }

    conversations: dict[str, object] = {
        "title": "Conversations recentes",
        "cta": "Voir toutes les conversations",
        "ctaHref": _page(agent_id, "historique"),
        "rows": [
            {
                "title": _truncate(str(c.get("first_q") or "Conversation"), 56),
                "user": _turns_label(int(c.get("turns") or 0)),
                "time": _fmt_dt(c.get("ended")),
                "status": "escalade" if c.get("escalated") else "resolu",
            }
            for c in tx["recent_convs"]
        ],
    }

    activity: dict[str, object] = {
        "title": "Activité récente",
        "rows": [
            {
                "time": (
                    m["created_at"].astimezone(_PARIS).strftime("%H:%M")
                    if m.get("created_at")
                    else "-"
                ),
                "label": ("Question utilisateur" if m.get("role") == "user" else "Réponse générée"),
                "kind": "info" if m.get("role") == "user" else "ok",
            }
            for m in tx["recent_msgs"]
        ],
    }

    prompt_rows, prompts_mtime = _prompt_inventory()
    prompts: dict[str, object] = {
        "title": "Prompts système actifs",
        "cta": "Voir tous les prompts",
        "ctaHref": _page(agent_id, "prompts"),
        "rows": [
            {
                "name": r["key"].replace("_", " ").capitalize(),
                "version": f"{len(r['langs'])} langues",
                "status": "actif",
                "updated": f"Mis à jour le {_fmt_dt(prompts_mtime)}",
            }
            for r in prompt_rows[:3]
        ],
    }

    languages: dict[str, object] = {
        "title": "Répartition par langue (évaluation)",
        "items": [
            {
                "label": _LANG_LABELS.get(code, code),
                "pct": round(100 * cnt / total) if total else 0,
                "tone": tone,
            }
            for (code, cnt), tone in zip(snap.languages, _TONES, strict=False)
        ],
    }

    timeline: dict[str, object] = {
        "title": "Derniers changements",
        "cta": "Voir l'historique",
        "ctaHref": _page(agent_id, "historique"),
        "rows": _timeline_rows(snap, tx, prompts_mtime),
    }

    alerts: dict[str, object] = {
        "title": "Alertes & signaux",
        "cta": "Voir les garde-fous",
        "ctaHref": _page(agent_id, "garde-fous"),
        "items": [
            {
                "label": "Taux d'escalade (eval)",
                "value": f"{escal_pct:.1f} %".replace(".", ","),
                "tone": "warn" if escal_pct >= _ESCAL_WARN_PCT else "good",
            },
            {
                "label": "Temps de réponse P95",
                "value": _secs(p95),
                "tone": "warn" if p95 > _GOOD_P95_MS else "good",
            },
            {
                "label": "Cas en échec",
                "value": f"{failed}/{total}",
                "tone": "crit" if failed > total / 2 else "warn",
            },
            {
                "label": "Chaîne d'audit",
                "value": "Intacte" if chain_ok else "Rompue",
                "tone": "good" if chain_ok else "crit",
            },
        ],
    }

    quick_config: dict[str, object] = {
        "title": "Configuration rapide",
        "cta": "Voir toutes les configurations",
        "ctaHref": _page(agent_id, "configurations"),
        "items": [
            {"label": "Sources de connaissances", "href": _page(agent_id, "connaissances")},
            {"label": "Garde-fous", "href": _page(agent_id, "garde-fous")},
            {"label": "Prompts système", "href": _page(agent_id, "prompts")},
            {"label": "Configuration de l'agent", "href": _page(agent_id, "configurations")},
        ],
    }

    return {
        "meta": {
            "mode": "Données réelles",
            "period": _period_label(period_days),
            "updated": _fmt_dt(last_at),
            "replayAt": "Relire à T",
            "comparison": "Aucune comparaison",
        },
        "kpis": kpis,
        "profile": profile,
        "capabilities": capabilities,
        "topics": topics,
        "performance": performance,
        "config": config,
        "conversations": conversations,
        "activity": activity,
        "prompts": prompts,
        "channels": languages,
        "timeline": timeline,
        "alerts": alerts,
        "quick_config": quick_config,
    }


def _timeline_rows(
    snap: EvalSnapshot, tx: dict[str, Any], prompts_mtime: datetime | None
) -> list[dict[str, object]]:
    """Real change events from file mtimes + ingest/eval timestamps, newest first."""
    events: list[tuple[datetime, str, str, str]] = []

    def _add(when: datetime | None, label: str, detail: str, kind: str) -> None:
        aware = _aware(when)
        if aware is not None:
            events.append((aware, label, detail, kind))

    _add(prompts_mtime, "Prompts mis à jour", f"{_PROMPTS_DIR.name}/*.yaml", "info")
    _add(_mtime(_POLICY_FILE), "Politique garde-fous", "policy.yaml", "ok")
    newest_doc = tx["newest_doc"]
    _add(
        newest_doc.get("inserted_at"),
        "Source de connaissances ajoutée",
        str(newest_doc.get("locator") or "source"),
        "ok",
    )
    _add(snap.run_datetime(), "Évaluation exécutée", snap.model, "info")
    _add(tx["totals"].get("last_at"), "Dernière conversation", "transcript", "info")

    events.sort(key=lambda e: e[0], reverse=True)
    return [
        {
            "time": dt.astimezone(_PARIS).strftime("%d/%m %H:%M"),
            "label": label,
            "detail": detail,
            "kind": kind,
        }
        for dt, label, detail, kind in events[:_RECENT_ACTIVITY]
    ]


async def compute_agent_synthese(
    agent_id: str = DEFAULT_AGENT_ID, period_days: int | None = None
) -> dict[str, object]:
    """Return the Synthese dashboard payload, sourced end to end from real data.

    Args:
        agent_id: The agent whose slice to compute. Transcript-derived figures
            are scoped to this agent (per-turn attribution) and all internal
            links point at ``/agents/<agent_id>/...``.
        period_days: Trailing window (in days) the transcript-derived figures are
            restricted to. ``None`` means the whole history.
    """
    snap = load_eval_snapshot()
    tx = await _fetch_transcript(agent_id, period_days)
    try:
        chain = verify_audit_chain(get_settings().guard.audit_file)
        chain_ok = chain.verified
    except (OSError, ValueError):
        chain_ok = True
    return _assemble(snap, tx, chain_ok, agent_id, period_days=period_days)
