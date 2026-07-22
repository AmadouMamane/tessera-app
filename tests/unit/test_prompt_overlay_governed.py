"""ADR 0037 — the per-agent prompt overlay is governed by proposal and approval.

Witnesses, ADR 0026 style:

* the lifecycle: propose stores an attributed draft; approve (by ANOTHER
  person) promotes it; reject discards it; revoke retires the serving text;
  approving an empty draft is the governed retirement;
* self-approval raises — a two-person rule with one person is none;
* a draft the injection guard refuses raises and is NEVER stored (fail-closed
  at the seam — the guard's own efficacy is measured in the limes eval);
* only the APPROVED text resolves; the resolver fails open to none, loudly;
* the chat ROUTE puts the approved overlay into the graph state;
* the reporter appends it under the bundle's header — and a verbatim console
  override suppresses it;
* every language bundle carries the header.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast

import pytest

from tessera.agent import reporter
from tessera.agent.state import AgentState, new_state
from tessera.authz import Actor
from tessera.observability import prompt_overlay
from tessera.settings import LanguageCode

if TYPE_CHECKING:
    from pathlib import Path


def _actor(principal: str) -> Actor:
    return Actor(principal=principal, role="super-admin")


@pytest.fixture(autouse=True)
def _tmp_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(prompt_overlay, "_store_path", lambda: tmp_path / "overlay.json")


# --------------------------------------------------------------------------- #
# The lifecycle
# --------------------------------------------------------------------------- #


def test_propose_stores_an_attributed_draft() -> None:
    state = prompt_overlay.propose_overlay(
        "support-client", "Mentionner la campagne A.", actor=_actor("alice")
    )
    assert state["draft"] == {
        "text": "Mentionner la campagne A.",
        "author": "alice",
        "at": state["draft"]["at"],
    }
    assert state["approved"] is None
    assert state["history"][0]["event"] == "proposed"
    assert state["history"][0]["author"] == "alice"


def test_approval_by_another_person_promotes_and_serves() -> None:
    prompt_overlay.propose_overlay(
        "support-client", "Mentionner la campagne A.", actor=_actor("alice")
    )
    state = prompt_overlay.review_overlay("support-client", "approve", reviewer="bob")
    assert state["draft"] is None
    assert state["approved"]["text"] == "Mentionner la campagne A."
    assert state["approved"]["author"] == "alice"
    assert state["approved"]["approved_by"] == "bob"
    assert prompt_overlay.resolve_prompt_overlay("support-client") == "Mentionner la campagne A."


def test_self_approval_is_refused_and_the_draft_survives() -> None:
    prompt_overlay.propose_overlay("support-client", "Texte.", actor=_actor("alice"))
    with pytest.raises(prompt_overlay.SelfApprovalError):
        prompt_overlay.review_overlay("support-client", "approve", reviewer="alice")
    state = prompt_overlay.load_overlay_state("support-client")
    assert state["draft"] is not None  # nothing was silently consumed
    assert state["approved"] is None
    assert prompt_overlay.resolve_prompt_overlay("support-client") is None


def test_reject_discards_the_draft_and_keeps_the_serving_text() -> None:
    prompt_overlay.propose_overlay("support-client", "V1.", actor=_actor("alice"))
    prompt_overlay.review_overlay("support-client", "approve", reviewer="bob")
    prompt_overlay.propose_overlay("support-client", "V2.", actor=_actor("alice"))
    state = prompt_overlay.review_overlay("support-client", "reject", reviewer="bob")
    assert state["draft"] is None
    assert state["approved"]["text"] == "V1."  # the serving text is untouched


def test_revoke_retires_the_serving_overlay() -> None:
    prompt_overlay.propose_overlay("support-client", "V1.", actor=_actor("alice"))
    prompt_overlay.review_overlay("support-client", "approve", reviewer="bob")
    state = prompt_overlay.review_overlay("support-client", "revoke", reviewer="bob")
    assert state["approved"] is None
    assert prompt_overlay.resolve_prompt_overlay("support-client") is None


def test_approving_an_empty_draft_is_the_governed_retirement() -> None:
    prompt_overlay.propose_overlay("support-client", "V1.", actor=_actor("alice"))
    prompt_overlay.review_overlay("support-client", "approve", reviewer="bob")
    prompt_overlay.propose_overlay("support-client", "", actor=_actor("alice"))
    state = prompt_overlay.review_overlay("support-client", "approve", reviewer="bob")
    assert state["approved"] is None


def test_review_without_a_draft_says_so() -> None:
    with pytest.raises(prompt_overlay.OverlayNotPendingError):
        prompt_overlay.review_overlay("support-client", "approve", reviewer="bob")


def test_an_oversized_draft_is_refused_never_stored() -> None:
    with pytest.raises(ValueError, match="2000"):
        prompt_overlay.propose_overlay("support-client", "x" * 2001, actor=_actor("alice"))
    assert prompt_overlay.load_overlay_state("support-client")["draft"] is None


def test_a_guard_refused_draft_is_refused_never_stored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fail-closed at the seam: the guard says no → raise, and NOTHING lands."""
    from types import SimpleNamespace

    monkeypatch.setattr(
        "tessera.guard.adapter.check_user_input",
        lambda _text, *, actor: SimpleNamespace(
            allowed=False, decisions=(), sanitised_text="", actor=actor
        ),
    )
    with pytest.raises(prompt_overlay.OverlayGuardRefusedError):
        prompt_overlay.propose_overlay("support-client", "texte quelconque", actor=_actor("alice"))
    assert prompt_overlay.load_overlay_state("support-client")["draft"] is None


