"""Agent overview ("Synthese de l'agent") dashboard payload (reference image 25).

The Synthese page is the operator's at-a-glance, **operational** cockpit for a
single agent — events only, never continuous eval signals (those live in the
Evaluations page; surfacing them here is the AT-01 trap). It carries a KPI strip
(conversations / turns / users / resolution / satisfaction / latency / handoffs),
the agent profile and capabilities, the routing-motive distribution, detailed
operational performance, active prompts, recent conversations, the rich AT-01
activity feed, and a right column (agent context, operational alerts, quick
access).

Every panel is backed by a real artifact:

- conversations / turns / messages / users / resolution / latency / recent
  conversations / activity come from the durable transcript (``conversation_messages``)
  and the per-turn ``latency_ms`` / ``subject_id`` / escalation heuristic, scoped to
  ``agent_id`` and to real traffic (``synthetic`` test turns excluded, ADR 0040);
- handoffs (incoming/outgoing), the routing-motive distribution and the
  garde-fou / outil activity items come from the S1 hash-chained journal
  (``tessera.agent.handoff`` / ``tessera.agent.routing`` / ``tessera.guard.audit``);
- knowledge sources come from the live pgvector ``documents`` table;
- active prompts come from ``agent/prompts/{fr,de,en}.yaml``;
- the identity / capabilities (name, owner, model, tools) come from the governed
  agent **registry** (``agents.yaml``), layered with the editable Configurations
  overrides; alerts include the live guard audit-chain integrity status.

Both formerly-empty KPIs now have a real source, and still render an honest empty
state (never an invented number) until that source has data:

- **Utilisateurs servis** — ``count(DISTINCT subject_id)`` over real turns (ADR 0040);
  "—" when no turn carried a captured identity.
- **Satisfaction (CSAT)** — the share of positive customer votes from the durable
  ``customer_feedback`` store (ADR 0041); "—" until a customer has voted.

The page is FR-only (it never had a ``lang`` parameter); free-text data is
verbatim French.
"""

from __future__ import annotations

import sys
from collections import Counter, deque
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from psycopg.rows import dict_row

from tessera.agent.identity import DEFAULT_AGENT_ID
from tessera.agent.registry import Agent, get_agent
from tessera.guard.ledger_store import read_ledger_entries, verify_active_ledger
from tessera.observability.agent_configurations import _effective
from tessera.retrieval.store import _connection

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["compute_agent_synthese"]

_ROOT = Path(__file__).resolve().parents[3]
_PROMPTS_DIR = _ROOT / "src" / "tessera" / "agent" / "prompts"
_PARIS = ZoneInfo("Europe/Paris")

_GOOD_MEAN_MS = 4000
_GOOD_RESOLUTION_PCT = 70.0
_GOOD_CSAT_PCT = 70  # a real customer-satisfaction rate at or above this reads "good"
_ESCAL_WARN_PCT = 20.0
_HANDOFF_OUT_WARN = 40  # outgoing handoffs over the window above which we warn
_SPARK_DAYS = 7
_MIN_SERIES = 2
_RECENT_CONVERSATIONS = 5
_RECENT_ACTIVITY = 8
_JOURNAL_EVENT_CAP = 6  # most-recent guard/tool journal events kept for the feed
_PROMPTS_SHOWN = 3

_TONES = ("violet", "blue", "amber", "green", "cyan", "slate")

# Real LLM-callable tools -> human capability labels (verbatim French).
_TOOL_LABELS: dict[str, str] = {
    "account_balance": "Consultation de solde",
    "card_block": "Blocage de carte",
    "transaction_search": "Recherche de transactions",
    "loan_simulate": "Simulation de crédit",
    "ticket_escalate": "Escalade vers un conseiller",
}

