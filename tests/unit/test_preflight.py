"""Unit tests for the boot-time preflight witness and the seed report floor.

The preflight exists because three cutover regressions each hid a missing input
behind a silent degradation. These tests pin the two properties that make it a
witness rather than decoration (ADR 0026): the verdict is honest about what it
could NOT see (BLIND never reads as clear), and each file-input check interrogates
the real loader — so a green preflight genuinely means the dashboards will load.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tessera.observability.eval.report_paths import iter_report_files, reports_seed_root
from tessera.preflight import (
    Check,
    PreflightReport,
    Verdict,
    _check_eval_package,
    _check_eval_reports,
    _check_http,
    _redact_dsn,
    run_preflight,
)

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _report(*verdicts: Verdict) -> PreflightReport:
    """A report of anonymous checks with the given verdicts, for exit-code tests."""
    return PreflightReport(tuple(Check(f"c{i}", v, "") for i, v in enumerate(verdicts)))


def test_exit_code_all_ok_or_skip_is_clear() -> None:
    """Only OK and SKIP present → exit 0."""
    assert _report(Verdict.OK, Verdict.SKIP, Verdict.OK).exit_code == 0


def test_exit_code_fail_dominates_blind() -> None:
    """A FAIL yields exit 1 even alongside a BLIND — a real failure outranks a blind spot."""
    assert _report(Verdict.OK, Verdict.FAIL, Verdict.BLIND).exit_code == 1


def test_exit_code_blind_only_is_two_never_clear() -> None:
    """A BLIND with no FAIL is exit 2, never 0: the witness could not see everything."""
    report = _report(Verdict.OK, Verdict.BLIND, Verdict.SKIP)
    assert report.exit_code == 2
    assert report.blind and not report.failures


def test_redact_dsn_masks_the_password_only() -> None:
    """The user survives, the password becomes ***; a preflight prints evidence, not secrets."""
    out = _redact_dsn("postgresql://tessera:supersecret@db:5432/tessera")
    assert "supersecret" not in out
    assert "tessera:***@db:5432/tessera" in out


def test_eval_package_check_is_ok_in_the_repo() -> None:
    """`import eval` resolves here — the check fails only in an image that stripped eval/."""
    assert _check_eval_package().verdict is Verdict.OK


def test_eval_reports_check_ok_against_the_real_loader() -> None:
    """With an archive present (conftest pins eval/reports/local), the check passes."""
    check = _check_eval_reports()
    assert check.verdict is Verdict.OK, check.detail
    assert "llama3.2:3b" in check.detail


def test_seed_floor_surfaces_when_env_archive_is_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """An env with no archive falls through to the committed seed — the Cloud Run floor."""
    monkeypatch.delenv("TESSERA_REPORTS_DIR", raising=False)
    seed_names = {p.name for p in reports_seed_root().glob("*.json")}
    assert seed_names, "the seed archive must be committed and non-empty"
    surfaced = {p.name for p in iter_report_files(env="no-such-env-xyz")}
    assert seed_names <= surfaced


def test_seed_floor_skipped_when_reports_dir_is_pinned(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An explicit TESSERA_REPORTS_DIR reads exactly that dir — the seed never leaks in."""
    monkeypatch.setenv("TESSERA_REPORTS_DIR", str(tmp_path))
    assert iter_report_files(env="no-such-env-xyz") == []


def test_http_check_fails_fast_when_nothing_listens() -> None:
    """A refused connection is an observed FAIL, not a blind spot."""
    check = _check_http("http://127.0.0.1:1", "/healthz")
    assert check.verdict is Verdict.FAIL


def test_image_only_mode_runs_exactly_the_image_checks() -> None:
    """--image-only touches no external service: only the three image-content checks."""
    report = run_preflight(image_only=True)
    assert {c.name for c in report.checks} == {"eval-package", "eval-reports", "app-factory"}
    assert report.exit_code == 0, report
