"""Unit tests for tool-call validity (ADR 0010, #29)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from tessera.observability.tool_validity import compute_tool_validity

if TYPE_CHECKING:
    from pathlib import Path


def _write(path: Path, entries: list[dict[str, object]]) -> None:
    path.write_text(
        "\n".join(json.dumps(e) for e in entries) + "\n",
        encoding="utf-8",
    )


def test_tool_validity_counts(tmp_path: Path) -> None:
    log = tmp_path / "audit.log"
    _write(
        log,
        [
            {
                "type": "tessera.guard.audit",
                "target": "account_balance",
                "outcome": "allowed",
                "decisions": [],
            },
            {
                "type": "tessera.guard.audit",
                "target": "loan_simulate",
                "outcome": "denied",
                "decisions": [{"policy_rule": "tool.loan_simulate.argument.amount"}],
            },
            {
                "type": "tessera.guard.audit",
                "target": "card_block",
                "outcome": "error",
                "decisions": [],
            },
            # user_input checks are excluded from tool validity.
            {
                "type": "tessera.guard.audit",
                "target": "user_input",
                "outcome": "denied",
                "decisions": [],
            },
        ],
    )
    report = compute_tool_validity(log)
    assert report.total == 3
    assert report.allowed == 1
    assert report.denied == 1
    assert report.errored == 1
    assert report.arg_failures == 1
    assert report.validity_rate == 1 / 3


def test_tool_validity_empty(tmp_path: Path) -> None:
    report = compute_tool_validity(tmp_path / "missing.log")
    assert report.total == 0
    assert report.validity_rate == 1.0
