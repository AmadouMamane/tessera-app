"""The sweep's one HTTP address — and the mirrors it must not let drift.

Two arithmetics are mirrored rather than shared (TypeScript cannot import the runner, and
``src/`` must not import the untyped ``eval/`` package): the catalogue-version hash and the
alias rule. A mirror that nothing pins is two answers waiting to disagree, so the tests here
pin both to the COMMITTED artefacts — the version the real reports carry, the aliases the real
sweep directory holds — not to fixtures that would drift with the code they test.
"""

from __future__ import annotations

import json

from tessera.observability.eval_sweep import (
    FAILURES_DIR,
    SWEEP_DIR,
    assemble_sweep,
    catalogue_version_of,
    compute_eval_sweep,
    load_case_result,
)


def _report(
    run_at: str,
    *,
    model: str = "llama3.2:3b",
    catalogue_version: str = "2-aaaaaaaa",
    regraded_at: str | None = "20260805T140107Z",
) -> dict[str, object]:
    doc: dict[str, object] = {
        "run_at": run_at,
        "model": model,
        "catalogue_version": catalogue_version,
        "summary": {"total": 2, "passed": 1, "failed": 1, "pass_rate": 0.5},
        "cost": {"input_tokens": 10, "output_tokens": 7, "estimated_cost_eur": 0.0},
        "results": [
            {"case_id": "01_a", "language": "fr", "passed": True, "duration_ms": 120.0},
            {"case_id": "01_a", "language": "de", "passed": False, "duration_ms": 80.0},
        ],
        "grader_criteria_sha_partial": "2-bbbbbbbb",
        "grader_criteria_unstampable": ["01_a|de"],
    }
    if regraded_at is not None:
        doc["regraded_at"] = regraded_at
    return doc


class TestVersionMirror:
    """The hash here IS the runner's — pinned to the committed artefacts."""

    def test_the_mirror_reproduces_the_stamp_the_real_reports_carry(self) -> None:
        ids = [p.stem for p in FAILURES_DIR.glob("*.json") if not p.name.startswith("_")]
        computed = catalogue_version_of(ids)

        newest = max(SWEEP_DIR.glob("2*.json"))
        stamped = json.loads(newest.read_text(encoding="utf-8"))["catalogue_version"]
        assert computed == stamped, (
            "the version mirror and the runner disagree — the screen would call every "
            "committed run off-referential"
        )

    def test_the_floor_is_stamped_with_the_same_referential(self) -> None:
        from tessera.observability.eval_floor import NULL_BASELINE

        floor = json.loads(NULL_BASELINE.read_text(encoding="utf-8"))
        ids = [p.stem for p in FAILURES_DIR.glob("*.json") if not p.name.startswith("_")]
        assert floor["catalogue_version"] == catalogue_version_of(ids)


class TestAliasRule:
    def test_three_spellings_of_one_run_are_one_run_named_for_its_model(self) -> None:
        doc = _report("20260712T131902Z")
        payload = assemble_sweep(
            reports=[
                ("20260712T131902Z", doc),
                ("latest", doc),
                ("llama3.2-3b", doc),
            ],
            floor_raw=None,
            power_raw=None,
            power_error=None,
            cases=[],
            schema_raw=None,
        )
        runs = payload["runs"]
        assert isinstance(runs, list)
        assert len(runs) == 1
        assert runs[0]["id"] == "llama3.2-3b"

    def test_runs_scored_on_another_catalogue_are_held_apart_never_merged(self) -> None:
        newest = _report("20260801T000000Z", catalogue_version="2-aaaaaaaa")
        elder = _report("20260701T000000Z", catalogue_version="2-ffffffff")
        payload = assemble_sweep(
            reports=[("a", newest), ("b", elder)],
            floor_raw=None,
            power_raw=None,
            power_error=None,
            cases=[],
            schema_raw=None,
        )
        assert payload["catalogue_version"] == "2-aaaaaaaa"
        runs = payload["runs"]
        off = payload["off_referential"]
        assert isinstance(runs, list) and isinstance(off, list)
        assert [r["id"] for r in runs] == ["a"]
        assert [r["id"] for r in off] == ["b"]


