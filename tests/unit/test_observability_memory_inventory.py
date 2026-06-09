"""Unit tests for memory inventory (ADR 0010, #135)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from tessera.observability.memory_inventory import InventoryItem, summarize_inventory

_NOW = datetime(2026, 6, 9, tzinfo=UTC)


def _item(mid: int, subject: str, kind: str, expires_in_days: int) -> InventoryItem:
    return InventoryItem(
        memory_id=mid,
        subject_id=subject,
        kind=kind,
        text=f"memory {mid}",
        created_at=_NOW,
        expires_at=_NOW + timedelta(days=expires_in_days),
    )


def test_empty() -> None:
    report = summarize_inventory([], now=_NOW)
    assert report.n_memories == 0
    assert report.n_subjects == 0
    assert report.by_kind == {}


def test_counts_by_kind_and_subject() -> None:
    items = [
        _item(1, "alice", "semantic", 365),
        _item(2, "alice", "episodic", 90),
        _item(3, "bob", "semantic", 365),
    ]
    report = summarize_inventory(items, now=_NOW)
    assert report.n_memories == 3
    assert report.n_subjects == 2
    assert report.by_kind == {"semantic": 2, "episodic": 1}


def test_expiring_soon() -> None:
    items = [
        _item(1, "a", "semantic", 5),  # soon
        _item(2, "a", "semantic", 10),  # soon
        _item(3, "a", "semantic", 200),  # not soon
    ]
    report = summarize_inventory(items, now=_NOW, soon_days=30)
    assert report.n_expiring_soon == 2


def test_samples_capped_and_redacted() -> None:
    items = [_item(i, f"subject-{i}", "semantic", 100) for i in range(20)]
    report = summarize_inventory(items, now=_NOW)
    assert len(report.samples) == 8
    assert all(len(s.subject) <= 12 for s in report.samples)
    assert report.samples[0].expires_in_days >= 0
