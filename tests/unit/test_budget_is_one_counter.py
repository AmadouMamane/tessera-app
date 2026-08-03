"""ADR 0034 says "one org-wide daily breaker". There were N of them, one per worker.

Each process built its own :class:`BudgetTracker`, accumulated in memory, and rewrote the
whole file from that memory on every record. Nobody re-read. So with ``api.workers = 4`` the
day total on disk was whichever worker wrote last, each worker's ceiling check saw only its
own spend, and the real ceiling was four times the configured one — in last-writer-wins, so
the number on the dashboard was not even the maximum.

The counter is now read-modify-written under an OS lock, which is the scope a
``threading.Lock`` never had.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from tessera.llm.budget import BudgetTracker

if TYPE_CHECKING:
    from pathlib import Path

_A_MILLION = 1_000_000


def _record(tracker: BudgetTracker, output_tokens: int) -> None:
    tracker.record(
        backend="openai",
        model="gpt-5.5",
        input_tokens=0,
        output_tokens=output_tokens,
    )


def test_two_workers_share_one_day_total(tmp_path: Path) -> None:
    path = tmp_path / "budget.json"
    worker_a = BudgetTracker(persist_path=path)
    worker_b = BudgetTracker(persist_path=path)

    _record(worker_a, _A_MILLION)
    _record(worker_b, _A_MILLION)

    # gpt-5.5 output is 8.80 EUR per million tokens: two million tokens is 17.60, whichever
    # worker is asked. Before the fix each answered 8.80 — and a ceiling of 10 EUR would have
    # let both keep spending.
    for worker in (worker_a, worker_b):
        snapshot = worker.snapshot()
        assert snapshot.day_output_tokens == 2 * _A_MILLION
        assert snapshot.day_cost_eur == Decimal("17.60")


def test_a_third_reader_sees_what_the_others_spent(tmp_path: Path) -> None:
    """The dashboard is a reader too, and it was reading one worker's share."""
    path = tmp_path / "budget.json"
    _record(BudgetTracker(persist_path=path), _A_MILLION)
    _record(BudgetTracker(persist_path=path), _A_MILLION)

    observer = BudgetTracker(persist_path=path)
    assert observer.snapshot().day_cost_eur == Decimal("17.60")


def test_a_tracker_with_no_persistence_still_counts_its_own(tmp_path: Path) -> None:
    """The in-memory mode (tests, ephemeral runs) must not have been broken by the locking."""
    tracker = BudgetTracker(persist_path=None)
    _record(tracker, _A_MILLION)
    assert tracker.snapshot().day_cost_eur == Decimal("8.80")


def test_an_unreadable_budget_file_is_reported_rather_than_read_as_zero(tmp_path: Path) -> None:
    """A breaker reading zero because it lost its file is not a breaker reading zero."""
    path = tmp_path / "budget.json"
    path.write_text("{ this is not json", encoding="utf-8")

    tracker = BudgetTracker(persist_path=path)
    snapshot = tracker.snapshot()

    assert snapshot.degraded is True
    assert snapshot.day_cost_eur == Decimal("0")


def test_a_healthy_tracker_is_not_degraded(tmp_path: Path) -> None:
    """Proves the flag means something — it is not simply always on."""
    tracker = BudgetTracker(persist_path=tmp_path / "budget.json")
    _record(tracker, 1_000)
    assert tracker.snapshot().degraded is False
