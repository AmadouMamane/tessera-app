"""Durable recouvrement case queue (create-the-source, RC product).

The product surface showed a queue that did not exist: ONE mock case (RC-2048)
hardcoded in :mod:`tessera.agent.recouvrement` and invented nav counters in the
frontend. This module IS the real queue — a durable JSON store of collection
cases with a mutable workflow status, read by the queue/case endpoints and by
the workflow's own case loader.

Honesty contract: the STORE is real (durable, mutable, queryable); its initial
content is a **declared seed book** — every seeded case carries ``"seed": true``
so no surface can present the demo book as production data. RC-2048 is part of
the seed and mirrors the historical mock byte-for-byte, so the real workflow
(and its tests) keep their ground truth.
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
    "STATUSES",
    "CaseNotFoundError",
    "get_case",
    "load_cases",
    "queue_counters",
    "set_case_status",
]

#: The workflow statuses a case can carry — the queue's closed vocabulary.
STATUSES: Final[tuple[str, ...]] = (
    "relance_a_valider",
    "echeancier_a_confirmer",
    "situation_a_verifier",
    "traite",
)


class CaseNotFoundError(KeyError):
    """A case id nobody holds — said loudly, never a fabricated dossier."""


def _cases_path() -> Path:
    return get_settings().guard.audit_file.parent / "recouvrement_cases.json"


#: The declared demo book. RC-2048 mirrors the historical mock exactly.
_SEED: Final[list[dict[str, Any]]] = [
    {
        "case_id": "RC-2048",
        "client": "M. D.",
        "amount_due": 840.0,
        "days_late": 32,
        "missed_promise_date": "2026-06-12",
        "contact_window_start": "08:00",
        "contact_window_end": "20:00",
        "recommended_channel": "appel sortant",
        "alternative_channel": "email de confirmation",
        "status": "relance_a_valider",
        "seed": True,
    },
    {
        "case_id": "RC-2051",
        "client": "Mme B.",
        "amount_due": 1260.5,
        "days_late": 18,
        "missed_promise_date": None,
        "contact_window_start": "09:00",
        "contact_window_end": "18:00",
        "recommended_channel": "email de relance",
        "alternative_channel": "appel sortant",
        "status": "relance_a_valider",
        "seed": True,
    },
    {
        "case_id": "RC-2055",
        "client": "M. K.",
        "amount_due": 430.0,
        "days_late": 45,
        "missed_promise_date": "2026-06-02",
        "contact_window_start": "08:00",
        "contact_window_end": "20:00",
        "recommended_channel": "appel sortant",
        "alternative_channel": "courrier",
        "status": "echeancier_a_confirmer",
        "seed": True,
    },
    {
        "case_id": "RC-2058",
        "client": "Mme L.",
        "amount_due": 2150.0,
        "days_late": 61,
        "missed_promise_date": "2026-05-20",
        "contact_window_start": "10:00",
        "contact_window_end": "19:00",
        "recommended_channel": "appel sortant",
        "alternative_channel": "email de confirmation",
        "status": "situation_a_verifier",
        "seed": True,
    },
    {
        "case_id": "RC-2060",
        "client": "M. T.",
        "amount_due": 95.9,
        "days_late": 9,
        "missed_promise_date": None,
        "contact_window_start": "08:00",
        "contact_window_end": "20:00",
        "recommended_channel": "email de relance",
        "alternative_channel": "appel sortant",
        "status": "traite",
        "seed": True,
    },
]


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


def load_cases() -> list[dict[str, Any]]:
    """Every case in the queue; first read materialises the declared seed book."""
    raw = _load_json(_cases_path(), None)
    if isinstance(raw, list):
        return [c for c in raw if isinstance(c, dict)]
    seeded = [dict(c) for c in _SEED]
    _save_json(_cases_path(), seeded)
    return seeded


def get_case(case_id: str) -> dict[str, Any]:
    """One case by id.

    Raises:
        CaseNotFoundError: Unknown id — never a fabricated dossier.
    """
    for case in load_cases():
        if case.get("case_id") == case_id:
            return case
    raise CaseNotFoundError(case_id)


def queue_counters() -> dict[str, int]:
    """The real per-status tally the product nav displays (plus ``total``/``open``)."""
    cases = load_cases()
    counters = {status: 0 for status in STATUSES}
    for case in cases:
        status = str(case.get("status", ""))
        if status in counters:
            counters[status] += 1
    counters["total"] = len(cases)
    counters["open"] = counters["total"] - counters["traite"]
    return counters


def set_case_status(case_id: str, status: str, *, by: str) -> dict[str, Any]:
    """Move one case to a workflow status, attributed (ADR 0024).

    Args:
        case_id: The case to move.
        status: One of :data:`STATUSES` — anything else raises ``ValueError``.
        by: The verified principal — no default, ever.

    Raises:
        CaseNotFoundError: Unknown case.
        ValueError: Unknown status.
    """
    if status not in STATUSES:
        raise ValueError(f"unknown case status {status!r} — the vocabulary is closed")
    cases = load_cases()
    for case in cases:
        if case.get("case_id") == case_id:
            case["status"] = status
            case["updated_at"] = datetime.now(UTC).isoformat()
            case["updated_by"] = by
            _save_json(_cases_path(), cases)
            return case
    raise CaseNotFoundError(case_id)
