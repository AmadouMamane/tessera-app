"""Push alerts — the cockpit's knowledge leaves the cockpit (ADR 0055).

The uptime witness closed ADR 0052's blind spot: the leader probes the declared stack every
minute and journals what it saw, cockpit open or not. What remained was the stated nuance —
*nothing pushes*: an operator learns about a breach by looking at a page, so a breach at
03:00 is discovered at 09:00 with six hours of red already journalled. This module is the
push: when a watched condition CHANGES STATE, one message leaves the process toward a
webhook the operator configured (Slack-compatible ``{"text": ...}``), and the act is
journalled with the delivery outcome read off the HTTP response — never off the intent
(ADR 0026: a witness interrogates the thing).

Three postures, three honest behaviours:

* **transition** (``False → True`` or back) — push once, journal the event and its delivery;
* **steady state** — push nothing: an alert channel that repeats itself trains its reader
  to ignore it, and the journal already carries the duration;
* **cannot say** (``active=None`` — the reading itself failed) — freeze the stored state and
  push nothing: a blind beat may never claim a recovery (ADR 0026), and equally may never
  page on a hole in its own instrumentation.

No webhook configured means OFF: conditions are still evaluated and journalled on
transitions (the cockpit card reads them), only the push is skipped — and the report says
``configured: false`` out loud rather than looking armed.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final

from tessera.fsutil import atomic_write_text
from tessera.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

__all__ = [
    "AlertReading",
    "alerts_report",
    "process_beat",
    "push_webhook",
]

#: Webhook round-trip budget. A sink slower than this is treated as failed delivery — the
#: beat runs on the leader loop and must never hold it hostage.
_WEBHOOK_TIMEOUT_S: Final = 10.0

#: How much journal the report re-reads. The journal is append-only jsonl; the cockpit card
#: shows the last few acts, the file keeps them all.
_REPORT_TAIL: Final = 20

#: The 2xx band — an HTTP answer inside it is a delivery, anything else is not.
_HTTP_OK_FLOOR: Final = 200
_HTTP_OK_CEILING: Final = 300


@dataclass(frozen=True, slots=True)
class AlertReading:
    """One condition, as this beat could read it.

    ``active`` is three-valued on purpose: ``True`` (the condition holds), ``False`` (it
    verifiably does not), ``None`` (this beat could not read it — which is neither).
    """

    condition: str
    active: bool | None
    #: Operator-facing message for the ACTIVE transition, written by the caller who holds
    #: the facts (names of failing checks, the observed rate). French: the alert channel
    #: has one reader and it is the operator.
    message: str
    #: Message for the recovery transition.
    recovery: str


def _state_path() -> Path:
    """Sibling of the component journal — it must outlive the process (ADR 0044)."""
    return get_settings().guard.audit_file.parent / "alerts_state.json"


def _journal_path() -> Path:
    return get_settings().guard.audit_file.parent / "alerts_journal.jsonl"


def _read_state() -> dict[str, bool]:
    """Last known definite state per condition.

    Unreadable folds to empty — the first transition into ``active`` will then fire,
    which is the safe direction to fail in.
    """
    path = _state_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): bool(v) for k, v in data.items() if isinstance(v, bool)}


def _write_state(state: dict[str, bool]) -> None:
    """Persist the definite states, best effort — like the scheduler stamp.

    A full disk degrades the memory of what was already pushed (worst case: one duplicate
    alert), never the probe or the request path.
    """
    path = _state_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, json.dumps(state, indent=2, sort_keys=True))
    except OSError:
        return


def _append_journal(event: dict[str, object]) -> None:
    path = _journal_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
    except OSError:
        return


def push_webhook(url: str, text: str) -> dict[str, object]:
    """POST ``{"text": ...}`` to the webhook and report what actually happened.

    Returns:
        ``{"delivered": bool, "status": int}`` on an HTTP answer (2xx = delivered), or
        ``{"delivered": False, "error": str}`` when no answer came back. The caller
        journals this verbatim: delivery is a fact about the response, not the attempt.
    """
    body = json.dumps({"text": text}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(  # noqa: S310 — the operator configured this URL
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=_WEBHOOK_TIMEOUT_S) as response:  # noqa: S310
            status = int(response.status)
            return {"delivered": _HTTP_OK_FLOOR <= status < _HTTP_OK_CEILING, "status": status}
    except urllib.error.HTTPError as exc:
        return {"delivered": False, "status": int(exc.code)}
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return {"delivered": False, "error": str(exc)}


def process_beat(
    readings: Sequence[AlertReading],
    *,
    now: datetime | None = None,
) -> list[dict[str, object]]:
    """Fold one beat's readings into state, journal and (when configured) the webhook.

    Returns:
        The journal events this beat produced — empty on a steady beat, which is the
        common case and the point: transitions are rare, the loop is not.
    """
    instant = (now or datetime.now(UTC)).isoformat()
    webhook = get_settings().observability.alert_webhook_url
    state = _read_state()
    events: list[dict[str, object]] = []
    for reading in readings:
        if reading.active is None:
            continue  # cannot say — freeze; a blind beat neither pages nor recovers
        previous = state.get(reading.condition)
        if previous is not None and previous == reading.active:
            continue  # steady — the journal already carries the duration
        if previous is None and reading.active is False:
            # First sighting and it is quiet: record the baseline silently. Paging
            # "recovered" about a condition that was never known to be active is noise.
            state[reading.condition] = False
            continue
        kind = "critical" if reading.active else "recovered"
        text = reading.message if reading.active else reading.recovery
        # The severity emoji belongs to the CHANNEL's presentation, not to the fact: the
        # cockpit card draws its own severity dot, so an emoji baked into the journalled
        # text rendered as a double bullet there (operator report, 2026-08-27). The journal
        # keeps the plain sentence; the webhook line gets the glyph at send time.
        delivery: dict[str, object] = (
            push_webhook(webhook, f"{'🔴' if reading.active else '🟢'} {text}")
            if webhook
            else {"delivered": False, "skipped": "no-webhook"}
        )
        event: dict[str, object] = {
            "at": instant,
            "condition": reading.condition,
            "kind": kind,
            "text": text,
            "delivery": delivery,
        }
        _append_journal(event)
        events.append(event)
        state[reading.condition] = reading.active
    _write_state(state)
    return events


def alerts_report() -> dict[str, object]:
    """What the cockpit may say about the push channel — from what was written, not meant.

    Returns:
        ``configured`` (a webhook URL is set — the URL itself never leaves the process),
        ``conditions`` (last definite state per condition), and ``recent`` (journal tail,
        newest last, each event carrying its delivery outcome).
    """
    path = _journal_path()
    recent: list[dict[str, object]] = []
    if path.exists():
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            lines = []
        for line in lines[-_REPORT_TAIL:]:
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                recent.append(parsed)
    return {
        "configured": bool(get_settings().observability.alert_webhook_url),
        "conditions": dict(_read_state()),
        "recent": recent,
    }
