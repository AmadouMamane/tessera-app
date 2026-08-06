"""Langfuse-backed trace observability for the SURVEILLER overview.

Tessera instruments every span with OpenTelemetry and fans it out to the running
observability stack (the OTel Collector → **Langfuse** trace platform, Phoenix for
retrieval, Prometheus/Grafana for metrics). "Best tool for the job": Langfuse is the
trace warehouse, so we read the REAL trace volume + latency back through its public
API rather than re-deriving it — and deep-link the operator to each tool for the job
it is best at (Langfuse = trace explorer, Grafana = dashboards, Phoenix = retrieval).

As-of-T is honoured via Langfuse's ``toTimestamp`` (only traces at or before T), so
this panel projects like every other block under the rail. Degrades to
``available: false`` if the stack is down — never a fabricated number.

Config is read from the environment (the local stack's demo keys are the documented
fallback, matching ``docker-compose.obs.claude.yml``): ``LANGFUSE_HOST``,
``LANGFUSE_PUBLIC_KEY``, ``LANGFUSE_SECRET_KEY``, ``LANGFUSE_PROJECT_ID``,
``GRAFANA_URL``, ``PHOENIX_URL``.
"""

from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import asdict, dataclass
from threading import Lock
from typing import Final

from tessera.preflight import Verdict
from tessera.urlfetch import urlopen_http

__all__ = [
    "LangfuseReadHealth",
    "TracesObservability",
    "compute_traces_observability",
    "langfuse_read_health",
]

_HOST = os.environ.get("LANGFUSE_HOST", "http://localhost:3900")
_PUBLIC = os.environ.get("LANGFUSE_PUBLIC_KEY", "pk-lf-claude-public")
_SECRET = os.environ.get("LANGFUSE_SECRET_KEY", "sk-lf-claude-secret")
_PROJECT = os.environ.get("LANGFUSE_PROJECT_ID", "claude-project")
_GRAFANA = os.environ.get("GRAFANA_URL", "http://localhost:13000")
_PHOENIX = os.environ.get("PHOENIX_URL", "http://localhost:16006")


@dataclass(frozen=True)
class TracesObservability:
    """Real trace observability read from Langfuse (or an honest empty state)."""

    available: bool
    total: int
    latency_p50_s: float | None
    latency_p95_s: float | None
    top_ops: list[dict[str, object]]
    recent: list[dict[str, object]]
    langfuse_url: str
    grafana_url: str
    phoenix_url: str
    as_of: str | None


def _traces_url() -> str:
    return f"{_HOST}/project/{_PROJECT}/traces"


def _empty(at: str | None) -> TracesObservability:
    return TracesObservability(
        available=False,
        total=0,
        latency_p50_s=None,
        latency_p95_s=None,
        top_ops=[],
        recent=[],
        langfuse_url=_traces_url(),
        grafana_url=_GRAFANA,
        phoenix_url=_PHOENIX,
        as_of=at,
    )


def _get_json(url: str, timeout: float) -> dict[str, object]:
    token = base64.b64encode(f"{_PUBLIC}:{_SECRET}".encode()).decode()
    request = urllib.request.Request(url, headers={"Authorization": f"Basic {token}"})  # noqa: S310
    with urlopen_http(request, timeout=timeout) as response:
        payload = json.load(response)
    return payload if isinstance(payload, dict) else {}


@dataclass(frozen=True)
class LangfuseReadHealth:
    """Whether this module's own authenticated read path works, spoken as a probe verdict."""

    verdict: Verdict
    detail: str


#: Same TTL as the stack probe, for the same reason: the dashboard polls, and one authenticated
#: round-trip per 15 s answers it as well as one per request.
_READ_TTL_S: Final = 15.0
_read_cache: tuple[float, LangfuseReadHealth] | None = None
_read_cache_lock = Lock()


def _read_health_uncached() -> LangfuseReadHealth:
    """One authenticated read against the same API this module's numbers come from."""
    url = f"{_HOST}/api/public/traces?limit=1"
    try:
        _get_json(url, timeout=3.0)
    except urllib.error.HTTPError as exc:
        # The service answered and refused (401/403) or failed (5xx): the read path is BROKEN,
        # which is a different repair from a dead container — fix keys, not restarts.
        return LangfuseReadHealth(Verdict.FAIL, f"HTTP {exc.code} on {url}")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return LangfuseReadHealth(Verdict.BLIND, str(exc))
    except (json.JSONDecodeError, ValueError) as exc:
        return LangfuseReadHealth(Verdict.FAIL, f"unparseable answer: {exc}")
    return LangfuseReadHealth(Verdict.OK, "authenticated read answered")


