"""The bundled eval snapshot is a COPY, and a copy that drifts is a second original.

`webapp/frontend/data/eval/` is the only eval source inside the standalone image — there is no
`pyproject.toml` above `/app`, so `eval-sweep.ts::sources` never finds the repo. It was tracked
and hand-maintained alongside `eval/reports/` + `eval/baselines/` + `eval/failures/`, and by
2026-08-05 the two had drifted in four separate ways at once (see `scripts/build_eval_bundle.py`
for the measurements). The worst was not the biggest: the shipped sweep named FEWER blind runs
than the repo's, so the served surface claimed more coverage than had been measured.

The lesson is the one this repository keeps relearning: *a directory has no identity — every copy
must be interrogated.* Two `.eval-noise/` directories cost a false alarm; two registry files
nearly cost 98 insights. Here the fix is to stop having two originals: the bundle is derived, and
this module fails the moment what is committed stops being what the builder would write.
"""

from __future__ import annotations

import json

from scripts.build_eval_bundle import BUNDLE, catalogue, planned


def test_every_bundled_file_is_what_the_builder_would_write() -> None:
    """The claim in one line: `make eval-bundle` is a no-op on a clean tree."""
    stale = []
    for rel, content in planned().items():
        target = BUNDLE / rel
        if not target.exists():
            stale.append(f"{rel}: MISSING from the bundle")
        elif target.read_text(encoding="utf-8") != content:
            stale.append(f"{rel}: differs from the repo source")
    assert not stale, (
        "the bundled eval snapshot has drifted from the repo — this is what production serves:\n  "
        + "\n  ".join(stale)
        + "\nRun `make eval-bundle` and commit the result."
    )


def test_the_bundle_holds_nothing_the_repo_does_not() -> None:
    """The other direction: a run kept only in the bundle is a run the gate has never seen."""
    wanted = set(planned())
    orphans = [
        path.relative_to(BUNDLE).as_posix()
        for path in sorted(BUNDLE.rglob("*.json"))
        if path.relative_to(BUNDLE).as_posix() not in wanted
    ]
    assert not orphans, f"bundled files with no repo source: {orphans}"


def test_the_comparison_is_not_vacuous() -> None:
    """Positive control. An empty plan would make both assertions above pass on an empty bundle.

    Written because that is exactly how this class of check goes green over a hole: the builder
    silently finds no sources (a moved directory, a renamed glob) and reports a clean sweep.
    """
    plan = planned()
    assert len(plan) >= 5, f"the builder found almost nothing to bundle: {sorted(plan)}"
    assert any(rel.startswith("sweep/") for rel in plan), "no sweep report in the plan"
    assert "catalogue.json" in plan
    assert "null-control.json" in plan
    assert "discrimination.json" in plan, (
        "the power baseline must be bundled: its ABSENCE reads as 'not measured yet' on the "
        "served surface, which is a different claim from the one the artefact makes"
    )


def test_the_catalogue_carries_the_criteria_the_grader_applies() -> None:
    """The drift that mattered most, pinned at its own grain.

    36 of 63 cases shipped `pass_criteria` the grader no longer applied — including every case
    corrected the previous night. A screen showing a criterion nobody scored against is the
    over-claim this project treats as non-negotiable, and it is worth its own assertion rather
    than being folded into a byte comparison that says only "something differs".
    """
    bundled = json.loads((BUNDLE / "catalogue.json").read_text(encoding="utf-8"))
    live = {case["id"]: case for case in catalogue()}
    assert {case["id"] for case in bundled} == set(live)
    drifted = [
        case["id"]
        for case in bundled
        if case.get("pass_criteria") != live[case["id"]].get("pass_criteria")
    ]
    assert not drifted, f"cases whose shipped criteria are not the graded ones: {drifted}"
