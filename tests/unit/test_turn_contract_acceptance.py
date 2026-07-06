"""ADR 0018 — platform-level acceptance criteria, run against the reference runtime.

These are the acceptance tests of the *turn contract* (ADR 0018 §Acceptance criteria),
exercised on the shipped reference implementation (``run_recouvrement_graph_v1``).
They pin the platform properties every agent runtime must satisfy — deterministic
policy answers, grammar-stamped events, no internal-label leakage, the contract keys —
without asserting any recouvrement copywriting.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tessera.agent.recouvrement import run_recouvrement_graph_v1
from tessera.agent.turn_contract import TURN_RESULT_KEYS
from tessera.guard import audit
from tessera.observability import business_events as business_events_mod, replay as replay_mod
from tessera.observability.business_events import GRAMMAR_VERSION
from tessera.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

_INTERNAL_LABELS = (
    "check_contact_rule",
    "propose_schedule",
    "draft_reminder",
    "summarize_case",
    "explain_payment_options",
    "business_rule.checked",
    "policy.decision_made",
    "artifact.created",
)


@pytest.fixture
def isolated_stores(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Isolate the observability stores, mirroring the graph-v1 test fixture."""
    settings = get_settings()
    monkeypatch.setattr(settings.guard, "audit_file", tmp_path / "audit.log")
    monkeypatch.setattr(settings.guard, "audit_sink", "file")
    monkeypatch.setattr(audit, "_last_hash", None)
    previous_store = business_events_mod.get_business_event_store()
    business_events_mod.set_business_event_store(business_events_mod.InMemoryBusinessEventStore())
    monkeypatch.setattr(replay_mod, "_bundles_path", lambda: tmp_path / "bundles.jsonl")
    replay_mod._BUNDLES.clear()
    monkeypatch.setattr(replay_mod, "_WARMED", False)
    yield
    business_events_mod.set_business_event_store(previous_store)


def _run(message: str, turn_id: str) -> dict[str, object]:
    output = run_recouvrement_graph_v1(
        case_id="RC-2048",
        message=message,
        conversation_id="conv-turn-contract",
        turn_id=turn_id,
    )
    return dict(output)


def _scores_by_metric(output: dict[str, object]) -> dict[str, dict[str, object]]:
    scores = output.get("businessScores")
    assert isinstance(scores, list)
    return {str(row.get("metric")): dict(row) for row in scores if isinstance(row, dict)}


@pytest.mark.usefixtures("isolated_stores")
def test_output_carries_the_turn_contract_keys() -> None:
    """ADR 0018 §1 — the runtime output is the TurnResult serialisation."""
    output = _run("Résume le dossier", "turn-contract-keys")
    assert set(output) >= TURN_RESULT_KEYS


@pytest.mark.usefixtures("isolated_stores")
def test_every_turn_emits_grammar_stamped_events() -> None:
    """ADR 0017 §2 — every business event carries the grammar version."""
    output = _run("Puis-je l'appeler à 22h ?", "turn-grammar-stamp")
    events = output.get("businessEvents")
    assert isinstance(events, list) and events
    assert all(row.get("grammar_version") == GRAMMAR_VERSION for row in events)


@pytest.mark.usefixtures("isolated_stores")
def test_out_of_window_contact_is_deterministically_blocked() -> None:
    """ADR 0018 criterion 2 — the 22h answer comes from the policy, not the model."""
    output = _run("Puis-je l'appeler à 22h ?", "turn-contact-window")
    by_metric = _scores_by_metric(output)
    contact = by_metric.get("contact_window_compliance")
    assert contact is not None
    assert contact.get("score") == 1.0
    assert contact.get("reason") == "outside_contact_window_blocked"


@pytest.mark.usefixtures("isolated_stores")
def test_schedule_proposals_require_validation() -> None:
    """ADR 0018 criterion 7 / 0017 §A1.3 — external effects demand validation."""
    output = _run("Peux-tu proposer un échéancier ?", "turn-schedule-validation")
    by_metric = _scores_by_metric(output)
    validation = by_metric.get("validation_required_compliance")
    assert validation is not None
    assert validation.get("score") == 1.0
    assert validation.get("reason") == "validation_requested_pending_or_declared"


@pytest.mark.usefixtures("isolated_stores")
def test_internal_labels_never_leak_into_visible_replies() -> None:
    """ADR 0018 criterion 4 — internal ids are never user-facing copy."""
    for index, message in enumerate(
        (
            "Puis-je l'appeler à 22h ?",
            "Peux-tu proposer un échéancier ?",
            "Résume le dossier",
        )
    ):
        output = _run(message, f"turn-label-leak-{index}")
        reply = output.get("visibleReply")
        assert isinstance(reply, str) and reply
        for label in _INTERNAL_LABELS:
            assert label not in reply, f"internal label {label!r} leaked into the reply"
