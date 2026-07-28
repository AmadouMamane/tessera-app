"""The chrome memo: single-flight + short-TTL (ADR 0044 follow-up).

The bell is identical for every viewer at a moment, so a burst of chrome requests — rapid
navigation, the 15 s client poll, several operators — must collapse to ONE six-read fan-out
per worker per window instead of one per request. These tests pin that: a fresh hit skips the
compute, a reset forces it, concurrent callers share a single compute, and languages are keyed
apart.
"""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

from tessera.observability import chrome

if TYPE_CHECKING:
    import pytest

_SENTINEL: dict[str, object] = {"badges": {}, "notifications": {"count": 0, "items": []}}


def test_second_call_within_ttl_is_served_from_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    def fake(_lang: str = "fr") -> dict[str, object]:
        calls.append(1)
        return _SENTINEL

    monkeypatch.setattr(chrome, "_compute_chrome_uncached", fake)
    first = chrome.compute_chrome("fr")
    second = chrome.compute_chrome("fr")
    assert first is second is _SENTINEL
    assert calls == [1], "the second call within the TTL must not recompute"


def test_reset_forces_a_recompute(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []
    monkeypatch.setattr(
        chrome, "_compute_chrome_uncached", lambda _lang="fr": (calls.append(1), _SENTINEL)[1]
    )
    chrome.compute_chrome("fr")
    chrome.reset_chrome_cache()
    chrome.compute_chrome("fr")
    assert calls == [1, 1], "reset must drop the memo so the next call recomputes"


def test_languages_are_cached_apart(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []
    monkeypatch.setattr(
        chrome, "_compute_chrome_uncached", lambda lang="fr": (seen.append(lang), _SENTINEL)[1]
    )
    chrome.compute_chrome("fr")
    chrome.compute_chrome("de")
    chrome.compute_chrome("fr")  # fr still cached
    assert seen == ["fr", "de"], "each language computes once; neither evicts the other"


def test_concurrent_callers_share_one_compute(monkeypatch: pytest.MonkeyPatch) -> None:
    """Single-flight: eight threads hitting a cold memo yield exactly one fan-out."""
    calls: list[int] = []

    def slow(_lang: str = "fr") -> dict[str, object]:
        calls.append(1)
        time.sleep(0.15)  # hold the lock long enough that all threads pile up behind it
        return _SENTINEL

    monkeypatch.setattr(chrome, "_compute_chrome_uncached", slow)

    barrier = threading.Barrier(8)

    def worker() -> None:
        barrier.wait()  # release all eight at once onto the cold cache
        chrome.compute_chrome("fr")

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert calls == [1], f"single-flight failed: {len(calls)} concurrent computes, expected 1"
