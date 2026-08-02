"""A curve for a control, computed by the control's OWN derivation over narrower windows.

Until 2026-08-01 exactly one row of "Contrôles critiques" had a curve — faithfulness — and it
had one because a line in ``overview-dashboard.tsx`` named it:

    row.id === "faithfulness" ? { ...row, trend: d.trend?.buckets.map(b => b.mean) } : row

Everything else showed a number with an empty chart slot beside it. The tempting fix is a
second derivation per control ("compute a toxicity trend"), and that is how a curve comes to
contradict the value printed under it — the very defect the control registry was built to end,
reappearing on the time axis.

So this module derives nothing. It slices the window into buckets and re-runs **the same
handler** the point value comes from, once per bucket, with the bucket as its scope. A bucket
is not a new concept: it is a :class:`~tessera.observability.spine.scope.Scope` whose window
happens to be one slice of the page's. The front then feeds each bucket's payload through
``readControls`` — the identical function that produced the number — and reads the ratio off
the result. The curve cannot disagree with the value because nothing computes it separately.

Two honesty properties follow, and both are asserted in
``tests/unit/test_control_series_shares_the_derivation.py``:

* A bucket with no traffic yields ``null``, never ``0``. An empty window is a gap in the line;
  a zero is a claim that the metric was measured and was zero. On a leak rate those render the
  same colour and mean opposite things.
* A control whose sample carries no per-row timestamp gets **no series at all**, and says which
  of the reasons applies. A fixed-corpus probe re-run over a narrower window returns the same
  fixed corpus, so bucketing it would draw a flat line that looks like a stable metric and is
  actually the same measurement repeated once per slice.
"""

from __future__ import annotations

import asyncio
import inspect
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from tessera.observability.logging import get_logger
from tessera.observability.spine.scope import Scope

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = [
    "DEFAULT_BUCKETS",
    "MAX_BUCKETS",
    "REASON_TOO_SLOW",
    "SERIES_SOURCES",
    "SOURCE_TIMEOUT_S",
    "SeriesBucket",
    "SeriesReport",
    "buckets_for_window",
    "compute_control_series",
    "series_capability",
]

#: Buckets a curve is drawn from when the window's length says nothing — a window of "all
#: history" has no width to slice, so this is only ever the fallback. Eight is the width the
#: sparkline assumed for its first year (the SLO trend has used ``_MAX_BUCKETS = 8`` since it
#: was written).
DEFAULT_BUCKETS = 8
#: A caller may ask for fewer or more, bounded: each bucket is a full re-read of the window's
#: stores, so an unbounded ``?buckets=`` is an unbounded read.
MAX_BUCKETS = 32

#: How long ONE source gets, per bucket.
#:
#: A source is computed by calling the same route handler the page calls, and those handlers
#: have no deadline of their own. One of them — ``contradiction`` — embeds every captured turn
#: through the local model, which answers in milliseconds warm and took **8.8 s for a single
#: input** once the model had been evicted (measured 2026-08-02, ``bge-m3`` under Ollama). All
#: thirteen are gathered, so a cold model does not slow this report down: it stops it. The
#: request never resolves, and every curve on the page falls back to "no history yet" — the
#: cockpit reporting an empty window because a model was asleep.
#:
#: A source that runs out of time is OMITTED, exactly like one that raises. That is not a new
#: behaviour, it is the existing one: a missing payload is already a hole in that control's
#: line rather than a zero, so the other twelve controls keep their curves. Fifteen seconds is
#: ~6x the slowest FULL report measured warm (2.3 s for thirty buckets), so it cannot cut a
#: healthy read short.
SOURCE_TIMEOUT_S = 15.0

_LOG = get_logger("tessera.observability.control_series")

#: Round clock units a bucket may be, in hours. A bucket of 90 h spans "three days and
#: eighteen hours", which is not a duration anyone reads an axis in.
_ROUND_HOURS: tuple[float, ...] = (1, 2, 3, 6, 12, 24, 48, 72, 168)

