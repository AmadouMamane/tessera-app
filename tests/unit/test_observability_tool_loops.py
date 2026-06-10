"""Unit tests for tool-call loop / oscillation detection (ADR 0010, #88)."""

from __future__ import annotations

from tessera.observability import tool_loops


def test_no_loops_on_clean_stream() -> None:
    report = tool_loops.detect_loops({"global": ["account_balance", "card_block", "loan_simulate"]})
    assert report.n_loops == 0
    assert report.n_calls == 3
    assert report.n_streams == 1


def test_detects_consecutive_repeat() -> None:
    report = tool_loops.detect_loops({"c1": ["account_balance"] * 4})
    assert report.n_loops == 1
    loop = report.loops[0]
    assert loop.kind == "repeat"
    assert loop.tools == ["account_balance"]
    assert loop.length == 4


def test_repeat_below_threshold_is_ignored() -> None:
    report = tool_loops.detect_loops({"c1": ["card_block", "card_block"]})
    assert report.n_loops == 0


def test_detects_oscillation() -> None:
    report = tool_loops.detect_loops(
        {"c1": ["account_balance", "card_block", "account_balance", "card_block"]}
    )
    assert report.n_loops == 1
    loop = report.loops[0]
    assert loop.kind == "oscillation"
    assert loop.tools == ["account_balance", "card_block"]
    assert loop.length == 4


def test_oscillation_not_flagged_when_too_short() -> None:
    report = tool_loops.detect_loops({"c1": ["account_balance", "card_block", "account_balance"]})
    assert all(loop.kind != "oscillation" for loop in report.loops)


def test_threshold_is_configurable() -> None:
    report = tool_loops.detect_loops({"c1": ["loan_simulate"] * 2}, repeat_threshold=2)
    assert report.repeat_threshold == 2
    assert report.n_loops == 1
