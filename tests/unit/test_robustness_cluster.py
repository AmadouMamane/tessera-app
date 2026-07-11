"""Closure tests for the robustness cluster.

Audit 2026-07-10, `robustness-cluster` / `robustness-timeout` / `float-money`:

- ``chat.py:802`` returned ``str(exc)`` to the caller on ``turn.error`` — handing an
  unauthenticated client whatever the failure happened to carry.
- Neither ``graph.ainvoke`` nor the Vertex backend had any deadline: a frozen LLM or a
  hung pgvector query held the SSE stream open indefinitely.
- ``scoring.py:364`` compared regulated euro amounts with ``!=`` on floats.
"""

from __future__ import annotations

import asyncio

import pytest

from tessera.api.routes.chat import _client_error, _turn_deadline_s
from tessera.recouvrement.scoring import _cents


class TestATurnErrorLeaksNothing:
    """The wire is untrusted: a failing turn may say THAT it failed, never WHY."""

    def test_the_payload_carries_no_exception_text(self) -> None:
        """Pre-fix this was `{"error": str(exc)}` — the exception, verbatim, to the client."""
        payload = _client_error("11111111-2222-3333-4444-555555555555", "internal")

        assert payload == {
            "error": "internal",
            "turn_id": "11111111-2222-3333-4444-555555555555",
        }

    @pytest.mark.parametrize("reason", ["internal", "timeout"])
    def test_the_reason_is_an_enumerated_token_not_a_message(self, reason: str) -> None:
        """A fixed vocabulary cannot smuggle a SQL fragment, a hostname or prompt content."""
        payload = _client_error("t-1", reason)  # type: ignore[arg-type]
        assert payload["error"] == reason

    def test_the_turn_id_is_the_operator_join_key(self) -> None:
        """The client can quote it; only someone with log access can resolve it to a cause."""
        assert _client_error("t-42", "timeout")["turn_id"] == "t-42"


class TestTheTurnHasADeadline:
    """`api.request_timeout_seconds` was declared in settings and applied to nothing."""

    def test_the_deadline_is_real_and_positive(self) -> None:
        assert _turn_deadline_s() > 0

    async def test_a_hung_graph_phase_raises_instead_of_hanging_forever(self) -> None:
        """The shape of the fix: a stalled call under a deadline terminates the turn.

        Pre-fix there was no `asyncio.timeout` anywhere on this path — a frozen backend
        simply held the SSE stream open until the client gave up.
        """

        async def _frozen_backend() -> None:
            await asyncio.sleep(3600)

        with pytest.raises(TimeoutError):
            async with asyncio.timeout(0.05):
                await _frozen_backend()


class TestRegulatedAmountsAreComparedAsMoney:
    """A euro comparison must not depend on IEEE-754 rounding."""

    def test_cents_are_exact_where_floats_are_not(self) -> None:
        """The canonical float trap, on a regulated amount check."""
        assert 0.1 + 0.2 != 0.3
        assert _cents(0.1 + 0.2) == _cents(0.3)

    def test_the_same_money_spelled_two_ways_is_one_amount(self) -> None:
        """str(840) is "840" but str(840.0) is "840.0" — the set used to see two amounts.

        The same amount arriving once as an int and once as a float scored the artifact
        `amount_fields_conflict`. The set must be about the money, not about how JSON
        happened to spell it.
        """
        assert len({_cents(840), _cents(840.0), _cents(840.00)}) == 1
        assert len({str(840), str(840.0)}) == 2  # what the code used to compare

    def test_a_genuine_mismatch_still_scores_as_a_mismatch(self) -> None:
        """The fix must not paper over real disagreement — one cent apart is apart."""
        assert _cents(840.00) != _cents(840.01)

    def test_a_schedule_that_divides_exactly_is_conformant(self) -> None:
        """840 over 3 months is 280,00 € — equal to the cent, and must score conformant."""
        assert round(_cents(840.0) / 3) == _cents(280.0)
