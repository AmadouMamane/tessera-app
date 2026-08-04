"""A re-graded run is ONE run with ONE ruler — and its own totals must follow it.

The operator's report was that eval runs "do not always come up on the UI, notably today's".
Interrogating the archive rather than the screens found three mechanisms, all in the same
family: *a number displayed without the act that produced it*.

1. **One run, two rows.** ``latest_<agent>.json`` and its timestamped archive hold the same
   sampling event. The registry counted files, so it published each recent run twice, and the
   2026-08-04 re-grade wrote **only the pointer** — so the two rows carried two different
   ``grader_criteria_sha`` and, for ``recouvrement``, two different verdicts on
   ``56_policy_violation_disparage_bank|de``. Which one a consumer read came down to
   ``Path.glob`` enumeration order.
2. **A summary that did not follow its verdicts.** The re-grade rewrote ``results`` and left
   ``summary`` alone. ``latest_recouvrement.json`` shipped with ``summary.passed = 76`` over
   **77** passing rows: the flip existed in the file and reached no screen. Every KPI reads
   ``summary``.
3. **A fabricated language.** A multilingual agent run carries ``lang: null``; ``str(None)``
   turned that absence into the four-character *value* ``"None"``, which the registry then
   published in ``languages`` — offering the operator a filter for a language that does not
   exist, on the 48 runs (of 75) that were multilingual, i.e. every recent one.

The invariant these tests defend is deliberately stronger than "the registry folds well": two
files of one run must **agree**. Once they do, every downstream tie-break — and several
loaders do break ties on run_at alone — is benign no matter what order the disk hands them
back. That is why the archive is checked directly, not only through the loader.
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import TYPE_CHECKING, Any

import pytest

from eval.regrade import _rederive_totals, _with_run_twins
from tessera.observability.eval.report_paths import reports_write_dir
from tessera.observability.eval.runs import load_runs

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

# Files under eval/reports/<env>/ that are caches, not runs.
_NOT_A_RUN = ("_agent_judge.json", "_model_judge.json", "pan_input_calibration.json")


def _archive() -> Path:
    return reports_write_dir()


def _reports() -> Iterator[tuple[Path, dict[str, Any]]]:
    """Every real report in the environment archive, parsed."""
    for path in sorted(_archive().glob("*.json")):
        if path.name in _NOT_A_RUN:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(payload, dict) and isinstance(payload.get("results"), list):
            yield path, payload


def _identity(payload: dict[str, Any]) -> tuple[str, str, str] | None:
    run_at, model = payload.get("run_at"), payload.get("model")
    if not isinstance(run_at, str) or not run_at or not isinstance(model, str):
        return None
    eval_set = payload.get("eval_set") or payload.get("agent_id")
    return (run_at, model, eval_set if isinstance(eval_set, str) else "")


# --------------------------------------------------------------------------------------
# The archive itself
# --------------------------------------------------------------------------------------


def test_the_scan_actually_reads_the_archive() -> None:
    """Positive control: without it, every assertion below is vacuously green.

    Each check here is "for all reports …". A resolution bug that yielded nothing would pass
    all of them while looking at nothing — the failure mode ADR 0026 names.
    """
    reports = list(_reports())
    assert len(reports) > 40, f"only {len(reports)} reports scanned — the archive is not being read"
    assert any(p.name.startswith("latest_") for p, _ in reports), "no latest_* pointer found"
    assert sum(1 for _, o in reports if o.get("regraded_at")) > 0, "no re-graded report found"


@pytest.mark.parametrize(
    "name", ["latest_onboarding", "latest_recouvrement", "latest_support-client"]
)
def test_a_reports_summary_agrees_with_its_own_verdicts(name: str) -> None:
    """The headline number is derived from the rows, so it must equal them.

    Named per agent rather than looped so a failure says *which* report contradicts itself.
    """
    payload = json.loads((_archive() / f"{name}.json").read_text(encoding="utf-8"))
    rows = payload["results"]
    summary = payload["summary"]
    actual = sum(1 for r in rows if r.get("passed"))
    assert (
        summary["passed"] == actual
    ), f"{name}: summary says {summary['passed']} passed, its own results say {actual}"
    assert summary["total"] == len(rows)
    assert summary["failed"] == len(rows) - actual


def test_no_report_in_the_archive_contradicts_its_own_summary() -> None:
    """The same check as a class, over every report — the one that catches the next instance."""
    offenders = [
        (path.name, o["summary"].get("passed"), sum(1 for r in o["results"] if r.get("passed")))
        for path, o in _reports()
        if isinstance(o.get("summary"), dict)
    ]
    wrong = [(n, s, a) for n, s, a in offenders if s != a]
    assert offenders, "positive control: no report carried a summary at all"
    assert not wrong, f"reports whose summary disagrees with their verdicts: {wrong}"


def test_two_files_of_one_run_agree_on_ruler_and_verdicts() -> None:
    """One sampling event may not be on disk twice saying two different things.

    This is the check that would have refused the 2026-08-04 state, where the pointer had been
    re-graded and its archive had not.
    """
    groups: dict[tuple[str, str, str], list[tuple[Path, dict[str, Any]]]] = defaultdict(list)
    for path, payload in _reports():
        identity = _identity(payload)
        if identity is not None:
            groups[identity].append((path, payload))

    twinned = {k: v for k, v in groups.items() if len(v) > 1}
    assert twinned, (
        "positive control: no run is present twice, so this test proved nothing. "
        "If the pointers were removed on purpose, delete this control with them."
    )

    disputes: list[str] = []
    for identity, members in twinned.items():
        rulers = {str(o.get("grader_criteria_sha")) for _, o in members}
        verdicts = {
            tuple((r.get("case_id"), r.get("language"), r.get("passed")) for r in o["results"])
            for _, o in members
        }
        if len(rulers) > 1 or len(verdicts) > 1:
            names = ", ".join(p.name for p, _ in members)
            disputes.append(
                f"{identity}: {names} "
                f"(rulers={sorted(rulers)}, verdicts differ={len(verdicts) > 1})"
            )
    assert not disputes, "the same run is on disk under two gradings:\n  " + "\n  ".join(disputes)


# --------------------------------------------------------------------------------------
# The registry
# --------------------------------------------------------------------------------------


def _write(directory: Path, name: str, **over: Any) -> None:
    payload: dict[str, Any] = {
        "run_at": "20260803T231840Z",
        "model": "llama3.2:3b",
        "eval_set": "recouvrement",
        "lang": None,
        "catalogue_version": "43-abc",
        "summary": {"total": 2, "passed": 1, "failed": 1, "pass_rate": 0.5},
        "results": [{"case_id": "01", "passed": True}, {"case_id": "02", "passed": False}],
    }
    payload.update(over)
    (directory / name).write_text(json.dumps(payload), encoding="utf-8")


def test_the_registry_counts_runs_not_files(tmp_path: Path) -> None:
    """Pointer + archive of one run is ONE row, and the fold is reported, not swallowed."""
    _write(tmp_path, "20260803T231840Z_recouvrement.json")
    _write(tmp_path, "latest_recouvrement.json", regraded_at="20260804T192619Z")
    registry = load_runs(tmp_path)
    assert registry.n == 1
    assert registry.superseded == 1
    assert registry.runs[0].superseded_copies == 1


def test_the_newest_grading_wins_and_the_disk_never_decides(tmp_path: Path) -> None:
    """Negative control on the tie-break: the answer must not depend on enumeration order.

    ``load_runs`` reads whatever ``Path.glob`` hands it. Writing the two copies in both orders
    into two directories exercises the only thing under our control — that the *rule*, not the
    order, picks the winner.
    """
    for order in (("a_archive.json", "b_pointer.json"), ("b_pointer.json", "a_archive.json")):
        directory = tmp_path / "".join(order)
        directory.mkdir()
        for name in order:
            if "archive" in name:
                _write(directory, name, grader_criteria_sha="28-OLD")
            else:
                _write(
                    directory,
                    name,
                    grader_criteria_sha="28-NEW",
                    regraded_at="20260804T192619Z",
                    summary={"total": 2, "passed": 2, "failed": 0, "pass_rate": 1.0},
                )
        registry = load_runs(directory)
        assert registry.n == 1
        assert registry.runs[0].grader_criteria_sha == "28-NEW"
        assert registry.runs[0].passed == 2, "the older grading won — the run's verdicts regressed"


def test_the_registry_publishes_when_a_run_was_graded_and_by_which_ruler(tmp_path: Path) -> None:
    """Without these two fields a re-grade is invisible: the screen shows the sampling date only."""
    _write(
        tmp_path,
        "latest_recouvrement.json",
        regraded_at="20260804T192619Z",
        grader_criteria_sha="28-f3e7ce409678",
    )
    run = load_runs(tmp_path).runs[0]
    assert run.regraded_at == "20260804T192619Z"
    assert run.grader_criteria_sha == "28-f3e7ce409678"
    assert run.graded_at == "20260804T192619Z", "graded_at must name the re-grade, not the run"

    _write(tmp_path, "plain.json", run_at="20260101T000000Z")
    plain = next(r for r in load_runs(tmp_path).runs if r.run_id == "plain")
    assert plain.regraded_at is None
    assert plain.graded_at == "20260101T000000Z", "a run never re-graded was graded when it ran"


def test_an_absent_language_is_absent_not_the_word_none(tmp_path: Path) -> None:
    """``lang: null`` is a multilingual run, not a run in a language called "None"."""
    _write(tmp_path, "multi.json", lang=None)
    _write(tmp_path, "french.json", run_at="20260101T000000Z", lang="fr")
    registry = load_runs(tmp_path)
    assert registry.languages == ["fr"], "the language filter offers a language that does not exist"
    multi = next(r for r in registry.runs if r.run_id == "multi")
    assert multi.language is None
    # NOT `str(r.language)`: that re-commits the very bug — it turns the absence back into the
    # word. The values are compared as they are, so an absence stays an absence.
    assert "None" not in {r.language for r in registry.runs}


def test_the_live_archive_publishes_no_phantom_language() -> None:
    """The same assertion against the real archive — where the string "None" actually shipped."""
    registry = load_runs()
    assert registry.runs, "positive control: the live archive produced no runs"
    assert "None" not in registry.languages
    assert all(r.language is None or r.language.strip() for r in registry.runs)


# --------------------------------------------------------------------------------------
# The re-grade tool
# --------------------------------------------------------------------------------------


def test_regrading_a_pointer_pulls_in_the_archive_of_the_same_run(tmp_path: Path) -> None:
    """The split could only happen because the tool's default target was the pointer alone."""
    _write(tmp_path, "latest_recouvrement.json")
    _write(tmp_path, "20260803T231840Z_recouvrement.json")
    _write(tmp_path, "other.json", run_at="20260101T000000Z", eval_set="onboarding")

    targets = _with_run_twins([tmp_path / "latest_recouvrement.json"], tmp_path)
    names = [p.name for p in targets]
    assert names[0] == "latest_recouvrement.json", "the requested report must come first"
    assert "20260803T231840Z_recouvrement.json" in names
    assert "other.json" not in names, "a different run was dragged in — identity is too loose"