#: Bucket WIDTH in hours, per cockpit period — a *chosen* resolution, measured against the
#: live cockpit on 2026-08-02, not derived from a formula.
#:
#: It has to be chosen, because the right resolution depends on how the traffic is spread and
#: no rule can know that. It also has to be measured over MANY window ends, not one: the first
#: sweep compared 3 h and 2 h slices at a single instant, called them equal, and an hour later
#: they had swapped — where the bursts fall against the grid changes hourly, so one instant
#: decides nothing. Replayed at 6-10 window ends per period, over three controls (the fraction
#: of cases where a curve was drawable at all, and where part of it was drawn as a LINE rather
#: than isolated dots):
#:
#: ======  ==========================  ====================  ====================  ==========
#: window  slices                      drawable              drawn as a line       points
#: ======  ==========================  ====================  ====================  ==========
#: 24 h    8x3 h / **12x2 h** / 24x1 h  15 / 16 / 16 of 30    11 / 10 / 10 of 30    56/69/72
#: 7 j     8x21 h / **14x12 h** / 28x6 h  **0** / 3 / 4 of 24   **0** / 3 / 2 of 24   6/9/11
#: 30 j    8x90 h / 15x48 h / **30x24 h**  6 / 6 / 6 of 18     6 / 6 / 6 of 18       27/38/55
#: ======  ==========================  ====================  ====================  ==========
#:
#: Which refutes both tempting rules. "Finest that fits" is right at 30 j and buys nothing at
#: 24 h and 7 j, where a slice narrower than the gaps between requests puts a hole between
#: every pair of points. And the flat eight this replaced never drew a 7-day curve AT ALL, in
#: any of 24 replays — the reported defect, and the only row of this table that is not close.
#: Elsewhere the choice buys resolution rather than connectivity: same lines, ~25-100 % more
#: measured points.
#:
#: What none of them fixes: at 7 j only 3 cases in 24 are drawable even at 12 h. That is the
#: traffic — two bursts six days apart — and no grid invents a measurement between them.
#: Any other window falls back to :func:`buckets_for_window`'s general rule.
_LADDER: dict[float, float] = {1.0: 2.0, 7.0: 12.0, 30.0: 24.0}

#: What the general rule aims for on a window the ladder does not name. Fourteen sits between
#: the three chosen counts (12 / 14 / 30) and never shatters as badly as the finest fit. It is
#: also what makes the rule agree with the ladder at 24 h and 7 j: only 30 j is an override.
_TARGET_BUCKETS = 14

#: Float slack on "this unit divides the window". Not a tolerance anyone tunes: a window is
#: given in days and a unit in hours, so the quotient is exact up to representation.
_GRID_SLACK = 1e-6


def buckets_for_window(period_days: float) -> int:
    """How many slices a window of ``period_days`` is cut into.

    A window the ladder does not name is cut on the round unit that divides it EVENLY and
    lands closest to :data:`_TARGET_BUCKETS`. The even division is the part worth spelling
    out: choosing a width and then rounding the count gives a real width of ``hours / count``,
    which is a different number — 90 days aiming for weekly slices produced 13 buckets of
    166 h, i.e. "six days, twenty-two hours", the exact species of duration this ladder
    exists to avoid.

    Args:
        period_days: The window's length in days.

    Returns:
        A bucket count in ``[1, MAX_BUCKETS]``.
    """
    hours = period_days * 24
    chosen = _LADDER.get(period_days)
    if chosen is not None:
        return max(1, min(MAX_BUCKETS, round(hours / chosen)))

    def off_grid(unit: float) -> float:
        """How far the window falls from a whole number of ``unit`` — ``0`` when it divides."""
        remainder = math.fmod(hours, unit)
        return min(remainder, unit - remainder)

    even = [
        unit
        for unit in _ROUND_HOURS
        if 1 <= hours / unit <= MAX_BUCKETS and off_grid(unit) < _GRID_SLACK
    ]
    # Ties break toward the FINER slicing: at equal distance from the target, more points say
    # more. A window no round unit divides (53 days) keeps the nearest width and an uneven
    # slice — an honest last resort, not a promise this function silently breaks.
    width = (
        min(even, key=lambda unit: (abs(hours / unit - _TARGET_BUCKETS), unit))
        if even
        else min(_ROUND_HOURS, key=lambda unit: abs(unit - hours / _TARGET_BUCKETS))
    )
    return max(1, min(MAX_BUCKETS, round(hours / width)))


@dataclass(frozen=True, slots=True)
class SeriesBucket:
    """One time slice, carrying the payload the point value would be computed from."""

    index: int
    since: str
    until: str
    #: ``{payload key: that handler's answer over this bucket}`` — the same keys, and the same
    #: shapes, the page's live payload uses. The front runs its own ``readControls`` on it.
    payload: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SeriesReport:
    """The buckets of a window, plus what the window could not reach."""

    days: float | None
    n_buckets: int
    since: str | None
    until: str | None
    buckets: list[SeriesBucket] = field(default_factory=list)
    #: ``{payload key: reason}`` for the sources deliberately absent from every bucket. The UI
    #: renders the reason instead of an empty chart, so "no curve" is never mistaken for
    #: "flat".
    unwindowed: dict[str, str] = field(default_factory=dict)


