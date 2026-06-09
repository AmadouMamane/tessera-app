"""Unit tests for guard decision explainability (ADR 0010, #19)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from tessera.observability import guard_explain

if TYPE_CHECKING:
    from pathlib import Path


def _write_audit(path: Path, entries: list[dict[str, object]]) -> None:
    path.write_text("\n".join(json.dumps(e) for e in entries), encoding="utf-8")


def test_missing_file_is_empty(tmp_path: Path) -> None:
    report = guard_explain.compute_guard_explain(path=tmp_path / "nope.log")
    assert report.n_entries == 0
    assert report.rules == []


def test_aggregates_and_ranks_rules(tmp_path: Path) -> None:
    audit = tmp_path / "audit.log"
    _write_audit(
        audit,
        [
            {
                "type": "tessera.guard.audit",
                "decisions": [
                    {"policy_rule": "prompt_injection.deny_patterns", "decision": "deny"},
                    {"policy_rule": "tool.account_balance.allow", "decision": "allow"},
                ],
            },
            {
                "type": "tessera.guard.audit",
                "decisions": [
                    {"policy_rule": "prompt_injection.deny_patterns", "decision": "deny"},
                ],
            },
            {"type": "other", "decisions": [{"policy_rule": "x", "decision": "deny"}]},
        ],
    )
    report = guard_explain.compute_guard_explain(path=audit)
    assert report.n_entries == 2  # the "other" line is ignored
    assert report.n_decisions == 3
    assert report.n_denials == 2
    top = report.rules[0]
    assert top.rule == "prompt_injection.deny_patterns"
    assert top.decision == "deny"
    assert top.count == 2
