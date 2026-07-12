"""Integration tests for Tier 2 long-term memory, reflector, and erasure (ADR 0007).

Hit a live Postgres with pgvector; embeddings and the extraction LLM are mocked
so the tests are deterministic and offline. The long-term table is recreated at
a small vector dimension to keep the fixtures light. Skips when no DB.
"""

from __future__ import annotations

import hashlib
import struct
import uuid
from typing import TYPE_CHECKING

import psycopg
import pytest

from tessera.agent.state import ConversationMessage
from tessera.authz import Actor
from tessera.memory import scope_for
from tessera.memory.governance import (
    consent_allows,
    ensure_consent_schema,
    erase_subject,
    set_consent,
)
from tessera.memory.persistent import (
    PersistentBackend,
    delete_subject,
    ensure_longterm_schema,
    purge_expired,
    search_memory,
    upsert_memory,
)
from tessera.memory.protocol import EntityLedger, TurnRecord
from tessera.memory.summary import ensure_summary_schema, load_summary, save_summary
from tessera.memory.transcript import (
    append_messages,
    ensure_transcript_schema,
    load_transcript,
)
from tessera.settings import LanguageCode, get_settings

#: The verified operator these integration tests act as. An erasure with no author is not
#: a test of the erasure this product ships — the parameter has no default, on purpose.
_A_TEST_OPERATOR = Actor(principal="integration@bank.eu", role="admin")

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tessera.llm.router import ChatMessage

pytestmark = pytest.mark.integration

_DIM = 8


