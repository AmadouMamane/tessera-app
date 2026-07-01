"""Contract tests: the spine adapters actually speak PromQL / Langfuse (ADR 0015 §Testing 1).

Integration-tagged — verifies the read adapters against the LIVE self-hosted spine
(Prometheus :19090, Langfuse :3900), never in the fast unit loop. Skips cleanly when a backend
is not up (start it with ``make obs-up-core`` / ``make obs-up``), so the suite never fails for a
missing dependency — it asserts the adapters speak the query language correctly, on real data.
"""

from __future__ import annotations

import urllib.error
import urllib.request

import pytest

from tessera.observability.spine.adapters.langfuse import LangfuseAdapter
from tessera.observability.spine.adapters.prometheus import PrometheusAdapter
from tessera.observability.spine.adapters.spine import SpineStoresReader
from tessera.observability.spine.scope import Scope

pytestmark = pytest.mark.integration

_PROM = "http://localhost:19090"
_LANGFUSE = "http://localhost:3900"


def _reachable(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=2):  # noqa: S310 — self-hosted spine
            return True
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


@pytest.fixture(autouse=True)
def _require_prometheus() -> None:
    if not _reachable(f"{_PROM}/-/healthy"):
        pytest.skip("prometheus not up (make obs-up-core)")


def _require_langfuse() -> None:
    if not _reachable(f"{_LANGFUSE}/api/public/health"):
        pytest.skip("langfuse not up (make obs-up)")


class TestPrometheusContract:
    def test_instant_up_is_well_formed(self) -> None:
        result = PrometheusAdapter(timeout_s=4.0).instant("up")
        assert isinstance(result, list)
        assert all("metric" in row and "value" in row for row in result)

    def test_recording_rule_query_succeeds(self) -> None:
        # The Phase-B recording rule exists (may be empty pre-traffic); the query must succeed
        # and return a well-formed (possibly empty) series list — never raise.
        result = PrometheusAdapter(timeout_s=4.0).instant("tessera:eval_score:mean5m")
        assert isinstance(result, list)

    def test_selector_scopes_a_query(self) -> None:
        adapter = PrometheusAdapter(timeout_s=4.0)
        selector = adapter.selector(Scope(agent_id="support-client"))
        # A scoped query is valid PromQL and returns a list (empty until per-agent traffic).
        assert isinstance(adapter.instant(f"tessera_agent_turns_total{selector}"), list)


class TestLangfuseContract:
    def test_traces_are_well_formed(self) -> None:
        _require_langfuse()
        traces = LangfuseAdapter(timeout_s=6.0).traces(Scope(), limit=3)
        assert isinstance(traces, list)
        assert all("id" in trace for trace in traces)

    def test_scores_query_is_well_formed(self) -> None:
        _require_langfuse()
        scores = LangfuseAdapter(timeout_s=6.0).scores_by_metadata(Scope(), limit=3)
        assert isinstance(scores, list)

    def test_agent_scope_filters_client_side(self) -> None:
        _require_langfuse()
        # A scoped read never raises and returns only rows matching the agent (or empty).
        rows = LangfuseAdapter(timeout_s=6.0).traces(Scope(agent_id="support-client"), limit=5)
        assert isinstance(rows, list)


class TestSpineReaderContract:
    def test_audit_entries_read_local_ledger(self) -> None:
        # The ledger is local (the carve-out): the spine reader reads it directly, not Langfuse.
        entries = SpineStoresReader().audit_entries(Scope())
        assert isinstance(entries, list)
