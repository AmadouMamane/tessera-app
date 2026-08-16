"""The stack-probe scheduler's own record — who watches when nobody is looking.

ADR 0052 shipped the component history with a stated limitation: *the probe runs when the
cockpit asks*, so the journal covered whatever happened to be watched — 1.3 % of a day, on the
day it shipped — and every availability figure was a true statement about a sliver. The page
published the sliver (``observed_ratio``) rather than hiding it, which was honest and useless
at the same time: an operator cannot act on "99 % of 18 minutes".

Amendment 1 adds the scheduler: the ADR 0044 leader probes the declared components on a
fixed cadence, so the journal is written even when every cockpit is closed. This module holds
the parts of that which are not the loop itself (the loop lives with its siblings in
``api/main.py``):

* the **stamp** — each cycle writes ``probe_scheduler.json`` beside the journal. The stamp is
  how another process can know the scheduler is alive: under ADR 0044 the loop runs in the
  LEADER process and the endpoint answering the page may be any worker, so liveness must cross
  a process boundary through the filesystem, like the journal it vouches for.
* the **posture** — one function reads the setting, so the boot log line and the loop can never
  disagree about whether scheduling is on (the seal/canary/purge pattern).
* the **report** — what the history endpoint publishes about the scheduler. Derived from the
  stamp the loop actually writes, never from configuration: a report read off the settings
  would say "scheduled" about a leader that died an hour ago (ADR 0026 — interrogate the
  thing, not its declaration).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Final, Literal

from tessera.fsutil import atomic_write_text
from tessera.settings import get_settings

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "ProbeSchedulerStamp",
    "probe_posture",
    "read_stamp",
    "scheduler_report",
    "write_stamp",
]

#: Grace multiplier before a stamp is read as "the scheduler stopped". Two intervals plus a
#: fixed slack: one missed beat is a slow cycle, two is a dead loop — and the slack keeps a
#: 15-second cadence from flapping to "stale" on one garbage-collection pause.
_STALE_AFTER: Final = 2.0
_STALE_SLACK: Final = timedelta(seconds=30)

#: What the scheduler is doing, as three words rather than two booleans. ``never`` — no stamp
#: exists (never ran here, or the state dir was wiped); ``active`` — the last beat is recent
#: enough; ``stale`` — a stamp exists and its beat has stopped, which is a dead leader loop and
#: a different repair from "not configured".
SchedulerState = Literal["never", "active", "stale"]


@dataclass(frozen=True, slots=True)
class ProbeSchedulerStamp:
    """One heartbeat of the scheduler loop, as persisted."""

    interval_s: float
    last_run_at: str
    pid: int

    def instant(self) -> datetime | None:
        """``last_run_at`` as an aware instant, or ``None`` when it will not parse."""
        try:
            stamp = datetime.fromisoformat(self.last_run_at)
        except (TypeError, ValueError):
            return None
        return stamp.replace(tzinfo=UTC) if stamp.tzinfo is None else stamp.astimezone(UTC)


def _stamp_path() -> Path:
    """Sibling of the component journal, for the same reason: it must outlive the process."""
    return get_settings().guard.audit_file.parent / "probe_scheduler.json"


def probe_posture() -> dict[str, object]:
    """The scheduling decision, from its single source (the setting).

    Returns:
        ``scheduling`` and the ``interval_s`` it will use — the loop and the boot log both read
        this, so they cannot drift into announcing one cadence and running another.
    """
    interval = get_settings().observability.probe_interval_s
    return {"scheduling": interval > 0, "interval_s": interval if interval > 0 else None}


def write_stamp(*, at: datetime | None = None) -> None:
    """Record one scheduler beat, best effort.

    A full disk degrades the *liveness report*, never the probe itself — the journal write has
    the same posture (ADR 0015).
    """
    now = at or datetime.now(UTC)
    interval = get_settings().observability.probe_interval_s
    path = _stamp_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            path,
            json.dumps(
                {
                    "interval_s": float(interval),
                    "last_run_at": now.isoformat(),
                    "pid": os.getpid(),
                },
                indent=2,
            ),
        )
    except OSError:
        return


def read_stamp() -> ProbeSchedulerStamp | None:
    """The last persisted beat, or ``None`` — unreadable is indistinguishable from absent.

    Folding those two cases is deliberate: both mean the report may not claim the scheduler is
    alive, and that is the only claim the stamp exists to support.
    """
    path = _stamp_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    try:
        return ProbeSchedulerStamp(
            interval_s=float(data["interval_s"]),
            last_run_at=str(data["last_run_at"]),
            pid=int(data["pid"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def scheduler_report(*, now: datetime | None = None) -> dict[str, object]:
    """What the page may say about the scheduler — derived from the stamp, never the config.

    Returns:
        ``state`` (``never`` / ``active`` / ``stale``), ``interval_s`` (the cadence the last
        beat declared, falling back to the configured one so a page can still announce the
        intent before the first beat), and ``last_run_at`` (the beat itself, ``None`` when
        there has never been one).
    """
    instant = now or datetime.now(UTC)
    stamp = read_stamp()
    configured = get_settings().observability.probe_interval_s
    if stamp is None:
        return {
            "state": "never",
            "interval_s": float(configured) if configured > 0 else None,
            "last_run_at": None,
        }
    beat = stamp.instant()
    fresh = (
        beat is not None
        and timedelta()
        <= instant - beat
        <= timedelta(seconds=stamp.interval_s * _STALE_AFTER) + _STALE_SLACK
    )
    state: SchedulerState = "active" if fresh else "stale"
    return {
        "state": state,
        "interval_s": stamp.interval_s,
        "last_run_at": stamp.last_run_at,
    }
