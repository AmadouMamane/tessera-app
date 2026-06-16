"""Unit tests for the Evaluations dashboard payload."""

from __future__ import annotations

from tessera.observability.agent_evaluations import compute_agent_evaluations


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
