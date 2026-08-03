"""The demo ledger must be visible whatever day it is read.

Fixed data behind a sliding window carries an expiry date. ``transaction_search`` pinned two
transactions to 2026-05-26 and 2026-05-25; ``account_lookup`` asks for the ninety days ending
today and the schema refuses anything wider. Computed, the demo customer was going to lose one
of two rows on **2026-08-24** and both on **2026-08-25**, after which every demo conversation
would have answered "Aucune opération n'a été trouvée sur les 90 derniers jours" — well formed,
false, and produced with no error, no log and no probe.

Two witnesses, deliberately of different kinds:

* an **executable** one that runs the real worker on a sweep of calendar days, including the
  two the audit computed and dates far enough out that nobody will re-derive them;
* an **algebraic** one that reads the worker's own window and the ledger's own offsets, and
  therefore covers every day rather than the handful swept.

And a third that proves the first two can go red: the "no transaction" branch is still
reachable, so a green sweep means the ledger was found, not that the branch disappeared.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, cast

import pytest

from tessera.agent.state import AgentState, new_state
from tessera.agent.tools import transaction_search
from tessera.agent.workers import account_lookup
from tessera.authz import AuthState
from tessera.guard.audit import current_auth_state, current_tool_call_counts
from tessera.settings import LanguageCode

if TYPE_CHECKING:
    from collections.abc import Iterator

#: The days the sweep visits. The first two are the ones the audit computed; the rest are
#: chosen to cross a month end, a year end and a leap day, and to sit far beyond any date a
#: reader of this file will be around to notice.
_SWEEP: tuple[date, ...] = (
    date(2026, 8, 24),
    date(2026, 8, 25),
    date(2026, 12, 31),
    date(2027, 1, 1),
    date(2028, 2, 29),
    date(2036, 8, 3),
    date(2099, 1, 2),
)


def _frozen_date(day: date) -> type[date]:
    """Return a ``date`` subclass whose ``today()`` is ``day``."""

    class _Frozen(date):
        @classmethod
        def today(cls) -> date:
            return day

    return _Frozen


def _state(text: str) -> AgentState:
    state = new_state(
        conversation_id=uuid.uuid4(),
        turn_id=uuid.uuid4(),
        user_input=text,
        language=LanguageCode.FR,
    )
    state["intents"] = ["transaction_search"]
    state["plan"] = []
    return state


@pytest.fixture
def _as_customer() -> Iterator[None]:
    """Run inside the authenticated posture the transaction tool requires."""
    auth_token = current_auth_state.set(AuthState.CUSTOMER)
    counts_token = current_tool_call_counts.set({})
    try:
        yield
    finally:
        current_tool_call_counts.reset(counts_token)
        current_auth_state.reset(auth_token)


@pytest.mark.parametrize("day", _SWEEP, ids=lambda d: d.isoformat())
@pytest.mark.asyncio
@pytest.mark.usefixtures("_as_customer")
async def test_the_worker_finds_the_demo_ledger_on_any_day(
    monkeypatch: pytest.MonkeyPatch,
    day: date,
) -> None:
    monkeypatch.setattr(transaction_search, "_today", lambda: day)
    monkeypatch.setattr(account_lookup, "date", _frozen_date(day))

    update = await account_lookup.run(_state("Montrez-moi mes dernières opérations"))

    draft = cast("str", update["draft_response"])
    assert draft != account_lookup._TRANSACTIONS_NONE[LanguageCode.FR]
    # Header plus one line per demo transaction.
    assert len(draft.splitlines()) == 1 + len(transaction_search._DEMO_LEDGER["demo-customer-001"])
    assert "Carte VISA" in draft


@pytest.mark.parametrize("day", _SWEEP, ids=lambda d: d.isoformat())
def test_the_ledger_labels_follow_the_day_they_are_posted_on(day: date) -> None:
    """A salary line dated in December must not still read "Salaire mai 2026"."""
    entries = transaction_search._DEMO_LEDGER["demo-customer-001"]
    salary = next(entry for entry in entries if entry.direction == "credit")
    posted = transaction_search._materialise(salary, anchor=day)
    expected_month = transaction_search._FR_MONTHS[posted.posted_at.month - 1]
    assert posted.label == f"Salaire {expected_month} {posted.posted_at.year}"


def test_every_demo_entry_sits_inside_the_window_the_worker_asks_for() -> None:
    """The general claim the sweep only demonstrates on seven days.

    Read from the two modules rather than restated: the worker's lookback and the ledger's
    own offsets. Nothing here can drift out of date, because there is no date in it.
    """
    offsets = [
        entry.days_ago for entries in transaction_search._DEMO_LEDGER.values() for entry in entries
    ]
    assert offsets, "an empty ledger would make every other assertion here vacuous"
    assert max(offsets) < account_lookup._LOOKBACK_DAYS
    assert max(offsets) <= transaction_search._MAX_LOOKBACK_DAYS
    assert min(offsets) >= 0  # a transaction posted in the future is not "recent activity"


@pytest.mark.asyncio
async def test_the_empty_answer_is_still_reachable() -> None:
    """Proves the sweep is green because the ledger was found, not because it cannot fail."""
    result = await transaction_search.search(
        customer_id="no-such-customer",
        since=date(2026, 1, 1),
        until=date(2026, 3, 1),
    )
    assert result.transactions == []


@pytest.mark.asyncio
async def test_a_stale_window_still_returns_nothing() -> None:
    """The window filter is real: anchoring on today did not make every query match."""
    anchor = datetime.now(UTC).date()
    result = await transaction_search.search(
        customer_id="demo-customer-001",
        since=anchor - timedelta(days=80),
        until=anchor - timedelta(days=30),
    )
    assert result.transactions == []
