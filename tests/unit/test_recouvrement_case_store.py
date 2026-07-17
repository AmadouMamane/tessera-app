"""Lot 9 — the durable recouvrement case queue (create-the-source).

The queue is REAL: durable, mutable, queryable. Its initial content is a
declared seed book (every case flagged ``seed: true``) and RC-2048 mirrors the
historical mock so the workflow's ground truth survives the migration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tessera.observability import recouvrement_case_store as store

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def _wire(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(store, "_cases_path", lambda: tmp_path / "recouvrement_cases.json")


def test_first_read_materialises_the_declared_seed_book() -> None:
    cases = store.load_cases()
    assert all(c.get("seed") is True for c in cases)
    rc = store.get_case("RC-2048")
    # RC-2048 mirrors the historical mock exactly — the workflow's ground truth.
    assert rc["amount_due"] == 840.0
    assert rc["days_late"] == 32
    assert rc["missed_promise_date"] == "2026-06-12"
    assert rc["contact_window_start"] == "08:00"
    # And the store is durable: the file exists after the first read.
    assert store._cases_path().exists()


def test_counters_tally_the_real_statuses() -> None:
    counters = store.queue_counters()
    assert counters["total"] == len(store.load_cases())
    assert counters["open"] == counters["total"] - counters["traite"]
    assert sum(counters[s] for s in store.STATUSES) == counters["total"]


def test_unknown_case_is_a_loud_refusal_never_a_fabricated_dossier() -> None:
    with pytest.raises(store.CaseNotFoundError):
        store.get_case("RC-9999")


def test_status_transition_is_attributed_and_durable() -> None:
    moved = store.set_case_status("RC-2048", "traite", by="julie@bank.eu")
    assert moved["status"] == "traite"
    assert moved["updated_by"] == "julie@bank.eu"
    # Durable: a fresh read sees it; the counters move with it.
    assert store.get_case("RC-2048")["status"] == "traite"
    assert store.queue_counters()["traite"] >= 2
    with pytest.raises(ValueError, match="closed"):
        store.set_case_status("RC-2048", "bogus", by="julie@bank.eu")
    with pytest.raises(store.CaseNotFoundError):
        store.set_case_status("RC-9999", "traite", by="julie@bank.eu")


def test_the_workflow_snapshot_derives_from_the_store() -> None:
    """`_case_for` reads the store — the single-mock era is over."""
    from tessera.agent.recouvrement import _case_for

    snap = _case_for("RC-2055")
    assert snap.case_id == "RC-2055"
    assert snap.client == "M. K."
    assert snap.amount_due == 430.0
    # Unknown ids keep the historical graph fallback (RC-2048), loudly NOT a crash.
    assert _case_for("RC-0000").case_id == "RC-2048"
    # The FR amount label format survives (the historical "840,00 €").
    assert _case_for("RC-2048").amount_due_label == "840,00 €"
