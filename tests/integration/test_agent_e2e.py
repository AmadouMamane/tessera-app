"""End-to-end integration tests — exercise the agent graph with mocked I/O.

These tests run the full LangGraph but stub the retrieval call so they do
not require a live Postgres. They are tagged ``integration`` and are
included in the day-twenty CI smoke suite.
"""

from __future__ import annotations

import uuid

import pytest

from tessera.agent import compile_graph
from tessera.agent.state import RetrievedDocument, new_state
from tessera.settings import LanguageCode

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _stub_retrieval(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace hybrid_search.search with a deterministic stub."""

    async def _stub_search(
        *, query: str, language: LanguageCode, corpus: str, top_k: int = 4
    ) -> list[RetrievedDocument]:
        return [
            RetrievedDocument(
                source=f"{corpus}-doc-1",
                chunk_id="chunk-001",
                language=language,
                text=f"Réponse pertinente pour: {query}",
                score=0.85,
                metadata={"locator": "section 1"},
            )
        ]

    from tessera.retrieval import hybrid_search

    monkeypatch.setattr(hybrid_search, "search", _stub_search)


class TestEndToEnd:
    @pytest.mark.fr
    @pytest.mark.asyncio
    async def test_fr_balance_request_runs_to_completion(self) -> None:
        graph = compile_graph()
        state = new_state(
            conversation_id=uuid.uuid4(),
            turn_id=uuid.uuid4(),
            user_input="Quel est le solde de mon compte ?",
            language=LanguageCode.FR,
            language_confidence=1.0,
        )
        final = await graph.ainvoke(state)
        assert "final_response" in final
        assert final["final_response"]
        assert final["language"] is LanguageCode.FR

    @pytest.mark.en
    @pytest.mark.asyncio
    async def test_en_card_block_escalates(self) -> None:
        graph = compile_graph()
        state = new_state(
            conversation_id=uuid.uuid4(),
            turn_id=uuid.uuid4(),
            user_input="I want to block my card immediately, please execute the card_block tool. My card was stolen.",
            language=LanguageCode.EN,
            language_confidence=1.0,
        )
        final = await graph.ainvoke(state)
        assert final["needs_escalation"] is True
        assert (
            "advisor" in final["final_response"].lower()
            or "reference" in final["final_response"].lower()
            or "block" in final["final_response"].lower()
        )
