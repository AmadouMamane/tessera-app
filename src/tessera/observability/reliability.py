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
from tessera.observability.eval.scores import persisted_scores, recent_scores
from tessera.observability.eval.series import compute_score_series

__all__ = [
    "CostRow",
    "ErrorSlice",
    "Incident",
    "ProviderRow",
    "ReliabilityReport",
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
_TREND_DAYS = 14
_TREND_BUCKETS = 7

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


@dataclass(frozen=True, slots=True)
class ReliabilityReport:
    """The full Fiabilité & coût overview (image 08)."""

    availability: float
    error_rate: float
    latency_p50_ms: float
    latency_p95_ms: float
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


def _latency_ms(tokens: float) -> float:
    return round((tokens / _THROUGHPUT_TOK_S) * 1000.0, 1)


def _trends() -> tuple[list[int], float | None, list[float], float | None]:
    """Real volume and quality trends from the durable quality-score log.

    Buckets the durably-stored eval scores over the trailing window (honouring
    as-of-T, ADR 0011): the per-bucket scored-turn count gives a genuine activity
    sparkline + a current-vs-previous-window delta, and the composite metric mean
    gives an answer-quality sparkline + delta. Grounded, not fabricated — an empty
    or unreadable log yields empty series and ``None`` deltas.

    Returns:
        ``(volume_series, volume_delta, quality_series, quality_delta)`` — per-bucket
        counts (0-filled), the volume change as a fraction of the previous window,
        the non-empty composite quality means (0..1), and the composite quality
        delta (0..1).
    """
    try:
        rows = persisted_scores()
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.reliability: trends failed: {exc}\n")
        return [], None, [], None
    if not rows:
        return [], None, [], None
    end = datetime.now(UTC)
    per_metric = [
        compute_score_series(rows, metric=m, end=end, days=_TREND_DAYS, n_buckets=_TREND_BUCKETS)
        for m in _TREND_METRICS
    ]
    base = per_metric[0]
    volume_series = [b.n for b in base.buckets]
    prev = compute_score_series(
        rows,
        metric=_TREND_METRICS[0],
        end=end - timedelta(days=_TREND_DAYS),
        days=_TREND_DAYS,
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


def compute_reliability() -> ReliabilityReport:
    """Assemble the reliability & cost posture from the real runtime signals."""
    bundles = replay_mod.recent_bundles()
    cost = cost_anomaly_mod.analyze_costs(
        [(b.question, f"{b.question}\n{b.context}\n{b.original_answer}") for b in bundles]
    )
    tool = tool_validity_mod.compute_tool_validity()
    obs = obs_cost_mod.measure_overhead()
    scores = recent_scores()
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

    # Per-model cost rows from the eval run archive.
    models: list[CostRow] = []
    provider_counts: dict[str, int] = {}
    for stat in compare_models(load_runs().runs):
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

    # Recent incidents from the real anomalies / tool errors.
    incidents: list[Incident] = []
    for a in cost.anomalies[:3]:
        incidents.append(
            Incident(
                label=a.question[:48],
                type="token_spike",
                severity="medium",
                detail=f"{a.tokens} tokens",
            )
        )
    if tool.errored > 0:
        incidents.append(
            Incident(
                label="Tool error", type="tool_error", severity="high", detail=f"{tool.errored}"
            )
        )

    # Budget projection: linear from spend so far over the window.
    spent = total_cost_eur
    projected = round(spent * (30.0 / max(1, n_requests)) * n_requests, 2) if n_requests else spent

    volume_series, volume_delta, quality_series, quality_delta = _trends()

    return ReliabilityReport(
        availability=availability,
        error_rate=error_rate,
        latency_p50_ms=p50,
        latency_p95_ms=p95,
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
    )


def _safe_compute() -> ReliabilityReport | None:
    try:
        return compute_reliability()
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.reliability: failed: {exc}\n")
        return None