def langfuse_read_health() -> LangfuseReadHealth:
    """Can *this module* actually read Langfuse — not "is the port open".

    On 2026-08-06 the observability page said ``langfuse-web OK`` (its health endpoint answered
    200) and the overview said *"Stack d'observabilite injoignable"* — because THIS module's
    authenticated read was failing while the socket was fine. Two surfaces contradicted each
    other about one system; the witness was interrogating the neighbourhood (ADR 0026). This
    probe asks the thing itself: one ``limit=1`` read through the same URL, credentials and
    parser the real numbers use.
    """
    global _read_cache
    with _read_cache_lock:
        cached = _read_cache
        if cached is not None and (time.time() - cached[0]) < _READ_TTL_S:
            return cached[1]
    # Outside the lock — the probe can take its full 3 s timeout, and a queue of dashboard
    # readers serialised behind one round-trip is the failure the cache exists to prevent.
    health = _read_health_uncached()
    with _read_cache_lock:
        _read_cache = (time.time(), health)
    return health


def _percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(len(ordered) * q))
    return round(ordered[index], 3)


def compute_traces_observability(
    at: str | None = None, sample: int = 100, recent: int = 6, timeout: float = 4.0
) -> TracesObservability:
    """Read real trace volume + latency from Langfuse, as of instant ``at`` if given.

    Args:
        at: Optional ISO instant T; only traces at or before T are counted (Langfuse
            ``toTimestamp``), so the panel projects as-of-T like the rest of the page.
        sample: Number of recent traces to pull for the latency/top-ops aggregates.
        recent: Number of traces surfaced in the "recent" list.
        timeout: HTTP timeout (seconds) before degrading to the empty state.

    Returns:
        A :class:`TracesObservability` — real figures when Langfuse answers, or an
        honest empty state (``available: false``) when the stack is unreachable.
    """
    url = f"{_HOST}/api/public/traces?limit={max(1, sample)}&orderBy=timestamp.desc"
    if at:
        url += f"&toTimestamp={urllib.parse.quote(at)}"
    try:
        payload = _get_json(url, timeout)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return _empty(at)

    raw = payload.get("data")
    data: list[dict[str, object]] = (
        [row for row in raw if isinstance(row, dict)] if isinstance(raw, list) else []
    )
    meta = payload.get("meta")
    total = 0
    if isinstance(meta, dict):
        total_items = meta.get("totalItems")
        total = int(total_items) if isinstance(total_items, int | float) else 0

    latencies: list[float] = []
    for trace in data:
        latency = trace.get("latency")
        if isinstance(latency, int | float):
            latencies.append(float(latency))
    ops = Counter(str(t.get("name") or "?").split("?")[0] for t in data)
    top_ops: list[dict[str, object]] = [
        {"name": name, "count": count} for name, count in ops.most_common(5)
    ]
    recent_rows: list[dict[str, object]] = [
        {
            "id": str(t.get("id", "")),
            "name": str(t.get("name") or "?").split("?")[0],
            "timestamp": str(t.get("timestamp", "")),
            "latency_s": t.get("latency") if isinstance(t.get("latency"), int | float) else None,
            "url": f"{_HOST}/project/{_PROJECT}/traces/{t.get('id', '')}",
        }
        for t in data[: max(1, recent)]
    ]
    return TracesObservability(
        available=True,
        total=total,
        latency_p50_s=_percentile(latencies, 0.5),
        latency_p95_s=_percentile(latencies, 0.95),
        top_ops=top_ops,
        recent=recent_rows,
        langfuse_url=_traces_url(),
        grafana_url=_GRAFANA,
        phoenix_url=_PHOENIX,
        as_of=at,
    )


def as_payload(at: str | None = None) -> dict[str, object]:
    """Convenience: the observability payload as a plain dict for the API route."""
    return asdict(compute_traces_observability(at))
