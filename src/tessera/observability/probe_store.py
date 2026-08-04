"""Durable journal of fixed-corpus probe runs — the store ``probe_history`` never was.

Two controls on "Contrôles critiques" — ``refusal`` and ``firewall`` — carried the reason
``fixed-corpus``: re-running the same adversarial corpus against the same policy inside a
narrower window returns the same number, so bucketing the *handler* would draw a flat line
that reads as "stable" while being one measurement repeated once per slice.

That reason was accurate about the handler and wrong about the metric. These probes *do*
change over time — not because the corpus moves, but because **the policy does**. What was
missing was never a derivation; it was a record of *when each measurement was taken*. A
comment in :mod:`tessera.observability.control_series` claimed one existed, in the present
tense, naming ``probe_history`` — a name that appeared nowhere else in the repository. This
module is that store, written rather than described.

**Deduplicated by content, deliberately.** A probe is deterministic given its corpus and the
policy, and both route handlers memoise on the policy hash, so every cockpit refresh yields a
byte-identical answer. Appending one row per read would fill a bounded journal with page
refreshes and — worse — would let a curve be drawn from 400 rows that are one measurement.
So an identical answer **extends** the run it repeats instead of starting a new one, and the
journal holds *changes*: "from ``first_seen`` to ``last_seen``, this probe measured X".

What a bucket then reads is :func:`probe_run_at` — the run in effect at that instant. The
resulting curve is a step function, and each step is a real, dated measurement. A bucket that
falls before the first recorded run gets **nothing**, never a zero: the probe was not run then,
and on a refusal rate a zero and a gap render the same colour and mean opposite things.

``n_observations`` counts how many times the measurement was **read back**, not how many times
the corpus was scored — the probes are memoised, so those are different numbers and only the
honest one is stored under a name that says which.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from tessera.fsutil import atomic_write_text
from tessera.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

__all__ = [
    "VOLATILE_KEYS",
    "ProbeRun",
    "append_probe_run",
    "load_probe_runs",
    "probe_run_at",
    "probe_runs",
    "record_probe_run",
]

#: Keep the journal bounded; oldest entries roll off. Five hundred *changes* is a long history
#: for a probe that only moves when the policy does — unlike five hundred reads, which is an
#: afternoon of cockpit refreshes.
_MAX_RUNS = 500

#: Payload keys excluded from the identity of a measurement. ``observed_at`` is the live
#: recompute stamp (ADR 0029): it is *when the report was read*, deliberately not part of the
#: reproducible content. Leaving it in the fingerprint would make every single read a distinct
#: "change" and turn this store back into the append-per-refresh log it exists to avoid.
VOLATILE_KEYS = frozenset({"observed_at"})


@dataclass(frozen=True, slots=True)
class ProbeRun:
    """One measured value of a fixed-corpus probe, and the span over which it held."""

    probe: str
    #: When this value was first observed — the instant the curve steps to it.
    first_seen: str
    #: When it was last observed unchanged. Equal to ``first_seen`` for a single read.
    last_seen: str
    #: How many times this value was read back. Not how many times the corpus was scored.
    n_observations: int
    payload: dict[str, Any] = field(default_factory=dict)


def _state_path() -> Path:
    """Sibling of the guard audit log, so the journal outlives the container."""
    return get_settings().guard.audit_file.parent / "probe_runs.json"


def _fingerprint(payload: Mapping[str, Any]) -> str:
    """A stable identity for a measurement, ignoring the keys that are about the read."""
    stable = {k: v for k, v in payload.items() if k not in VOLATILE_KEYS}
    return json.dumps(stable, sort_keys=True, ensure_ascii=False, default=str)


def load_probe_runs() -> list[ProbeRun]:
    """Every recorded run of every probe, oldest first (best-effort read).

    An unreadable or corrupt journal returns empty rather than raising: this feeds a curve on
    a dashboard, and the caller already renders "no runs recorded" as a gap. It must not be
    able to take a page down.
    """
    path = _state_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, list):
        return []
    runs: list[ProbeRun] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        try:
            runs.append(
                ProbeRun(
                    probe=str(entry["probe"]),
                    first_seen=str(entry["first_seen"]),
                    last_seen=str(entry["last_seen"]),
                    n_observations=int(entry["n_observations"]),
                    payload=dict(entry.get("payload") or {}),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue  # one malformed row must not hide the rest of the history
    return runs


def probe_runs(probe: str) -> list[ProbeRun]:
    """The recorded runs of one probe, oldest first."""
    return [run for run in load_probe_runs() if run.probe == probe]


def probe_run_at(
    probe: str, instant: datetime, *, runs: list[ProbeRun] | None = None
) -> ProbeRun | None:
    """The run **in effect** at ``instant`` — the newest one first seen at or before it.

    Args:
        probe: The probe's key, as it appears in the control payload (``refusal``…).
        instant: The moment to read the probe at; normally a bucket's right edge.
        runs: A pre-loaded journal, so bucketing a window does not re-read the file once per
            slice. Loaded on demand when omitted.

    Returns:
        The :class:`ProbeRun` that held at ``instant``, or ``None`` when nothing had been
        recorded yet — which the caller must render as a gap, never as a zero.
    """
    candidates = runs if runs is not None else load_probe_runs()
    in_effect: ProbeRun | None = None
    for run in candidates:
        if run.probe != probe:
            continue
        try:
            first = datetime.fromisoformat(run.first_seen)
        except ValueError:
            continue
        if first.tzinfo is None:
            first = first.replace(tzinfo=UTC)
        if first <= instant and (in_effect is None or run.first_seen >= in_effect.first_seen):
            in_effect = run
    return in_effect


def record_probe_run(probe: str, payload: Mapping[str, Any]) -> None:
    """Record that ``probe`` measured ``payload``, now.

    An answer identical to this probe's most recent one **extends** that run rather than
    appending a new one — see the module docstring. A different answer starts a new run, and
    that boundary is the step the curve draws.

    Best effort by construction: this is called from a read path, and a read-only filesystem
    (ADR 0015) or a full disk must degrade the *history*, never the response the operator
    asked for.
    """
    now = datetime.now(UTC).isoformat()
    runs = load_probe_runs()
    fingerprint = _fingerprint(payload)

    latest_index: int | None = None
    for index in range(len(runs) - 1, -1, -1):
        if runs[index].probe == probe:
            latest_index = index
            break

    if latest_index is not None and _fingerprint(runs[latest_index].payload) == fingerprint:
        previous = runs[latest_index]
        runs[latest_index] = ProbeRun(
            probe=probe,
            first_seen=previous.first_seen,
            last_seen=now,
            n_observations=previous.n_observations + 1,
            payload=previous.payload,
        )
    else:
        runs.append(
            ProbeRun(
                probe=probe,
                first_seen=now,
                last_seen=now,
                n_observations=1,
                payload={k: v for k, v in payload.items() if k not in VOLATILE_KEYS},
            )
        )

    _write(runs)


def append_probe_run(probe: str, payload: Mapping[str, Any]) -> None:
    """Record a run of ``probe`` **without** collapsing it into an identical predecessor.

    For probes whose every run is an act somebody triggered rather than a value somebody read —
    the red-team campaign is the one — repetition is information: "we ran it again and three
    still bypass" says something "we have not looked since Tuesday" does not. Content
    deduplication would erase exactly that distinction, which is why it is a different
    function and not a flag.
    """
    now = datetime.now(UTC).isoformat()
    runs = load_probe_runs()
    runs.append(
        ProbeRun(
            probe=probe,
            first_seen=now,
            last_seen=now,
            n_observations=1,
            payload={k: v for k, v in payload.items() if k not in VOLATILE_KEYS},
        )
    )
    _write(runs)


def _write(runs: list[ProbeRun]) -> None:
    """Persist the journal, newest entries kept. Best effort — see :func:`record_probe_run`."""
    path = _state_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            path, json.dumps([asdict(r) for r in runs[-_MAX_RUNS:]], indent=2, ensure_ascii=False)
        )
    except OSError:
        return  # read-only fs / full disk: the probe still answered, the history just did not grow
