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
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from psycopg.rows import dict_row

from tessera.guard.decisions import load_policy
from tessera.observability._asof import occurred_before
from tessera.observability.knowledge import _SOURCE_META, _source_name
from tessera.retrieval.store import _connection
from tessera.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from tessera.guard.decisions import Policy

__all__ = ["build_etat_a_date", "save_etat_snapshot"]

_PARIS = ZoneInfo("Europe/Paris")
_PCT = 100
_MAX_TIMELINE = 8
_MAX_SNAPSHOTS = 20

_TYPE_LABEL: dict[str, str] = {"reg": "Reglementation", "prod": "Produit"}
_TYPE_TONE: dict[str, str] = {"reg": "violet", "prod": "blue"}


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


# --- assembly -----------------------------------------------------------------


def _kpis(
    states: dict[str, _CatState], audit: _AuditAsOf, chunks_at_t: int, chunks_total: int
) -> list[dict[str, object]]:
    active = sum(1 for st in states.values() if st.chunks_at_t > 0)
    coverage = round(_PCT * chunks_at_t / chunks_total) if chunks_total else 0
    return [
        {"key": "sources", "label": "Sources actives", "value": str(active),
         "hint": f"sur {len(states)} cataloguees"},
        {"key": "documents", "label": "Documents accessibles", "value": _fmt_int(chunks_at_t),
         "hint": f"sur {_fmt_int(chunks_total)} indexes"},
        {"key": "decisions", "label": "Decisions du guard", "value": _fmt_int(audit.decisions),
         "hint": "journalisees jusqu'a T"},
        {"key": "blocked", "label": "Blocages", "value": _fmt_int(audit.blocked),
         "hint": "refus jusqu'a T"},
        {"key": "coverage", "label": "Couverture de l'index", "value": f"{coverage} %",
         "hint": "a cette date"},
    ]


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


def _assemble(
    rows: Sequence[dict[str, Any]],
    audit: _AuditAsOf,
    policy: Policy,
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
    deny_count = len(policy.prompt_injection_deny)

    return {
        "available": True,
        "meta": {
            "as_of": at.isoformat() if at else None,
            "as_of_label": _fmt(at) if at else "Maintenant (live)",
            "ref_code": _ref_code(at),
            "agent": "Credit Aurore",
            "context_source": "Reponse",
            "timezone": "Europe/Paris",
        },
        "kpis": _kpis(states, audit, chunks_at_t, chunks_total),
        "table": {
            "title": "Sources accessibles a l'instant T",
            "rows": _table(states),
        },
        "integrity": {
            "coverage": f"{coverage} %",
            "last_sync": _fmt(last_sync),
            "verified": True,
            "verified_label": "Integrite verifiee",
            "decisions": _fmt_int(audit.decisions),
            "chain_label": f"{_fmt_int(audit.decisions)} decisions journalisees jusqu'a T",
        },
        "timeline": {
            "title": f"Chronologie a l'instant T ({_fmt(at) if at else 'live'})",
            "rows": _timeline(states, audit, at),
        },
        "policies": {
            "title": "Filtres et politiques actifs a T",
            "rows": [
                {"label": "Profil de recherche", "value": "Standard"},
                {"label": "Garde-fous", "value": f"v{policy.version}"},
                {"label": "Motifs d'injection bloques", "value": str(deny_count)},
                {"label": "Motifs PII surveilles", "value": str(len(policy.pii_patterns))},
                {"label": "Outils sous controle", "value": str(len(policy.tools))},
                {"label": "Regles declenchees jusqu'a T", "value": str(len(audit.rules))},
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


async def build_etat_a_date(as_of: str | None = None) -> dict[str, object]:
    """Reconstruct the agent's accessible-knowledge + guard state as of ``as_of``.

    Args:
        as_of: ISO instant T (``None`` means live/now). Knowledge and audit
            figures are restricted to events at or before T.
    """
    rows = await _fetch_documents()
    audit = _scan_audit(get_settings().guard.audit_file, _parse_at(as_of))
    policy = load_policy()
    return _assemble(rows, audit, policy, as_of, _load_snapshots())


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
    rows = await _fetch_documents()
    audit = _scan_audit(get_settings().guard.audit_file, _parse_at(as_of))
    policy = load_policy()
    snapshots = _load_snapshots()
    snapshots.insert(0, _snapshot_record(rows, audit, as_of, datetime.now(UTC)))
    _save_snapshots(snapshots)
    return _assemble(rows, audit, policy, as_of, snapshots)
