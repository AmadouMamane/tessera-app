"""Component verdicts over TIME — the dimension a poll-and-render page cannot have.

``/observability/components`` answers *what is true now*. Now is the one instant an operator
did not need help with: they are looking at the page because something happened, and "happened"
is a word about the past. A component that fell and came back between two 15-second polls left
no trace anywhere in this system.

So each probe run is journalled, and the journal stores **phases** — "``clickhouse`` was ``fail``
from 09:12 to 09:41" — rather than one row per observation. A row per observation would be a
page-refresh log: at one poll every fifteen seconds a single browser left open overnight writes
5 760 rows that say nothing changed.

**A gap is not a verdict, and this is the whole design.** The probe only runs when somebody
asks, so the journal knows about the minutes a cockpit was open and nothing at all about the
hours it was closed. Extending a phase across that silence would manufacture uptime out of
nobody looking — the exact over-claim ADR 0026 forbids, and the easiest one to write by
accident. A phase therefore only absorbs an observation that arrives within
:data:`CONTINUITY_WINDOW`; a later one starts a **new** phase, and the hole between them is
reported as ``unobserved`` and never as ``ok``.

That is why :func:`availability` publishes ``observed_ratio`` beside every percentage. "99.9 %
available" over a window that was watched for four of its twenty-four hours is a true sentence
about four hours and a false one about the day; the reader gets both numbers or neither.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Final

from tessera.fsutil import atomic_write_text
from tessera.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence
    from pathlib import Path

__all__ = [
    "CONTINUITY_WINDOW",
    "Availability",
    "ComponentPhase",
    "Transition",
    "availability",
    "load_phases",
    "record_observation",
    "transitions",
]

#: How long a phase may reach forward from its last observation before the record is considered
#: to have stopped. Eight times the 15 s probe TTL: wide enough that an ordinary slow poll, a
#: retry or a redeploy does not shred one steady phase into confetti, narrow enough that a
#: closed cockpit becomes a hole within two minutes instead of an assumption.
CONTINUITY_WINDOW: Final = timedelta(seconds=120)

#: Phases kept, oldest rolling off. Twenty components, a handful of real transitions a day:
#: leaves months of history; a flapping component costs its own share and no one else's,
#: because the cap is applied per component rather than to the file.
_MAX_PHASES_PER_COMPONENT: Final = 200


@dataclass(frozen=True, slots=True)
class ComponentPhase:
    """One uninterrupted stretch during which a component held one verdict.

    ``until`` is the last instant the probe **observed** this verdict, not the instant it
    stopped being true. The difference is the point of this module: everything after ``until``
    is unknown until the next observation, and the reader is told so.
    """

    component: str
    verdict: str
    since: str
    until: str
    n_observations: int

    def start(self) -> datetime | None:
        """``since`` as an aware instant, or ``None`` when it will not parse."""
        return _instant(self.since)

    def end(self) -> datetime | None:
        """``until`` as an aware instant, or ``None`` when it will not parse."""
        return _instant(self.until)


@dataclass(frozen=True, slots=True)
class Transition:
    """A component changing verdict — the event a poll-and-render page throws away."""

    component: str
    #: Never ``None``. A first-ever observation is **not** a transition: nothing changed, the
    #: record merely began — a component might have been failing for a week before anyone
    #: looked. Emitting it would announce an incident every time a container restarts, and the
    #: only alternative, inventing ``ok`` as the implied starting point, reports a recovery
    #: nobody witnessed.
    from_verdict: str
    to_verdict: str
    at: str
    #: True when the previous phase ended more than :data:`CONTINUITY_WINDOW` before this one
    #: began — the change happened somewhere inside a hole, so its instant is a *discovery*
    #: time, not an occurrence time, and the UI must word it that way.
    after_gap: bool


@dataclass(frozen=True, slots=True)
class Availability:
    """How one component fared across a window, and how much of that window was watched."""

    component: str
    #: Seconds observed in each verdict, keyed by verdict. Sums to ``observed_seconds``.
    seconds_by_verdict: dict[str, float]
    observed_seconds: float
    window_seconds: float

    @property
    def observed_ratio(self) -> float:
        """The share of the window the probe actually looked at. Zero ⇒ nothing may be claimed."""
        return self.observed_seconds / self.window_seconds if self.window_seconds > 0 else 0.0

    @property
    def ok_ratio(self) -> float | None:
        """Share of the **observed** time the component was ``ok`` — ``None`` when unobserved.

        ``None`` rather than ``0.0`` or ``1.0``: a window nobody watched has no availability,
        and both numeric answers are assertions the record cannot support.
        """
        if self.observed_seconds <= 0:
            return None
        return self.seconds_by_verdict.get("ok", 0.0) / self.observed_seconds


def _state_path() -> Path:
    """Sibling of the guard audit log, so the journal outlives the container."""
    return get_settings().guard.audit_file.parent / "component_phases.json"


def _instant(value: str) -> datetime | None:
    try:
        stamp = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    return stamp.replace(tzinfo=UTC) if stamp.tzinfo is None else stamp.astimezone(UTC)


def load_phases() -> list[ComponentPhase]:
    """Every recorded phase, oldest first (best effort).

    An unreadable or corrupt journal returns empty rather than raising — this feeds a card on a
    dashboard, and the caller renders "nothing recorded" as a hole. It must not take a page down.
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
    phases: list[ComponentPhase] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        try:
            phases.append(
                ComponentPhase(
                    component=str(entry["component"]),
                    verdict=str(entry["verdict"]),
                    since=str(entry["since"]),
                    until=str(entry["until"]),
                    n_observations=int(entry["n_observations"]),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue  # one malformed row must not hide the rest of the history
    return phases


def record_observation(
    verdicts: Mapping[str, str],
    *,
    at: datetime | None = None,
    phases: list[ComponentPhase] | None = None,
) -> list[ComponentPhase]:
    """Fold one probe run into the journal and persist it.

    Called from the read path when a probe **actually ran** — never when its cached answer was
    handed back, which would count re-reads as observations and inflate coverage with nothing.

    Args:
        verdicts: Component key → the verdict just observed.
        at: The observation instant; defaults to now.
        phases: A pre-loaded journal, for tests. Loaded from disk when omitted.

    Returns:
        The updated journal, as written.
    """
    now = at or datetime.now(UTC)
    known = load_phases() if phases is None else list(phases)
    latest: dict[str, int] = {}
    for index, phase in enumerate(known):
        latest[phase.component] = index

    for component, verdict in sorted(verdicts.items()):
        position = latest.get(component)
        previous = known[position] if position is not None else None
        end = previous.end() if previous is not None else None
        # An observation joins the phase before it only when the verdict is unchanged AND the
        # silence since the last look is short enough to stand for continuity. Both halves
        # matter: the first keeps a change from being swallowed, the second keeps a closed
        # cockpit from being rendered as uptime.
        continuous = (
            previous is not None
            and end is not None
            and previous.verdict == verdict
            and timedelta() <= now - end <= CONTINUITY_WINDOW
        )
        if continuous and previous is not None and position is not None:
            known[position] = ComponentPhase(
                component=component,
                verdict=verdict,
                since=previous.since,
                until=now.isoformat(),
                n_observations=previous.n_observations + 1,
            )
        else:
            known.append(
                ComponentPhase(
                    component=component,
                    verdict=verdict,
                    since=now.isoformat(),
                    until=now.isoformat(),
                    n_observations=1,
                )
            )
    trimmed = _trim(known)
    _write(trimmed)
    return trimmed


def _trim(phases: Sequence[ComponentPhase]) -> list[ComponentPhase]:
    """Cap the history **per component**, so one flapping node cannot evict the others."""
    counts: dict[str, int] = {}
    keep: list[ComponentPhase] = []
    for phase in reversed(phases):
        seen = counts.get(phase.component, 0)
        if seen >= _MAX_PHASES_PER_COMPONENT:
            continue
        counts[phase.component] = seen + 1
        keep.append(phase)
    keep.reverse()
    return keep


def transitions(
    *,
    since: datetime,
    until: datetime | None = None,
    phases: Iterable[ComponentPhase] | None = None,
) -> list[Transition]:
    """Every verdict change whose phase began inside the window, newest first.

    A phase that merely *overlaps* the window is not a transition inside it — the change
    happened earlier, and reporting it as recent is how a stale incident gets re-litigated
    every morning.
    """
    end = until or datetime.now(UTC)
    known = list(phases) if phases is not None else load_phases()
    by_component: dict[str, list[ComponentPhase]] = {}
    for phase in known:
        by_component.setdefault(phase.component, []).append(phase)

    found: list[Transition] = []
    for component, series in by_component.items():
        ordered = [p for p in series if p.start() is not None]
        ordered.sort(key=lambda p: p.since)
        for position, phase in enumerate(ordered):
            start = phase.start()
            if start is None or start < since or start > end:
                continue
            if position == 0:
                continue  # the record beginning, not the component changing — see Transition
            previous = ordered[position - 1]
            if previous.verdict == phase.verdict:
                # Same verdict on both sides of a hole: the record restarted, the component did
                # not change. Reporting it as a transition would invent an incident out of a
                # cockpit having been closed.
                continue
            previous_end = previous.end()
            found.append(
                Transition(
                    component=component,
                    from_verdict=previous.verdict,
                    to_verdict=phase.verdict,
                    at=phase.since,
                    after_gap=previous_end is None or (start - previous_end) > CONTINUITY_WINDOW,
                )
            )
    found.sort(key=lambda t: t.at, reverse=True)
    return found


def availability(
    *,
    since: datetime,
    until: datetime | None = None,
    phases: Iterable[ComponentPhase] | None = None,
) -> dict[str, Availability]:
    """Time spent in each verdict per component, plus how much of the window was observed.

    Each phase contributes ``[since, until]`` clipped to the window — its *observed* span, which
    stops at the last probe rather than running on to the window's edge. Whatever is left over
    is time nobody watched, and it stays out of every numerator and every denominator except
    ``window_seconds``.
    """
    end = until or datetime.now(UTC)
    window_seconds = max((end - since).total_seconds(), 0.0)
    known = list(phases) if phases is not None else load_phases()

    spans: dict[str, dict[str, float]] = {}
    for phase in known:
        start, stop = phase.start(), phase.end()
        if start is None or stop is None:
            continue
        left, right = max(start, since), min(stop, end)
        if right < left:
            continue  # the phase lies wholly outside the window
        # ``right == left`` is kept, at zero seconds. A component observed once has a point
        # phase and no observed DURATION, which is a true and useful thing to render — while
        # dropping the row entirely says "never observed", a different and false statement, and
        # leaves the card listing fewer components than the table above it.
        spans.setdefault(phase.component, {})
        spans[phase.component][phase.verdict] = (
            spans[phase.component].get(phase.verdict, 0.0) + (right - left).total_seconds()
        )

    return {
        component: Availability(
            component=component,
            seconds_by_verdict=dict(by_verdict),
            observed_seconds=sum(by_verdict.values()),
            window_seconds=window_seconds,
        )
        for component, by_verdict in spans.items()
    }


def _write(phases: Sequence[ComponentPhase]) -> None:
    """Persist the journal, best effort.

    A read-only filesystem or a full disk degrades the HISTORY, never the answer the operator
    asked for (ADR 0015).
    """
    path = _state_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            path, json.dumps([asdict(p) for p in phases], indent=2, ensure_ascii=False)
        )
    except OSError:
        return
