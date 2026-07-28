"""Durable incident store (create-the-source, page #10 — lot 10).

The Incidents page has a REAL derived feed (guard-deny clusters, low-score
turns — :mod:`tessera.observability.incidents`) and, until this lot, a
demonstration lifecycle. This module IS the lifecycle's real substrate: a
durable JSON store of incidents an operator OPENED — manually, or by promoting
a derived cluster — each carrying an attributed journal of every act performed
on it (ADR 0024: the author is the verified principal, never a default).

Honesty contract: the store starts EMPTY (no seeded incidents — an incident
records that someone decided something was one); playbooks are a catalogue
DECLARED in code (a procedure is a declared thing, like the automation rules),
and "running" one means attaching it to an incident and journalling the steps
an operator actually performed.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Final

from tessera.fsutil import atomic_write_text
from tessera.settings import get_settings

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "INCIDENT_STATUSES",
    "PLAYBOOKS",
    "SEVERITIES",
    "IncidentNotFoundError",
    "attach_playbook",
    "create_incident",
    "get_incident",
    "incidents_as_of",
    "load_incidents",
    "open_durable_counts",
    "transition_incident",
]

#: The lifecycle vocabulary — closed, like every governed enum here.
INCIDENT_STATUSES: Final[tuple[str, ...]] = ("ouvert", "en_cours", "resolu")
SEVERITIES: Final[tuple[str, ...]] = ("critique", "eleve", "moyen", "faible")

#: The declared playbook catalogue (a procedure is a declared thing; running
#: one is a journalled act on an incident). Ids are stable; copy lives in i18n.
PLAYBOOKS: Final[tuple[dict[str, str], ...]] = (
    {"id": "pb-injection", "domain": "securite"},
    {"id": "pb-pii-purge", "domain": "conformite"},
    {"id": "pb-quality-review", "domain": "qualite"},
    {"id": "pb-degradation", "domain": "fiabilite"},
)

_MAX_INCIDENTS: Final = 500


class IncidentNotFoundError(KeyError):
    """An incident id nobody opened — said loudly, never a fabricated record."""


def _incidents_path() -> Path:
    return get_settings().guard.audit_file.parent / "incidents.json"


def _load_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return fallback


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json.dumps(data, indent=2, ensure_ascii=False))


def load_incidents() -> list[dict[str, Any]]:
    """Every durable incident, oldest first (best-effort read; starts empty)."""
    raw = _load_json(_incidents_path(), [])
    return [e for e in raw if isinstance(e, dict)] if isinstance(raw, list) else []


def _parse_iso(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


# The journal's ``action`` strings are a contract THIS module owns (every writer
# above calls ``_journal_entry``); the as-of fold below parses that contract.
_ACTION_STATUS_PREFIX: Final = "statut → "
_ACTION_PLAYBOOK_PREFIX: Final = "playbook attaché : "


def incidents_as_of(at: datetime) -> list[dict[str, Any]]:
    """The durable incidents as they stood at T, replayed from each journal.

    An incident opened after T does not exist at T. Status, playbook attachment
    and closure are the last journalled acts at or before T (a journal entry
    with no parseable instant is skipped — unplaceable acts have no place in a
    state-at-T view); the journal itself is trimmed to ≤ T so the drawer shows
    the history as it stood.
    """
    out: list[dict[str, Any]] = []
    for incident in load_incidents():
        opened = _parse_iso(incident.get("opened_at"))
        if opened is None or opened > at:
            continue
        folded = dict(incident)
        folded["status"] = "ouvert"
        folded["playbook_id"] = None
        folded["closed_at"] = None
        folded["closed_by"] = None
        raw_journal = incident.get("journal")
        kept: list[dict[str, Any]] = []
        for entry in raw_journal if isinstance(raw_journal, list) else []:
            if not isinstance(entry, dict):
                continue
            when = _parse_iso(entry.get("at"))
            if when is None or when > at:
                continue
            kept.append(entry)
            action = str(entry.get("action", ""))
            if action.startswith(_ACTION_STATUS_PREFIX):
                status = action.removeprefix(_ACTION_STATUS_PREFIX)
                folded["status"] = status
                if status == "resolu":
                    folded["closed_at"] = entry.get("at")
                    folded["closed_by"] = entry.get("actor")
                else:
                    folded["closed_at"] = None
                    folded["closed_by"] = None
            elif action.startswith(_ACTION_PLAYBOOK_PREFIX):
                folded["playbook_id"] = action.removeprefix(_ACTION_PLAYBOOK_PREFIX)
        folded["journal"] = kept
        out.append(folded)
    return out


def get_incident(incident_id: str) -> dict[str, Any]:
    """One incident by id.

    Raises:
        IncidentNotFoundError: Unknown id.
    """
    for incident in load_incidents():
        if incident.get("incident_id") == incident_id:
            return incident
    raise IncidentNotFoundError(incident_id)


def _journal_entry(actor: str, action: str) -> dict[str, str]:
    return {"at": datetime.now(UTC).isoformat(), "actor": actor, "action": action}


def create_incident(
    *,
    title: str,
    severity: str,
    domain: str,
    opened_by: str,
    source: str = "manual",
) -> dict[str, Any]:
    """Open one incident, attributed and journalled from its first breath.

    Args:
        title: What happened, in the operator's words (blank refused).
        severity: One of :data:`SEVERITIES`.
        domain: Free classification (securite/qualite/conformite/fiabilite…).
        opened_by: The verified principal — no default, ever (ADR 0024).
        source: ``manual`` (an operator typed it) or ``promoted`` (a derived
            cluster was promoted into a durable incident).

    Raises:
        ValueError: Blank title or unknown severity/source.
    """
    if not title.strip():
        raise ValueError("an incident carries its title — blank refused")
    if severity not in SEVERITIES:
        raise ValueError(f"unknown severity {severity!r} — the vocabulary is closed")
    if source not in ("manual", "promoted"):
        raise ValueError(f"unknown source {source!r}")
    now = datetime.now(UTC)
    incidents = load_incidents()
    incident: dict[str, Any] = {
        "incident_id": f"INC-{now:%Y%m%d}-{len(incidents) + 1:03d}",
        "title": title.strip(),
        "severity": severity,
        "domain": domain.strip() or "autres",
        "status": "ouvert",
        "source": source,
        "opened_at": now.isoformat(),
        "opened_by": opened_by,
        "closed_at": None,
        "closed_by": None,
        "playbook_id": None,
        "journal": [_journal_entry(opened_by, f"ouverture ({source})")],
    }
    incidents.append(incident)
    _save_json(_incidents_path(), incidents[-_MAX_INCIDENTS:])
    return incident


def transition_incident(incident_id: str, status: str, *, by: str) -> dict[str, Any]:
    """Move one incident along its lifecycle, attributed and journalled.

    Resolving stamps ``closed_at``/``closed_by``; re-opening clears them (and
    both moves land in the journal — a lifecycle with amnesia is a fixture).

    Raises:
        IncidentNotFoundError: Unknown id.
        ValueError: Unknown status.
    """
    if status not in INCIDENT_STATUSES:
        raise ValueError(f"unknown incident status {status!r} — the vocabulary is closed")
    incidents = load_incidents()
    for incident in incidents:
        if incident.get("incident_id") == incident_id:
            incident["status"] = status
            if status == "resolu":
                incident["closed_at"] = datetime.now(UTC).isoformat()
                incident["closed_by"] = by
            else:
                incident["closed_at"] = None
                incident["closed_by"] = None
            journal = incident.get("journal")
            if isinstance(journal, list):
                journal.append(_journal_entry(by, f"statut → {status}"))
            _save_json(_incidents_path(), incidents)
            return incident
    raise IncidentNotFoundError(incident_id)


def attach_playbook(incident_id: str, playbook_id: str, *, by: str) -> dict[str, Any]:
    """Attach one declared playbook to an incident — a journalled act.

    Raises:
        IncidentNotFoundError: Unknown incident.
        ValueError: Unknown playbook.
    """
    if playbook_id not in {p["id"] for p in PLAYBOOKS}:
        raise ValueError(f"unknown playbook {playbook_id!r} — the catalogue is declared in code")
    incidents = load_incidents()
    for incident in incidents:
        if incident.get("incident_id") == incident_id:
            incident["playbook_id"] = playbook_id
            journal = incident.get("journal")
            if isinstance(journal, list):
                journal.append(_journal_entry(by, f"playbook attaché : {playbook_id}"))
            _save_json(_incidents_path(), incidents)
            return incident
    raise IncidentNotFoundError(incident_id)


def open_durable_counts() -> tuple[int, int]:
    """``(open, critical)`` among the DURABLE incidents (feeds the sidebar sum)."""
    incidents = load_incidents()
    open_ones = [i for i in incidents if i.get("status") != "resolu"]
    critical = sum(1 for i in open_ones if i.get("severity") == "critique")
    return len(open_ones), critical
