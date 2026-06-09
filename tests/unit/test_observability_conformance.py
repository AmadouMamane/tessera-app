"""Unit tests for schema/format conformance (ADR 0010, #47)."""

from __future__ import annotations

from tessera.guard.decisions import load_policy
from tessera.observability import conformance


def _card_block_policy():
    return load_policy().tool("card_block")


def test_conformant_arguments() -> None:
    checked, conformant, violations = conformance.check_arguments(
        {"card_last_four": "1234", "reason": "lost"}, _card_block_policy()
    )
    assert checked == 2
    assert conformant == 2
    assert violations == []


def test_malformed_argument_flagged() -> None:
    checked, conformant, violations = conformance.check_arguments(
        {"card_last_four": "12", "reason": "lost"}, _card_block_policy()
    )
    assert checked == 2
    assert conformant == 1
    assert violations == ["card_last_four"]


def test_redacted_and_unknown_fields_skipped() -> None:
    # customer_id is redacted in audit; an out-of-policy field is ignored.
    checked, _conformant, _violations = conformance.check_arguments(
        {"customer_id": "[redacted]", "card_last_four": "9999", "reason": "stolen", "extra": "x"},
        _card_block_policy(),
    )
    assert checked == 2  # only card_last_four + reason are observable & patterned


def test_compute_conformance_handles_missing_file(tmp_path) -> None:
    report = conformance.compute_conformance(tmp_path / "nope.log")
    assert report.n_calls == 0
    assert report.conformance_rate == 1.0
