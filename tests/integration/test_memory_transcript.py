"""Integration tests for the durable conversation transcript (ADR 0007, Mechanism A).

These hit a live Postgres. They are tagged ``integration`` and skip cleanly when
no database is reachable, so the fast unit loop is never blocked.
"""

from __future__ import annotations

import uuid

import psycopg
import pytest

from tessera.agent.state import ConversationMessage
from tessera.memory.transcript import (
    append_messages,
    ensure_transcript_schema,
    list_conversations,
    load_transcript,
)

pytestmark = pytest.mark.integration


@pytest.fixture
async def _schema() -> None:
    """Ensure the transcript schema exists, or skip when Postgres is unavailable.

    A short-timeout probe first so the skip is fast (~2s) rather than waiting on
    the connection pool's default 30s timeout when no database is running.
    """
    from tessera.settings import get_settings

    dsn = str(get_settings().postgres.dsn)
    try:
        conn = await psycopg.AsyncConnection.connect(dsn, connect_timeout=2)
        await conn.close()
    except (psycopg.OperationalError, OSError) as exc:
        pytest.skip(f"Postgres unavailable: {exc}")
    await ensure_transcript_schema()


@pytest.mark.usefixtures("_schema")
class TestTranscriptRoundTrip:
    async def test_append_then_load_is_chronological(self) -> None:
        conv = uuid.uuid4()
        turn1 = uuid.uuid4()
        turn2 = uuid.uuid4()
        await append_messages(
            conv,
            turn1,
            [
                ConversationMessage(role="user", content="Bonjour, mon solde ?"),
                ConversationMessage(role="assistant", content="Votre solde est de 100 €."),
            ],
        )
        await append_messages(
            conv,
            turn2,
            [
                ConversationMessage(role="user", content="Et mes dernières transactions ?"),
                ConversationMessage(role="assistant", content="Voici vos transactions."),
            ],
        )
        loaded = await load_transcript(conv)
        assert [m.role for m in loaded] == ["user", "assistant", "user", "assistant"]
        assert loaded[0].content == "Bonjour, mon solde ?"
        assert loaded[-1].content == "Voici vos transactions."

    async def test_persists_subject_id_and_synthetic_marker(self) -> None:
        # ADR 0040: the transcript records who the turn served (``subject_id``) and
        # whether it was an operator TEST (``synthetic``), so real-traffic reads can
        # count clients and exclude tests. Read the columns back raw — ``load_transcript``
        # intentionally returns only the conversational record.
        from tessera.settings import get_settings

        conv = uuid.uuid4()
        turn_real = uuid.uuid4()
        turn_test = uuid.uuid4()
        await append_messages(
            conv,
            turn_real,
            [
                ConversationMessage(role="user", content="Bonjour"),
                ConversationMessage(role="assistant", content="Bonjour, comment aider ?"),
            ],
            agent_id="recouvrement",
            subject_id="client-x",
            synthetic=False,
        )
        await append_messages(
            conv,
            turn_test,
            [
                ConversationMessage(role="user", content="test"),
                ConversationMessage(role="assistant", content="réponse de test"),
            ],
            agent_id="recouvrement",
            subject_id="tester",
            synthetic=True,
        )
        dsn = str(get_settings().postgres.dsn)
        async with await psycopg.AsyncConnection.connect(dsn, connect_timeout=2) as conn:
            cur = await conn.execute(
                "SELECT turn_id, synthetic, subject_id FROM conversation_messages "
                "WHERE conversation_id = %s AND role = 'user'",
                (conv,),
            )
            rows = {str(r[0]): (r[1], r[2]) for r in await cur.fetchall()}
        assert rows[str(turn_real)] == (False, "client-x")
        assert rows[str(turn_test)] == (True, "tester")

    async def test_load_limit_returns_most_recent_in_order(self) -> None:
        conv = uuid.uuid4()
        for i in range(5):
            await append_messages(
                conv,
                uuid.uuid4(),
                [ConversationMessage(role="user", content=f"q{i}")],
            )
        loaded = await load_transcript(conv, limit=2)
        assert [m.content for m in loaded] == ["q3", "q4"]

    async def test_only_user_and_assistant_roles_persist(self) -> None:
        conv = uuid.uuid4()
        await append_messages(
            conv,
            uuid.uuid4(),
            [
                ConversationMessage(role="system", content="system note"),
                ConversationMessage(role="user", content="real question"),
                ConversationMessage(role="tool", content="tool output"),
                ConversationMessage(role="assistant", content="real answer"),
            ],
        )
        loaded = await load_transcript(conv)
        assert [m.role for m in loaded] == ["user", "assistant"]

    async def test_unknown_conversation_is_empty(self) -> None:
        assert await load_transcript(uuid.uuid4()) == []

    async def test_missed_pan_seam_is_masked_at_persistence(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Defence-in-depth backstop (pii-input-redaction §4.2): a Luhn-valid
        # PAN reaching the durable transcript unmasked is stored masked and the
        # missed seam is logged — fail-safe, the write proceeds.
        conv = uuid.uuid4()
        await append_messages(
            conv,
            uuid.uuid4(),
            [
                ConversationMessage(role="user", content="ma carte 4242 4242 4242 4242 svp"),
                ConversationMessage(role="assistant", content="Je m'en occupe."),
            ],
        )
        loaded = await load_transcript(conv)
        assert loaded[0].content == "ma carte XXXX XXXX XXXX 4242 svp"
        assert loaded[1].content == "Je m'en occupe."
        assert "missed seam" in capsys.readouterr().err

    async def test_luhn_invalid_run_persists_verbatim(self) -> None:
        # The declared residual (§4.4): a card-shaped typo is NOT rewritten.
        conv = uuid.uuid4()
        await append_messages(
            conv,
            uuid.uuid4(),
            [ConversationMessage(role="user", content="carte 4970 1012 3456 7890 ?")],
        )
        loaded = await load_transcript(conv)
        assert loaded[0].content == "carte 4970 1012 3456 7890 ?"


@pytest.mark.usefixtures("_schema")
class TestListConversations:
    async def test_lists_agent_conversations_with_title_and_counts(self) -> None:
        agent = f"recouvrement-test-{uuid.uuid4().hex[:8]}"
        conv = uuid.uuid4()
        await append_messages(
            conv,
            uuid.uuid4(),
            [
                ConversationMessage(role="user", content="Mon impayé ?"),
                ConversationMessage(role="assistant", content="Voici vos options."),
            ],
            agent_id=agent,
        )
        await append_messages(
            conv,
            uuid.uuid4(),
            [
                ConversationMessage(role="user", content="Et l'échéancier ?"),
                ConversationMessage(role="assistant", content="Le voici."),
            ],
            agent_id=agent,
        )
        convos = await list_conversations(agent)
        assert len(convos) == 1
        summary = convos[0]
        assert summary.conversation_id == str(conv)
        # Title is the FIRST user message; counts cover the persisted record.
        assert summary.title == "Mon impayé ?"
        assert summary.message_count == 4
        assert summary.turn_count == 2

    async def test_scopes_to_agent_and_orders_recent_first(self) -> None:
        agent = f"recouvrement-test-{uuid.uuid4().hex[:8]}"
        other = f"other-test-{uuid.uuid4().hex[:8]}"
        first = uuid.uuid4()
        second = uuid.uuid4()
        await append_messages(
            first, uuid.uuid4(), [ConversationMessage(role="user", content="A")], agent_id=agent
        )
        await append_messages(
            second, uuid.uuid4(), [ConversationMessage(role="user", content="B")], agent_id=agent
        )
        await append_messages(
            uuid.uuid4(),
            uuid.uuid4(),
            [ConversationMessage(role="user", content="C")],
            agent_id=other,
        )
        convos = await list_conversations(agent)
        ids = [c.conversation_id for c in convos]
        # Only this agent's conversations, most-recently-active first.
        assert ids == [str(second), str(first)]