# Supervisor routing motive (prefix of the ``reason`` field, before "->").
_ROUTING_MOTIFS: dict[str, str] = {
    "stay": "Continuité de session",
    "intent": "Changement d'intention",
    "policy": "Politique de routage",
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


def _parse_iso(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return _aware(datetime.fromisoformat(value))
    except ValueError:
        return None


# --- live transcript -----------------------------------------------------------

# Assistant turns whose content matches these are treated as an escalation/handoff
# to a human, used to derive the operational resolution rate from the transcript.
_ESCAL_SQL = (
    "role = 'assistant' AND (content ILIKE '%%escalad%%' OR content ILIKE '%%conseiller%%' "
    "OR content ILIKE '%%ticket%%' OR content ILIKE '%%transf%%')"
)


async def _fetch_transcript(agent_id: str, period_days: int | None) -> dict[str, Any]:
    """Read the durable conversation transcript aggregates for one agent.

    Returns totals, per-day buckets (for the KPI sparklines, including a per-day
    resolution and latency series), the most recent conversations and the latest
    messages (for the activity feed). Every transcript-derived figure is scoped to
    ``agent_id`` at the turn grain (one ``user`` message = one turn) and, when
    ``period_days`` is set, to that trailing window.
    """
    # An interval literal cannot be a placeholder; period_days is a validated int.
    window = f"created_at >= now() - interval '{int(period_days)} days'" if period_days else "TRUE"
    # ADR 0040: the Synthèse reflects REAL traffic — operator TEST turns (Console,
    # marked ``synthetic``) are written to the transcript but excluded here, so they
    # never inflate this agent's conversations / tours / résolution / latence.
    where = f"agent_id = %s AND NOT synthetic AND ({window})"
    async with _connection() as conn:
        conn.row_factory = dict_row
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT count(DISTINCT conversation_id) AS convs, count(*) AS msgs, "  # noqa: S608
                "count(*) FILTER (WHERE role = 'user') AS turns, "
                "count(*) FILTER (WHERE role = 'assistant') AS answers, "
                "count(DISTINCT subject_id) FILTER (WHERE subject_id IS NOT NULL) AS subjects, "
                f"count(DISTINCT conversation_id) FILTER (WHERE {_ESCAL_SQL}) AS escal_convs, "
                "avg(latency_ms) FILTER (WHERE latency_ms IS NOT NULL) AS lat_ms, "
                f"max(created_at) AS last_at FROM conversation_messages WHERE {where}",
                (agent_id,),
            )
            totals = await cur.fetchone() or {}

            await cur.execute(
                "SELECT date_trunc('day', created_at) AS day, "  # noqa: S608
                "count(DISTINCT conversation_id) AS convs, "
                f"count(DISTINCT conversation_id) FILTER (WHERE {_ESCAL_SQL}) AS escal_convs, "
                "count(*) FILTER (WHERE role = 'user') AS turns, "
                "avg(latency_ms) FILTER (WHERE latency_ms IS NOT NULL) AS lat_ms "
                f"FROM conversation_messages WHERE {where} GROUP BY 1 ORDER BY 1",
                (agent_id,),
            )
            daily = list(await cur.fetchall())

            await cur.execute(
                "SELECT conversation_id, max(created_at) AS ended, "  # noqa: S608
                "count(*) FILTER (WHERE role = 'user') AS turns, "
                "(array_agg(content ORDER BY id) "
                "  FILTER (WHERE role = 'user'))[1] AS first_q, "
                f"bool_or({_ESCAL_SQL}) AS escalated "
                f"FROM conversation_messages WHERE {where} GROUP BY conversation_id "
                "ORDER BY ended DESC LIMIT %s",
                (agent_id, _RECENT_CONVERSATIONS),
            )
            recent_convs = list(await cur.fetchall())

            await cur.execute(
                "SELECT role, content, latency_ms, created_at "  # noqa: S608
                f"FROM conversation_messages WHERE {where} ORDER BY id DESC LIMIT %s",
                (agent_id, _RECENT_ACTIVITY),
            )
            recent_msgs = list(await cur.fetchall())

            await cur.execute("SELECT count(*) AS n FROM documents")
            doc_count = (await cur.fetchone() or {}).get("n", 0)

            await cur.execute("SELECT count(DISTINCT metadata->>'category') AS n FROM documents")
            cat_count = (await cur.fetchone() or {}).get("n", 0)

    return {
        "totals": totals,
        "daily": daily,
        "recent_convs": recent_convs,
        "recent_msgs": recent_msgs,
        "doc_count": int(doc_count or 0),
        "cat_count": int(cat_count or 0),
    }


async def _fetch_csat(agent_id: str, period_days: int | None) -> dict[str, int]:
    """Real customer-satisfaction counts for one agent (ADR 0041).

    Reads the durable ``customer_feedback`` store — a 👍/👎 the customer left on an
    assistant reply — scoped to ``agent_id`` and, like the transcript reads, to real
    traffic (``NOT synthetic``) and the trailing window. Returns ``{up, total}``; the
    Synthèse renders an honest "—" when ``total`` is 0.

    Degrades to zeros (never raises) so a missing store or an unreachable Postgres reads
    as "no votes yet", never as a broken dashboard.
    """
    window = f"created_at >= now() - interval '{int(period_days)} days'" if period_days else "TRUE"
    where = f"agent_id = %s AND NOT synthetic AND ({window})"
    try:
        async with _connection() as conn:
            conn.row_factory = dict_row
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT count(*) FILTER (WHERE rating = 'up') AS up, "  # noqa: S608
                    f"count(*) AS total FROM customer_feedback WHERE {where}",
                    (agent_id,),
                )
                row = await cur.fetchone() or {}
    except Exception as exc:  # never break the Synthèse over a feedback read
        sys.stderr.write(f"tessera.observability.agent_synthese: csat read failed: {exc}\n")
        return {"up": 0, "total": 0}
    return {"up": int(row.get("up") or 0), "total": int(row.get("total") or 0)}


