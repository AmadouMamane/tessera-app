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
happens to be one eighth of the page's. The front then feeds each bucket's payload through
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
  actually the same measurement repeated eight times.
"""

from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from tessera.observability.spine.scope import Scope

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = [
    "DEFAULT_BUCKETS",
    "MAX_BUCKETS",
    "SERIES_SOURCES",
    "SeriesBucket",
    "SeriesReport",
    "compute_control_series",
    "series_capability",
]

#: Buckets a curve is drawn from. Eight is the width the sparkline already assumed (the SLO
#: trend has used ``_MAX_BUCKETS = 8`` since it was written), kept so the one existing curve
#: does not change shape the day every other row grows one.
DEFAULT_BUCKETS = 8
#: A caller may ask for fewer or more, bounded: each bucket is a full re-read of the window's
#: stores, so an unbounded ``?buckets=`` is an unbounded read.
MAX_BUCKETS = 32


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
        # bucket of them a real measurement rather than the whole sample, drawn eight times.
        SeriesSource("citations", compliance.observability_citations),
        SeriesSource("contradiction", evals.observability_contradictions),
        SeriesSource("localeFormat", compliance.observability_locale_format),
        # Fixed-corpus probes. Re-running the same adversarial corpus against the same policy
        # inside a narrower window returns the same number — a flat line that reads as "stable"
        # while being one measurement drawn eight times. They earn a real curve only once their
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
    n_buckets: int = DEFAULT_BUCKETS,
) -> SeriesReport:
    """Bucket ``scope``'s window and compute every bucketable source inside each.

    Args:
        scope: The page's active scope. Its window is what gets sliced; its agent / language /
            model facets ride along unchanged, so a curve is scoped exactly as its number is.
        n_buckets: How many slices, clamped to ``[1, MAX_BUCKETS]``.

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

    count = max(1, min(int(n_buckets), MAX_BUCKETS))
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
                return source.key, await _call(source.handler, **kwargs)
            except Exception:  # a source that fails is OMITTED, never zero-filled
                return source.key, None

        settled = await asyncio.gather(*(_one(s) for s in bucketable))
        return SeriesBucket(
            index=index,
            since=(since + span * index).isoformat(),
            until=bucket_end.isoformat(),
            payload={key: value for key, value in settled if value is not None},
        )

    buckets = await asyncio.gather(*(_bucket(i) for i in range(count)))
    return SeriesReport(
        days=scope.period_days,
        n_buckets=count,
        since=since.isoformat(),
        until=until.isoformat(),
        buckets=list(buckets),
        unwindowed=unwindowed,
    )


def now_iso() -> str:
    """The current instant, for callers that need to stamp a report after the fact."""
    return datetime.now(UTC).isoformat()
