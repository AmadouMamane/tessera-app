"""`compute_chrome` runs its independent reads concurrently and assembles them in order.

The cockpit bell hangs on all 32 pages and its reads — operator items, incidents, curation,
the signal catalogue, canary verdicts, ledger posture — are independent, so `compute_chrome`
runs them in a threadpool bounded by the slowest read instead of their sum. These tests pin the
three properties that make that safe: the composed output is assembled in the SAME order as the
sequential version (byte-identical, honest-empty preserved), the reads actually overlap, and the
operator-items read that feeds BOTH queue surfaces happens exactly ONCE.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from tessera.observability import chrome

if TYPE_CHECKING:
    import pytest


def _slow(value: Any, delay: float = 0.12) -> Any:
    def fn(*_a: object, **_k: object) -> Any:
        time.sleep(delay)
        return value

    return fn


def test_compute_chrome_assembles_reads_in_order(monkeypatch: pytest.MonkeyPatch) -> None:
    """Badges and notifications keep their sequential order; a ``None`` badge stays omitted."""
    monkeypatch.setattr(chrome, "_queue_halves", lambda: "HALVES")
    monkeypatch.setattr(
        chrome,
        "_queue_badges",
        lambda _now, halves: (
            {"a_traiter": {"count": 1, "tone": "warning"}} if halves == "HALVES" else {}
        ),
    )
    monkeypatch.setattr(chrome, "_incidents_badge", lambda: {"count": 2, "tone": "danger"})
    monkeypatch.setattr(chrome, "_curation_badge", lambda: {"count": 3, "tone": "warning"})
    monkeypatch.setattr(chrome, "_signal_catalog_badge", lambda: None)  # honest-empty → omitted
    monkeypatch.setattr(
        chrome,
        "_queue_notifications",
        lambda _lang, _now, halves: [{"id": "q"}] if halves == "HALVES" else [],
    )
    monkeypatch.setattr(chrome, "_canary_notifications", lambda _lang: [{"id": "canary"}])
    monkeypatch.setattr(chrome, "_ledger_notifications", lambda _lang: [{"id": "ledger"}])

    out = chrome.compute_chrome("fr")

    badges = out["badges"]
    assert isinstance(badges, dict)
    # Badge order: queue badge, incidents, curation — signal_catalog omitted (its read is None).
    assert list(badges.keys()) == ["a_traiter", "incidents", "curation"]
    assert badges["incidents"] == {"count": 2, "tone": "danger"}

    notifications = out["notifications"]
    assert isinstance(notifications, dict)
    items = notifications["items"]
    assert isinstance(items, list)
    # Notification order preserved: queue, then canary, then ledger.
    assert [i["id"] for i in items] == ["q", "canary", "ledger"]
    assert notifications["count"] == 3


def test_compute_chrome_reads_run_concurrently(monkeypatch: pytest.MonkeyPatch) -> None:
    """Six 0.12 s reads finish well under their 0.72 s serial sum — they overlap."""
    monkeypatch.setattr(chrome, "_queue_halves", _slow("HALVES"))
    monkeypatch.setattr(chrome, "_queue_badges", lambda _now, _halves: {})
    monkeypatch.setattr(chrome, "_incidents_badge", _slow(None))
    monkeypatch.setattr(chrome, "_curation_badge", _slow(None))
    monkeypatch.setattr(chrome, "_signal_catalog_badge", _slow(None))
    monkeypatch.setattr(chrome, "_queue_notifications", lambda _lang, _now, _halves: [])
    monkeypatch.setattr(chrome, "_canary_notifications", _slow([]))
    monkeypatch.setattr(chrome, "_ledger_notifications", _slow([]))

    start = time.perf_counter()
    chrome.compute_chrome("fr")
    elapsed = time.perf_counter() - start

    assert elapsed < 0.4, f"reads did not overlap (serial would be ~0.72s): {elapsed:.2f}s"


def test_compute_chrome_reads_operator_items_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """The operator-items read feeds both queue surfaces but must be paid only once."""
    calls: list[int] = []

    def halves() -> str:
        calls.append(1)
        return "HALVES"

    monkeypatch.setattr(chrome, "_queue_halves", halves)
    monkeypatch.setattr(chrome, "_queue_badges", lambda _now, _halves: {})
    monkeypatch.setattr(chrome, "_incidents_badge", lambda: None)
    monkeypatch.setattr(chrome, "_curation_badge", lambda: None)
    monkeypatch.setattr(chrome, "_signal_catalog_badge", lambda: None)
    monkeypatch.setattr(chrome, "_queue_notifications", lambda _lang, _now, _halves: [])
    monkeypatch.setattr(chrome, "_canary_notifications", lambda _lang: [])
    monkeypatch.setattr(chrome, "_ledger_notifications", lambda _lang: [])

    chrome.compute_chrome("fr")

    assert calls == [1], "the shared operator-items read must happen exactly once"