#: Why a control has no curve. Each is a different thing to tell the operator, and collapsing
#: them into one "unavailable" is how a fixable gap gets read as a permanent one.
REASON_FIXED_CORPUS = "fixed-corpus"
REASON_NO_TIMESTAMP = "no-timestamp"
REASON_NOT_MEASURED = "not-measured"
#: The fourth, and the only one that is about THIS RUN rather than about the metric: the source
#: was asked and did not answer in time (:data:`SOURCE_TIMEOUT_S`). It says so instead of the
#: control simply having no line, because those are different facts and only one of them is
#: worth waking somebody for. Unlike its three siblings it is computed per request.
REASON_TOO_SLOW = "too-slow"


@dataclass(frozen=True, slots=True)
class SeriesSource:
    """One payload key: how to compute it for a bucket, or why it cannot be."""

    key: str
    handler: Callable[..., Any] | None
    #: ``None`` when the source IS bucketable; otherwise the reason it is not.
    reason: str | None = None


def series_capability(key: str) -> str | None:
    """The reason ``key`` has no curve, or ``None`` when it has one."""
    for source in SERIES_SOURCES:
        if source.key == key:
            return source.reason
    return REASON_NOT_MEASURED


def _sources() -> tuple[SeriesSource, ...]:
    """The payload keys a control reads, resolved late to avoid a route/observability cycle."""
    from tessera.api.routes.observability import business, compliance, evals, safety, signals

    return (
        # Bucketable: the sample is per-turn and carries its own timestamp, so a narrower
        # window is a genuinely different measurement.
        SeriesSource("slo", signals.observability_slo),
        SeriesSource("toxicity", safety.observability_toxicity),
        SeriesSource("pii", safety.observability_pii_leak),
        SeriesSource("conformance", signals.observability_conformance),
        SeriesSource("tools", safety.observability_tool_validity),
        SeriesSource("cost", signals.observability_cost),
        SeriesSource("anomalies", signals.observability_anomalies),
        SeriesSource("routing", signals.observability_routing),
        SeriesSource("intent", signals.observability_intent),
        SeriesSource("funnel", business.observability_funnel),
        # These three read per-turn samples too. They simply had no window to read them
        # under: their handlers took no scope at all, so "the last 30 days" and "everything"
        # were the same call. Giving them the scope the others already had is what makes a
        # bucket of them a real measurement rather than the whole sample, drawn once per slice.
        SeriesSource("citations", compliance.observability_citations),
        SeriesSource("contradiction", evals.observability_contradictions),
        SeriesSource("localeFormat", compliance.observability_locale_format),
        # Fixed-corpus probes. Re-running the same adversarial corpus against the same policy
        # inside a narrower window returns the same number — a flat line that reads as "stable"
        # while being one measurement drawn once per slice. They earn a real curve only once their
        # RUNS are durably recorded with the instant each ran at, which is what
        # ``probe_history`` now does; a probe with runs inside the window is served from there.
        SeriesSource("refusal", None, REASON_FIXED_CORPUS),
        SeriesSource("firewall", None, REASON_FIXED_CORPUS),
        SeriesSource("crossTenant", None, REASON_FIXED_CORPUS),
        SeriesSource("privilege", None, REASON_FIXED_CORPUS),
        SeriesSource("inversion", None, REASON_FIXED_CORPUS),
        # Whole-sample derivations: a k-means over failures, an inter-rater agreement, a
        # predictor's precision. Each needs the whole sample to mean anything, so a bucket of
        # it is not a smaller version of the same statistic — it is a different, noisier one
        # wearing the same label.
        SeriesSource("clusters", None, REASON_NO_TIMESTAMP),
        SeriesSource("calibration", None, REASON_NO_TIMESTAMP),
        SeriesSource("predictor", None, REASON_NO_TIMESTAMP),
    )


#: Resolved once, lazily — see :func:`_sources`.
SERIES_SOURCES: tuple[SeriesSource, ...] = ()


def _ensure_sources() -> tuple[SeriesSource, ...]:
    global SERIES_SOURCES
    if not SERIES_SOURCES:
        SERIES_SOURCES = _sources()
    return SERIES_SOURCES


async def _call(handler: Callable[..., Any], **kwargs: object) -> dict[str, object]:
    """Invoke a route handler, awaiting it only when it is one of the async ones."""
    result = handler(**kwargs)
    if inspect.isawaitable(result):
        return await result  # type: ignore[no-any-return]
    return result  # type: ignore[no-any-return]


