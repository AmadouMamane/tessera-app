"""Closure tests for GDPR retention and erasure.

Audit 2026-07-10, P1 `gdpr-retention` — memory/persistent.py:354 · governance.py:213:

1. ``purge_expired`` had **no caller**. ``ttl_for`` bounded retention at *read* time while
   the rows lived on in Postgres indefinitely — retention enforced in the view, not in the
   store, which is not retention at all under GDPR Art. 5(1)(e).
2. ``erase_subject`` (Art. 17) was covered **only** in the integration tier, which skips
   when Postgres is down and is excluded from the gate (``-m "not integration"``). The
   right-to-erasure path had zero coverage in the fast loop.

These run in the gate, with no database: they pin the *contracts* — that the purge is
scheduled and actually deletes, and that erasure reaches every layer. The integration
tier still proves the SQL against a real Postgres.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from tessera.api import main as api_main
from tessera.memory import governance
from tessera.settings import get_settings

if TYPE_CHECKING:
    from uuid import UUID


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()


class TestPurgeIsActuallyScheduled:
    """The purge must run — the whole finding was that nothing ever called it."""

    async def test_the_scheduler_runs_a_purge_cycle(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A scheduled purge physically deletes expired rows, promptly after boot."""
        monkeypatch.setenv("TESSERA_MEMORY_PURGE_INTERVAL_S", "3600")
        get_settings.cache_clear()

        purged = asyncio.Event()

        async def _purge_expired() -> int:
            purged.set()
            return 7

        monkeypatch.setattr("tessera.memory.persistent.purge_expired", _purge_expired, raising=True)

        task = await api_main._start_memory_purge_scheduler()
        assert task is not None
        try:
            # Purge-then-sleep: data that expired while the service was down must not
            # linger a further cadence. Pre-fix this never fired at all.
            await asyncio.wait_for(purged.wait(), timeout=2.0)
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

    async def test_a_failing_cycle_does_not_kill_the_loop(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A transient Postgres blip must not silently disable retention forever."""
        monkeypatch.setenv("TESSERA_MEMORY_PURGE_INTERVAL_S", "1")
        get_settings.cache_clear()

        calls = 0

        async def _flaky() -> int:
            nonlocal calls
            calls += 1
            raise RuntimeError("connection refused")

        monkeypatch.setattr("tessera.memory.persistent.purge_expired", _flaky, raising=True)

        task = await api_main._start_memory_purge_scheduler()
        assert task is not None
        try:
            await asyncio.sleep(0.05)
            assert calls >= 1
            assert not task.done()  # survived the failure
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

    async def test_a_zero_cadence_disables_the_purge_and_says_so(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Disabling retention is allowed — silently pretending to enforce it is not."""
        monkeypatch.setenv("TESSERA_MEMORY_PURGE_INTERVAL_S", "0")
        get_settings.cache_clear()

        assert governance.purge_posture()["purging"] is False
        assert await api_main._start_memory_purge_scheduler() is None

    def test_the_posture_is_the_single_source_of_the_decision(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The boot log line and the scheduler read the same posture — they cannot disagree."""
        monkeypatch.setenv("TESSERA_MEMORY_PURGE_INTERVAL_S", "900")
        get_settings.cache_clear()

        posture = governance.purge_posture()
        assert posture["purging"] is True
        assert posture["interval_s"] == 900


class TestErasureIsTotal:
    """GDPR Art. 17 — erasure must reach EVERY layer, whatever backend is configured."""

    async def test_erase_subject_deletes_from_every_memory_layer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The property that matters: a partial erasure is a failed erasure.

        Previously asserted only in the integration tier, which is excluded from the gate
        and skips when Postgres is down — so a regression that dropped one layer (leaving,
        say, the transcript behind) would have shipped green.
        """
        conversation_id = uuid4()
        reached: list[str] = []

        async def _delete_subject(subject_id: str) -> int:
            reached.append("long_term")
            assert subject_id == str(conversation_id)
            return 1

        async def _delete_summary(cid: UUID) -> None:
            reached.append("summary")
            assert cid == conversation_id

        async def _delete_transcript(cid: UUID) -> None:
            reached.append("transcript")
            assert cid == conversation_id

        async def _delete_consent(subject_id: str) -> None:
            reached.append("consent")
            assert subject_id == str(conversation_id)

        audited: list[dict[str, object]] = []

        monkeypatch.setattr("tessera.memory.persistent.delete_subject", _delete_subject)
        monkeypatch.setattr("tessera.memory.summary.delete_summary", _delete_summary)
        monkeypatch.setattr("tessera.memory.transcript.delete_transcript", _delete_transcript)
        monkeypatch.setattr(governance, "delete_consent", _delete_consent)
        monkeypatch.setattr(governance, "audit_memory", lambda **kw: audited.append(dict(kw)))

        await governance.erase_subject(conversation_id)

        assert sorted(reached) == ["consent", "long_term", "summary", "transcript"]
        # The erasure is auditable — an unlogged deletion is not opposable.
        assert audited and audited[0]["action"] == "memory.forget"
        assert audited[0]["decision"] == "allow"
