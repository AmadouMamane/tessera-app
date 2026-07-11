"""End-to-end integration tests — the full agent graph against a LIVE on-prem LLM.

LOCAL-ONLY. The retrieval leg is stubbed (``_stub_retrieval`` below), but the graph's
planner / reviewer / reporter nodes call the on-prem model (Ollama) for real — the shared
suite conftest forces ``TESSERA_LLM_PROFILE=on_prem``. So these need Ollama up
(``make run-on-prem`` stack), never a hosted runner and never a secret; ``_require_local_llm``
skips them cleanly when it is not reachable, which is why the nightly Integration workflow
reports them skipped. (An earlier docstring here claimed "mocked I/O"; only retrieval is
mocked — the model call is real, and that is what makes this file local-only.)
"""

from __future__ import annotations

import os
import socket
import uuid
from urllib.parse import urlparse

import pytest

from tessera.agent import compile_graph
from tessera.agent.state import RetrievedDocument, new_state
from tessera.settings import LanguageCode

pytestmark = pytest.mark.integration


def _ollama_reachable() -> bool:
    """Whether the on-prem LLM host answers a TCP connect — the local-only gate.

    Reads the same env the on-prem profile resolves (``TESSERA_OLLAMA_HOST``; default
    ``http://localhost:11434``). A cheap socket probe, not an HTTP round-trip: we only need
    to know a server is listening before spending a full graph turn against it.
    """
    raw = os.environ.get("TESSERA_OLLAMA_HOST", "http://localhost:11434")
    parsed = urlparse(raw)
    host, port = parsed.hostname or "localhost", parsed.port or 11434
    try:
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except OSError:
        return False


@pytest.fixture(autouse=True)
def _require_local_llm() -> None:
    """Skip this module unless the on-prem LLM is reachable (see the module docstring)."""
    if not _ollama_reachable():
        pytest.skip("on-prem LLM (Ollama) not reachable — local-only integration test")


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
            user_input="Block my card right now, I think I lost it.",
            language=LanguageCode.EN,
            language_confidence=1.0,
        )
        final = await graph.ainvoke(state)
        assert final["needs_escalation"] is True
        assert (
            "advisor" in final["final_response"].lower()
            or "reference" in final["final_response"].lower()
        )