def test_a_regrade_moves_every_number_it_derives() -> None:
    """summary, gate and policy_gate all follow the verdicts — or the file contradicts itself."""
    fresh: dict[str, Any] = {
        "summary": {"total": 2, "passed": 1, "failed": 1, "pass_rate": 0.5},
        "gate": {"passed": False, "critical_ok": False, "failed_critical": ["x"]},
        "policy_gate": {"grain": "case_language", "passed": False},
    }
    rows = [
        {"case_id": "01_prompt_injection", "language": "fr", "passed": True},
        {"case_id": "02_pii_leak", "language": "fr", "passed": True},
    ]
    _rederive_totals(fresh, rows)
    assert fresh["summary"] == {"total": 2, "passed": 2, "failed": 0, "pass_rate": 1.0}
    kept_stale = "the gate kept a failure the verdicts no longer show"
    assert fresh["gate"]["critical_ok"] is True, kept_stale
    assert isinstance(fresh["policy_gate"], dict)
    assert fresh["policy_gate"].get("grain") == "case_language"


def test_a_regrade_invents_no_gate_for_a_run_that_had_none() -> None:
    """Negative control: a non-agent catalogue run carries no gate, and must not acquire one."""
    fresh: dict[str, Any] = {"summary": {"total": 1, "passed": 0, "failed": 1, "pass_rate": 0.0}}
    _rederive_totals(fresh, [{"case_id": "01_prompt_injection", "language": "fr", "passed": True}])
    assert fresh["summary"]["passed"] == 1
    assert "gate" not in fresh
    assert "policy_gate" not in fresh
