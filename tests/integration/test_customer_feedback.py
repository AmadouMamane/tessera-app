"""Integration tests for the customer CSAT store (ADR 0041).

These hit a live Postgres. Tagged ``integration`` and skip cleanly when no database is
reachable, so the fast unit loop is never blocked. Each test uses a fresh agent id so its
counts are isolated from other rows in the shared dev store.
"""

from __future__ import annotations

import uuid

import psycopg
import pytest

from tessera.observability.agent_synthese import _fetch_csat
from tessera.observability.customer_feedback import (
    ensure_customer_feedback_schema,
    record_customer_feedback,
)

pytestmark = pytest.mark.integration


@pytest.fixture
async def _schema() -> None:
    """Ensure the customer-feedback schema exists, or skip when Postgres is unavailable."""
    from tessera.settings import get_settings

    dsn = str(get_settings().postgres.dsn)
    try:
        conn = await psycopg.AsyncConnection.connect(dsn, connect_timeout=2)
        await conn.close()
    except (psycopg.OperationalError, OSError) as exc:
        pytest.skip(f"Postgres unavailable: {exc}")
    await ensure_customer_feedback_schema()


@pytest.mark.usefixtures("_schema")
class TestCustomerFeedbackRoundTrip:
    async def test_real_votes_count_and_test_votes_are_excluded(self) -> None:
        agent = f"csat-{uuid.uuid4().hex[:10]}"
        for _ in range(8):
            await record_customer_feedback(
                uuid.uuid4(), uuid.uuid4(), agent_id=agent, rating="up", synthetic=False
            )
        for _ in range(2):
            await record_customer_feedback(
                uuid.uuid4(), uuid.uuid4(), agent_id=agent, rating="down", synthetic=False
            )
        # Votes on TEST turns must not move the real CSAT (ADR 0040/0041).
        for _ in range(5):
            await record_customer_feedback(
                uuid.uuid4(), uuid.uuid4(), agent_id=agent, rating="up", synthetic=True
            )
        assert await _fetch_csat(agent, None) == {"up": 8, "total": 10}

    async def test_a_revote_updates_rather_than_piles_rows(self) -> None:
        agent = f"csat-{uuid.uuid4().hex[:10]}"
        conv, turn = uuid.uuid4(), uuid.uuid4()
        await record_customer_feedback(conv, turn, agent_id=agent, rating="up", synthetic=False)
        await record_customer_feedback(conv, turn, agent_id=agent, rating="down", synthetic=False)
        # One rated turn, one row: the vote flipped to "down", not a second row.
        assert await _fetch_csat(agent, None) == {"up": 0, "total": 1}