class TestProvenanceTravels:
    """The exact fields the front's zod used to strip — the payload's reason to exist."""

    def test_regrade_provenance_survives_into_the_payload(self) -> None:
        payload = assemble_sweep(
            reports=[("run", _report("20260712T131902Z"))],
            floor_raw=None,
            power_raw=None,
            power_error=None,
            cases=[],
            schema_raw=None,
        )
        runs = payload["runs"]
        assert isinstance(runs, list)
        run = runs[0]
        assert run["regraded_at"] == "20260805T140107Z"
        assert run["grader_criteria_sha_partial"] == "2-bbbbbbbb"
        assert run["grader_blind_runs"] == ["01_a|de"]

    def test_the_committed_sweep_serves_all_three_runs_with_their_regrade(self) -> None:
        payload = compute_eval_sweep()
        runs = payload["runs"]
        assert isinstance(runs, list)
        assert len(runs) == 3, "the committed sweep holds three runs behind seven files"
        assert all(r["regraded_at"] for r in runs), (
            "every committed sweep report carries regraded_at — a payload without it "
            "would be the zod strip rebuilt server-side"
        )
        floor = payload["floor"]
        assert isinstance(floor, dict)
        raw = json.loads(
            (FAILURES_DIR.parent / "baselines" / "null-control.json").read_text(encoding="utf-8")
        )
        assert floor["totals"] == raw["totals"], "the floor travels as committed, never restated"
        assert floor["grader_criteria_sha"] == raw["grader_criteria_sha"]


class TestCaseResult:
    def test_an_id_is_resolved_against_the_directory_never_joined_onto_a_path(self) -> None:
        assert load_case_result("../../../etc/passwd", "01_a", "fr") is None
        assert load_case_result("nonexistent-run", "01_a", "fr") is None

    def test_one_real_verdict_comes_back_with_its_evidence(self) -> None:
        found = load_case_result("llama3.3-70b", "01_prompt_injection", "fr")
        assert found is not None
        result = found["result"]
        run = found["run"]
        assert isinstance(result, dict) and isinstance(run, dict)
        assert isinstance(result.get("final_response"), str)
        assert result.get("passed") in (True, False)
        assert "verdicts" not in run, "the caller already holds the 174 booleans"


class TestReleaseControlCarriesTheDecision:
    """`/release-control` used to DROP the lifecycle decision — blocked_by, the levels.

    The fleet column then said PRÊT while the only fields able to contradict it never
    crossed the wire (they existed one endpoint away, one agent at a time). The row now
    carries the decision whole.
    """

    def test_every_row_carries_the_decision_with_its_blocking_fields(self) -> None:
        from tessera.observability.release_control import compute_release_control

        payload = compute_release_control()
        agents = payload["agents"]
        assert isinstance(agents, list) and agents
        for row in agents:
            assert isinstance(row, dict)
            decision = row["decision"]
            assert isinstance(decision, dict)
            for key in (
                "allowed",
                "blocked_by",
                "observability_level",
                "required_level",
                "floor_graded",
                "floor_regressions",
                "reason",
            ):
                assert key in decision, f"decision.{key} missing — the drop is back"


def test_the_route_degrades_to_unavailable_never_to_a_traceback() -> None:
    from tessera.api.routes.observability.evals import observability_eval_sweep

    payload = observability_eval_sweep()
    assert payload.get("available") is True
    assert "runs" in payload and "floor" in payload and "power" in payload


class TestRunDocument:
    def test_the_full_report_comes_back_whole_for_a_known_run(self) -> None:
        from tessera.observability.eval_sweep import load_run_document

        doc = load_run_document("llama3.3-70b")
        assert doc is not None
        results = doc["results"]
        assert isinstance(results, list) and len(results) == 174
        assert doc.get("regraded_at"), "the full document carries its regrade stamp"

    def test_an_unknown_or_traversal_id_is_refused(self) -> None:
        from tessera.observability.eval_sweep import load_run_document

        assert load_run_document("../../pyproject") is None
        assert load_run_document("no-such-run") is None
