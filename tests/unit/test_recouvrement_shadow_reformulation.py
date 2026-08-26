"""ADR 0054 slice 3 — layer 3 drafts in SHADOW, and the declaration matches the thing.

Same three planes of witness as the understanding suite (ADR 0017 §A5, here §A6): the
declaration (template_referent + an existing referent that names the agent), the governed
config's honest degradations (OFF is the base, an illegal store state degrades to OFF and
says so), and the shadow seam (only an approved-template, unblocked draft spawns; OFF spends
nothing; the recorded row carries measurements and NEVER the candidate text).
"""

from __future__ import annotations

import asyncio
import inspect

import pytest

from eval.reformulation_bench import DEFAULT_SET_PATH, load_reformulation_set
from tessera.agent.agentspec import ReformulationMode, ReformulationSpec
from tessera.agent.registry import get_agent
from tessera.api.config_overrides import (
    REFORMULATION_MODE_KEY,
    REFORMULATION_THRESHOLD_KEY,
    ReformulationConfig,
    _interpret_reformulation_rows,
)
from tessera.api.routes import recouvrement_assistant
from tessera.observability import business_events as business_events_mod
from tessera.recouvrement.reformulation import FidelityJudgement, ReformulationOutcome

# ── A6: the declaration, and the declaration against the thing ──────────────────────────


def test_recouvrement_declares_template_referent_reformulation() -> None:
    spec = get_agent("recouvrement").observability
    assert spec is not None and spec.reformulation is not None
    assert spec.reformulation.mode is ReformulationMode.TEMPLATE_REFERENT
    assert spec.reformulation.bench_set == "recouvrement"


def test_declared_bench_set_exists_and_names_the_declaring_agent() -> None:
    """The referent the manifest points at exists on disk and is about this agent."""
    spec = get_agent("recouvrement").observability
    assert spec is not None and spec.reformulation is not None
    bench_set = spec.reformulation.bench_set
    assert bench_set is not None
    assert DEFAULT_SET_PATH.name == f"{bench_set}.json"
    assert load_reformulation_set().agent_id == "recouvrement"


def test_template_referent_without_bench_set_is_refused_at_load() -> None:
    with pytest.raises(ValueError, match="requires bench_set"):
        ReformulationSpec(mode=ReformulationMode.TEMPLATE_REFERENT)


def test_the_declaring_agents_turn_route_wires_the_shadow_seam() -> None:
    """The declaration is held to the wiring: the message route spawns the shadow (ADR 0026)."""
    source = inspect.getsource(recouvrement_assistant.recouvrement_assistant_message)
    assert "_spawn_shadow_reformulation" in source


# ── The governed config's honest degradations ───────────────────────────────────────────


def test_no_stored_rows_serve_off() -> None:
    """The base is OFF — the compliance pass is a precondition to shadow (ADR 0054)."""
    config = _interpret_reformulation_rows({}, default_timeout_s=20.0)
    assert config == ReformulationConfig(mode="off", threshold=None, timeout_s=20.0, model=None)


