"""The first-class ``Scope`` value object (ADR 0015).

``Scope`` is the set of dimension filters a cockpit signal is read under. It is parsed
**once** per request (server: from query params via :meth:`Scope.from_query`; client:
from the URL via ``lib/scope.ts``) and generalises ADR 0011's as-of-T: the temporal
``at`` is one dimension of ``Scope``, not a separate mechanism. Adding a dimension later
(``language``, ``model``, ``environment``) is a field here, not a route sweep.

The temporal dimension has **two** bounds, and until 2026-08-01 only one of them was
here. ``at`` is where the window *ends*; ``period_days`` is how far back it *starts*.
The cockpit has shown a 24 h / 7 d / 30 d selector since the rail was built, and that
selector reached nothing: no fetch sent it, no handler declared it, and FastAPI drops an
undeclared query param in silence — ``/observability/slo?days=1``, ``?days=7`` and
``?days=30`` all answered ``n=67``. Three choices, one number.

Both bounds are read off the same field of the same rows (``scored_at``), so they are one
capability, not two: a signal that can be read as-of-T can be read over a window, and one
that cannot do either declares no :data:`Dimension.TIME` and has the period dropped by
:meth:`narrow_to` — which is what makes the ignored-but-shown state unrepresentable here
too, rather than something each surface has to remember to say.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["PERIOD_DAYS", "Dimension", "Scope", "parse_period_days"]

_ALL_AGENTS = "all"  # the deduplicated org view (mirrors ``lib/agent-scope`` on the front)

#: The cockpit's period keys and their length in days — the ONE mapping between the rail's
#: vocabulary (``lib/stores/window-store.ts``) and a number of days on the wire.
#: ``tests/unit/test_period_reaches_the_data.py`` pins it against the front's own list, so a
#: period added to the selector cannot quietly mean nothing to the backend.
PERIOD_DAYS: dict[str, int] = {"h24": 1, "d7": 7, "d30": 30}


class Dimension(str, Enum):
    """A slicing dimension a signal may or may not support."""

    AGENT = "agent"
    TIME = "time"
    LANGUAGE = "language"
    MODEL = "model"
    ENVIRONMENT = "environment"


@dataclass(frozen=True, slots=True)
class Scope:
    """An immutable set of dimension filters over the dimensioned fact model.

    ``agent_id`` of ``None`` is the org view (all agents, deduplicated). ``at`` of
    ``None`` is live; a set ``at`` is an as-of-T window end (ADR 0011). ``period_days``
    of ``None`` is all history; a set value is how far back the window reaches from that
    end. ``language`` / ``model`` / ``environment`` are additional filters (wired into
    the UI in Phase F).
    """

    at: str | None = None
    agent_id: str | None = None
    language: str | None = None
    model: str | None = None
    environment: str | None = None
    # Fractional on purpose. A sparkline bucket is a narrow window and nothing else — one
    # eighth of seven days — so bucketing reuses this field instead of introducing a second
    # way to say "between these two instants". That matters more than it looks: the curve and
    # the number are then computed by the same code path over the same field, and a curve that
    # disagrees with the value beneath it becomes unrepresentable rather than merely unlikely.
    period_days: float | None = None

    @classmethod
    def from_query(cls, params: Mapping[str, str | None]) -> Scope:
        """Parse a ``Scope`` from request query params.

        ``agent`` of ``"all"`` / empty maps to the org view (``agent_id=None``); any
        other value is a concrete agent id. ``at`` is the as-of-T instant. ``days`` is
        the window length — accepted either as a number or as one of the rail's period
        keys (``h24`` / ``d7`` / ``d30``), so a caller may send whichever vocabulary it
        already holds. Blank values are dropped so a filter is never silently the empty
        string, and an UNPARSEABLE window is dropped to ``None`` (all history) rather
        than guessed at: a period nobody can read must not silently become a default one
        the operator did not choose.

        Args:
            params: A mapping of query-param name to its raw string value (or ``None``).

        Returns:
            The parsed, normalised :class:`Scope`.
        """

        def _clean(value: str | None) -> str | None:
            if value is None:
                return None
            trimmed = value.strip()
            return trimmed or None

        agent_raw = _clean(params.get("agent"))
        agent_id = None if agent_raw is None or agent_raw == _ALL_AGENTS else agent_raw
        return cls(
            at=_clean(params.get("at")),
            agent_id=agent_id,
            language=_clean(params.get("language")),
            model=_clean(params.get("model")),
            environment=_clean(params.get("environment")),
            period_days=parse_period_days(_clean(params.get("days"))),
        )

    @property
    def agent_param(self) -> str:
        """The ``?agent=`` wire value: the id, or ``"all"`` for the org view."""
        return self.agent_id if self.agent_id is not None else _ALL_AGENTS

    @property
    def filters(self) -> frozenset[Dimension]:
        """The dimensions this scope actively constrains (each with a non-None value)."""
        active: set[Dimension] = set()
        if self.at is not None or self.period_days is not None:
            active.add(Dimension.TIME)
        if self.agent_id is not None:
            active.add(Dimension.AGENT)
        if self.language is not None:
            active.add(Dimension.LANGUAGE)
        if self.model is not None:
            active.add(Dimension.MODEL)
        if self.environment is not None:
            active.add(Dimension.ENVIRONMENT)
        return frozenset(active)

    def narrow_to(self, supported: frozenset[Dimension]) -> Scope:
        """Drop every filter the signal does not declare.

        This is what makes an unsupported dimension *impossible* to silently apply: the
        registry narrows the request scope to a signal's declared dimensions before the
        read, so a per-agent filter can never reach an org-wide signal's read path.
        """
        return Scope(
            at=self.at if Dimension.TIME in supported else None,
            agent_id=self.agent_id if Dimension.AGENT in supported else None,
            language=self.language if Dimension.LANGUAGE in supported else None,
            model=self.model if Dimension.MODEL in supported else None,
            environment=(self.environment if Dimension.ENVIRONMENT in supported else None),
            # Both temporal bounds ride TIME: a signal reads them off the same field of the
            # same rows, so it can honour both or neither. A fixed-corpus probe declares no
            # TIME and gets the period dropped here — and therefore reported as *ignored*,
            # which is the only reason the UI can say "this number is not windowed" without
            # anyone maintaining a second list of which numbers those are.
            period_days=self.period_days if Dimension.TIME in supported else None,
        )

    def window(self) -> tuple[datetime | None, datetime | None]:
        """The ``(since, until)`` interval this scope selects — the ONE resolver.

        ``until`` is the as-of instant when set, else "now" — and ``None`` when neither
        bound applies, because a read over all history must not be silently capped at the
        clock of the machine answering it. ``since`` is ``until`` minus the period, and
        ``None`` when no period is set.

        Every windowed read goes through here rather than doing its own arithmetic. That
        is not tidiness: the same subtraction written twice is how the rail's axis and the
        card's number came to disagree about which week they were showing.
        """
        if self.at is None:
            until = datetime.now(UTC) if self.period_days is not None else None
        else:
            until = datetime.fromisoformat(self.at)
            if until.tzinfo is None:
                until = until.replace(tzinfo=UTC)
        since = until - timedelta(days=self.period_days) if until and self.period_days else None
        return since, until

    def within(self, ts: object) -> bool:
        """Whether a row's timestamp falls inside this scope's window.

        Fails **open** on an unparseable or absent timestamp — the same posture
        :func:`tessera.observability._asof.occurred_before` takes for the upper bound, and
        for the same reason: a bad ``scored_at`` must not silently delete real data from a
        count. The row is kept and the count is honest about being a superset.
        """
        since, until = self.window()
        if since is None and until is None:
            return True
        if not isinstance(ts, str):
            return True
        try:
            moment = datetime.fromisoformat(ts)
        except ValueError:
            return True
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=UTC)
        if since is not None and moment < since:
            return False
        return not (until is not None and moment > until)

    def to_labels(self) -> dict[str, str]:
        """A label selector for the spine (Prometheus / Langfuse) — only set dimensions.

        The temporal ``at`` is *not* a label (it is a time-range bound, applied by the
        adapter), so it is intentionally absent here.
        """
        labels: dict[str, str] = {}
        if self.agent_id is not None:
            labels["agent_id"] = self.agent_id
        if self.language is not None:
            labels["language"] = self.language
        if self.model is not None:
            labels["model"] = self.model
        if self.environment is not None:
            labels["environment"] = self.environment
        return labels

    def key(self) -> str:
        """A stable, order-independent cache key for this scope (null-safe).

        ``days`` belongs here for the same reason every other dimension does, and the cost
        of forgetting it is worse than a stale read: the snapshot context memoises by this
        key, so a 30-day read already in the map would be handed straight back to a caller
        asking for 24 hours — the period would *appear* wired and still show one number.
        """
        return "|".join(
            f"{name}={value or ''}"
            for name, value in (
                ("at", self.at),
                ("agent", self.agent_id),
                ("lang", self.language),
                ("model", self.model),
                ("env", self.environment),
                ("days", None if self.period_days is None else str(self.period_days)),
            )
        )


def parse_period_days(raw: str | None) -> float | None:
    """A window length from the wire: a number of days, or a rail period key.

    Returns ``None`` for absent, unreadable, or non-positive input — "all history", the
    same thing the cockpit meant before a period could reach the data at all. Refusing to
    guess is the point: coercing an unreadable ``?days=`` into 7 would put a window the
    operator never picked behind numbers they are about to act on.

    Parsed as a FLOAT, not an int. The rail only ever sends whole days, but a sparkline
    bucket is one eighth of the window and travels through this same parser — and ``int()``
    on ``"0.875"`` raises, which this function turns into ``None``, which means all
    history. Every bucket of a seven-day curve would then have covered all of time and the
    line would have been flat and wrong, with nothing anywhere reporting a failure.

    Args:
        raw: The raw ``days`` query value — ``"7"``, ``"0.875"``, ``"d7"``, or nonsense.

    Returns:
        A positive number of days, or ``None`` for all history.
    """
    if raw is None:
        return None
    key = raw.strip()
    if key in PERIOD_DAYS:
        return float(PERIOD_DAYS[key])
    try:
        days = float(key)
    except ValueError:
        return None
    return days if days > 0 else None
