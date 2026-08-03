"""Transaction search tool — returns recent transactions for a customer.

Bounded by a maximum lookback window (90 days) at the schema level so the
LLM cannot accidentally request a multi-year dump that would breach the
data-minimisation principle of GDPR Art. 5(1)(c).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = [
    "Transaction",
    "TransactionSearchRequest",
    "TransactionSearchResult",
    "search",
]

_MAX_LOOKBACK_DAYS: Final[int] = 90
_MAX_RESULTS: Final[int] = 50


def _today() -> date:
    """Return the day the demo ledger and the default window are anchored on.

    Indirected on purpose: the property this module owes is "the demo set is visible
    whatever the day it is read", and no witness can ask that of a hard-coded
    ``date.today()``.
    """
    return datetime.now(UTC).date()


class TransactionSearchRequest(BaseModel):
    """Input schema for the transaction search tool."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    customer_id: str = Field(min_length=4, max_length=64)
    since: date
    until: date | None = None
    limit: int = Field(default=10, ge=1, le=_MAX_RESULTS)
    direction: Literal["debit", "credit", "both"] = "both"

    @model_validator(mode="after")
    def _check_window(self) -> TransactionSearchRequest:
        upper = self.until or _today()
        if upper < self.since:
            raise ValueError("until must be on or after since")
        if (upper - self.since).days > _MAX_LOOKBACK_DAYS:
            raise ValueError(
                f"window exceeds the {_MAX_LOOKBACK_DAYS}-day data-minimisation "
                "limit; narrow the search range"
            )
        return self


class Transaction(BaseModel):
    """One transaction record."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    posted_at: datetime
    amount: Decimal
    currency: str = Field(min_length=3, max_length=3)
    direction: Literal["debit", "credit"]
    counterparty_masked: str
    label: str


class TransactionSearchResult(BaseModel):
    """Output schema for the transaction search tool."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    customer_id: str
    transactions: list[Transaction]
    truncated: bool = Field(
        description="True when the underlying store had more results than the " "configured limit.",
    )


@dataclass(frozen=True, slots=True)
class _DemoEntry:
    """One demo transaction, positioned RELATIVE to the day the ledger is read."""

    days_ago: int
    at: time
    amount: Decimal
    direction: Literal["debit", "credit"]
    counterparty_masked: str
    label: str


_FR_MONTHS: Final[tuple[str, ...]] = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)

# Demo dataset: a small, deterministic ledger so screenshots reproduce.
#
# The offsets are relative, and that is the whole point. Two ABSOLUTE datetimes used to sit
# here — 2026-05-26 and 2026-05-25 — while the only caller asks for the ninety days ending
# today (``workers/account_lookup.py``) and this schema refuses any wider window. Fixed data
# behind a sliding window carries an expiry date: this ledger was going to lose one of its two
# rows on 2026-08-24 and both on 2026-08-25, after which the agent would have answered "no
# transaction was found in the last 90 days" to every demo customer — a well-formed sentence,
# false, with no error, no log and no probe behind it. Anchoring on the day of the query
# removes the expiry instead of postponing it. Frozen by
# ``tests/unit/test_demo_ledger_does_not_expire.py``.
_DEMO_LEDGER: Final[dict[str, tuple[_DemoEntry, ...]]] = {
    "demo-customer-001": (
        _DemoEntry(
            days_ago=3,
            at=time(11, 12),
            amount=Decimal("-42.30"),
            direction="debit",
            counterparty_masked="MONOPRIX PARIS XX",
            label="Carte VISA XXXX 4242",
        ),
        _DemoEntry(
            days_ago=4,
            at=time(9, 0),
            amount=Decimal("1850.00"),
            direction="credit",
            counterparty_masked="EMPLOYEUR XXXX",
            label="Salaire {month} {year}",
        ),
    ),
}


def _materialise(entry: _DemoEntry, *, anchor: date) -> Transaction:
    """Place one demo entry on the calendar, ``entry.days_ago`` before ``anchor``."""
    posted_at = datetime.combine(anchor - timedelta(days=entry.days_ago), entry.at, tzinfo=UTC)
    return Transaction(
        posted_at=posted_at,
        amount=entry.amount,
        currency="EUR",
        direction=entry.direction,
        counterparty_masked=entry.counterparty_masked,
        label=entry.label.format(month=_FR_MONTHS[posted_at.month - 1], year=posted_at.year),
    )


async def search(
    *,
    customer_id: str,
    since: date,
    until: date | None = None,
    limit: int = 10,
    direction: Literal["debit", "credit", "both"] = "both",
) -> TransactionSearchResult:
    """Return up to ``limit`` transactions for ``customer_id`` in the window."""
    request = TransactionSearchRequest(
        customer_id=customer_id,
        since=since,
        until=until,
        limit=limit,
        direction=direction,
    )
    anchor = _today()
    ledger = [
        _materialise(entry, anchor=anchor) for entry in _DEMO_LEDGER.get(request.customer_id, ())
    ]
    upper = request.until or anchor
    in_window = [
        txn
        for txn in ledger
        if request.since <= txn.posted_at.date() <= upper
        and (request.direction in ("both", txn.direction))
    ]
    truncated = len(in_window) > request.limit
    return TransactionSearchResult(
        customer_id=request.customer_id,
        transactions=in_window[: request.limit],
        truncated=truncated,
    )
