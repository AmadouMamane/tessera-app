"""Unit tests for the durable Console (Debug) operator feedback store."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tessera.observability import console_feedback

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def _isolated_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the feedback store at a temp file so tests never touch real state."""
    monkeypatch.setattr(console_feedback, "_state_path", lambda: tmp_path / "console_feedback.json")


def test_record_and_read_roundtrip() -> None:
    fresh = console_feedback.record_console_feedback("conv-1", 0, "up")
    assert fresh == {"0": "up"}
    assert console_feedback.console_feedback("conv-1") == {"0": "up"}


def test_same_rating_toggles_off() -> None:
    console_feedback.record_console_feedback("conv-1", 2, "down")
    cleared = console_feedback.record_console_feedback("conv-1", 2, "down")
    assert cleared == {}
    assert console_feedback.console_feedback("conv-1") == {}


def test_switching_rating_overwrites() -> None:
    console_feedback.record_console_feedback("conv-1", 1, "up")
    fresh = console_feedback.record_console_feedback("conv-1", 1, "down")
    assert fresh == {"1": "down"}


def test_none_clears_entry() -> None:
    console_feedback.record_console_feedback("conv-1", 0, "up")
    fresh = console_feedback.record_console_feedback("conv-1", 0, None)
    assert fresh == {}


def test_conversations_are_isolated() -> None:
    console_feedback.record_console_feedback("conv-a", 0, "up")
    console_feedback.record_console_feedback("conv-b", 0, "down")
    assert console_feedback.console_feedback("conv-a") == {"0": "up"}
    assert console_feedback.console_feedback("conv-b") == {"0": "down"}


def test_unknown_conversation_is_empty() -> None:
    assert console_feedback.console_feedback("nope") == {}
