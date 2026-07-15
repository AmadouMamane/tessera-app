"""Unit tests for the Evaluations dashboard payload."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tessera.observability.agent_evaluations import compute_agent_evaluations
from tessera.observability.eval_data import RunHistoryEntry

if TYPE_CHECKING:
    import pytest


def test_rows_carry_stable_keys_for_filtering_and_detail() -> None:
    payload = compute_agent_evaluations()
    table = payload["table"]
    rows = table["rows"]  # type: ignore[index]
    assert table["total"] == len(rows)  # type: ignore[index]
    assert rows, "the real eval run should yield at least one category row"
    for key in ("category_key", "quality_key", "is_fact", "score_num", "passed", "total", "type"):
        assert key in rows[0]


def test_filter_options_partition_the_rows() -> None:
    opts = compute_agent_evaluations()["filters"]["options"]  # type: ignore[index]
    # Types come from the real catalogue categories (more than one bites).
    assert len(opts["type"]) >= 2
    assert {o["key"] for o in opts["quality"]} == {"good", "warn", "bad"}
    assert {o["key"] for o in opts["halluc"]} == {"with", "without"}


def test_labels_are_accented() -> None:
    payload = compute_agent_evaluations()
    assert payload["title"] == "Évaluations"
    kpis = {k["key"]: k for k in payload["kpis"]}  # type: ignore[union-attr]
    assert kpis["success"]["label"] == "Taux de réussite"
    assert kpis["fidelity"]["label"] == "Fidélité (sources)"
    assert payload["detail_labels"]["tabs"][0] == "Résumé"  # type: ignore[index]


def test_meta_is_present_for_the_frontend_detail() -> None:
    meta = compute_agent_evaluations()["meta"]
    assert meta["model"]  # type: ignore[index]
    assert isinstance(meta["rbac"], list)  # type: ignore[index]
    assert meta["rbac"]  # type: ignore[index]


def test_quick_actions_are_keyed() -> None:
    quick = compute_agent_evaluations()["quick"]
    keys = {i["key"] for i in quick["items"]}  # type: ignore[index]
    assert {"run", "compare", "results", "sets"} <= keys


# ── ER-01 run rail ───────────────────────────────────────────────────────────


def _entry(
    run_at: str,
    passed: int,
    total: int,
    catalogue_version: str,
    gate_passed: bool | None = True,
) -> RunHistoryEntry:
    return RunHistoryEntry(
        run_at=run_at,
        total=total,
        passed=passed,
        gate_passed=gate_passed,
        eval_set="support-client",
        catalogue_version=catalogue_version,
        model="llama3.2:3b",
    )


def test_runs_rail_items_carry_their_own_provenance() -> None:
    """Eval-gate policy § provenance: every run shows its date + catalogue version."""
    runs = compute_agent_evaluations("support-client")["runs"]
    items = runs["items"]  # type: ignore[index]
    assert runs["count"] == len(items) > 0  # type: ignore[index]
    for item in items:
        assert item["run_at"]
        assert item["date_label"]
        assert item["catalogue_version"], "a run without its catalogue version masks staggering"
        assert item["model"]
        assert isinstance(item["passed"], int)
        assert isinstance(item["total"], int)
    # Newest first — the journal is ordered, not a bag.
    stamps = [item["run_at"] for item in items]
    assert stamps == sorted(stamps, reverse=True)


def test_runs_rail_delta_only_against_a_same_catalogue_previous_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Δ compares two runs of the same exam; a catalogue change breaks comparability."""
    history = (
        _entry("20260704T083507Z", 114, 119, "v2"),
        _entry("20260703T225158Z", 111, 119, "v2"),
        _entry("20260618T083906Z", 59, 119, "v1"),
    )
    monkeypatch.setattr(
        "tessera.observability.agent_evaluations.load_agent_run_history",
        lambda _agent_id: history,
    )
    items = compute_agent_evaluations("support-client")["runs"]["items"]  # type: ignore[index]
    assert items[0]["delta_pass_rate"] == round(114 / 119 - 111 / 119, 4)
    assert items[1]["delta_pass_rate"] is None, "previous run is another catalogue version"
    assert items[2]["delta_pass_rate"] is None, "the oldest run has nothing to compare to"


def test_runs_rail_gate_verdict_is_the_recorded_one_never_invented(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    history = (_entry("20260704T083507Z", 114, 119, "v2", gate_passed=None),)
    monkeypatch.setattr(
        "tessera.observability.agent_evaluations.load_agent_run_history",
        lambda _agent_id: history,
    )
    items = compute_agent_evaluations("support-client")["runs"]["items"]  # type: ignore[index]
    assert items[0]["gate_passed"] is None
    # A single run also gets no Δ: one point is not a trend.
    assert items[0]["delta_pass_rate"] is None


def test_runs_rail_is_honest_empty_for_an_agent_without_runs() -> None:
    runs = compute_agent_evaluations("hello-agent")["runs"]
    assert runs["count"] == 0  # type: ignore[index]
    assert runs["items"] == []  # type: ignore[index]
    assert "Éval non exécutée" in str(runs["empty_label"])  # type: ignore[index]