def _accepted(handler: Callable[..., Any], **kwargs: object) -> dict[str, object]:
    """Keep only the kwargs this handler actually declares.

    The handlers differ in which scope facets they take, and passing one an argument it does
    not declare is a ``TypeError`` that would silently become an omitted bucket. Filtering by
    the real signature means a handler that gains a facet starts receiving it with no change
    here — and one that never had it is not quietly assumed to.
    """
    params = inspect.signature(handler).parameters
    return {name: value for name, value in kwargs.items() if name in params}


async def compute_control_series(
    scope: Scope,
    n_buckets: int | None = None,
) -> SeriesReport:
    """Bucket ``scope``'s window and compute every bucketable source inside each.

    Args:
        scope: The page's active scope. Its window is what gets sliced; its agent / language /
            model facets ride along unchanged, so a curve is scoped exactly as its number is.
        n_buckets: How many slices, clamped to ``[1, MAX_BUCKETS]``. ``None`` — the normal
            case — lets the window choose, via :func:`buckets_for_window`. That default lives
            here rather than in each caller because a resolution chosen per surface is a
            resolution that diverges: the same control's curve is drawn on Vue d'ensemble and
            on Qualité IA, and two counts would give it two shapes.

    Returns:
        A :class:`SeriesReport`. With no period on the scope, the report is empty and carries
        no buckets: a curve over "all history" has no width to slice, and inventing one from
        the oldest row present would make the axis depend on how long the demo has been
        running.
    """
    sources = _ensure_sources()
    unwindowed = {s.key: s.reason for s in sources if s.reason is not None}
    since, until = scope.window()
    if since is None or until is None or scope.period_days is None:
        return SeriesReport(
            days=scope.period_days,
            n_buckets=0,
            since=since.isoformat() if since else None,
            until=until.isoformat() if until else None,
            unwindowed=unwindowed,
        )

    requested = buckets_for_window(scope.period_days) if n_buckets is None else int(n_buckets)
    count = max(1, min(requested, MAX_BUCKETS))
    width_days = scope.period_days / count
    span = (until - since) / count
    bucketable = [s for s in sources if s.handler is not None]

    async def _bucket(index: int) -> SeriesBucket:
        bucket_end = since + span * (index + 1)
        bucket_scope = Scope(
            at=bucket_end.isoformat(),
            agent_id=scope.agent_id,
            language=scope.language,
            model=scope.model,
            environment=scope.environment,
            period_days=width_days,
        )

        async def _one(source: SeriesSource) -> tuple[str, object | None]:
            assert source.handler is not None  # narrowed by `bucketable`
            try:
                kwargs = _accepted(
                    source.handler,
                    at=bucket_scope.at,
                    agent=scope.agent_id or "all",
                    days=str(width_days),
                )
                call = _call(source.handler, **kwargs)
                return source.key, await asyncio.wait_for(call, SOURCE_TIMEOUT_S)
            except TimeoutError:
                # Omitted like a failure, but SAID — twice. In the log, for whoever is on call;
                # and in the report's `unwindowed`, so the cell carries a reason instead of an
                # empty chart. "This control has no curve" and "something upstream is asleep"
                # are different facts, and only one of them is worth waking somebody for.
                timed_out.add(source.key)
                _LOG.warning(
                    "control_series.source_timeout",
                    source=source.key,
                    bucket=index,
                    seconds=SOURCE_TIMEOUT_S,
                )
                return source.key, None
            except Exception:  # a source that fails is OMITTED, never zero-filled
                return source.key, None

        settled = await asyncio.gather(*(_one(s) for s in bucketable))
        return SeriesBucket(
            index=index,
            since=(since + span * index).isoformat(),
            until=bucket_end.isoformat(),
            payload={key: value for key, value in settled if value is not None},
        )

    #: Sources this run asked for and did not get in time. Written by `_one`, read after the
    #: gather — a set because the same source may time out in several buckets and the operator
    #: is owed one sentence, not one per slice.
    timed_out: set[str] = set()
    buckets = await asyncio.gather(*(_bucket(i) for i in range(count)))
    # A source that answered SOMEWHERE keeps its curve: the points it did return are real, and
    # `readControlSeries` already draws the missing slice as a hole rather than a zero. Only a
    # source that answered nowhere has nothing to show, and that is what earns the reason.
    answered = {key for bucket in buckets for key in bucket.payload}
    return SeriesReport(
        days=scope.period_days,
        n_buckets=count,
        since=since.isoformat(),
        until=until.isoformat(),
        buckets=list(buckets),
        unwindowed=unwindowed | {key: REASON_TOO_SLOW for key in timed_out - answered},
    )


def now_iso() -> str:
    """The current instant, for callers that need to stamp a report after the fact."""
    return datetime.now(UTC).isoformat()
