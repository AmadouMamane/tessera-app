"""Unit tests for tool input/output schemas — exercised through the workers'
corpus generation paths."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from tessera.agent.tools import account_balance, loan_simulate, transaction_search


class TestAccountBalance:
    @pytest.mark.asyncio
    async def test_fetch_returns_demo_record(self) -> None:
        balance = await account_balance.fetch(customer_id="demo-customer-001")
        assert balance.currency == "EUR"
        assert balance.amount > Decimal("0")
        assert balance.iban_masked.startswith("FRXX")

    @pytest.mark.asyncio
    async def test_unknown_customer_raises(self) -> None:
        with pytest.raises(KeyError):
            await account_balance.fetch(customer_id="not-a-customer")


class TestLoanSimulator:
    @pytest.mark.asyncio
    async def test_payment_is_deterministic(self) -> None:
        result_a = await loan_simulate.compute(amount=200_000, years=20, rate=3.5)
        result_b = await loan_simulate.compute(amount=200_000, years=20, rate=3.5)
        assert result_a.monthly_payment == result_b.monthly_payment

    @pytest.mark.asyncio
    async def test_total_repayment_exceeds_principal(self) -> None:
        result = await loan_simulate.compute(amount=100_000, years=25, rate=4.0)
        assert result.total_repayment > result.amount
        assert result.total_interest == result.total_repayment - result.amount

    @pytest.mark.asyncio
    async def test_zero_rate_yields_simple_division(self) -> None:
        result = await loan_simulate.compute(amount=120_000, years=10, rate=0.1)
        assert result.monthly_payment > Decimal("0")


class TestTransactionSearch:
    @pytest.mark.asyncio
    async def test_window_too_wide_is_rejected(self) -> None:
        with pytest.raises(Exception):  # noqa: B017  pydantic validation error
            await transaction_search.search(
                customer_id="demo-customer-001",
                since=date(2020, 1, 1),
                until=date(2026, 1, 1),
            )

    @pytest.mark.asyncio
    async def test_in_window_returns_demo_ledger(self) -> None:
        # The window is relative because the ledger is. Asking for May 2026 used to be the
        # way to see the demo data and is now the way to see nothing — see
        # `tests/unit/test_demo_ledger_does_not_expire.py` for why that swap is the fix.
        today = datetime.now(UTC).date()
        result = await transaction_search.search(
            customer_id="demo-customer-001",
            since=today - timedelta(days=30),
        )
        assert result.customer_id == "demo-customer-001"
        assert len(result.transactions) >= 1
