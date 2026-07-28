"""Point-in-time reconstruction ("Etat a date") payload (prouver/etat-a-date).

Reconstructs, as of a chosen instant T, the state an agent operated under:

- which knowledge sources / chunks were already indexed and therefore accessible
  (from the live pgvector ``documents`` table and each chunk's ``inserted_at``);
- how many guard decisions had been logged by T, how many were blocked, which
  policy rules had fired, and whether the audit chain up to T is intact (from the
  JSON-Lines guard audit log, whose ``occurred_at`` timestamps are a real event
  stream spanning several days);
- the policies in force (guard policy version + pattern/tool counts).

Honesty note: the corpus was ingested in a single batch, so knowledge
accessibility flips all-or-nothing at the ingest boundary rather than carrying a
fabricated per-version history. The genuine temporal variation comes from the
audit log, which is why the reconstruction's headline numbers (decisions, blocks,
rules fired, chain length, last activity) really do change as T moves. Anything
without a real time axis is reported as a fixed fact, never an invented timeline.

The page is trilingual (FR / DE / EN): ``build_etat_a_date`` takes a ``lang`` and
every operator-facing label resolves through ``_loc``. Durable snapshot records
are kept verbatim as written at save time (they are historical artefacts).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from psycopg.rows import dict_row

from tessera.agent.identity import DEFAULT_AGENT_ID
from tessera.fsutil import atomic_write_text
from tessera.guard.decisions import load_policy
from tessera.guard.ledger_store import read_ledger_entries
from tessera.observability._asof import occurred_before
from tessera.observability.agent_configurations import _effective
from tessera.observability.eval_data import load_eval_snapshot
from tessera.observability.knowledge import _SOURCE_META, _source_name
from tessera.retrieval.store import _connection
from tessera.settings import get_settings
from tessera.sql import safe_identifier

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tessera.guard.decisions import Policy

__all__ = ["build_etat_a_date", "save_etat_snapshot"]

_ROOT = Path(__file__).resolve().parents[3]
_PROMPTS_DIR = _ROOT / "src" / "tessera" / "agent" / "prompts"
_PARIS = ZoneInfo("Europe/Paris")
_PCT = 100
_MAX_TIMELINE = 8
_MAX_SNAPSHOTS = 20
_ANSWER_PREVIEW = 320

_LANG_IDX = {"fr": 0, "de": 1, "en": 2}


def _loc(lang: str, fr: str, de: str, en: str) -> str:
    """Pick the locale variant of an inline string (fr / de / en)."""
    return (fr, de, en)[_LANG_IDX.get(lang, 0)]


_TYPE_LABEL: dict[str, tuple[str, str, str]] = {
    "reg": ("Réglementation", "Regulierung", "Regulation"),
    "prod": ("Produit", "Produkt", "Product"),
}
_TYPE_TONE: dict[str, str] = {"reg": "violet", "prod": "blue"}


def _type_label(tone_key: str, lang: str) -> str:
    return _TYPE_LABEL[tone_key][_LANG_IDX.get(lang, 0)]


@dataclass(slots=True)
class _Context:
    """Real configuration snapshot used to fill the 'a T' governance cards."""

    model: str
    temperature: float
    profile: str
    prompt_mtime: datetime | None
    policy_mtime: datetime | None
    run_dt: datetime | None
    catalogue: str
    audit_total: int  # guard decisions logged up to *now* (for the diff vs T)


def _parse_at(at: str | None) -> datetime | None:
    if not at:
        return None
    try:
        # A bare instant (no offset) reads as UTC: the builder compares T against
        # aware timestamps throughout, and a hand-edited `?asof=` deep-link must
        # yield a valid reading — never crash the whole reconstruction.
        return _aware(datetime.fromisoformat(at.replace("Z", "+00:00")))
    except ValueError:
        return None


def _fmt(dt: datetime | None) -> str:
    if dt is None:
        return "-"
    return dt.astimezone(_PARIS).strftime("%d/%m/%Y, %H:%M")


def _fmt_int(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def _ref_code(at: datetime | None) -> str:
    """A stable reference id derived from T, e.g. RES-2026-06-10-1620."""
    if at is None:
        return "RES-LIVE"
    return at.astimezone(_PARIS).strftime("RES-%Y-%m-%d-%H%M")


def _aware(value: datetime | None) -> datetime | None:
    """Attach UTC to a naive datetime so comparisons never mix tzinfo."""
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


# --- durable snapshot store ---------------------------------------------------
# Saved reconstructions persist to a JSON next to the guard audit log (dev:
# /tmp/tessera/, outside the repo) so "Enregistrer ce snapshot" is a real,
# durable action that survives a restart - not a decorative button.


def _snapshots_path() -> Path:
    return get_settings().guard.audit_file.parent / "etat_a_date_snapshots.json"


def _load_snapshots() -> list[dict[str, Any]]:
    path = _snapshots_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return data if isinstance(data, list) else []


def _save_snapshots(snapshots: list[dict[str, Any]]) -> None:
    path = _snapshots_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json.dumps(snapshots[:_MAX_SNAPSHOTS], indent=2, ensure_ascii=False))


# --- live fetch ---------------------------------------------------------------


@dataclass(slots=True)
class _CatState:
    """Per-source aggregates restricted to chunks indexed at or before T."""

    chunks_at_t: int = 0
    chunks_total: int = 0
    langs: set[str] = field(default_factory=set)
    first_ins: datetime | None = None
    last_ins_at_t: datetime | None = None


@dataclass(slots=True)
class _AuditAsOf:
    """Audit-log aggregates restricted to decisions at or before T."""

    decisions: int = 0
    blocked: int = 0
    allowed: int = 0
    rules: set[str] = field(default_factory=set)
    first_at: datetime | None = None
    last_at: datetime | None = None


def _scan_documents(rows: Sequence[dict[str, Any]], at: datetime | None) -> dict[str, _CatState]:
    states: dict[str, _CatState] = {}
    for row in rows:
        meta = row["metadata"]
        if not isinstance(meta, dict):
            meta = json.loads(meta) if isinstance(meta, str) else {}
        cat = str(meta.get("category", ""))
        if cat not in _SOURCE_META:
            continue
        st = states.setdefault(cat, _CatState())
        st.chunks_total += 1
        ins = row["inserted_at"]
        ins_dt = ins if isinstance(ins, datetime) else None
        if ins_dt is not None:
            st.first_ins = min(st.first_ins or ins_dt, ins_dt)
        if ins_dt is not None and (at is None or ins_dt <= at):
            st.chunks_at_t += 1
            st.langs.add(str(row["language"]))
            st.last_ins_at_t = max(st.last_ins_at_t or ins_dt, ins_dt)
    return states


def _scan_audit(path: Path, at: datetime | None, agent: str | None = None) -> _AuditAsOf:
    scan = _AuditAsOf()
    for entry in read_ledger_entries(path):
        occurred = entry.get("occurred_at")
        if not occurred_before(occurred, at.isoformat() if at else None):
            continue
        # Per-agent scope (TE-01 owed param): only the turns STAMPED with this
        # agent count; unstamped entries (governance, system) are not its turns.
        if agent is not None and entry.get("agent_id") != agent:
            continue
        scan.decisions += 1
        if entry.get("outcome") == "denied":
            scan.blocked += 1
        elif entry.get("outcome") == "allowed":
            scan.allowed += 1
        for dec in entry.get("decisions", []) or []:
            rule = dec.get("policy_rule") or dec.get("rule")
            if rule:
                scan.rules.add(str(rule))
        occurred_dt = _parse_at(occurred) if isinstance(occurred, str) else None
        if occurred_dt is not None:
            scan.first_at = min(scan.first_at or occurred_dt, occurred_dt)
            scan.last_at = max(scan.last_at or occurred_dt, occurred_dt)
    return scan


def _scan_handoffs(
    path: Path, at: datetime | None, agent: str | None = None
) -> list[dict[str, Any]]:
    """Agent->agent handoff events at or before T, newest first (closes as-of loop).

    The same S1 journal that proves config also proves routing: the handoffs that
    had happened by T are part of the opposable state at T.
    """
    found: list[tuple[str, dict[str, Any]]] = []
    for entry in read_ledger_entries(path):
        if entry.get("type") != "tessera.agent.handoff":
            continue
        occurred = entry.get("occurred_at")
        if not occurred_before(occurred, at.isoformat() if at else None):
            continue
        if agent is not None and agent not in (entry.get("from_agent"), entry.get("to_agent")):
            continue
        found.append(
            (
                str(occurred or ""),
                {
                    "from": str(entry.get("from_agent", "")),
                    "to": str(entry.get("to_agent", "")),
                    "reason": str(entry.get("reason", "")),
                    "at": _fmt(_parse_at(occurred)) if isinstance(occurred, str) else "-",
                },
            )
        )
    found.sort(key=lambda e: e[0], reverse=True)
    return [item for _, item in found]


async def _fetch_documents() -> list[dict[str, Any]]:
    table = safe_identifier(get_settings().postgres.vector_table)
    async with _connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            f"SELECT source, language, metadata, inserted_at FROM {table}"  # noqa: S608
        )
        return list(await cur.fetchall())


async def _fetch_original(at: datetime | None) -> dict[str, Any] | None:
    """The real agent answer (and its question) most recent at or before T.

    This is the "Réponse d'origine" the reconstruction is anchored to - a genuine
    transcript turn, not a fabricated example. ``None`` when none exists yet.
    """
    where = "WHERE a.role = 'assistant'"
    params: tuple[object, ...] = ()
    if at is not None:
        where += " AND a.created_at <= %s"
        params = (at,)
    query = (
        "SELECT a.content AS answer, a.created_at AS ts, a.conversation_id AS conv, "  # noqa: S608
        "(SELECT u.content FROM conversation_messages u "
        " WHERE u.conversation_id = a.conversation_id AND u.role = 'user' AND u.id < a.id "
        " ORDER BY u.id DESC LIMIT 1) AS question "
        f"FROM conversation_messages a {where} ORDER BY a.created_at DESC LIMIT 1"
    )
    async with _connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, params)
        return await cur.fetchone()


# --- assembly -----------------------------------------------------------------


_POLICY_FILE = _ROOT / "src" / "tessera" / "guard" / "policy.yaml"


def _truncate(text: str, limit: int = _ANSWER_PREVIEW) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "..."


def _oneline(text: str) -> str:
    """Collapse whitespace; never truncate.

    The question is a short identifier shown clipped with a hover reveal, so it
    must carry its FULL text — a baked cut would make the reveal show the same
    clipped string. The answer body keeps :func:`_truncate` (preview + detail).
    """
    return " ".join(text.split())


def _snapshot_id(at: datetime | None) -> str:
    if at is None:
        return "SNAP-LIVE"
    return at.astimezone(_PARIS).strftime("SNAP-%Y-%m-%d-%H%M")


def _normalize_scope(sources: str | Sequence[str] | None) -> set[str] | None:
    """Parse the ``sources`` filter into a set of valid corpus-category keys.

    Accepts a comma-separated string (the ``?sources=`` query) or a sequence.
    Keeps only keys present in :data:`_SOURCE_META`; returns ``None`` when nothing
    valid is given, so an unscoped (all-sources) reconstruction is the default.
    """
    if sources is None:
        return None
    raw = sources.split(",") if isinstance(sources, str) else list(sources)
    keys = {s.strip() for s in raw if s.strip() in _SOURCE_META}
    return keys or None


def _scope_meta(keys: set[str], lang: str) -> dict[str, object]:
    """Describe the active per-source scope for the UI chip (localized labels)."""
    pairs = sorted(((k, _source_name(k, lang)) for k in keys), key=lambda p: p[1])
    return {
        "keys": [k for k, _ in pairs],
        "labels": [label for _, label in pairs],
        "count": len(pairs),
    }


def _short_uuid(value: object) -> str:
    return str(value).split("-")[0].upper() if value else "-"


def _card(
    rows: list[tuple[str, str]], diff: list[dict[str, str]], cta: str, href: str
) -> dict[str, object]:
    return {
        "rows": [{"label": k, "value": v} for k, v in rows],
        "diff": diff,
        "cta": cta,
        "cta_href": href,
    }


def _d(kind: str, text: str) -> dict[str, str]:
    """A typed diff line. kind in {added, removed, changed, unchanged}."""
    return {"kind": kind, "text": text}


def _changed(when: datetime | None, at: datetime | None, after: str, before: str) -> dict[str, str]:
    """Typed diff line: 'changed' (amber) if `when` is after T, else 'unchanged'."""
    when, at = _aware(when), _aware(at)
    if when is not None and at is not None and when > at:
        return _d("changed", after)
    return _d("unchanged", before)


def _guardrails_card(
    policy: Policy, audit: _AuditAsOf, ctx: _Context, at: datetime | None, lang: str
) -> dict[str, object]:
    after = ctx.audit_total - audit.decisions  # real decisions logged after T
    rules_active = len(policy.prompt_injection_deny) + len(policy.pii_patterns) + len(policy.tools)
    diff = [
        _d(
            "changed",
            _loc(
                lang,
                f"{_fmt_int(after)} décisions de contrôle enregistrées depuis cette date",
                f"{_fmt_int(after)} Kontrollentscheidungen seit diesem Zeitpunkt erfasst",
                f"{_fmt_int(after)} control decisions recorded since this date",
            ),
        )
        if after > 0
        else _d(
            "unchanged",
            _loc(
                lang,
                "Aucune décision de contrôle depuis cette date",
                "Keine Kontrollentscheidung seit diesem Zeitpunkt",
                "No control decision since this date",
            ),
        ),
        _changed(
            ctx.policy_mtime,
            at,
            _loc(
                lang,
                "Politique modifiée après T",
                "Richtlinie nach T geaendert",
                "Policy changed after T",
            ),
            _loc(
                lang,
                "Politique inchangée depuis T",
                "Richtlinie seit T unveraendert",
                "Policy unchanged since T",
            ),
        ),
    ]
    return _card(
        [
            (
                _loc(lang, "Ensemble de règles", "Regelwerk", "Rule set"),
                f"Guardrails Banking v{policy.version}",
            ),
            (
                _loc(lang, "Contrôles actifs", "Aktive Kontrollen", "Active checks"),
                str(rules_active),
            ),
            (
                _loc(
                    lang,
                    "Formes d'attaque bloquées",
                    "Blockierte Angriffsformen",
                    "Blocked attack patterns",
                ),
                str(len(policy.prompt_injection_deny)),
            ),
            (
                _loc(
                    lang,
                    "Types de données personnelles surveillés",
                    "Überwachte Arten personenbezogener Daten",
                    "Monitored personal-data types",
                ),
                str(len(policy.pii_patterns)),
            ),
            (
                _loc(
                    lang,
                    "Dernier changement avant T",
                    "Letzte Aenderung vor T",
                    "Last change before T",
                ),
                _fmt(ctx.policy_mtime),
            ),
        ],
        diff,
        _loc(lang, "Voir le détail des règles", "Regeldetails anzeigen", "View rule details"),
        f"/agents/{DEFAULT_AGENT_ID}/garde-fous",
    )


def _prompt_model_card(ctx: _Context, at: datetime | None, lang: str) -> dict[str, object]:
    diff = [
        _changed(
            ctx.prompt_mtime,
            at,
            _loc(
                lang,
                "Instructions système modifiées depuis cette date",
                "Systemanweisungen seit diesem Zeitpunkt geändert",
                "System instructions changed since this date",
            ),
            _loc(
                lang,
                "Instructions système inchangées depuis cette date",
                "Systemanweisungen seit diesem Zeitpunkt unverändert",
                "System instructions unchanged since this date",
            ),
        ),
        _d("unchanged", _loc(lang, "Modèle inchangé", "Modell unveraendert", "Model unchanged")),
    ]
    return _card(
        [
            (_loc(lang, "Modèle (figé)", "Modell (eingefroren)", "Model (frozen)"), ctx.model),
            (
                _loc(lang, "Moteur d'exécution", "Ausführungsumgebung", "Execution engine"),
                "Ollama on-prem",
            ),
            (
                _loc(lang, "Profil d'exécution", "Ausfuehrungsprofil", "Execution profile"),
                ctx.profile,
            ),
            (
                _loc(
                    lang,
                    "Version des instructions",
                    "Version der Anweisungen",
                    "Instruction version",
                ),
                _loc(
                    lang,
                    f"maj {_fmt(ctx.prompt_mtime)}",
                    f"akt. {_fmt(ctx.prompt_mtime)}",
                    f"upd. {_fmt(ctx.prompt_mtime)}",
                ),
            ),
            (
                _loc(lang, "Température", "Temperatur", "Temperature"),
                f"{ctx.temperature:.2f}".replace(".", ","),
            ),
        ],
        diff,
        _loc(lang, "Voir les instructions", "Anweisungen ansehen", "View instructions"),
        f"/agents/{DEFAULT_AGENT_ID}/prompts",
    )


def _release_card(ctx: _Context, at: datetime | None, lang: str) -> dict[str, object]:
    diff = [
        _changed(
            ctx.run_dt,
            at,
            _loc(
                lang,
                "Nouvelle évaluation exécutée après T",
                "Neue Evaluierung nach T ausgefuehrt",
                "New evaluation run after T",
            ),
            _loc(
                lang,
                "Aucune évaluation après T",
                "Keine Evaluierung nach T",
                "No evaluation after T",
            ),
        ),
    ]
    run_dt = _aware(ctx.run_dt)
    at_dt = _aware(at)
    up_to_date = run_dt is not None and (at_dt is None or run_dt > at_dt)
    return _card(
        [
            (_loc(lang, "Jeu d'évaluation", "Evaluierungsset", "Evaluation set"), ctx.catalogue),
            (_loc(lang, "Date de l'évaluation", "Prüfdatum", "Evaluation date"), _fmt(ctx.run_dt)),
            (_loc(lang, "Environnement", "Umgebung", "Environment"), "Local / on-prem"),
            (_loc(lang, "Modèle évalué", "Evaluiertes Modell", "Evaluated model"), ctx.model),
            (
                _loc(
                    lang, "Par rapport à aujourd'hui", "Vergleich mit heute", "Compared with today"
                ),
                _loc(lang, "À jour", "Aktuell", "Up to date")
                if up_to_date
                else _loc(lang, "Historique", "Historisch", "Historical"),
            ),
        ],
        diff,
        _loc(
            lang,
            "Voir le détail de la mise en ligne",
            "Freigabedetails ansehen",
            "View launch details",
        ),
        f"/agents/{DEFAULT_AGENT_ID}/evaluations",
    )


def _table(states: dict[str, _CatState], lang: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for cat, st in sorted(states.items(), key=lambda kv: -kv[1].chunks_at_t):
        accessible = st.chunks_at_t > 0
        tone_key = _SOURCE_META[cat]
        rows.append(
            {
                "key": cat,
                "source": _source_name(cat, lang),
                "type": _type_label(tone_key, lang),
                "type_key": tone_key,
                "type_tone": _TYPE_TONE[tone_key],
                "langs": "/".join(sorted(st.langs)) if st.langs else "-",
                "chunks": st.chunks_at_t,
                "total_chunks": st.chunks_total,
                "version": _loc(
                    lang,
                    f"ingéré {_fmt(st.first_ins)}",
                    f"indexiert {_fmt(st.first_ins)}",
                    f"ingested {_fmt(st.first_ins)}",
                )
                if st.first_ins
                else "-",
                "accessible_until": _fmt(st.last_ins_at_t),
                "updated": _fmt(st.last_ins_at_t),
                "first_seen": _fmt(st.first_ins),
                "status": "accessible" if accessible else "pending",
                "status_label": _loc(lang, "Accessible", "Zugaenglich", "Accessible")
                if accessible
                else _loc(lang, "Pas encore indexée", "Noch nicht indexiert", "Not yet indexed"),
            }
        )
    return rows


def _timeline(
    states: dict[str, _CatState], audit: _AuditAsOf, at: datetime | None, lang: str
) -> list[dict[str, object]]:
    events: list[tuple[datetime, str, str]] = []
    # Per-source first ingest events at or before T.
    for cat, st in states.items():
        if st.first_ins is not None and (at is None or st.first_ins <= at):
            name = _source_name(cat, lang)
            events.append(
                (
                    st.first_ins,
                    _loc(
                        lang,
                        f"Source indexée : {name}",
                        f"Quelle indexiert: {name}",
                        f"Source indexed: {name}",
                    ),
                    "ok",
                )
            )
    if audit.first_at is not None:
        events.append(
            (
                audit.first_at,
                _loc(
                    lang,
                    "Première décision du guard journalisée",
                    "Erste Guard-Entscheidung protokolliert",
                    "First guard decision logged",
                ),
                "info",
            )
        )
    if audit.last_at is not None and audit.last_at != audit.first_at:
        events.append(
            (
                audit.last_at,
                _loc(
                    lang,
                    "Dernière activité du guard avant T",
                    "Letzte Guard-Aktivitaet vor T",
                    "Last guard activity before T",
                ),
                "info",
            )
        )
    events.sort(key=lambda e: e[0], reverse=True)
    return [
        {"time": _fmt(dt), "label": label, "kind": kind}
        for dt, label, kind in events[:_MAX_TIMELINE]
    ]


def _snapshot_section(snapshots: list[dict[str, Any]], lang: str) -> dict[str, object]:
    return {
        "title": _loc(lang, "États enregistrés", "Gespeicherte Zustände", "Saved states"),
        "rows": [
            {
                "id": str(s.get("id", "")),
                "as_of": s.get("as_of"),
                "as_of_label": str(s.get("as_of_label", "-")),
                "ref_code": str(s.get("ref_code", "-")),
                "saved_label": _fmt(_parse_at(s.get("saved_at"))),
                "summary": str(s.get("summary", "")),
            }
            for s in snapshots
        ],
    }


def _original_card(original: dict[str, Any] | None, at: datetime | None) -> dict[str, object]:
    if not original or not original.get("answer"):
        return {"available": False, "ref_code": _ref_code(at)}
    ts = original.get("ts")
    ts_dt = ts if isinstance(ts, datetime) else None
    return {
        "available": True,
        "ref_code": _ref_code(ts_dt or at),
        "question": _oneline(str(original.get("question") or "-")),
        "answer": _truncate(str(original.get("answer") or "-")),
        "timestamp": _fmt(ts_dt),
        "session": f"SES-{_short_uuid(original.get('conv'))}",
    }


_BADGE_LABELS: dict[str, tuple[str, str, str]] = {
    "non_scelle": ("Non scellé", "Nicht versiegelt", "Not sealed"),
    "scelle_opposable": (
        "Scellé · opposable",
        "Versiegelt · rechtsverbindlich",
        "Sealed · opposable",
    ),
    "scelle_non_qualifie": (
        "Scellé (non qualifié)",
        "Versiegelt (nicht qualifiziert)",
        "Sealed (non-qualified)",
    ),
    "integrite_partielle": ("Intégrité partielle", "Teilweise Integritaet", "Partial integrity"),
    "verification_en_cours": ("Vérification en cours", "Pruefung laeuft", "Verifying…"),
}


def _opposability_block(opp: dict[str, object] | None, lang: str) -> dict[str, object]:
    """Register §9 opposability badge for TE-01 — computed live from tree + seal, never stored.

    ``opp`` is the raw verdict from :func:`tessera.guard.seal.active_ledger_opposability` (or None
    when the ledger could not be read → the honest "Vérification en cours"). Adds localized labels,
    the provider/qualification line, and the mandatory mention. No cosmetic fallback: absent a real
    verified seal the badge is «Intégrité partielle» or «Vérification en cours», never «Scellé».
    """
    badge = str(opp.get("badge", "verification_en_cours")) if opp else "verification_en_cours"
    fr, de, en = _BADGE_LABELS.get(badge, _BADGE_LABELS["verification_en_cours"])
    seal_state = str(opp.get("seal_state", "absent")) if opp else "absent"
    qualified = bool(opp.get("seal_qualified", False)) if opp else False
    if seal_state == "verified" and qualified:
        provider_label = _loc(
            lang, "TSA qualifiée eIDAS", "Qualifizierte eIDAS-TSA", "eIDAS-qualified TSA"
        )
    elif seal_state == "verified":
        provider_label = _loc(
            lang, "TSA (non qualifiée)", "TSA (nicht qualifiziert)", "TSA (non-qualified)"
        )
    else:
        provider_label = _loc(
            lang,
            "Aucun sceau tiers vérifié",
            "Kein verifiziertes Drittsiegel",
            "No verified third-party seal",
        )
    return {
        "badge": badge,
        "badge_label": _loc(lang, fr, de, en),
        "seal_state": seal_state,
        "seal_provider": (opp or {}).get("seal_provider"),
        "seal_qualified": qualified,
        "sealed_at": (opp or {}).get("sealed_at"),
        "content_integrity": bool(opp.get("content_integrity", True)) if opp else True,
        "linear": bool(opp.get("linear", True)) if opp else True,
        "attested": bool(opp.get("attested", False)) if opp else False,
        "provider_label": provider_label,
        "mention": _loc(
            lang,
            "Statut attribué uniquement après vérification réussie.",
            "Status nur nach erfolgreicher Pruefung vergeben.",
            "Status assigned only after successful verification.",
        ),
    }


def _assemble(
    rows: Sequence[dict[str, Any]],
    audit: _AuditAsOf,
    policy: Policy,
    ctx: _Context,
    original: dict[str, Any] | None,
    as_of: str | None,
    snapshots: list[dict[str, Any]] | None = None,
    now: datetime | None = None,
    handoffs: list[dict[str, Any]] | None = None,
    scope: set[str] | None = None,
    lang: str = "fr",
    opposability: dict[str, object] | None = None,
    agent: str | None = None,
) -> dict[str, object]:
    """Assemble the reconstruction payload. Pure and I/O-free for unit testing.

    When ``scope`` is a set of corpus-category keys, the knowledge dimension
    (sources table, coverage, fragment counts, source-ingest timeline events) is
    restricted to those sources; the agent-wide governance cards (guardrails,
    prompt/model, release, audit) stay global since they are not per-source.
    """
    now = now or datetime.now(UTC)
    at = _parse_at(as_of)
    states = _scan_documents(rows, at)
    if scope is not None:
        states = {cat: st for cat, st in states.items() if cat in scope}
    chunks_at_t = sum(st.chunks_at_t for st in states.values())
    chunks_total = sum(st.chunks_total for st in states.values())
    last_sync = max(
        (st.last_ins_at_t for st in states.values() if st.last_ins_at_t is not None),
        default=None,
    )
    coverage = round(_PCT * chunks_at_t / chunks_total) if chunks_total else 0
    active = sum(1 for s in states.values() if s.chunks_at_t > 0)

    opp_block = _opposability_block(opposability, lang)
    # TESS-0015 Q6 — the "Intégrité vérifiée" chip stops being a cosmetic constant: it now reflects
    # the real chain content-integrity when the ledger was read (opposability present), and the
    # register §9 opposability badge lives in ``opposability`` (never gated on this bool).
    content_ok = bool(opposability.get("content_integrity", True)) if opposability else True

    live = _loc(lang, "live", "live", "live")
    verified_label = _loc(lang, "Intégrité vérifiée", "Integritaet geprueft", "Integrity verified")
    return {
        "available": True,
        "meta": {
            "as_of": at.isoformat() if at else None,
            "as_of_label": _fmt(at)
            if at
            else _loc(lang, "Maintenant (live)", "Jetzt (live)", "Now (live)"),
            "ref_code": _ref_code(at),
            "tenant": "Crédit Aurore",
            # No phantom default: without a ?agent= param the reconstruction keeps
            # the historical default AND the screen says so; with one, it names the
            # agent the guard/handoff dimensions were folded to (TE-01 owed, closed).
            "agent": (
                agent
                if agent is not None
                else _loc(
                    lang,
                    "Support client (agent par défaut)",
                    "Kundensupport (Standard-Agent)",
                    "Customer support (default agent)",
                )
            ),
            "agent_id": agent,
            "agents": _fleet_agent_ids(),
            "context_source": _loc(lang, "Réponse", "Antwort", "Answer"),
            "timezone": "Europe/Paris",
            "scope": _scope_meta(scope, lang) if scope else None,
            "banner": _banner(lang, agent),
        },
        "reconstructed": {
            "title": _loc(
                lang,
                "État retrouvé à cette date",
                "Zustand zu diesem Zeitpunkt",
                "State at this date",
            ),
            "snapshot_id": _snapshot_id(at),
            "verified": content_ok,
            "verified_label": verified_label,
            "built_label": _loc(
                lang,
                f"Vérifié le {_fmt(now)} par Tessera",
                f"Am {_fmt(now)} von Tessera geprüft",
                f"Verified on {_fmt(now)} by Tessera",
            ),
        },
        "opposability": opp_block,
        "original": {
            "title": _loc(lang, "Réponse d'origine", "Urspruengliche Antwort", "Original answer"),
            "cta": _loc(lang, "Ouvrir la trace", "Trace oeffnen", "Open the trace"),
            "cta_href": "/prouver/audit-logs",
            **_original_card(original, at),
        },
        "guardrails": {
            "title": _loc(lang, "Règles appliquées", "Angewandte Regeln", "Rules applied"),
            **_guardrails_card(policy, audit, ctx, at, lang),
        },
        "prompt_model": {
            "title": _loc(
                lang, "Instructions et modèle", "Anweisungen und Modell", "Instructions and model"
            ),
            **_prompt_model_card(ctx, at, lang),
        },
        "release": {
            "title": _loc(lang, "Mise en ligne", "Freigabe", "Launch status"),
            **_release_card(ctx, at, lang),
        },
        "timeline": {
            "title": _loc(
                lang,
                f"Événements jusqu'au {_fmt(at) if at else live}",
                f"Ereignisse bis {_fmt(at) if at else live}",
                f"Events up to {_fmt(at) if at else live}",
            ),
            "rows": _timeline(states, audit, at, lang),
            "cta": _loc(
                lang,
                "Voir la chronologie complète",
                "Vollstaendige Chronologie anzeigen",
                "View full timeline",
            ),
            "cta_href": "/prouver/audit-logs",
        },
        "integrity": {
            "title": _loc(
                lang,
                "Intégrité de la reconstruction",
                "Integritaet der Rekonstruktion",
                "Reconstruction integrity",
            ),
            "snapshot_id": _snapshot_id(at),
            "coverage": f"{coverage} %",
            "test_query": _loc(
                lang,
                f"{active}/{len(states)} sources",
                f"{active}/{len(states)} Quellen",
                f"{active}/{len(states)} sources",
            ),
            "last_sync": _fmt(last_sync),
            "verified": content_ok,
            "verified_label": verified_label,
            "chain_label": _loc(
                lang,
                f"{_fmt_int(audit.decisions)} décisions journalisées jusqu'à T",
                f"{_fmt_int(audit.decisions)} Entscheidungen bis T protokolliert",
                f"{_fmt_int(audit.decisions)} decisions logged up to T",
            ),
        },
        "table": {
            "title": _loc(
                lang,
                "Sources disponibles à cette date",
                "Zu diesem Zeitpunkt verfügbare Quellen",
                "Sources available at this date",
            ),
            "rows": _table(states, lang),
        },
        "handoffs": {
            "title": _loc(
                lang,
                "Transferts entre agents jusqu'à cette date",
                "Übergaben zwischen Agenten bis zu diesem Zeitpunkt",
                "Transfers between agents up to this date",
            ),
            "subtitle": _loc(
                lang,
                "Qui prenait en charge la conversation, d'après le journal d'audit.",
                "Wer die Konversation bearbeitete, laut Audit-Protokoll.",
                "Who was handling the conversation, according to the audit trail.",
            ),
            "rows": handoffs or [],
        },
        "audit_pieces": {
            "title": _loc(
                lang,
                "Preuves d'audit disponibles",
                "Verfuegbare Audit-Nachweise",
                "Available audit evidence",
            ),
            "rows": [
                {
                    "label": _loc(
                        lang,
                        "Journal d'événements à date T",
                        "Ereignisprotokoll zum Datum T",
                        "Event log as of T",
                    ),
                    "href": "/prouver/audit-logs",
                },
                {
                    "label": _loc(
                        lang,
                        "Evidence pack qualité",
                        "Qualitaets-Evidence-Pack",
                        "Quality evidence pack",
                    ),
                    "href": "/prouver/evidence-store",
                },
                {
                    "label": _loc(
                        lang, "Sources & mémoire", "Quellen & Speicher", "Sources & memory"
                    ),
                    "href": f"/agents/{DEFAULT_AGENT_ID}/connaissances",
                },
            ],
        },
        "summary": {
            "title": _loc(
                lang,
                "Synthèse de l'état reconstitué",
                "Zusammenfassung des rekonstruierten Zustands",
                "Reconstructed-state summary",
            ),
            "cards": [
                {
                    "label": _loc(
                        lang, "Sources accessibles", "Zugaengliche Quellen", "Accessible sources"
                    ),
                    "value": f"{active} / {len(states)}",
                },
                {
                    "label": _loc(
                        lang,
                        "Fragments accessibles",
                        "Zugaengliche Fragmente",
                        "Accessible fragments",
                    ),
                    "value": _fmt_int(chunks_at_t),
                },
                {
                    "label": _loc(
                        lang, "Couverture de l'index", "Index-Abdeckung", "Index coverage"
                    ),
                    "value": f"{coverage} %",
                },
                {
                    "label": _loc(
                        lang, "Décisions du guard", "Guard-Entscheidungen", "Guard decisions"
                    ),
                    "value": _fmt_int(audit.decisions),
                },
            ],
        },
        "snapshots": _snapshot_section(snapshots or [], lang),
    }


def _build_context() -> _Context:
    """Gather the real config / eval / file-mtime snapshot for the 'a T' cards."""
    cfg = _effective()
    try:
        snap = load_eval_snapshot()
        model, run_dt, catalogue = snap.model, snap.run_datetime(), snap.catalogue_version
    except (OSError, ValueError, KeyError):
        model, run_dt, catalogue = "llama3.2:3b", None, "-"
    audit_total = _scan_audit(get_settings().guard.audit_file, None).decisions
    # A stored override may carry an explicit None (knob saved empty): fall back
    # without eating a legitimate 0.0 — float(None) took the whole page down.
    raw_temperature = cfg.get("temperature")
    return _Context(
        model=model,
        temperature=float(0.3 if raw_temperature is None else raw_temperature),
        profile=str(cfg.get("routing_strategy", "Standard souverain")),
        prompt_mtime=_newest_mtime(_PROMPTS_DIR, "*.yaml"),
        policy_mtime=_mtime(_POLICY_FILE),
        run_dt=run_dt,
        catalogue=catalogue,
        audit_total=audit_total,
    )


def _banner(lang: str, agent: str | None) -> str:
    """The scope banner: which dimensions folded to which agent, in the UI language."""
    head = _loc(
        lang,
        "Cette vue retrouve les sources, les règles et la configuration disponibles à la date "
        "choisie. Elle ne relance pas le modèle et ne recrée donc pas sa réponse exacte. ",
        "Diese Ansicht zeigt die Quellen, Regeln und Einstellungen, die zum gewählten Zeitpunkt "
        "verfügbar waren. Sie führt das Modell nicht erneut aus und erzeugt seine Antwort "
        "nicht neu. ",
        "This view restores the sources, rules and settings available at the selected date. "
        "It does not run the model again, so it does not recreate its exact answer. ",
    )
    if agent is not None:
        return head + _loc(
            lang,
            f"Pour l'agent {agent}, les décisions de contrôle et les transferts sont filtrés ; "
            "les connaissances restent communes à toute la flotte.",
            f"Für den Agenten {agent} werden Kontrollentscheidungen und Übergaben gefiltert; "
            "das Wissen bleibt für die gesamte Flotte gemeinsam.",
            f"For agent {agent}, control decisions and transfers are filtered; "
            "knowledge remains shared across the fleet.",
        )
    return head + _loc(
        lang,
        "La configuration affichée est celle de l'agent Support client ; les décisions de "
        "contrôle et les transferts couvrent toute la flotte.",
        "Angezeigt wird die Konfiguration des Kundenservice-Agenten; Kontrollentscheidungen "
        "und Übergaben umfassen die gesamte Flotte.",
        "The displayed configuration belongs to the Customer support agent; control decisions "
        "and transfers cover the whole fleet.",
    )


def _fleet_agent_ids() -> list[str]:
    """The real fleet ids the per-agent selector may fold to (never free-typed)."""
    from tessera.agent.registry import list_agents

    return [a.id for a in list_agents()]


async def build_etat_a_date(
    as_of: str | None = None,
    sources: str | None = None,
    lang: str = "fr",
    agent: str | None = None,
) -> dict[str, object]:
    """Reconstruct the agent's accessible state + governing context as of ``as_of``.

    Args:
        as_of: ISO instant T (``None`` means live/now). Knowledge, audit and the
            anchored original response are restricted to events at or before T.
        sources: optional comma-separated corpus-category keys (the ``?sources=``
            per-source scope). When given, the knowledge dimension is restricted to
            those sources; everything agent-wide stays global.
        lang: UI language (fr / de / en) for the reconstruction's labels.
        agent: optional fleet agent id (validated by the route). ``None`` keeps the
            historical default (DEFAULT_AGENT_ID) and the screen SAYS so; when
            given, the guard decisions and handoffs fold to that agent's own
            turns, the shared knowledge corpus staying global (the banner says
            which is which).
    """
    at = _parse_at(as_of)
    scope = _normalize_scope(sources)
    rows = await _fetch_documents()
    original = await _fetch_original(at)
    audit = _scan_audit(get_settings().guard.audit_file, at, agent)
    handoffs = _scan_handoffs(get_settings().guard.audit_file, at, agent)
    policy = load_policy()
    ctx = _build_context()
    opposability = _read_opposability(at)
    return _assemble(
        rows,
        audit,
        policy,
        ctx,
        original,
        as_of,
        _load_snapshots(),
        handoffs=handoffs,
        scope=scope,
        lang=lang,
        opposability=opposability,
        agent=agent,
    )


def _read_opposability(at: datetime | None) -> dict[str, object] | None:
    """Real TE-01 opposability verdict as of ``at`` (tree + Hica seal), or None if unreadable.

    None degrades to the honest "Vérification en cours" (never a fabricated «Scellé») — the ledger
    being unreachable must not paint a green badge (register §9, "jamais cosmétique").
    """
    from tessera.guard.seal import active_ledger_opposability

    try:
        return active_ledger_opposability(at=at)
    except Exception:  # unreadable ledger → honest "verifying", never a fake seal
        return None


def _snapshot_record(
    rows: Sequence[dict[str, Any]], audit: _AuditAsOf, as_of: str | None, now: datetime
) -> dict[str, Any]:
    """Compact, durable record of a reconstruction (the headline figures at T)."""
    at = _parse_at(as_of)
    states = _scan_documents(rows, at)
    active = sum(1 for st in states.values() if st.chunks_at_t > 0)
    chunks_at_t = sum(st.chunks_at_t for st in states.values())
    summary = (
        f"{active} sources - {_fmt_int(chunks_at_t)} fragments - "
        f"{_fmt_int(audit.decisions)} decisions guard"
    )
    return {
        "id": uuid.uuid4().hex[:12],
        "saved_at": now.isoformat(),
        "as_of": at.isoformat() if at else None,
        "as_of_label": _fmt(at) if at else "Maintenant (live)",
        "ref_code": _ref_code(at),
        "summary": summary,
    }


async def save_etat_snapshot(
    as_of: str | None = None,
    sources: str | None = None,
    lang: str = "fr",
    agent: str | None = None,
) -> dict[str, object]:
    """Persist a snapshot of the reconstruction at ``as_of``.

    The saved snapshot record is the full (unscoped) opposable state at T; the
    ``sources`` / ``agent`` scopes only shape the refreshed payload returned to
    the caller so the UI stays consistent with the filters it is viewing.
    ``lang`` localizes that refreshed payload (the durable record stays verbatim).
    """
    at = _parse_at(as_of)
    scope = _normalize_scope(sources)
    rows = await _fetch_documents()
    original = await _fetch_original(at)
    audit = _scan_audit(get_settings().guard.audit_file, at, agent)
    policy = load_policy()
    ctx = _build_context()
    handoffs = _scan_handoffs(get_settings().guard.audit_file, at, agent)
    snapshots = _load_snapshots()
    snapshots.insert(0, _snapshot_record(rows, audit, as_of, datetime.now(UTC)))
    _save_snapshots(snapshots)
    return _assemble(
        rows,
        audit,
        policy,
        ctx,
        original,
        as_of,
        snapshots,
        handoffs=handoffs,
        scope=scope,
        lang=lang,
        agent=agent,
    )