def test_resolver_fails_open_loudly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def _boom(*_a: object) -> dict[str, object]:
        msg = "store corrupt"
        raise RuntimeError(msg)

    monkeypatch.setattr(prompt_overlay, "load_overlay_state", _boom)
    assert prompt_overlay.resolve_prompt_overlay("support-client") is None
    assert "prompt_overlay" in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# The route seam
# --------------------------------------------------------------------------- #


def test_chat_route_puts_the_approved_overlay_into_the_graph_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from typing import Any

    from starlette.testclient import TestClient

    from tessera.api.main import build_app
    from tessera.api.routes import chat as chat_route

    monkeypatch.setattr(chat_route, "resolve_prompt_overlay", lambda _agent: "Directive approuvée.")

    class _ProbeGraph:
        def __init__(self) -> None:
            self.overlay: object = None

        async def ainvoke(self, state: dict[str, Any], config: object = None) -> object:
            self.overlay = state.get("prompt_overlay")
            msg = "probe: the turn stops here"
            raise RuntimeError(msg)

    probe = _ProbeGraph()
    monkeypatch.setattr(chat_route, "_streaming_graph", lambda: probe)

    async def _no_prior_agent(_conversation_id: object) -> None:
        return None

    monkeypatch.setattr(chat_route, "last_agent_for", _no_prior_agent)
    client = TestClient(build_app())
    response = client.post("/chat", json={"message": "un tour de test"})
    assert response.status_code == 200
    assert "turn.error" in response.text
    assert probe.overlay == "Directive approuvée."


# --------------------------------------------------------------------------- #
# The reporter — appended under the bundle header, never under an override
# --------------------------------------------------------------------------- #


def _chat_state(user_input: str) -> AgentState:
    return new_state(
        conversation_id=uuid.uuid4(),
        turn_id=uuid.uuid4(),
        user_input=user_input,
        language=LanguageCode.FR,
        language_confidence=1.0,
    )


def test_reporter_appends_the_overlay_under_the_bundle_header() -> None:
    prompts = reporter.load_prompts(LanguageCode.FR)
    state = _chat_state("Bonjour")
    state["prompt_overlay"] = "Mentionner les nouveaux horaires."
    system_prompt, _ = reporter._build_synthesis_input(cast("AgentState", state), prompts)
    assert prompts["overlay_header"].strip() in system_prompt
    assert "Mentionner les nouveaux horaires." in system_prompt
    # The overlay sits AFTER the base — the absolute rules keep their position.
    assert system_prompt.index("Règles absolues") < system_prompt.index(
        "Mentionner les nouveaux horaires."
    )


def test_a_console_override_suppresses_the_overlay() -> None:
    prompts = reporter.load_prompts(LanguageCode.FR)
    state = _chat_state("Bonjour")
    state["prompt_overlay"] = "Mentionner les nouveaux horaires."
    state["system_prompt_override"] = "PROMPT EXACT"
    system_prompt, _ = reporter._build_synthesis_input(cast("AgentState", state), prompts)
    assert system_prompt == "PROMPT EXACT"


@pytest.mark.parametrize("language", [LanguageCode.FR, LanguageCode.DE, LanguageCode.EN])
def test_every_bundle_carries_the_overlay_header(language: LanguageCode) -> None:
    assert reporter.load_prompts(language).get("overlay_header", "").strip()


def test_overlay_history_at_t_drops_later_and_unplaceable_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OT-01 (v1.13): the decision history at T is the events ≤ T, nothing else."""
    from datetime import UTC, datetime

    from tessera.observability import agent_prompts as ap

    state = {
        "approved": None,
        "draft": None,
        "history": [
            {"at": "2026-06-01T10:00:00+00:00", "event": "proposed", "author": "op"},
            {"at": "2026-06-15T10:00:00+00:00", "event": "approved", "author": "root"},
            {"event": "rejected", "author": "root"},  # no instant: unplaceable at T
        ],
    }
    monkeypatch.setattr(
        "tessera.observability.prompt_overlay.load_overlay_state", lambda _aid: dict(state)
    )

    live_history = ap._overlay_section("support-client", "fr")["history"]
    assert isinstance(live_history, list)
    assert len(live_history) == 3  # live keeps everything, unplaceable included

    at_t_history = ap._overlay_section(
        "support-client", "fr", until=datetime(2026, 6, 10, tzinfo=UTC)
    )["history"]
    assert isinstance(at_t_history, list)
    assert [e["event"] for e in at_t_history] == ["proposed"]

    assert ap._parse_until("not-a-date") is None  # malformed reads live, never raises
