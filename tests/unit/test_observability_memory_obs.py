"""Unit tests for memory observability (ADR 0010, #23)."""

from __future__ import annotations

from tessera.observability.memory_obs import aggregate_memory_audit


def _entry(target: str, outcome: str, rationale: str) -> dict[str, object]:
    return {
        "type": "tessera.guard.audit",
        "target": target,
        "outcome": outcome,
        "decisions": [{"policy_rule": f"{target}.governance", "rationale": rationale}],
    }


def test_empty() -> None:
    report = aggregate_memory_audit([])
    assert report.n_actions == 0
    assert report.recall_hit_rate == 0.0


def test_ignores_non_memory_targets() -> None:
    report = aggregate_memory_audit(
        [
            {"type": "tessera.guard.audit", "target": "account_balance", "outcome": "allowed"},
            _entry("memory.write", "allowed", "persisted 1/1 candidate fact(s)"),
        ]
    )
    assert report.n_actions == 1
    assert report.n_writes == 1


def test_write_accept_and_reject() -> None:
    report = aggregate_memory_audit(
        [
            _entry("memory.write", "allowed", "persisted 2/2 candidate fact(s)"),
            _entry("memory.write", "denied", "candidate rejected by screen (poisoning/PII)"),
        ]
    )
    assert report.n_writes == 2
    assert report.writes_allowed == 1
    assert report.writes_denied == 1


def test_recall_hit_miss_and_screened_out() -> None:
    report = aggregate_memory_audit(
        [
            _entry("memory.read", "allowed", "recalled 2/3 item(s) after screening"),
            _entry("memory.read", "allowed", "recalled 0/0 item(s) after screening"),
        ]
    )
    assert report.n_reads == 2
    assert report.recall_hits == 1
    assert report.recall_misses == 1
    assert report.recall_hit_rate == 0.5
    assert report.items_recalled == 2
    # One poisoned/PII item dropped on read (3 found, 2 surfaced).
    assert report.items_screened_out == 1


def test_forget_counted() -> None:
    report = aggregate_memory_audit(
        [_entry("memory.forget", "allowed", "subject erasure (GDPR Art. 17)")]
    )
    assert report.n_forgets == 1
