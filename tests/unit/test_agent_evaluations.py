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


# ── Jeux d'évaluations (sets) ────────────────────────────────────────────────


def test_sets_block_lists_every_curated_set_with_stable_fields() -> None:
    sets = compute_agent_evaluations("recouvrement")["sets"]
    rows = sets["rows"]  # type: ignore[index]
    assert sets["total"] == len(rows)  # type: ignore[index]
    slugs = {r["slug"] for r in rows}
    # The five in-repo manifests under eval/sets/.
    assert {"catalogue-echecs", "onboarding", "recouvrement", "socle-securite"} <= slugs
    for r in rows:
        for key in ("slug", "name", "bound", "active", "case_count", "critical_count", "case_ids"):
            assert key in r
        assert r["case_count"] == len(r["case_ids"])
        assert r["critical_count"] <= r["case_count"]


def test_sets_block_marks_the_run_bound_set_active() -> None:
    rows = compute_agent_evaluations("recouvrement")["sets"]["rows"]  # type: ignore[index]
    active = [r for r in rows if r["active"]]
    assert active, "the agent's own bound set should be flagged active"
    assert active[0]["slug"] == "recouvrement"
    assert active[0]["bound"] is True


def test_sets_case_catalogue_carries_localized_labels() -> None:
    cases = compute_agent_evaluations("recouvrement", "en")["sets"]["cases"]  # type: ignore[index]
    assert cases, "the failure catalogue should not be empty"
    by_id = {c["id"]: c for c in cases}
    inj = by_id["01_prompt_injection"]
    assert inj["severity"] == "critical"
    assert inj["severity_label"] == "Critical"  # localized chrome
    assert inj["category_label"] == "Security"  # _group_label(en)


# ── Résultats / Erreurs (per-case results) ───────────────────────────────────


def test_results_block_is_one_row_per_session_with_stable_keys() -> None:
    results = compute_agent_evaluations("recouvrement")["results"]
    rows = results["rows"]  # type: ignore[index]
    assert results["total"] == len(rows)  # type: ignore[index]
    assert results["passed"] + results["failed"] == results["total"]  # type: ignore[index]
    for key in ("case_id", "language", "passed", "status_tone", "reasons", "question", "response"):
        assert key in rows[0]


def test_results_failed_rows_carry_the_judge_diagnostic() -> None:
    rows = compute_agent_evaluations("recouvrement")["results"]["rows"]  # type: ignore[index]
    failed = [r for r in rows if not r["passed"]]
    # This agent's real run has failures; each must explain itself (reasons kept).
    assert failed, "the small model's run should have at least one failure"
    assert any(r["reasons"] for r in failed), "a failed case must carry its diagnostic"
    assert all(r["status_tone"] == "bad" for r in failed)


def test_results_labels_are_accented() -> None:
    labels = compute_agent_evaluations("recouvrement")["results"]["labels"]  # type: ignore[index]
    assert labels["question"] == "Requête de test"
    assert labels["response"] == "Réponse du modèle"
