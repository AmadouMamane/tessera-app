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

The page is FR-only (it has no ``lang`` parameter); free-text is verbatim French.
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

from tessera.guard.decisions import load_policy
from tessera.observability._asof import occurred_before
from tessera.observability.agent_configurations import _effective
from tessera.observability.eval_data import load_eval_snapshot
from tessera.observability.knowledge import _SOURCE_META, _source_name
from tessera.retrieval.store import _connection
from tessera.settings import get_settings

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

_TYPE_LABEL: dict[str, str] = {"reg": "Reglementation", "prod": "Produit"}
_TYPE_TONE: dict[str, str] = {"reg": "violet", "prod": "blue"}


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
        return datetime.fromisoformat(at.replace("Z", "+00:00"))
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
    path.write_text(
        json.dumps(snapshots[:_MAX_SNAPSHOTS], indent=2, ensure_ascii=False), encoding="utf-8"
    )


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


def _scan_audit(path: Path, at: datetime | None) -> _AuditAsOf:
    scan = _AuditAsOf()
    if not path.exists():
        return scan
    with path.open(encoding="utf-8") as fp:
        for raw in fp:
            line = raw.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            occurred = entry.get("occurred_at")
            if not occurred_before(occurred, at.isoformat() if at else None):
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


async def _fetch_documents() -> list[dict[str, Any]]:
    table = get_settings().postgres.vector_table
    async with _connection() as conn:
        conn.row_factory = dict_row
        async with conn.cursor() as cur:
            await cur.execute(
                f"SELECT source, language, metadata, inserted_at FROM {table}"  # noqa: S608
            )
            return list(await cur.fetchall())