def test_active_without_threshold_degrades_to_off_loudly(
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = _interpret_reformulation_rows(
        {REFORMULATION_MODE_KEY: "active"}, default_timeout_s=20.0
    )
    assert config.mode == "off"
    assert "illegal store state" in capsys.readouterr().err


def test_a_stored_shadow_mode_serves_shadow() -> None:
    config = _interpret_reformulation_rows(
        {REFORMULATION_MODE_KEY: "shadow", REFORMULATION_THRESHOLD_KEY: "0.9"},
        default_timeout_s=20.0,
    )
    assert config.mode == "shadow"
    assert config.threshold == 0.9


# ── The shadow seam ─────────────────────────────────────────────────────────────────────


@pytest.fixture
def _memory_ledger() -> None:
    business_events_mod.set_business_event_store(business_events_mod.InMemoryBusinessEventStore())


_DRAFT = (
    "Bonjour Marie Lefèvre,\n\nNous vous contactons au sujet du dossier RC-2048. "
    "Le montant restant dû est de 1 260,50 €.\n\nCordialement,\nCrédit Aurore"
)


def _fake_result(
    *,
    generation_mode: str = "approved_template",
    policy_status: str = "approved",
    with_draft: bool = True,
) -> dict[str, object]:
    """A minimal route result carrying the draft artifact and its policy event."""
    return {
        "decisions": {"intent": "draft_reminder"},
        "artifact": {
            "id": "artifact-1",
            "type": "reminder_draft_v1",
            "task": "draft_reminder",
            "title": "Relance",
            "status": "draft",
            "content": {"message_client": _DRAFT} if with_draft else {},
        },
        "businessEvents": [
            {
                "event_name": "policy.decision_made",
                "payload": {
                    "policy_rule": "recouvrement.client_message_safety",
                    "generation_mode": generation_mode,
                    "policy_review_status": policy_status,
                    "template_id": "recouvrement_reminder_short_v1",
                    "template_version": "1.0.0",
                },
                "surface": "dedicated-ui",
                "conversation_id": "conv-reform",
                "turn_id": "turn-reform",
                "environment": "dev",
            }
        ],
    }


def _payload() -> recouvrement_assistant.RecouvrementAssistantRequest:
    return recouvrement_assistant.RecouvrementAssistantRequest(
        case_id="RC-2048", message="Prépare une relance", language="fr"
    )


async def _drain_shadow_tasks() -> None:
    while recouvrement_assistant._SHADOW_TASKS:
        await asyncio.gather(*tuple(recouvrement_assistant._SHADOW_TASKS))


def _stub_config(monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    async def _resolve() -> ReformulationConfig:
        return ReformulationConfig(
            mode=mode,  # type: ignore[arg-type]
            threshold=None,
            timeout_s=20.0,
            model=None,
        )

    monkeypatch.setattr(recouvrement_assistant, "resolve_reformulation_config", _resolve)


def _stub_generation(monkeypatch: pytest.MonkeyPatch, *, text: str) -> None:
    async def _reformulate(template_text: str, **_: object) -> ReformulationOutcome:
        return ReformulationOutcome(
            status="candidate",
            text=text,
            detail=None,
            model="fake-model",
            prompt_version="recouvrement_tone.v1",
            latency_ms=42.0,
        )

    async def _judge(template_text: str, candidate_text: str, **_: object) -> FidelityJudgement:
        return FidelityJudgement(
            status="scored",
            fidelity=0.92,
            reasons=("intact",),
            detail=None,
            model="fake-model",
            prompt_version="recouvrement_fidelity.v1",
            latency_ms=21.0,
        )

    monkeypatch.setattr(recouvrement_assistant, "reformulate_tone_llm", _reformulate)
    monkeypatch.setattr(recouvrement_assistant, "judge_template_fidelity_llm", _judge)


async def test_mode_off_spends_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """The base state costs zero model calls — resolved inside the task, off the hot path."""
    called = False

    async def _reformulate(template_text: str, **_: object) -> ReformulationOutcome:
        nonlocal called
        called = True
        raise AssertionError("unreachable")

    _stub_config(monkeypatch, "off")
    monkeypatch.setattr(recouvrement_assistant, "reformulate_tone_llm", _reformulate)
    recouvrement_assistant._spawn_shadow_reformulation(_payload(), _fake_result())
    await _drain_shadow_tasks()
    assert called is False


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"with_draft": False}, "no client-message draft this turn"),
        ({"generation_mode": "llm_rewrite"}, "not an approved-template draft"),
        ({"policy_status": "blocked"}, "the drafting policy blocked the draft"),
    ],
)
async def test_only_an_approved_unblocked_template_draft_spawns(
    monkeypatch: pytest.MonkeyPatch, kwargs: dict[str, object], reason: str
) -> None:
    resolved = False

    async def _resolve() -> ReformulationConfig:
        nonlocal resolved
        resolved = True
        return ReformulationConfig(mode="shadow", threshold=None, timeout_s=20.0, model=None)

    monkeypatch.setattr(recouvrement_assistant, "resolve_reformulation_config", _resolve)
    recouvrement_assistant._spawn_shadow_reformulation(
        _payload(),
        _fake_result(**kwargs),  # type: ignore[arg-type]
    )
    await _drain_shadow_tasks()
    assert resolved is False, reason


async def test_a_shadowed_draft_records_measurements_and_never_the_text(
    monkeypatch: pytest.MonkeyPatch, _memory_ledger: None
) -> None:
    """The row joins its turn, names checker + judge results — and carries NO letter text.

    The candidate is an unapproved letter: persisting it would turn the ledger into a
    store of unreviewed regulated wording. Only measurements land.
    """
    candidate = _DRAFT.replace("Nous vous contactons", "Nous revenons vers vous")
    _stub_config(monkeypatch, "shadow")
    _stub_generation(monkeypatch, text=candidate)
    recouvrement_assistant._spawn_shadow_reformulation(_payload(), _fake_result())
    await _drain_shadow_tasks()
    rows = business_events_mod.business_event_rows(
        agent_id="recouvrement", conversation_id="conv-reform", turn_id="turn-reform"
    )
    shadow_rows = [row for row in rows if row.get("node_name") == "shadow_reformulation"]
    assert len(shadow_rows) == 1
    payload = shadow_rows[0]["payload"]
    assert payload["message_kind"] == "shadow_reformulation"
    assert payload["generation_mode"] == "llm_rewrite"
    assert payload["template_id"] == "recouvrement_reminder_short_v1"
    generation = payload["client_message_generation"]
    assert generation["shadow"] is True
    assert generation["llm_status"] == "candidate"
    assert generation["checker_ok"] is True
    assert generation["fidelity"] == 0.92
    assert generation["judge_status"] == "scored"
    # The privacy pin: no fragment of the candidate letter reaches the ledger row.
    import json as json_mod

    serialized = json_mod.dumps(payload, ensure_ascii=False, default=str)
    assert "Nous revenons vers vous" not in serialized
    assert "Marie Lefèvre" not in serialized


async def test_a_mutated_candidate_is_named_by_the_checker(
    monkeypatch: pytest.MonkeyPatch, _memory_ledger: None
) -> None:
    """The REAL checker runs in the seam: a mutated amount is caught and its kind named."""
    _stub_config(monkeypatch, "shadow")
    _stub_generation(monkeypatch, text=_DRAFT.replace("1 260,50 €", "1 270,50 €"))
    recouvrement_assistant._spawn_shadow_reformulation(_payload(), _fake_result())
    await _drain_shadow_tasks()
    rows = business_events_mod.business_event_rows(
        agent_id="recouvrement", conversation_id="conv-reform", turn_id="turn-reform"
    )
    payload = next(r for r in rows if r.get("node_name") == "shadow_reformulation")["payload"]
    generation = payload["client_message_generation"]
    assert generation["checker_ok"] is False
    assert any(str(f).startswith("amount_missing:") for f in generation["checker_failures"])
