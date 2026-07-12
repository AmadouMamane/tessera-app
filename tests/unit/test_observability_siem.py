"""Unit tests for SIEM integration (ADR 0010, #172).

Audit 2026-07-12, the attribution lane. This file used to assert the bug:

    assert export.events[0].actor == "s1"     # "s1" is arguments["subject_id"]

``subject_id`` is the person whose data was touched. For a ``memory.forget`` — which this
module classifies ``iam``, severity 7 — that shipped the bank's SOC an identity event naming
**the erased data subject as the author of their own erasure**. The export read the victim into
the actor field, and the test *demanded* that it do so, which is why neither review caught it:
the confusion was green.
"""

from __future__ import annotations

from tessera.observability.siem import to_siem_events

#: The data subject — WHOSE record. Never the author of anything.
A_SUBJECT = "s1"
#: The verified principal who acted — WHO. A different person, always.
AN_OPERATOR = "bob@bank.eu"


def _entry(
    target: str,
    outcome: str,
    decision: str,
    rationale: str = "",
    actor: str | None = AN_OPERATOR,
) -> dict[str, object]:
    """An audit entry as the emitter writes it: actor at the TOP level, subject in arguments.

    ``actor=None`` produces a **pre-v3** entry — one written before the schema carried an
    author at all. Those exist in the live ledger and must be handled honestly, not guessed at.
    """
    entry: dict[str, object] = {
        "type": "tessera.guard.audit",
        "target": target,
        "outcome": outcome,
        "occurred_at": "2026-06-10T10:00:00+00:00",
        "arguments": {"subject_id": A_SUBJECT},
        "decisions": [{"decision": decision, "rationale": rationale}],
    }
    if actor is not None:
        entry["version"] = 3
        entry["actor"] = actor
        entry["actor_role"] = "admin"
    return entry


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


def test_the_soc_is_told_who_erased_the_record_not_who_was_erased() -> None:
    """The finding, stated as the invariant it should always have been.

    An analyst opening this alert asks one question first — *who did this?* — and the answer
    they were being handed was the person the act was done TO. The two fields are now distinct
    and both present, so the alert carries the whole fact and neither half can stand in for the
    other.
    """
    export = to_siem_events([_entry("memory.forget", "allowed", "allow", "erasure")])

    event = export.events[0]
    assert event.category == "iam"
    assert event.actor == AN_OPERATOR, "the SOC must be told WHO erased the record"
    assert event.subject == A_SUBJECT, "and, separately, WHOSE record it was"
    assert event.actor != event.subject, (
        "the erased data subject was named as the author of their own erasure — "
        "the export read arguments['subject_id'] into the actor field"
    )


def test_a_pre_v3_entry_reaches_the_soc_labelled_unattributable() -> None:
    """Entries written before the schema had an author must say so, not borrow a name.

    Honest-empty, at the security boundary: an event nobody can be held to is a fact the
    analyst needs, and it is strictly more useful than a plausible substitute. Substituting the
    subject is how this went wrong the first time; substituting the *model name* is how the
    cockpit Journal went wrong at the same moment, for the same reason.
    """
    export = to_siem_events([_entry("memory.forget", "allowed", "allow", "erasure", actor=None)])

    event = export.events[0]
    assert "unattributed" in event.actor
    assert event.subject == A_SUBJECT, "the subject is still known — only the author is not"
    assert A_SUBJECT not in event.actor, "an unattributable act must not borrow the subject's name"


def test_denied_memory_write_high_severity() -> None:
    export = to_siem_events([_entry("memory.write", "denied", "deny", "poisoning rejected")])
    assert export.events[0].severity >= 7
    assert export.events[0].outcome == "failure"