# --- S1 journal scan -----------------------------------------------------------


def _scan_journal(agent_id: str, since: datetime | None) -> dict[str, Any]:
    """Single pass over the S1 hash-chained journal, scoped to ``agent_id``.

    Returns the handoff counts (incoming/outgoing), the supervisor routing-motive
    distribution (by the prefix of ``reason``), and the most recent journal events
    (handoffs + guard/tool decisions) for the AT-01 activity feed. Everything here
    is a real, tamper-evident S1 event — never a fixture.
    """
    handoffs_in = handoffs_out = 0
    routing: Counter[str] = Counter()
    handoff_events: list[dict[str, Any]] = []
    guard_events: deque[dict[str, Any]] = deque(maxlen=_JOURNAL_EVENT_CAP)

    for obj in read_ledger_entries():
        when = _parse_iso(obj.get("occurred_at"))
        if since is not None and when is not None and when < since:
            continue
        kind = obj.get("type")
        if kind == "tessera.agent.handoff":
            _consume_handoff(obj, agent_id, when, handoff_events)
            if obj.get("to_agent") == agent_id:
                handoffs_in += 1
            if obj.get("from_agent") == agent_id:
                handoffs_out += 1
        elif kind == "tessera.agent.routing" and obj.get("agent_id") == agent_id:
            motif = str(obj.get("reason") or "").split("->", 1)[0].strip() or "autre"
            routing[motif] += 1
        elif kind == "tessera.guard.audit" and obj.get("agent_id") == agent_id:
            guard_events.append(_guard_event(obj, when))

    events = sorted(
        [e for e in (*handoff_events, *guard_events) if e["when"] is not None],
        key=lambda e: e["when"],
        reverse=True,
    )
    return {"in": handoffs_in, "out": handoffs_out, "routing": routing, "events": events}


def _consume_handoff(
    obj: dict[str, Any], agent_id: str, when: datetime | None, out: list[dict[str, Any]]
) -> None:
    if obj.get("to_agent") == agent_id:
        out.append(
            {
                "when": when,
                "label": "Conversation reçue par handoff",
                "detail": f"Depuis {obj.get('from_agent') or '-'}",
                "kind": "info",
                "badge": "Handoff entrant",
            }
        )
    if obj.get("from_agent") == agent_id:
        out.append(
            {
                "when": when,
                "label": "Conversation transférée",
                "detail": f"Vers {obj.get('to_agent') or '-'}",
                "kind": "warn",
                "badge": "Handoff sortant",
            }
        )


