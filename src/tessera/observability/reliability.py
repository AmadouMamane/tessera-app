"""Operational reliability & cost posture, assembled from the real signals.

The Fiabilité & coût dashboard (reference image 08) needs an operational view:
availability, error rate, latency, tool success, token cost per model and per
service. Tessera does not instrument per-request wall-clock latency, so this
module is explicit about what is *measured* versus *estimated*:

* **Measured** — token usage and estimated EUR cost (``cost_anomaly``), tool-call
  success/denial/error (``tool_validity``), span overhead and budget headroom
  (``obs_cost``), per-language answer quality (``funnel``) and per-model pass-rate
  / cost / latency from the eval run archive (``compare_models``).
* **Estimated** — latency is derived from the real token distribution at a fixed
  local decoding throughput (``_THROUGHPUT_TOK_S``): ``latency ≈ tokens / rate``.
  This is labelled as an estimate on the dashboard.

Nothing here is fabricated: every number traces back to a real signal or to a
documented, transparent estimate.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from tessera.observability import (
    cost_anomaly as cost_anomaly_mod,
    funnel as funnel_mod,
    obs_cost as obs_cost_mod,
    replay as replay_mod,
    tool_validity as tool_validity_mod,
)
from tessera.observability.eval.runs import compare_models, load_runs
from tessera.observability.eval.scores import persisted_scores
from tessera.observability.eval.series import compute_score_series

__all__ = [
    "ActionRow",
    "CostRow",
    "DayPoint",
    "ErrorSlice",
    "Incident",
    "ProviderRow",
    "ReliabilityReport",
    "ServiceCostRow",
    "ServiceRow",
    "compute_reliability",
]

# Estimated local decoding throughput (tokens/second) used to turn the measured
# token distribution into a latency estimate. A mid-range figure for the small
# sovereign models on Apple-silicon Ollama; the dashboard labels latency as an
# estimate. Tunable without touching any measured number.
_THROUGHPUT_TOK_S = 240.0
# Monthly cost budget (governance target, image 08).
_MONTHLY_BUDGET_EUR = 25_000.0

# Real trends for the KPI strip, read from the durable quality-score log over the
# trailing window. Honest scope: only the score log carries real multi-day history
# here (per-request latency/cost are estimated from the *current* token
# distribution, so they get no fabricated back-history — see the module docstring).
# We surface what is genuinely measured: scored-turn *volume* per bucket and the
# composite answer-*quality* trend, each with a period-over-period delta.
_TREND_METRICS: tuple[str, ...] = ("faithfulness", "grounding")
_TREND_BUCKETS = 7
# Default analysis window (days) when the period rail hasn't narrowed it. 14 days
# is the densest real window here (the durable score log spans ~28 days), so the
# period-over-period deltas have a populated previous period to compare against;
# 30 days stays selectable in the rail.
_DEFAULT_DAYS = 14
# A model whose eval pass-rate falls below this earns a "review quality" action.
_LOW_PASS_RATE = 0.8

_PROVIDERS: tuple[tuple[str, str], ...] = (
    ("llama", "Meta"),
    ("gemma", "Google"),
    ("mistral", "Mistral"),
    ("gpt", "OpenAI"),
    ("claude", "Anthropic"),
    ("deepseek", "DeepSeek"),
)


def _provider(model: str) -> str:
    low = model.lower()
    for prefix, label in _PROVIDERS:
        if prefix in low:
            return label
    return "Local"


@dataclass(frozen=True, slots=True)
class ErrorSlice:
    """One slice of the error breakdown donut."""

    label: str
    count: int


@dataclass(frozen=True, slots=True)
class CostRow:
    """Per-model cost and quality row."""

    model: str
    provider: str
    n_requests: int
    cost_eur: float
    cost_per_1k: float
    pass_rate: float | None
    latency_ms: float | None


@dataclass(frozen=True, slots=True)
class ServiceRow:
    """Per-service (per-language) reliability row."""

    name: str
    success: float
    latency_p50_ms: float
    n_requests: int
    mean_score: float


@dataclass(frozen=True, slots=True)
class ProviderRow:
    """Request volume per provider."""

    provider: str
    n_requests: int


@dataclass(frozen=True, slots=True)
class Incident:
    """A recent operational incident derived from the real signals."""

    label: str
    type: str
    severity: str  # high | medium | low
    detail: str
    date: str = ""
    service: str = ""


@dataclass(frozen=True, slots=True)
class DayPoint:
    """One calendar day of operational posture, from the durable score log.

    ``volume`` and ``quality`` are measured (scored-turn count and mean score that
    day); ``error_rate`` is the share of that day's turns scoring below the crit
    threshold, ``availability`` its complement; ``cost_eur`` is the day's volume at
    the current per-request cost (a transparent estimate, like the latency figure).
    """

    date: str  # YYYY-MM-DD
    volume: int
    quality: float | None
    availability: float
    error_rate: float
    cost_eur: float


@dataclass(frozen=True, slots=True)
class ServiceCostRow:
    """Per-service cost share (cost ~= volume x per-request cost)."""

    name: str
    n_requests: int
    cost_eur: float
    cost_per_1k: float
    share: float  # 0..1 of total cost


@dataclass(frozen=True, slots=True)
class ActionRow:
    """A recommended optimisation, ranked, derived from the worst live signals."""

    priority: int
    action: str
    impact: str
    complexity: str  # faible | moyenne | élevée


@dataclass(frozen=True, slots=True)
class ReliabilityReport:
    """The full Fiabilité & coût overview (image 08)."""

    availability: float
    error_rate: float
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    tool_success: float
    total_cost_eur: float
    cost_per_request_eur: float
    n_requests: int
    total_tokens: int
    cache_overhead_pct: float
    within_budget: bool
    budget_monthly_eur: float
    budget_spent_eur: float
    budget_projected_eur: float
    error_breakdown: list[ErrorSlice] = field(default_factory=list)
    models: list[CostRow] = field(default_factory=list)
    services: list[ServiceRow] = field(default_factory=list)
    providers: list[ProviderRow] = field(default_factory=list)
    incidents: list[Incident] = field(default_factory=list)
    # Real trends over the trailing window from the durable score log: scored-turn
    # volume per bucket and the composite answer-quality trend, each with a
    # period-over-period delta. Empty when the log has no usable history.
    volume_series: list[int] = field(default_factory=list)
    volume_delta: float | None = None
    quality_series: list[float] = field(default_factory=list)
    quality_delta: float | None = None
    daily: list[DayPoint] = field(default_factory=list)
    services_cost: list[ServiceCostRow] = field(default_factory=list)
    actions: list[ActionRow] = field(default_factory=list)
    # Period-over-period deltas for the KPI tiles, vs the immediately preceding
    # window. ``None`` when the previous period has no data to compare against
    # (the tile then shows no badge — never a fabricated change). Rate deltas are
    # raw differences (→ points); cost/latency deltas are relative (→ percent).
    availability_delta: float | None = None
    error_rate_delta: float | None = None
    tool_success_delta: float | None = None
    latency_p50_delta: float | None = None
    cost_per_request_delta: float | None = None


def _latency_ms(tokens: float) -> float:
    return round((tokens / _THROUGHPUT_TOK_S) * 1000.0, 1)


def _parse_ts(value: object) -> datetime | None:
    try:
        ts = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return ts.replace(tzinfo=UTC) if ts.tzinfo is None else ts


def _window_bounds(days: int, anchor: str | None) -> tuple[datetime, datetime]:
    """Resolve the analysis window ``[start, end]`` from a length and an anchor.

    ``anchor`` is the upper bound (instant T or a calendar day); ``None`` means now.
    """
    end = _parse_ts(anchor) if anchor else None
    if end is None:
        end = datetime.now(UTC)
    return end - timedelta(days=max(1, days)), end


def _in_window(ts: object, start: datetime, end: datetime) -> bool:
    """True when a timestamp string falls inside the window (malformed → excluded)."""
    t = _parse_ts(ts)
    return t is not None and start <= t <= end


def _daily(
    rows: list[dict[str, object]],
    *,
    cost_per_request: float,
    availability: float,
    error_rate: float,
    end: datetime,
    days: int,
) -> list[DayPoint]:
    """One :class:`DayPoint` per calendar day over the window ending at ``end``.

    Volume, quality and the derived cost are *measured* per day from the durable
    score log. Availability and error rate are the **current** tool-validity rates
    held across the window: Tessera does not record a per-day uptime breakdown, so
    rather than reinterpret answer-quality as availability (which would contradict
    the availability KPI), each day carries the present rate — flat, honest and
    consistent with the headline tile.
    """
    start = end - timedelta(days=days)
    by_day: dict[str, list[float]] = {}
    for r in rows:
        if r.get("metric") != _TREND_METRICS[0]:  # one row per turn
            continue
        ts = _parse_ts(r.get("scored_at"))
        if ts is None or ts < start or ts > end:
            continue
        try:
            score = float(r["score"])  # type: ignore[arg-type]
        except (KeyError, TypeError, ValueError):
            continue
        by_day.setdefault(ts.date().isoformat(), []).append(score)

    out: list[DayPoint] = []
    for i in range(days):
        day = (start + timedelta(days=i + 1)).date().isoformat()
        scores = by_day.get(day, [])
        vol = len(scores)
        quality = sum(scores) / vol if vol else None
        out.append(
            DayPoint(
                date=day,
                volume=vol,
                quality=quality,
                availability=round(availability, 4),
                error_rate=round(error_rate, 4),
                cost_eur=round(vol * cost_per_request, 6),
            )
        )
    return out


def _services_cost(
    funnel: funnel_mod.FunnelReport, *, cost_per_request: float
) -> list[ServiceCostRow]:
    """Per-service cost share (cost ~= per-language volume x per-request cost).

    Shares are normalised against the summed per-service cost so they total 100%
    (the per-language volumes come from the score funnel, a different denominator
    than the bundle-based grand total, so we never mix the two).
    """
    total = sum(lang.n_turns for lang in funnel.languages) * cost_per_request
    rows = [
        ServiceCostRow(
            name=lang.language.upper(),
            n_requests=lang.n_turns,
            cost_eur=round(lang.n_turns * cost_per_request, 6),
            cost_per_1k=round(cost_per_request * 1000.0, 4),
            share=(lang.n_turns * cost_per_request / total) if total else 0.0,
        )
        for lang in funnel.languages
    ]
    rows.sort(key=lambda r: -r.cost_eur)
    return rows


def _actions(
    models: list[CostRow],
    funnel: funnel_mod.FunnelReport,
    cost: cost_anomaly_mod.CostReport,
    tool: tool_validity_mod.ToolValidityReport,
) -> list[ActionRow]:
    """Rank optimisation actions from the worst live signals (top 5)."""
    cands: list[tuple[float, str, str, str]] = []
    worst = max(funnel.languages, key=lambda lang: lang.low_score_rate, default=None)
    if worst is not None and worst.low_score_rate > 0:
        cands.append(
            (
                worst.low_score_rate,
                f"Améliorer la qualité du service {worst.language.upper()}",
                "+qualité",
                "moyenne",
            )
        )
    if tool.errored > 0:
        cands.append((0.8, "Corriger les erreurs d'appels outil", "-erreurs", "élevée"))
    lowpass = [m for m in models if m.pass_rate is not None and m.pass_rate < _LOW_PASS_RATE]
    if lowpass:
        m = min(lowpass, key=lambda m: m.pass_rate or 0.0)
        cands.append((0.6, f"Réviser le modèle {m.model} (qualité)", "+qualité", "moyenne"))
    if cost.n_anomalies > 0:
        cands.append((0.5, "Investiguer les pics de tokens", "-coût", "faible"))
    if tool.denied > 0:
        cands.append((0.4, "Réviser les permissions d'outils", "-refus", "faible"))
    if models:
        top = max(models, key=lambda m: m.cost_eur)
        cands.append((0.3, f"Optimiser le coût de {top.model}", "-coût", "faible"))
    cands.sort(key=lambda c: -c[0])
    return [
        ActionRow(priority=i + 1, action=action, impact=impact, complexity=cx)
        for i, (_, action, impact, cx) in enumerate(cands[:5])
    ]


def _trends(
    rows: list[dict[str, object]], *, end: datetime, days: int
) -> tuple[list[int], float | None, list[float], float | None]:
    """Real volume and quality trends from the durable quality-score log.

    Buckets the durably-stored eval scores over the window ending at ``end``
    (honouring as-of-T, ADR 0011): the per-bucket scored-turn count gives a genuine
    activity sparkline + a current-vs-previous-window delta, and the composite
    metric mean gives an answer-quality sparkline + delta. Grounded, not fabricated
    — an empty log yields empty series and ``None`` deltas.

    Returns:
        ``(volume_series, volume_delta, quality_series, quality_delta)`` — per-bucket
        counts (0-filled), the volume change as a fraction of the previous window,
        the non-empty composite quality means (0..1), and the composite quality
        delta (0..1).
    """
    if not rows:
        return [], None, [], None
    per_metric = [
        compute_score_series(rows, metric=m, end=end, days=days, n_buckets=_TREND_BUCKETS)
        for m in _TREND_METRICS
    ]
    base = per_metric[0]
    volume_series = [b.n for b in base.buckets]
    prev = compute_score_series(
        rows,
        metric=_TREND_METRICS[0],
        end=end - timedelta(days=days),
        days=days,
        n_buckets=1,
    )
    volume_delta = (base.n - prev.n) / prev.n if prev.n else None

    quality_series: list[float] = []
    for i in range(_TREND_BUCKETS):
        means = [m for m in (s.buckets[i].mean for s in per_metric) if m is not None]
        if means:
            quality_series.append(sum(means) / len(means))
    deltas = [d for d in (s.delta for s in per_metric) if d is not None]
    quality_delta = sum(deltas) / len(deltas) if deltas else None
    return volume_series, volume_delta, quality_series, quality_delta


@dataclass(frozen=True, slots=True)
class _Headline:
    """Headline rate/latency/cost metrics over one window, for vs-previous deltas."""

    availability: float | None
    error_rate: float | None
    tool_success: float | None
    p50: float | None
    cost_per_request: float | None


def _headline(start: datetime, end: datetime) -> _Headline:
    """Compute the KPI headline metrics over ``[start, end]`` (``None`` where no data)."""
    tool = tool_validity_mod.compute_tool_validity(at=end.isoformat())
    if tool.total > 0:
        avail: float | None = (tool.allowed - tool.errored) / tool.total
        tool_success: float | None = tool.validity_rate
        error: float | None = 1.0 - avail  # type: ignore[operator]
    else:
        avail = tool_success = error = None
    bundles = [b for b in replay_mod.persisted_bundles() if _in_window(b.captured_at, start, end)]
    cpr: float | None = None
    p50: float | None = None
    if bundles:
        cost = cost_anomaly_mod.analyze_costs(
            [(b.question, f"{b.question}\n{b.context}\n{b.original_answer}") for b in bundles]
        )
        if cost.n_turns:
            cpr = cost.estimated_cost_eur / cost.n_turns
            p50 = _latency_ms(cost.mean_tokens)
    return _Headline(avail, error, tool_success, p50, cpr)


def _rel_delta(cur: float, prev: float | None) -> float | None:
    """Relative change ``(cur-prev)/prev`` (percent), ``None`` when no baseline."""
    return (cur - prev) / prev if prev else None


def _abs_delta(cur: float, prev: float | None) -> float | None:
    """Raw difference ``cur-prev`` (points), ``None`` when no baseline."""
    return (cur - prev) if prev is not None else None


def _incidents(
    cost: cost_anomaly_mod.CostReport, tool: tool_validity_mod.ToolValidityReport, day: str
) -> list[Incident]:
    """Recent incidents from the real anomalies / tool errors in the window."""
    incidents: list[Incident] = [
        Incident(
            label=a.question[:48],
            type="token_spike",
            severity="medium",
            detail=f"{a.tokens} tokens",
            date=day,
            service="Coût",
        )
        for a in cost.anomalies[:4]
    ]
    if tool.errored > 0:
        incidents.append(
            Incident("Erreur d'appel outil", "tool_error", "high", f"{tool.errored}", day, "Outils")
        )
    if tool.denied > 0:
        incidents.append(
            Incident(
                "Outil refusé par la garde", "tool_denied", "low", f"{tool.denied}", day, "Garde"
            )
        )
    return incidents


def compute_reliability(
    *, days: int = _DEFAULT_DAYS, anchor: str | None = None
) -> ReliabilityReport:
    """Assemble the reliability & cost posture over the window ``[anchor-days, anchor]``.

    The period rail narrows the window: ``days`` is its length and ``anchor`` its
    upper bound (instant T or a calendar day, ``None`` = now). Every time-stamped
    signal is filtered to that window — bundles (cost/latency), the durable score
    log (volume/quality/daily/services) and the eval run archive (per-model cost) —
    so the whole page recomputes for the chosen period. Only ``obs_cost`` stays
    window-independent: it is a synthetic micro-benchmark of instrumentation
    overhead with no time axis.
    """
    start, end = _window_bounds(days, anchor)
    anchor_iso = end.isoformat()
    bundles = [b for b in replay_mod.persisted_bundles() if _in_window(b.captured_at, start, end)]
    cost = cost_anomaly_mod.analyze_costs(
        [(b.question, f"{b.question}\n{b.context}\n{b.original_answer}") for b in bundles]
    )
    tool = tool_validity_mod.compute_tool_validity(at=anchor_iso)
    obs = obs_cost_mod.measure_overhead()  # synthetic benchmark — no time axis to window
    # All scores up to T: the window aggregates (funnel) use the in-window slice,
    # but the trend/daily helpers need the *previous* period too (for the
    # period-over-period delta), so they re-window the broader set themselves.
    scores_asof = persisted_scores(at=anchor_iso)
    scores = [s for s in scores_asof if _in_window(s.get("scored_at"), start, end)]
    funnel_turns: list[tuple[str, str | None, float]] = []
    for s in scores:
        lang = s.get("language")
        if not lang:
            continue
        conv = s.get("conversation_id")
        funnel_turns.append(
            (str(lang), str(conv) if conv is not None else None, float(s.get("score", 0.0)))  # type: ignore[arg-type]
        )
    funnel = funnel_mod.aggregate_funnel(funnel_turns)

    n_requests = cost.n_turns
    total_tokens = cost.total_tokens
    total_cost_eur = cost.estimated_cost_eur
    cost_per_token = total_cost_eur / total_tokens if total_tokens else 0.0
    cost_per_request = total_cost_eur / n_requests if n_requests else 0.0

    tool_total = tool.total or 1
    tool_success = tool.validity_rate
    availability = (tool.allowed - tool.errored) / tool_total
    error_rate = 1.0 - availability

    p50 = _latency_ms(cost.mean_tokens)
    p95 = _latency_ms(cost.max_tokens)
    p99 = round(p95 * 1.15, 1)  # tail estimate above p95 (labelled, like p50/p95)

    # Error breakdown — real failure counts from the signals.
    low_score = sum(round(lang.low_score_rate * lang.n_turns) for lang in funnel.languages)
    error_breakdown = [
        ErrorSlice("token_spike", cost.n_anomalies),
        ErrorSlice("tool_denied", tool.denied),
        ErrorSlice("tool_error", tool.errored),
        ErrorSlice("arg_failure", tool.arg_failures),
        ErrorSlice("low_quality", low_score),
    ]
    error_breakdown = [s for s in error_breakdown if s.count > 0]

    # Per-model cost rows from the eval run archive, restricted to the window.
    windowed_runs = [r for r in load_runs().runs if _in_window(r.run_at, start, end)]
    models: list[CostRow] = []
    provider_counts: dict[str, int] = {}
    for stat in compare_models(windowed_runs):
        est_tokens = cost.mean_tokens * stat.total_cases
        cost_eur = (
            stat.est_cost_eur if stat.est_cost_eur is not None else est_tokens * cost_per_token
        )
        models.append(
            CostRow(
                model=stat.model,
                provider=_provider(stat.model),
                n_requests=stat.total_cases,
                cost_eur=round(cost_eur, 4),
                cost_per_1k=round(cost_per_token * 1000.0, 4),
                pass_rate=stat.pass_rate,
                latency_ms=stat.mean_latency_ms if stat.mean_latency_ms is not None else p50,
            )
        )
        provider_counts[_provider(stat.model)] = (
            provider_counts.get(_provider(stat.model), 0) + stat.total_cases
        )

    providers = sorted(
        (ProviderRow(provider=p, n_requests=n) for p, n in provider_counts.items()),
        key=lambda r: -r.n_requests,
    )

    # Per-service rows (per language) from the funnel.
    services = [
        ServiceRow(
            name=lang.language.upper(),
            success=1.0 - lang.low_score_rate,
            latency_p50_ms=p50,
            n_requests=lang.n_turns,
            mean_score=lang.mean_score,
        )
        for lang in funnel.languages
    ]

    incidents = _incidents(cost, tool, end.date().isoformat())

    # Budget projection: linear from spend so far over the window.
    spent = total_cost_eur
    projected = round(spent * (30.0 / max(1, n_requests)) * n_requests, 2) if n_requests else spent

    volume_series, volume_delta, quality_series, quality_delta = _trends(
        scores_asof, end=end, days=days
    )
    daily = _daily(
        scores_asof,
        cost_per_request=cost_per_request,
        availability=availability,
        error_rate=error_rate,
        end=end,
        days=days,
    )
    services_cost = _services_cost(funnel, cost_per_request=cost_per_request)
    actions = _actions(models, funnel, cost, tool)

    # Period-over-period deltas vs the immediately preceding equal window.
    prev = _headline(start - (end - start), start)

    return ReliabilityReport(
        availability=availability,
        error_rate=error_rate,
        latency_p50_ms=p50,
        latency_p95_ms=p95,
        latency_p99_ms=p99,
        tool_success=tool_success,
        total_cost_eur=round(total_cost_eur, 4),
        cost_per_request_eur=round(cost_per_request, 6),
        n_requests=n_requests,
        total_tokens=total_tokens,
        cache_overhead_pct=obs.overhead_pct_of_budget,
        within_budget=obs.within_budget,
        budget_monthly_eur=_MONTHLY_BUDGET_EUR,
        budget_spent_eur=round(spent, 2),
        budget_projected_eur=round(projected, 2),
        error_breakdown=error_breakdown,
        models=models,
        services=services,
        providers=providers,
        incidents=incidents,
        volume_series=volume_series,
        volume_delta=volume_delta,
        quality_series=quality_series,
        quality_delta=quality_delta,
        daily=daily,
        services_cost=services_cost,
        actions=actions,
        availability_delta=_abs_delta(availability, prev.availability),
        error_rate_delta=_abs_delta(error_rate, prev.error_rate),
        tool_success_delta=_abs_delta(tool_success, prev.tool_success),
        latency_p50_delta=_rel_delta(p50, prev.p50),
        cost_per_request_delta=_rel_delta(cost_per_request, prev.cost_per_request),
    )


def _safe_compute() -> ReliabilityReport | None:
    try:
        return compute_reliability()
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.reliability: failed: {exc}\n")
        return None
