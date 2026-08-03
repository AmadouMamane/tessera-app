"""Zep adapter — long-term memory delegated to Zep (ADR 0007).

Recency stays local (:class:`WindowBackend`); cross-session memory is delegated
to Zep, with the ``subject_id`` used as the Zep session/user key. Requires the
``memory-zep`` extra. Targets Zep's documented async client; result access is
defensive across client versions.
"""

from __future__ import annotations

import os
import sys
from dataclasses import replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final

from tessera.authz import Actor
from tessera.memory import governance
from tessera.memory.adapters import MissingMemoryExtraError, required_env
from tessera.memory.protocol import EntityLedger, MemoryContext, MemoryItem
from tessera.memory.window import WindowBackend
from tessera.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tessera.agent.state import ConversationMessage
    from tessera.memory.protocol import MemoryScope, TurnRecord

#: Who screens a recalled memory, and who reads it. Both named, never defaulted (ADR 0024).
_MEMORY_READ_ACTOR: Final = Actor.system("memory-read-screen")
_TURN_ACTOR: Final = Actor.system("agent-turn")

__all__ = ["ZepBackend"]


class ZepBackend(WindowBackend):
    """Long-term memory backed by Zep; recency by the local window."""

    def __init__(self, *, history_window: int | None = None) -> None:
        """Initialise the Zep client, or fail with an install hint."""
        super().__init__(history_window=history_window)
        try:
            from zep_python.client import AsyncZep
        except ImportError as exc:
            raise MissingMemoryExtraError(
                backend="zep", package="zep_python", extra="memory-zep"
            ) from exc
        settings = get_settings()
        # `AsyncZep(api_key="")` is what stood here, under a comment saying the client "reads
        # them itself". An explicit empty string does not defer to the environment — it
        # OVERRIDES it. This backend authenticated as nobody, every call failed, and every
        # failure was swallowed into an empty recall by the `except Exception` below.
        api_key = required_env(
            "ZEP_API_KEY",
            backend="zep",
            why="It is the credential Zep authenticates this deployment with; without it every "
            "call fails and long-term memory silently returns nothing.",
        )
        base_url = os.environ.get("ZEP_API_URL", "").strip()
        self._client = AsyncZep(api_key=api_key, **({"base_url": base_url} if base_url else {}))
        self._top_k = settings.memory.long_term_top_k

    async def load(
        self,
        *,
        scope: MemoryScope,
        messages: Sequence[ConversationMessage],
        query: str,
    ) -> MemoryContext:
        """Recent window locally; long-term recall from Zep search."""
        base = await super().load(scope=scope, messages=messages, query=query)
        long_term: list[MemoryItem] = []
        try:
            found = await self._client.memory.search_sessions(
                text=query, user_id=scope.subject_id, limit=self._top_k
            )
            results = getattr(found, "results", found) or []
            for entry in results:
                text = getattr(getattr(entry, "message", None), "content", "") or ""
                long_term.append(
                    MemoryItem(
                        kind="semantic",
                        text=str(text),
                        entities=EntityLedger(),
                        score=float(getattr(entry, "score", 0.0) or 0.0),
                        created_at=datetime.now(UTC),
                    )
                )
        except Exception as exc:  # recall must never break a turn
            sys.stderr.write(f"tessera.memory.zep: search failed: {exc}\n")
        return MemoryContext(
            recent_verbatim=base.recent_verbatim,
            long_term=_screened(long_term, subject_id=scope.subject_id, engine="zep"),
        )

    async def record(self, *, scope: MemoryScope, turn: TurnRecord) -> None:
        """Persist the finished turn to the subject's Zep session."""
        try:
            await self._client.memory.add(
                session_id=scope.subject_id,
                messages=[{"role": m.role, "content": m.content} for m in turn.messages],
            )
        except Exception as exc:
            sys.stderr.write(f"tessera.memory.zep: add failed: {exc}\n")

    async def forget(self, *, scope: MemoryScope) -> None:
        """Delete the subject's Zep session (GDPR Art. 17)."""
        try:
            await self._client.memory.delete(session_id=scope.subject_id)
        except Exception as exc:
            sys.stderr.write(f"tessera.memory.zep: delete failed: {exc}\n")


def _screened(items: list[MemoryItem], *, subject_id: str, engine: str) -> list[MemoryItem]:
    """Screen recalled memories exactly as the native backend does.

    Poisoning is not a native-only risk, and an external engine is MORE exposed, not less: its
    store is written by a component Tessera does not own.

    `PersistentBackend._recall` has screened on read since ADR 0007 (anti-poisoning) and audited
    the read since ADR 0024. These adapters did neither: text came back from a third-party store
    and went straight into the prompt, unscreened, unmasked and unrecorded — so a memory could
    carry an injected instruction or a residual PAN, and the audit trail said nothing had been
    read at all.
    """
    kept: list[MemoryItem] = []
    for item in items:
        result = governance.screen_memory(item.text, actor=_MEMORY_READ_ACTOR)
        if result.allowed:
            kept.append(replace(item, text=result.text))
    governance.audit_memory(
        action="memory.read",
        subject_id=subject_id,
        decision="allow",
        rationale=f"{engine}: recalled {len(kept)}/{len(items)} item(s) after screening",
        actor=_TURN_ACTOR,
    )
    return kept
