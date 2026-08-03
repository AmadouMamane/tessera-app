"""Executable wiring for the three customer-account tools."""

from __future__ import annotations

import uuid
from typing import cast

import pytest

from tessera.agent.state import AgentState, ToolCallRecord, new_state
from tessera.agent.workers.account_lookup import run
from tessera.authz import AuthState
from tessera.guard.audit import confirmed_tools, current_auth_state, current_tool_call_counts
from tessera.settings import LanguageCode


def _state(text: str, intent: str) -> AgentState:
    state = new_state(
        conversation_id=uuid.uuid4(),
        turn_id=uuid.uuid4(),
        user_input=text,
        language=LanguageCode.FR,
    )
    state["intents"] = [intent]
    state["plan"] = []
    return state


@pytest.mark.asyncio
async def test_card_block_requires_then_accepts_explicit_control_confirmation() -> None:
    auth_token = current_auth_state.set(AuthState.CUSTOMER)
    counts_token = current_tool_call_counts.set({})
    try:
        pending = await run(_state("Bloquez ma carte 4242", "card_block"))
        pending_call = cast("list[ToolCallRecord]", pending["tool_calls"])[0]
        assert pending_call.tool_name == "card_block"
        assert pending_call.succeeded is False
        assert "Confirmez explicitement" in cast("str", pending["draft_response"])

        current_tool_call_counts.set({})
        confirm_token = confirmed_tools.set({"card_block": "4242"})
        try:
            completed = await run(_state("Je confirme : bloquez ma carte 4242", "card_block"))
        finally:
            confirmed_tools.reset(confirm_token)
    finally:
        current_tool_call_counts.reset(counts_token)
        current_auth_state.reset(auth_token)

    completed_call = cast("list[ToolCallRecord]", completed["tool_calls"])[0]
    assert completed_call.tool_name == "card_block"
    assert completed_call.succeeded is True
    assert "OP-" in cast("str", completed["draft_response"])


@pytest.mark.asyncio
async def test_transaction_search_intent_invokes_the_declared_tool() -> None:
    auth_token = current_auth_state.set(AuthState.CUSTOMER)
    counts_token = current_tool_call_counts.set({})
    try:
        update = await run(_state("Montrez mes dernières transactions", "transaction_search"))
    finally:
        current_tool_call_counts.reset(counts_token)
        current_auth_state.reset(auth_token)

    call = cast("list[ToolCallRecord]", update["tool_calls"])[0]
    assert call.tool_name == "transaction_search"
    assert call.succeeded is True
    assert "Carte VISA" in cast("str", update["draft_response"])
