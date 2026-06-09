"""Unit tests for SIEM integration (ADR 0010, #172)."""

from __future__ import annotations

from tessera.observability.siem import to_siem_events


def _entry(target: str, outcome: str, decision: str, rationale: str = "") -> dict[str, object]:
    return {
        "type": "tessera.guard.audit",
        "target": target,
        "outcome": outcome,
        "occurred_at": "2026-06-10T10:00:00+00:00",
        "arguments": {"subject_id": "s1"},
        "decisions": [{"decision": decision, "rationale": rationale}],
    }


def test_empty() -> None:
    export = to_siem_events([])
    assert export.n_events == 0
    assert export.n_high_severity == 0


def test_allowed_tool_call_is_not_forwarded() -> None:
    # A plain allowed tool call is not security-relevant.
    export = to_siem_events([_entry("account_balance", "allowed", "allow")])
    assert export.n_events == 0


def test_denied_tool_call_is_high_severity_failure() -> None:
    export = to_siem_events([_entry("card_block", "denied", "deny", "policy deny")])
    assert export.n_events == 1
    ev = export.events[0]
    assert ev.outcome == "failure"
    assert ev.severity >= 7
    assert ev.category == "intrusion_detection"
    assert export.n_high_severity == 1


def test_memory_actions_are_forwarded() -> None:
    export = to_siem_events(
        [
            _entry("memory.write", "allowed", "allow", "persisted 1/1"),
            _entry("memory.forget", "allowed", "allow", "erasure"),
        ]
    )
    assert export.n_events == 2
    cats = export.by_category
    assert cats.get("data_protection") == 1  # memory.write
    assert cats.get("iam") == 1  # memory.forget
    assert export.events[0].actor == "s1"


def test_denied_memory_write_high_severity() -> None:
    export = to_siem_events([_entry("memory.write", "denied", "deny", "poisoning rejected")])
    assert export.events[0].severity >= 7
    assert export.events[0].outcome == "failure"
