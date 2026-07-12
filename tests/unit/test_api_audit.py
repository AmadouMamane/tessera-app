"""Unit tests for the audit dashboard endpoint helpers."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from tessera.api.routes import audit

if TYPE_CHECKING:
    from pathlib import Path


def test_entry_normalisation_exposes_auditable_dashboard_fields() -> None:
    entry = audit._entry_from_payload(
        {
            "version": 1,
            "occurred_at": "2026-06-14T10:00:00+00:00",
            "target": "account_balance",
            "outcome": "allowed",
            "model": "llama3.2:3b",
            "data_residency": "eu",
            "arguments": {"account_id": "AC-12345"},
            "decisions": [
                {
                    "target": "account_balance",
                    "decision": "allow",
                    "policy_rule": "tool.account_balance.allow",
                    "rationale": "allowed by policy",
                    "redactions": [],
                    "occurred_at": "2026-06-14T10:00:00+00:00",
                }
            ],
            "prev_hash": "0" * 64,
            "hash": "abcdef1234567890",
        }
    )

    assert entry.event_type == "tool"
    assert entry.scope == "eu"
    assert entry.object_label == "AC-12345"
    assert entry.policy_rule == "tool.account_balance.allow"
    assert entry.proof_ref == "abcdef123456"
    # A version-1 entry recorded no author. It says so. It used to render `model or target` —
    # so the Journal's "who did this" column showed **llama3.2:3b**, and this test demanded it.
    assert entry.actor == "auteur non enregistré"
    assert "llama" not in entry.actor
    assert entry.actor_role == "service"


def test_the_journal_names_the_operator_who_erased_a_record() -> None:
    """The finding, at the surface a DPO actually reads.

    The GDPR erasure's entry type is ``tessera.guard.audit``. The Journal keyed its actor read
    on ``type.startswith("tessera.agent.")`` — so the erasure fell through to ``model or
    target`` and the cockpit displayed **the LLM's model name** in the author column, for the
    single most consequential act in the system. The name was written in the entry the whole
    time; the reader looked in the wrong place.

    Keyed now on the *presence of the field*, which is the thing that is actually true.
    """
    entry = audit._entry_from_payload(
        {
            "version": 3,
            "occurred_at": "2026-07-12T22:00:00+00:00",
            "target": "memory.forget",
            "outcome": "allowed",
            "model": "llama3.2:3b",
            "actor": "bob@bank.eu",
            "actor_role": "admin",
            "arguments": {"subject_id": "SUB-1"},
            "decisions": [
                {"decision": "allow", "policy_rule": "memory.forget.governance", "rationale": "x"}
            ],
        }
    )

    assert entry.actor == "bob@bank.eu"
    assert entry.actor_role == "human", "a named principal is a person, and can be asked"
    assert entry.model == "llama3.2:3b", "the model is still recorded — it is simply not the author"


def test_the_journal_marks_a_system_actor_as_a_machine() -> None:
    """The retention purge deleted a person's data. Nobody ordered it, and it says which task did.

    ``system:`` principals are machines that acted on policy — the distinction a reader of an
    audit trail needs, because a machine cannot be asked what it was thinking. Rendering them as
    "human" would be the same class of lie in the other direction.
    """
    entry = audit._entry_from_payload(
        {
            "version": 3,
            "occurred_at": "2026-07-12T22:00:00+00:00",
            "target": "memory.forget",
            "outcome": "allowed",
            "actor": "system:retention-purge",
            "actor_role": "system",
            "arguments": {"subject_id": "SUB-1"},
            "decisions": [],
        }
    )

    assert entry.actor == "system:retention-purge"
    assert entry.actor_role == "system"


def test_overview_counts_current_window_and_previous_delta() -> None:
    current_tool = audit._entry_from_payload(
        {
            "occurred_at": "2026-06-14T10:00:00+00:00",
            "target": "account_balance",
            "outcome": "allowed",
            "model": "llama3.2:3b",
            "arguments": {"account_id": "AC-12345"},
            "decisions": [{"policy_rule": "tool.account_balance.allow"}],
            "hash": "a" * 64,
        }
    )
    current_guard = audit._entry_from_payload(
        {
            "occurred_at": "2026-06-14T11:00:00+00:00",
            "target": "user_input",
            "outcome": "denied",
            "model": "llama3.2:3b",
            "decisions": [{"policy_rule": "prompt_injection.deny_patterns"}],
            "hash": "b" * 64,
        }
    )
    previous_guard = audit._entry_from_payload(
        {
            "occurred_at": "2026-06-13T11:00:00+00:00",
            "target": "user_input",
            "outcome": "denied",
            "model": "llama3.2:3b",
            "decisions": [{"policy_rule": "prompt_injection.deny_patterns"}],
            "hash": "c" * 64,
        }
    )

    overview = audit._build_overview(
        [previous_guard, current_guard, current_tool],
        audit.AuditIntegrity(verified=True, length=3),
        since=datetime(2026, 6, 14, tzinfo=UTC),
        until=datetime(2026, 6, 15, tzinfo=UTC),
    )
    metrics = {metric.key: metric for metric in overview.metrics}

    assert overview.total_events == 2
    assert metrics["signed_events"].value == 2
    assert metrics["signed_events"].previous_value == 1
    assert metrics["sensitive_actions"].value == 1
    assert metrics["guard_refusals"].value == 1
    assert metrics["chain_integrity"].value == 1
    assert sum(bucket.total for bucket in overview.timeline) == 2
    assert {target.key for target in overview.targets} == {"account_balance", "user_input"}
    assert overview.recent_proofs[0].hash == "b" * 64


def test_filter_entries_applies_policy_search_and_time_window() -> None:
    kept = audit._entry_from_payload(
        {
            "occurred_at": "2026-06-14T10:00:00+00:00",
            "target": "memory.write",
            "outcome": "allowed",
            "model": "llama3.2:3b",
            "arguments": {"subject_id": "SUB-1"},
            "decisions": [{"policy_rule": "memory.write.governance"}],
        }
    )
    dropped = audit._entry_from_payload(
        {
            "occurred_at": "2026-06-12T10:00:00+00:00",
            "target": "memory.read",
            "outcome": "allowed",
            "model": "llama3.2:3b",
            "arguments": {"subject_id": "SUB-2"},
            "decisions": [{"policy_rule": "memory.read.governance"}],
        }
    )

    filtered = audit._filter_entries(
        [kept, dropped],
        target=None,
        outcome="allowed",
        event_type=None,
        actor_role=None,
        scope=None,
        policy_rule="memory.write.governance",
        q="SUB-1",
        since=datetime(2026, 6, 14, tzinfo=UTC),
        until=datetime(2026, 6, 15, tzinfo=UTC),
    )

    assert filtered == [kept]


def test_read_entries_cache_invalidates_when_audit_file_changes(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    path.write_text(
        json.dumps(
            {
                "occurred_at": "2026-06-14T10:00:00+00:00",
                "target": "memory.read",
                "outcome": "allowed",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    audit._ENTRIES_CACHE = None
    first = audit._read_entries(path)
    second = audit._read_entries(path)

    assert first is second
    assert [entry.target for entry in first] == ["memory.read"]

    with path.open("a", encoding="utf-8") as fp:
        fp.write(
            json.dumps(
                {
                    "occurred_at": "2026-06-14T11:00:00+00:00",
                    "target": "memory.write",
                    "outcome": "allowed",
                }
            )
            + "\n"
        )

    refreshed = audit._read_entries(path)

    assert refreshed is not first
    assert [entry.target for entry in refreshed] == ["memory.read", "memory.write"]


def test_audit_integrity_length_honours_as_of(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """The chain length is the append-only count up to T (verification stays live)."""
    path = tmp_path / "audit.jsonl"
    rows = [
        {"occurred_at": "2026-06-14T10:00:00+00:00", "target": "a", "outcome": "allowed"},
        {"occurred_at": "2026-06-14T11:00:00+00:00", "target": "b", "outcome": "allowed"},
        {"occurred_at": "2026-06-15T09:00:00+00:00", "target": "c", "outcome": "allowed"},
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    audit._ENTRIES_CACHE = None
    audit._INTEGRITY_CACHE = None
    monkeypatch.setattr(audit, "_resolve_audit_path", lambda: path)

    # As-of after the first two entries → only those two are counted (not the later one).
    asof2 = asyncio.run(audit.audit_integrity(at="2026-06-14T12:00:00+00:00"))
    assert asof2.length == 2
    # As-of after all three → all counted.
    asof3 = asyncio.run(audit.audit_integrity(at="2026-06-16T00:00:00+00:00"))
    assert asof3.length == 3
    # As-of before any data → zero, never the live total.
    asof0 = asyncio.run(audit.audit_integrity(at="2026-06-01T00:00:00+00:00"))
    assert asof0.length == 0
    # The verification flag is preserved from the structural (live) chain check.
    assert isinstance(asof2.verified, bool)