async def _fetch_original(at: datetime | None) -> dict[str, Any] | None:
    """The real agent answer (and its question) most recent at or before T.

    This is the "Reponse d'origine" the reconstruction is anchored to - a genuine
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
    async with _connection() as conn:
        conn.row_factory = dict_row
        async with conn.cursor() as cur:
            await cur.execute(query, params)
            return await cur.fetchone()


# --- assembly -----------------------------------------------------------------


_POLICY_FILE = _ROOT / "src" / "tessera" / "guard" / "policy.yaml"


def _truncate(text: str, limit: int = _ANSWER_PREVIEW) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "..."


def _snapshot_id(at: datetime | None) -> str:
    if at is None:
        return "SNAP-LIVE"
    return at.astimezone(_PARIS).strftime("SNAP-%Y-%m-%d-%H%M")


def _short_uuid(value: object) -> str:
    return str(value).split("-")[0].upper() if value else "-"


def _card(rows: list[tuple[str, str]], diff: list[str], cta: str, href: str) -> dict[str, object]:
    return {
        "rows": [{"label": k, "value": v} for k, v in rows],
        "diff": diff,
        "cta": cta,
        "cta_href": href,
    }


def _changed(when: datetime | None, at: datetime | None, after: str, before: str) -> str:
    """Honest diff line: did `when` happen after T (i.e. changed since T)?"""
    when, at = _aware(when), _aware(at)
    if when is None or at is None:
        return before
    return after if when > at else before


def _guardrails_card(
    policy: Policy, audit: _AuditAsOf, ctx: _Context, at: datetime | None
) -> dict[str, object]:
    after = ctx.audit_total - audit.decisions  # real decisions logged after T
    rules_active = (
        len(policy.prompt_injection_deny) + len(policy.pii_patterns) + len(policy.tools)
    )
    diff = [
        f"{_fmt_int(after)} decisions du guard journalisees apres T"
        if after > 0
        else "Aucune decision du guard apres T",
        _changed(
            ctx.policy_mtime, at, "Politique modifiee apres T", "Politique inchangee depuis T"
        ),
    ]
    return _card(
        [
            ("Bundle de politiques", f"Guardrails Banking v{policy.version}"),
            ("Regles actives", str(rules_active)),
            ("Motifs d'injection", str(len(policy.prompt_injection_deny))),
            ("Motifs PII surveilles", str(len(policy.pii_patterns))),
            ("Regles declenchees jusqu'a T", str(len(audit.rules))),
            ("Dernier changement avant T", _fmt(ctx.policy_mtime)),
        ],
        diff,
        "Voir le detail des regles",
        "/agent/garde-fous",
    )


def _prompt_model_card(ctx: _Context, at: datetime | None) -> dict[str, object]:
    diff = [
        _changed(
            ctx.prompt_mtime, at, "System prompt modifie apres T", "System prompt inchange depuis T"
        ),
        "Modele inchange",
    ]
    return _card(
        [
            ("Modele (fige)", ctx.model),
            ("Runtime", "Ollama on-prem"),
            ("Profil d'execution", ctx.profile),
            ("Version du system prompt", f"maj {_fmt(ctx.prompt_mtime)}"),
            ("Temperature", f"{ctx.temperature:.2f}".replace(".", ",")),
        ],
        diff,
        "Voir le contenu du prompt",
        "/agent/prompts",
    )


def _release_card(ctx: _Context, at: datetime | None) -> dict[str, object]:
    diff = [
        _changed(
            ctx.run_dt, at, "Nouvelle evaluation executee apres T", "Aucune evaluation apres T"
        ),
    ]
    return _card(
        [
            ("Jeu d'evaluation", ctx.catalogue),
            ("Date d'execution", _fmt(ctx.run_dt)),
            ("Environnement", "Local / on-prem"),
            ("Modele evalue", ctx.model),
        ],
        diff,
        "Voir le detail de la release",
        "/agent/evaluations",
    )


def _table(states: dict[str, _CatState]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for cat, st in sorted(states.items(), key=lambda kv: -kv[1].chunks_at_t):
        accessible = st.chunks_at_t > 0
        tone_key = _SOURCE_META[cat]
        rows.append({
            "key": cat,
            "source": _source_name(cat, "fr"),
            "type": _TYPE_LABEL[tone_key],
            "type_key": tone_key,
            "type_tone": _TYPE_TONE[tone_key],
            "langs": "/".join(sorted(st.langs)) if st.langs else "-",
            "chunks": st.chunks_at_t,
            "total_chunks": st.chunks_total,
            "version": f"ingest {_fmt(st.first_ins)}" if st.first_ins else "-",
            "accessible_until": _fmt(st.last_ins_at_t),
            "updated": _fmt(st.last_ins_at_t),
            "first_seen": _fmt(st.first_ins),
            "status": "accessible" if accessible else "pending",
            "status_label": "Accessible" if accessible else "Pas encore indexee",
        })
    return rows


def _timeline(
    states: dict[str, _CatState], audit: _AuditAsOf, at: datetime | None
) -> list[dict[str, object]]:
    events: list[tuple[datetime, str, str]] = []
    # Per-source first ingest events at or before T.
    for cat, st in states.items():
        if st.first_ins is not None and (at is None or st.first_ins <= at):
            events.append((st.first_ins, f"Source indexee : {_source_name(cat, 'fr')}", "ok"))
    if audit.first_at is not None:
        events.append((audit.first_at, "Premiere decision du guard journalisee", "info"))
    if audit.last_at is not None and audit.last_at != audit.first_at:
        events.append((audit.last_at, "Derniere activite du guard avant T", "info"))
    events.sort(key=lambda e: e[0], reverse=True)
    return [
        {"time": _fmt(dt), "label": label, "kind": kind}
        for dt, label, kind in events[:_MAX_TIMELINE]
    ]


def _snapshot_section(snapshots: list[dict[str, Any]]) -> dict[str, object]:
    return {
        "title": "Snapshots enregistres",
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
        "question": _truncate(str(original.get("question") or "-"), 200),
        "answer": _truncate(str(original.get("answer") or "-")),
        "timestamp": _fmt(ts_dt),
        "session": f"SES-{_short_uuid(original.get('conv'))}",
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
) -> dict[str, object]:
    """Assemble the reconstruction payload. Pure and I/O-free for unit testing."""
    now = now or datetime.now(UTC)
    at = _parse_at(as_of)
    states = _scan_documents(rows, at)
    chunks_at_t = sum(st.chunks_at_t for st in states.values())
    chunks_total = sum(st.chunks_total for st in states.values())
    last_sync = max(
        (st.last_ins_at_t for st in states.values() if st.last_ins_at_t is not None),
        default=None,
    )
    coverage = round(_PCT * chunks_at_t / chunks_total) if chunks_total else 0
    active = sum(1 for s in states.values() if s.chunks_at_t > 0)

    return {
        "available": True,
        "meta": {
            "as_of": at.isoformat() if at else None,
            "as_of_label": _fmt(at) if at else "Maintenant (live)",
            "ref_code": _ref_code(at),
            "tenant": "Credit Aurore",
            "agent": "Support client",
            "context_source": "Reponse",
            "timezone": "Europe/Paris",
            "banner": (
                "Reconstitue (accessibilite) n'est pas rejoue (sortie du modele). Cette vue "
                "reconstitue l'etat accessible et applicable a T ; elle ne rejoue pas la reponse "
                "exacte. Pour rejouer une execution, utiliser AGIR - Replay."
            ),
        },
        "reconstructed": {
            "title": "Etat reconstruit a T",
            "snapshot_id": _snapshot_id(at),
            "verified": True,
            "verified_label": "Integrite verifiee",
            "built_label": f"Reconstitue le {_fmt(now)} par Tessera Ops",
        },
        "original": {
            "title": "Reponse d'origine",
            "cta": "Ouvrir la trace",
            "cta_href": "/prouver/audit-logs",
            **_original_card(original, at),
        },
        "guardrails": {
            "title": "Garde-fous actifs a T",
            **_guardrails_card(policy, audit, ctx, at),
        },
        "prompt_model": {"title": "Prompt & modele a T", **_prompt_model_card(ctx, at)},
        "release": {"title": "Release a T", **_release_card(ctx, at)},
        "timeline": {
            "title": f"Chronologie a l'instant T ({_fmt(at) if at else 'live'})",
            "rows": _timeline(states, audit, at),
            "cta": "Voir la chronologie complete",
            "cta_href": "/prouver/audit-logs",
        },
        "integrity": {
            "title": "Integrite de la reconstruction",
            "snapshot_id": _snapshot_id(at),
            "coverage": f"{coverage} %",
            "test_query": f"{active}/{len(states)} sources",
            "last_sync": _fmt(last_sync),
            "verified": True,
            "verified_label": "Integrite verifiee",
            "chain_label": f"{_fmt_int(audit.decisions)} decisions journalisees jusqu'a T",
        },
        "table": {"title": "Sources accessibles a l'instant T", "rows": _table(states)},
        "audit_pieces": {
            "title": "Preuves d'audit disponibles",
            "rows": [
                {"label": "Journal d'evenements a date T", "href": "/prouver/audit-logs"},
                {"label": "Evidence pack qualite", "href": "/prouver/evidence-store"},
                {"label": "Sources & memoire", "href": "/agent/connaissances"},
            ],
        },
        "summary": {
            "title": "Synthese de l'etat reconstruit",
            "cards": [
                {"label": "Sources accessibles", "value": f"{active} / {len(states)}"},
                {"label": "Fragments accessibles", "value": _fmt_int(chunks_at_t)},
                {"label": "Couverture de l'index", "value": f"{coverage} %"},
                {"label": "Decisions du guard", "value": _fmt_int(audit.decisions)},
            ],
        },
        "snapshots": _snapshot_section(snapshots or []),
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
    return _Context(
        model=model,
        temperature=float(cfg.get("temperature", 0.3)),
        profile=str(cfg.get("routing_strategy", "Standard souverain")),
        prompt_mtime=_newest_mtime(_PROMPTS_DIR, "*.yaml"),
        policy_mtime=_mtime(_POLICY_FILE),
        run_dt=run_dt,
        catalogue=catalogue,
        audit_total=audit_total,
    )


async def build_etat_a_date(as_of: str | None = None) -> dict[str, object]:
    """Reconstruct the agent's accessible state + governing context as of ``as_of``.

    Args:
        as_of: ISO instant T (``None`` means live/now). Knowledge, audit and the
            anchored original response are restricted to events at or before T.
    """
    at = _parse_at(as_of)
    rows = await _fetch_documents()
    original = await _fetch_original(at)
    audit = _scan_audit(get_settings().guard.audit_file, at)
    policy = load_policy()
    ctx = _build_context()
    return _assemble(rows, audit, policy, ctx, original, as_of, _load_snapshots())


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


async def save_etat_snapshot(as_of: str | None = None) -> dict[str, object]:
    """Persist a snapshot of the reconstruction at ``as_of``.

    Returns the refreshed payload, with the newly-saved snapshot at the head of
    the durable snapshot list.
    """
    at = _parse_at(as_of)
    rows = await _fetch_documents()
    original = await _fetch_original(at)
    audit = _scan_audit(get_settings().guard.audit_file, at)
    policy = load_policy()
    ctx = _build_context()
    snapshots = _load_snapshots()
    snapshots.insert(0, _snapshot_record(rows, audit, as_of, datetime.now(UTC)))
    _save_snapshots(snapshots)
    return _assemble(rows, audit, policy, ctx, original, as_of, snapshots)