def _vec(text: str) -> list[float]:
    """Deterministic small embedding: identical text → identical vector."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return [struct.unpack_from(">H", digest, i * 2)[0] / 65535.0 for i in range(_DIM)]


async def _fake_embed(texts: Sequence[str]) -> list[list[float]]:
    return [_vec(t) for t in texts]


class _FactExtractor:
    """Fake cheap model that emits two durable facts."""

    name = "fake"
    model = "fake"

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0.2,
        max_output_tokens: int | None = None,
    ):
        from tessera.llm.router import ChatResponse

        return ChatResponse(
            content="Le client préfère le français.\nLe client détient un Crédit Aurore.",
            model="fake",
            input_tokens=1,
            output_tokens=1,
            finish_reason="stop",
        )

    def stream_chat(self, messages, *, temperature=0.2, max_output_tokens=None):
        raise NotImplementedError


@pytest.fixture
async def _pg(monkeypatch: pytest.MonkeyPatch) -> None:
    dsn = str(get_settings().postgres.dsn)
    try:
        conn = await psycopg.AsyncConnection.connect(dsn, connect_timeout=2)
    except (psycopg.OperationalError, OSError) as exc:
        pytest.skip(f"Postgres unavailable: {exc}")
    # Recreate the long-term table at the small test dimension.
    await conn.execute("DROP TABLE IF EXISTS long_term_memory;")
    await conn.commit()
    await conn.close()
    monkeypatch.setattr("tessera.retrieval.embeddings.embedding_dimension", lambda: _DIM)
    monkeypatch.setattr("tessera.retrieval.embeddings.embed", _fake_embed)
    await ensure_longterm_schema()
    await ensure_consent_schema()
    await ensure_summary_schema()
    await ensure_transcript_schema()


@pytest.mark.usefixtures("_pg")
class TestLongTermStore:
    async def test_upsert_and_search(self) -> None:
        subject = str(uuid.uuid4())
        try:
            await upsert_memory(
                subject_id=subject,
                kind="semantic",
                text="Le client préfère le français.",
                entities=EntityLedger(),
            )
            hits = await search_memory(
                subject_id=subject, query="Le client préfère le français.", top_k=5
            )
            assert any("français" in h.text for h in hits)
            assert hits[0].score > 0.99  # identical text → ~1.0 cosine
        finally:
            await delete_subject(subject)

    async def test_dedup_upserts_in_place(self) -> None:
        subject = str(uuid.uuid4())
        try:
            for _ in range(3):
                await upsert_memory(
                    subject_id=subject,
                    kind="semantic",
                    text="Fait identique répété.",
                    entities=EntityLedger(),
                )
            hits = await search_memory(subject_id=subject, query="Fait identique répété.", top_k=10)
            assert len(hits) == 1  # de-duplicated, not appended
        finally:
            await delete_subject(subject)

    async def test_delete_subject_removes_all(self) -> None:
        subject = str(uuid.uuid4())
        await upsert_memory(
            subject_id=subject, kind="semantic", text="à supprimer", entities=EntityLedger()
        )
        deleted = await delete_subject(subject)
        assert deleted >= 1
        assert await search_memory(subject_id=subject, query="à supprimer", top_k=5) == []

    async def test_purge_expired_runs(self) -> None:
        assert await purge_expired() >= 0


@pytest.mark.usefixtures("_pg")
class TestReflectorAndConsent:
    async def test_consent_gate_blocks_write(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("tessera.llm.router.get_summary_backend", lambda: _FactExtractor())
        from tessera.memory.reflector import form_memories

        conv = uuid.uuid4()
        scope = scope_for(conv, LanguageCode.FR)
        turn = TurnRecord(
            user_input="je préfère le français",
            final_response="entendu",
            messages=[],
            language=LanguageCode.FR,
        )
        # No consent → nothing written.
        await form_memories(scope, turn)
        assert await search_memory(subject_id=scope.subject_id, query="français", top_k=5) == []

    async def test_reflector_writes_with_consent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("tessera.llm.router.get_summary_backend", lambda: _FactExtractor())
        from tessera.memory.reflector import form_memories

        conv = uuid.uuid4()
        scope = scope_for(conv, LanguageCode.FR)
        try:
            await set_consent(scope.subject_id, granted=True)
            assert await consent_allows(scope.subject_id) is True
            turn = TurnRecord(
                user_input="je préfère le français",
                final_response="entendu",
                messages=[],
                language=LanguageCode.FR,
            )
            await form_memories(scope, turn)
            hits = await search_memory(subject_id=scope.subject_id, query="français", top_k=5)
            assert any("français" in h.text for h in hits)
        finally:
            await erase_subject(conv, actor=_A_TEST_OPERATOR)


@pytest.mark.usefixtures("_pg")
class TestErasure:
    async def test_erase_subject_is_total(self) -> None:
        conv = uuid.uuid4()
        subject = str(conv)
        await upsert_memory(
            subject_id=subject, kind="semantic", text="souvenir", entities=EntityLedger()
        )
        await save_summary(conv, "un résumé", EntityLedger(amounts=("100 €",)))
        await append_messages(
            conv, uuid.uuid4(), [ConversationMessage(role="user", content="bonjour")]
        )
        await set_consent(subject, granted=True)

        await erase_subject(conv, actor=_A_TEST_OPERATOR)

        assert await search_memory(subject_id=subject, query="souvenir", top_k=5) == []
        summary, _ = await load_summary(conv)
        assert summary is None
        assert await load_transcript(conv) == []
        # Consent row cleared → falls back to the conservative default (False).
        assert await consent_allows(subject) is False


@pytest.mark.usefixtures("_pg")
class TestPersistentBackendRecall:
    async def test_load_includes_screened_long_term(self) -> None:
        conv = uuid.uuid4()
        scope = scope_for(conv, LanguageCode.FR)
        backend = PersistentBackend(history_window=2, top_k=5)
        try:
            await upsert_memory(
                subject_id=scope.subject_id,
                kind="semantic",
                text="Le client préfère le français.",
                entities=EntityLedger(),
            )
            ctx = await backend.load(
                scope=scope,
                messages=[ConversationMessage(role="user", content="bonjour")],
                query="Le client préfère le français.",
            )
            assert any("français" in item.text for item in ctx.long_term)
        finally:
            await erase_subject(conv, actor=_A_TEST_OPERATOR)
