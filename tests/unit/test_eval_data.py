"""Unit tests for the real eval-data loader and the Evaluations payload.

These lock in that the Evaluations dashboard is sourced from an actual
``llama3.2:3b`` failure-catalogue run (no fabricated fixtures) and that the
derived KPIs / table stay internally consistent with the snapshot.
"""

from __future__ import annotations

from tessera.agent.identity import DEFAULT_AGENT_ID
from tessera.observability.agent_evaluations import compute_agent_evaluations
from tessera.observability.eval_data import (
    SMALLEST_MODEL,
    load_agent_or_global_snapshot,
    load_eval_snapshot,
)


def test_snapshot_comes_from_smallest_model() -> None:
    snap = load_eval_snapshot()
    assert snap.model == SMALLEST_MODEL
    assert snap.total > 0
    assert 0 <= snap.passed <= snap.total
    assert snap.categories, "expected at least one scored category"
    assert all(0 <= c.passed <= c.total for c in snap.categories)
    # categories_by_pass_rate is worst-first.
    rates = [c.pass_rate for c in snap.categories_by_pass_rate()]
    assert rates == sorted(rates)


def test_evaluations_payload_is_consistent_with_the_run() -> None:
    # The payload reads the agent's OWN run (agent-or-global), not the global
    # catalogue snapshot — assert against the same source it actually uses.
    snap = load_agent_or_global_snapshot(DEFAULT_AGENT_ID)
    payload = compute_agent_evaluations()

    # One eval-set row per scored category; the total agrees.
    rows = payload["table"]["rows"]  # type: ignore[index]
    assert len(rows) == len(snap.categories)
    assert payload["table"]["total"] == len(rows)  # type: ignore[index]

    # The success gauge equals the real overall pass rate.
    success = next(k for k in payload["kpis"] if k["key"] == "success")  # type: ignore[index]
    assert success["gauge"] == round(snap.pass_rate * 100)

    # The snapshot bar reports the real model and case count.
    assert payload["snapshot"]["version"] == snap.model  # type: ignore[index]
    assert payload["snapshot"]["evalset"] == f"{snap.total} cas"  # type: ignore[index]