def _guard_event(obj: dict[str, Any], when: datetime | None) -> dict[str, Any]:
    """Map a guard.audit entry to a feed item (denied -> garde-fou, allowed -> outil)."""
    target = str(obj.get("target") or "")
    if obj.get("outcome") == "denied":
        decisions = obj.get("decisions")
        rule = ""
        if isinstance(decisions, list) and decisions:
            first = decisions[0]
            if isinstance(first, dict):
                rule = str(first.get("rule") or first.get("name") or "")
        return {
            "when": when,
            "label": "Règle de garde-fou déclenchée",
            "detail": rule or target or "contenu sensible détecté",
            "kind": "crit",
            "badge": "Garde-fou",
        }
    return {
        "when": when,
        "label": "Outil appelé",
        "detail": _TOOL_LABELS.get(target, target or "outil"),
        "kind": "ok",
        "badge": "Outil",
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
            # best-effort: skip a prompt YAML that will not load — non-gating coverage view (0015)
            continue
        if isinstance(loaded, dict):
            for key in loaded:
                per_key.setdefault(str(key), set()).add(lang)
    rows = [{"key": k, "langs": sorted(v)} for k, v in sorted(per_key.items())]
    return rows, _newest_mtime(_PROMPTS_DIR, "*.yaml")


def _capabilities_for(agent: Agent) -> list[str]:
    """Capability labels from this agent's governed tool bindings (registry)."""
    return [_TOOL_LABELS.get(t, t.replace("_", " ").title()) for t in agent.tools]


# --- assembly ------------------------------------------------------------------


def _kpi(
    key: str,
    label: str,
    value: str,
    delta: str,
    good: bool,
    series: Sequence[int],
    explain: dict[str, str] | None = None,
) -> dict[str, object]:
    kpi: dict[str, object] = {
        "key": key,
        "label": label,
        "value": value,
        "delta": delta,
        "good": good,
        "series": list(series),
    }
    # A MetricInfo tooltip (what/how/source) — attached only when a cell has a story
    # worth explaining, so an honest-but-small number is not mistaken for a bug.
    if explain is not None:
        kpi["explain"] = explain
    return kpi


def _delta_vs_yesterday(series: Sequence[float]) -> str:
    """Last-vs-previous day delta as a signed percentage, or '-' when undefined."""
    if len(series) < _MIN_SERIES or series[-2] == 0:
        return "-"
    pct = round(100 * (series[-1] - series[-2]) / series[-2])
    return f"{pct:+d}% vs hier"


def _period_label(period_days: int | None) -> str:
    """Human window label for the meta strip."""
    if period_days is None:
        return "Tout l'historique"
    if period_days <= 1:
        return "24 dernières heures"
    return f"{period_days} derniers jours"


def _page(agent_id: str, page: str) -> str:
    """Build an agent-scoped cockpit link (mirrors the front-end ``agentPath``)."""
    return f"/agents/{agent_id}/{page}"


def _kpis(tx: dict[str, Any], journal: dict[str, Any]) -> list[dict[str, object]]:
    """The 7 operational KPIs (events only), scoped to the agent + window."""
    totals = tx["totals"]
    daily = tx["daily"]
    n_convs = int(totals.get("convs") or 0)
    n_turns = int(totals.get("turns") or 0)
    n_subjects = int(totals.get("subjects") or 0)
    escal_convs = int(totals.get("escal_convs") or 0)
    obs_lat_ms = totals.get("lat_ms")

    # Real customer CSAT (ADR 0041): the share of positive votes over real votes. ``None``
    # total ⇒ honest "—" (nobody has voted yet), never a fabricated satisfaction.
    csat = tx.get("csat") or {}
    csat_up = int(csat.get("up") or 0)
    csat_total = int(csat.get("total") or 0)
    csat_pct = round(100 * csat_up / csat_total) if csat_total else None

    conv_series = [int(d["convs"]) for d in daily][-_SPARK_DAYS:]
    turn_series = [int(d["turns"]) for d in daily][-_SPARK_DAYS:]
    lat_series = [round(float(d["lat_ms"])) if d.get("lat_ms") else 0 for d in daily][-_SPARK_DAYS:]
    res_series = [
        round(100 * (int(d["convs"]) - int(d["escal_convs"] or 0)) / int(d["convs"]))
        if int(d["convs"])
        else 0
        for d in daily
    ][-_SPARK_DAYS:]

    resolution_pct = round(100 * (n_convs - escal_convs) / n_convs, 1) if n_convs else 0.0
    handoffs_in = int(journal["in"])
    handoffs_out = int(journal["out"])

    return [
        _kpi(
            "conversations",
            "Conversations touchées (24h)",
            _fmt_int(n_convs),
            _delta_vs_yesterday(conv_series),
            True,
            conv_series,
        ),
        _kpi(
            "turns",
            "Tours traités (24h)",
            _fmt_int(n_turns),
            _delta_vs_yesterday(turn_series),
            True,
            turn_series,
        ),
        # Distinct clients the agent served, from the turn's ``subject_id`` (ADR 0040).
        # Honest, not fabricated: a turn with no captured identity (anonymous) is not
        # counted, so the value is the real distinct-identity count or an honest "—".
        # The customer plane shares one seeded demo identity today, so this reads small
        # there; recouvrement counts distinct cases, where it is already meaningful.
        _kpi(
            "users",
            "Utilisateurs servis (24h)",
            _fmt_int(n_subjects) if n_subjects else "—",
            ("clients distincts servis" if n_subjects else "aucune identité client sur la période"),
            True,
            [],
            explain={
                "what": "Le nombre de clients DISTINCTS servis par l'agent sur la période.",
                "how": (
                    "count(DISTINCT subject_id) sur les tours réels ; un tour anonyme (sans "
                    "identité captée) n'est pas compté et les tours de test sont exclus."
                ),
                "source": (
                    "conversation_messages.subject_id (ADR 0040). Le plan client partage une "
                    "identité de démo unique aujourd'hui, d'où un nombre faible ; le recouvrement "
                    "compte des dossiers distincts. Un « 1 » ici est honnête, pas un bug."
                ),
            },
        ),
        _kpi(
            "resolution",
            "Taux de résolution",
            f"{resolution_pct:.1f}%".replace(".", ",") if n_convs else "—",
            (_delta_vs_yesterday(res_series) if n_convs else "aucune conversation"),
            resolution_pct >= _GOOD_RESOLUTION_PCT,
            res_series,
        ),
        # Real customer CSAT from captured 👍/👎 votes (ADR 0041). Honest "—" until a
        # customer has actually voted — a satisfaction rate is never fabricated.
        _kpi(
            "satisfaction",
            "Satisfaction moyenne",
            f"{csat_pct}%" if csat_pct is not None else "—",
            (
                f"{csat_up} / {csat_total} avis positifs"
                if csat_total
                else "aucun avis client sur la période"
            ),
            csat_pct is None or csat_pct >= _GOOD_CSAT_PCT,
            [],
            explain={
                "what": "La part d'avis clients positifs sur les réponses de l'agent.",
                "how": (
                    "count(pouce positif) / count(avis) sur les avis réels de la période ; "
                    "les avis laissés sur des tours de test sont exclus."
                ),
                "source": (
                    "customer_feedback — le pouce que le client laisse sous une réponse dans le "
                    "chat client (ADR 0041). « — » tant qu'aucun avis n'a été laissé."
                ),
            },
        ),
        _kpi(
            "latency",
            "Temps de réponse moyen",
            _secs(obs_lat_ms) if obs_lat_ms is not None else "—",
            ("trafic réel de l'agent" if obs_lat_ms is not None else "aucun tour mesuré"),
            (obs_lat_ms is not None and obs_lat_ms <= _GOOD_MEAN_MS),
            lat_series,
        ),
        _kpi(
            "handoffs",
            "Handoffs (24h)",
            str(handoffs_in + handoffs_out),
            f"{handoffs_in} entrants / {handoffs_out} sortants",
            True,
            [],
        ),
    ]


def _assemble(
    agent: Agent,
    cfg: dict[str, Any],
    tx: dict[str, Any],
    journal: dict[str, Any],
    chain_ok: bool,
    period_days: int | None = None,
    now: datetime | None = None,  # noqa: ARG001 — kept for signature stability/tests
) -> dict[str, object]:
    """Assemble the Synthese payload from the transcript + S1 journal + registry.

    Pure and I/O-free so it can be unit-tested with synthetic inputs.
    """
    agent_id = agent.id
    totals = tx["totals"]
    n_convs = int(totals.get("convs") or 0)
    n_msgs = int(totals.get("msgs") or 0)
    n_answers = int(totals.get("answers") or 0)
    escal_convs = int(totals.get("escal_convs") or 0)
    obs_lat_ms = totals.get("lat_ms")
    last_at = totals.get("last_at")
    cat_count = tx["cat_count"]
    doc_count = tx["doc_count"]
    handoffs_in = int(journal["in"])
    handoffs_out = int(journal["out"])
    resolution_pct = round(100 * (n_convs - escal_convs) / n_convs, 1) if n_convs else 0.0
    escal_pct = round(100 * escal_convs / n_convs, 1) if n_convs else 0.0

    owner = str(cfg.get("owner") or agent.owner)
    language = str(cfg.get("default_language") or _LANG_LABELS.get(agent.default_language, "—"))
    timezone = str(cfg.get("timezone") or "Europe/Paris")
    name = str(cfg.get("name") or agent.name)
    description = str(cfg.get("description") or agent.description)
    prompts_mtime = _newest_mtime(_PROMPTS_DIR, "*.yaml")

    kpis = _kpis(tx, journal)

    # Right column — Contexte de l'agent (governed identity, real fields only).
    context: dict[str, object] = {
        "name": name,
        "status": "actif",
        "agentId": agent_id,
        "description": description,
        "fields": [
            {"label": "Propriétaire", "value": owner},
            {"label": "Modèle principal", "value": agent.model or "—"},
            {"label": "Langue principale", "value": language},
            {"label": "Fuseau horaire", "value": timezone},
            {"label": "Garde-fous", "value": agent.guardrails},
            {"label": "Dernière mise à jour", "value": _fmt_dt(prompts_mtime)},
        ],
        "cta": "Voir la configuration",
        "ctaHref": _page(agent_id, "configurations"),
    }

    # Right column — Alertes opérationnelles (real thresholds; else "Aucune alerte").
    alert_items: list[dict[str, object]] = []
    if handoffs_out >= _HANDOFF_OUT_WARN:
        alert_items.append(
            {
                "label": "Handoffs sortants élevés",
                "detail": f"{handoffs_out} sur la période",
                "tone": "crit",
                "badge": "Critique",
            }
        )
    if escal_pct >= _ESCAL_WARN_PCT:
        alert_items.append(
            {
                "label": "Taux d'escalade en hausse",
                "detail": f"{escal_pct:.1f} % des conversations".replace(".", ","),
                "tone": "warn",
                "badge": "Attention",
            }
        )
    if not chain_ok:
        alert_items.append(
            {
                "label": "Chaîne d'audit rompue",
                "detail": "intégrité non vérifiée",
                "tone": "crit",
                "badge": "Critique",
            }
        )
    op_alerts: dict[str, object] = {
        "title": "Alertes opérationnelles",
        "cta": "Voir les garde-fous",
        "ctaHref": _page(agent_id, "garde-fous"),
        "items": alert_items,
    }

    # Right column — Accès rapides (real cockpit destinations).
    quick_access: dict[str, object] = {
        "title": "Accès rapides",
        "items": [
            {"label": "Surveiller", "sublabel": "Vue multi-agents", "href": "/surveiller"},
            {"label": "Agir", "sublabel": "Automatisations", "href": "/agir/automations"},
            {
                "label": "Connaissances",
                "sublabel": "Sources & mémoire",
                "href": _page(agent_id, "connaissances"),
            },
            {
                "label": "Prompts",
                "sublabel": "Versions & tests",
                "href": _page(agent_id, "prompts"),
            },
        ],
    }

    # Aperçu de l'agent (left) — identity snapshot, real values only.
    profile: dict[str, object] = {
        "name": name,
        "status": "actif",
        "fields": [
            {"label": "Nom", "value": name},
            {"label": "ID", "value": agent_id},
            {"label": "Modèle principal", "value": agent.model or "—"},
            {
                "label": "Sources rattachées",
                "value": f"{cat_count} sources / {doc_count} fragments",
            },
            {"label": "Conversations", "value": _fmt_int(n_convs)},
            {"label": "Dernière activité", "value": _fmt_dt(last_at)},
        ],
        "cta": "Voir la configuration active",
        "ctaHref": _page(agent_id, "configurations"),
    }

    capabilities: dict[str, object] = {
        "title": "Capacités principales",
        "items": _capabilities_for(agent),
        "cta": "Gérer les capacités",
        "ctaHref": _page(agent_id, "configurations"),
    }

    # Répartition des conversations — by supervisor routing motive (real S1 events).
    routing: Counter[str] = journal["routing"]
    routing_total = sum(routing.values())
    repartition: dict[str, object] = {
        "title": "Répartition des conversations (24h)",
        "subtitle": "Par motif de routage",
        "items": [
            {
                "label": _ROUTING_MOTIFS.get(motif, motif.capitalize()),
                "pct": round(100 * count / routing_total) if routing_total else 0,
                "tone": tone,
            }
            for (motif, count), tone in zip(routing.most_common(), _TONES, strict=False)
        ],
    }

    performance: dict[str, object] = {
        "title": "Performance détaillée (24h)",
        "rows": [
            {
                "label": "Taux de résolution",
                "value": f"{resolution_pct:.1f}%".replace(".", ","),
                "delta": f"{n_convs - escal_convs}/{n_convs}",
                "good": resolution_pct >= _GOOD_RESOLUTION_PCT,
            },
            {
                "label": "Taux d'escalade humaine",
                "value": f"{escal_pct:.1f}%".replace(".", ","),
                "delta": f"{escal_convs}/{n_convs}",
                "good": escal_pct < _ESCAL_WARN_PCT,
            },
            {
                "label": "Réponses générées",
                "value": _fmt_int(n_answers),
                "delta": "tours",
                "good": True,
            },
            {
                "label": "Messages échangés",
                "value": _fmt_int(n_msgs),
                "delta": "total",
                "good": True,
            },
            {
                "label": "Temps de réponse moyen",
                "value": _secs(obs_lat_ms) if obs_lat_ms is not None else "—",
                "delta": "réel" if obs_lat_ms is not None else "n/d",
                "good": obs_lat_ms is not None and obs_lat_ms <= _GOOD_MEAN_MS,
            },
            {
                "label": "Handoffs entrants / sortants",
                "value": f"{handoffs_in} / {handoffs_out}",
                "delta": "S1",
                "good": handoffs_out < _HANDOFF_OUT_WARN,
            },
        ],
        "cta": "Voir l'historique",
        "ctaHref": _page(agent_id, "historique"),
    }

    conversations: dict[str, object] = {
        "title": "Conversations récentes",
        "cta": "Voir l'historique des conversations",
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
        "title": "Activité de l'agent",
        "cta": "Voir toutes les activités",
        "ctaHref": _page(agent_id, "historique"),
        "rows": _activity_rows(tx, journal),
    }

    prompt_rows, _ = _prompt_inventory()
    prompts: dict[str, object] = {
        "title": "Prompts actifs",
        "cta": "Voir tous les prompts",
        "ctaHref": _page(agent_id, "prompts"),
        "rows": [
            {
                "name": r["key"].replace("_", " ").capitalize(),
                "version": f"{len(r['langs'])} langues",
                "status": "actif",
                "updated": f"Mis à jour le {_fmt_dt(prompts_mtime)}",
            }
            for r in prompt_rows[:_PROMPTS_SHOWN]
        ],
    }

    return {
        "meta": {
            "mode": "Données réelles",
            "period": _period_label(period_days),
            "updated": _fmt_dt(last_at),
            "replayAt": "État à date",
            "comparison": "Aucune comparaison",
        },
        "kpis": kpis,
        "context": context,
        "opAlerts": op_alerts,
        "quickAccess": quick_access,
        "profile": profile,
        "capabilities": capabilities,
        "repartition": repartition,
        "performance": performance,
        "conversations": conversations,
        "activity": activity,
        "prompts": prompts,
    }


def _activity_rows(tx: dict[str, Any], journal: dict[str, Any]) -> list[dict[str, object]]:
    """Merge transcript turns + S1 journal events into the AT-01 feed, newest first."""
    rows: list[dict[str, object]] = []
    for m in tx["recent_msgs"]:
        when = _aware(m.get("created_at"))
        is_user = m.get("role") == "user"
        lat = m.get("latency_ms")
        rows.append(
            {
                "when": when,
                "label": "Question reçue" if is_user else "Réponse générée",
                "detail": (
                    "tour utilisateur"
                    if is_user
                    else (f"Temps : {_secs(float(lat))}" if lat is not None else "réponse agent")
                ),
                "kind": "info" if is_user else "ok",
                "badge": "Question" if is_user else "Réponse",
            }
        )
    rows.extend(journal["events"])

    def _key(r: dict[str, object]) -> datetime:
        w = r.get("when")
        return w if isinstance(w, datetime) else datetime.min.replace(tzinfo=UTC)

    rows.sort(key=_key, reverse=True)
    out: list[dict[str, object]] = []
    for r in rows[:_RECENT_ACTIVITY]:
        at = r.get("when")
        out.append(
            {
                "time": (
                    at.astimezone(_PARIS).strftime("%H:%M") if isinstance(at, datetime) else "-"
                ),
                "label": str(r["label"]),
                "detail": str(r["detail"]),
                "kind": str(r["kind"]),
                "badge": str(r["badge"]),
            }
        )
    return out


async def compute_agent_synthese(
    agent_id: str = DEFAULT_AGENT_ID, period_days: int | None = None
) -> dict[str, object]:
    """Return the Synthese dashboard payload, sourced end to end from real data.

    Args:
        agent_id: The agent whose slice to compute. Transcript-derived figures and
            journal events are scoped to this agent (per-turn attribution) and all
            internal links point at ``/agents/<agent_id>/...``.
        period_days: Trailing window (in days) the operational figures are
            restricted to. ``None`` means the whole history.
    """
    try:
        agent = get_agent(agent_id)
    except KeyError:
        agent = get_agent(DEFAULT_AGENT_ID)
    cfg = _effective(agent.id)
    tx = await _fetch_transcript(agent.id, period_days)
    # Carry the real CSAT counts alongside the transcript aggregates (ADR 0041); the KPI
    # assembler reads ``tx["csat"]`` and renders an honest "—" when nobody has voted.
    tx["csat"] = await _fetch_csat(agent.id, period_days)
    since = datetime.now(UTC) - timedelta(days=period_days) if period_days else None
    journal = _scan_journal(agent.id, since)
    try:
        chain = verify_active_ledger()
        chain_ok = chain.verified
    except (OSError, ValueError):
        # Fail CLOSED, never open: an unverifiable chain (Postgres unreachable, a decode
        # error) must read as NOT-verified — reporting a green on a chain we could not verify
        # is exactly the "fabricated green" the project forbids. The twin in system_profile.py
        # already fails to False; this was the one that did not (P0.2 swallower fix).
        chain_ok = False
    return _assemble(agent, cfg, tx, journal, chain_ok, period_days=period_days)
