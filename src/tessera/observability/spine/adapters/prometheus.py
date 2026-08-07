"""Prometheus read adapter — PromQL instant/range + label selectors (ADR 0015 §Migration C).

Prometheus owns every dashboard *number*: SLO, rate, quantile, cost-aggregate, counts. It is a
pre-aggregated TSDB built for range + label queries, so the cockpit hot path reads aggregates
here (via the Phase-B recording rules) rather than summing raw traces. The label selector comes
straight from :meth:`Scope.to_labels`.

Self-hosted, **no auth** (a localhost scrape target — ADR 0015 §Security), so no credential is
needed. An unreachable Prometheus raises :class:`SpineUnavailableError`, so a signal degrades to
an honest-empty state rather than a fabricated zero.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import TYPE_CHECKING

from tessera.observability.spine.adapters.base import SpineUnavailableError
from tessera.observability.stack_components import base_url_for
from tessera.observability.store_spans import store_read
from tessera.urlfetch import urlopen_http

if TYPE_CHECKING:
    from tessera.observability.spine.scope import Scope

__all__ = ["PrometheusAdapter"]


class PrometheusAdapter:
    """Query client for the self-hosted Prometheus (ADR 0015 §Migration C)."""

    def __init__(self, base_url: str | None = None, *, timeout_s: float = 0.8) -> None:
        self._base_url = (
            base_url or base_url_for("prometheus", env="TESSERA_PROMETHEUS_URL")
        ).rstrip("/")
        self._timeout_s = timeout_s

    @property
    def base_url(self) -> str:
        """The Prometheus base URL this adapter queries."""
        return self._base_url

    def selector(self, scope: Scope) -> str:
        """Render ``scope`` as a PromQL label selector, e.g. ``{agent_id="support"}``.

        Only set dimensions are emitted; the empty scope renders ``""`` (match-all). The
        temporal ``at`` is a time bound (applied by :meth:`range`), not a label.
        """
        labels = scope.to_labels()
        if not labels:
            return ""
        inner = ",".join(f'{key}="{_escape(value)}"' for key, value in sorted(labels.items()))
        return "{" + inner + "}"

    def instant(self, query: str, *, at: str | None = None) -> list[dict[str, object]]:
        """Evaluate an instant PromQL query, optionally as of instant ``at`` (RFC3339).

        Returns the raw ``result`` list (each ``{metric: {...labels}, value: [ts, "v"]}``).
        """
        params = {"query": query}
        if at:
            params["time"] = at
        with store_read("prometheus", "prometheus.instant", target=self._base_url) as read:
            payload = self._get("/api/v1/query", params)
            rows = _result(payload)
            read.rows_read(len(rows))
        return rows

    def range(self, query: str, *, start: str, end: str, step: str) -> list[dict[str, object]]:
        """Evaluate a range PromQL query with an adaptive ``step`` (bounded point count)."""
        payload = self._get(
            "/api/v1/query_range",
            {"query": query, "start": start, "end": end, "step": step},
        )
        return _result(payload)

    def _get(self, path: str, params: dict[str, str]) -> dict[str, object]:
        url = f"{self._base_url}{path}?{urllib.parse.urlencode(params)}"
        request = urllib.request.Request(url)  # noqa: S310 — self-hosted localhost scrape target
        try:
            with urlopen_http(request, timeout=self._timeout_s) as response:
                payload = json.load(response)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            msg = f"prometheus unreachable at {self._base_url}: {exc}"
            raise SpineUnavailableError(msg) from exc
        if not isinstance(payload, dict) or payload.get("status") != "success":
            msg = f"prometheus query failed: {query_status(payload)}"
            raise SpineUnavailableError(msg)
        return payload


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _result(payload: dict[str, object]) -> list[dict[str, object]]:
    data = payload.get("data")
    if not isinstance(data, dict):
        return []
    result = data.get("result")
    return [row for row in result if isinstance(row, dict)] if isinstance(result, list) else []


def query_status(payload: object) -> str:
    if isinstance(payload, dict):
        return str(payload.get("error") or payload.get("status") or "unknown")
    return "unparseable response"
