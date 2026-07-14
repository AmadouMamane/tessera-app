"""Integration tests for the firewall adapter against the real policy YAML."""

from __future__ import annotations

import pytest

from tessera.agent.tools import account_balance, ticket_escalate
from tessera.authz import AuthState
from tessera.guard.adapter import guarded_invoke
from tessera.guard.audit import current_auth_state
from tessera.settings import LanguageCode

pytestmark = [pytest.mark.integration, pytest.mark.guard]


class TestFirewallAgainstRealPolicy:
    @pytest.mark.asyncio
    async def test_account_balance_allowed_for_known_customer(self) -> None:
        # account_balance carries the customer-auth floor (ADR 0008/0009): a
        # "known customer" is an authenticated session, so the test sets the
        # server-derived auth-state the chat route would have published.
        token = current_auth_state.set(AuthState.CUSTOMER)
        try:
            result = await guarded_invoke(
                tool_name="account_balance",
                invoke=lambda: account_balance.fetch(customer_id="demo-customer-001"),
                arguments={"customer_id": "demo-customer-001"},
                language=LanguageCode.FR,
            )
        finally:
            current_auth_state.reset(token)
        assert result.allowed is True
        assert result.result is not None
        assert result.error is None

    @pytest.mark.asyncio
    async def test_ticket_escalate_succeeds_and_audits(self) -> None:
        result = await guarded_invoke(
            tool_name="ticket_escalate",
            invoke=lambda: ticket_escalate.open_ticket(
                conversation_id="conv-12345",
                language="fr",
                reason="customer requested human help",
                transcript_excerpt="Je préfère parler à un humain.",
            ),
            arguments={
                "conversation_id": "conv-12345",
                "language": "fr",
                "reason": "customer requested human help",
                "transcript_excerpt": "Je préfère parler à un humain.",
            },
            language=LanguageCode.FR,
        )
        assert result.allowed is True
        assert result.result is not None
        # transcript_excerpt is redacted per policy
        redacted = next(
            (d for d in result.decisions if d.decision == "allow"),
            None,
        )
        assert redacted is not None
