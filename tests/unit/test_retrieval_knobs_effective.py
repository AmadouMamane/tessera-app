"""ADR 0035 — retrieval depth and reranking are per-agent, effective by construction.

Witnesses, ADR 0026 style (each interrogates the THING):

* the resolver returns the knobs the page displays — rerank always, depth only
  when SET (each worker's historical default is never overwritten by an
  invented shared number); fail-open, loudly;
* the chat ROUTE puts them into the graph state (captured inside ``ainvoke``);
* each lookup worker hands the STATE's knobs to ``hybrid_search.search`` — and
  its own historical constant when the state never crossed the seam;
* ``hybrid_search`` with ``rerank=False`` skips BOTH the reranker and the x3
  over-fetch, and serves the raw vector order;
* the save-side coercion clamps depth to [1, 10] as a whole number.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from tessera.agent.state import AgentState, new_state
from tessera.agent.workers import product_lookup, regulation_lookup
from tessera.observability import agent_configurations as configurations
from tessera.retrieval import hybrid_search
from tessera.retrieval.store import VectorHit
from tessera.settings import LanguageCode

if TYPE_CHECKING:
    import pytest

# --------------------------------------------------------------------------- #
# The resolver
# --------------------------------------------------------------------------- #


def test_resolver_default_is_rerank_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unset depth is ABSENT — each worker's own default serves, never one number."""
    monkeypatch.setattr(configurations, "_load_overrides", lambda *_a: {})
    assert configurations.resolve_retrieval("support-client") == {"rerank": True}


def test_resolver_follows_the_stored_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        configurations,
        "_load_overrides",
        lambda *_a: {"retrieval_top_k": 8.0, "retrieval_rerank": False},
    )
    assert configurations.resolve_retrieval("onboarding") == {"rerank": False, "top_k": 8}


def test_resolver_fails_open_loudly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def _boom(*_a: object) -> dict[str, object]:
        msg = "store corrupt"
        raise RuntimeError(msg)

    monkeypatch.setattr(configurations, "_effective", _boom)
    assert configurations.resolve_retrieval() == {"rerank": True}
    assert "resolve_retrieval" in capsys.readouterr().err


def test_depth_coercion_clamps_to_one_through_ten_whole() -> None:
    assert configurations._coerce("retrieval_top_k", 25) == 10.0
    assert configurations._coerce("retrieval_top_k", 0) == 1.0
    assert configurations._coerce("retrieval_top_k", 6.6) == 7.0
    assert configurations._coerce("retrieval_top_k", None) is None
    assert configurations._coerce("retrieval_rerank", False) is False


# --------------------------------------------------------------------------- #
# The route seam
# --------------------------------------------------------------------------- #


def test_chat_route_puts_the_retrieval_knobs_into_the_graph_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from starlette.testclient import TestClient

    from tessera.api.main import build_app
    from tessera.api.routes import chat as chat_route

    monkeypatch.setattr(
        configurations,
        "_load_overrides",
        lambda *_a: {"retrieval_top_k": 3, "retrieval_rerank": False},
    )

    class _ProbeGraph:
        def __init__(self) -> None:
            self.retrieval: object = None

        async def ainvoke(self, state: dict[str, Any], config: object = None) -> object:
            self.retrieval = state.get("retrieval")
            msg = "probe: the turn stops here"
            raise RuntimeError(msg)

    probe = _ProbeGraph()
    monkeypatch.setattr(chat_route, "_streaming_graph", lambda: probe)

    async def _no_prior_agent(_conversation_id: object) -> None:
        return None

    monkeypatch.setattr(chat_route, "last_agent_for", _no_prior_agent)
    client = TestClient(build_app())
    response = client.post("/chat", json={"message": "un tour de test"})
    assert response.status_code == 200
    assert "turn.error" in response.text
    assert probe.retrieval == {"rerank": False, "top_k": 3}


# --------------------------------------------------------------------------- #
# The workers — the state's knobs reach the search call
# --------------------------------------------------------------------------- #


def _chat_state(user_input: str) -> AgentState:
    return new_state(
        conversation_id=uuid.uuid4(),
        turn_id=uuid.uuid4(),
        user_input=user_input,
        language=LanguageCode.FR,
        language_confidence=1.0,
    )


class _CaptureSearch:
    def __init__(self) -> None:
        self.kwargs: dict[str, Any] | None = None

    async def __call__(self, **kwargs: Any) -> list[Any]:
        self.kwargs = kwargs
        return []


async def test_product_worker_hands_the_state_knobs_to_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capture = _CaptureSearch()
    monkeypatch.setattr(product_lookup.hybrid_search, "search", capture)
    state = _chat_state("Quels sont les taux du Crédit Aurore ?")
    state["retrieval"] = {"rerank": False, "top_k": 2}
    await product_lookup.run(state)
    assert capture.kwargs is not None
    assert capture.kwargs["top_k"] == 2
    assert capture.kwargs["rerank"] is False


async def test_product_worker_off_seam_keeps_its_historical_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capture = _CaptureSearch()
    monkeypatch.setattr(product_lookup.hybrid_search, "search", capture)
    await product_lookup.run(_chat_state("Quels sont les taux ?"))
    assert capture.kwargs is not None
    assert capture.kwargs["top_k"] == 4  # the worker's own constant
    assert capture.kwargs["rerank"] is True


async def test_regulation_worker_hands_the_state_knobs_to_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capture = _CaptureSearch()
    monkeypatch.setattr(regulation_lookup.hybrid_search, "search", capture)
    state = _chat_state("Que dit DORA sur la résilience ?")
    state["retrieval"] = {"rerank": True, "top_k": 9}
    await regulation_lookup.run(state)
    assert capture.kwargs is not None
    assert capture.kwargs["top_k"] == 9
    assert capture.kwargs["rerank"] is True


async def test_regulation_worker_off_seam_keeps_its_historical_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capture = _CaptureSearch()
    monkeypatch.setattr(regulation_lookup.hybrid_search, "search", capture)
    await regulation_lookup.run(_chat_state("Que dit DORA ?"))
    assert capture.kwargs is not None
    assert capture.kwargs["top_k"] == 6  # the worker's own constant


# --------------------------------------------------------------------------- #
# hybrid_search — rerank=False is a declared decision, not a silent change
# --------------------------------------------------------------------------- #


def _hit(source: str, score: float) -> VectorHit:
    return VectorHit(
        source=source,
        chunk_id=f"{source}-c1",
        language=LanguageCode.FR,
        text=f"texte {source}",
        score=score,
        metadata={},
    )


async def test_rerank_off_skips_overfetch_and_serves_vector_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested: dict[str, Any] = {}

    async def _embed(_texts: list[str]) -> list[list[float]]:
        return [[0.0]]

    async def _knn(**kwargs: Any) -> list[VectorHit]:
        requested.update(kwargs)
        return [_hit("a", 0.9), _hit("b", 0.8), _hit("c", 0.7)]

    async def _record(_categories: list[str]) -> None:
        return None

    def _never_rerank(**_kwargs: Any) -> list[Any]:
        raise AssertionError("rerank=False must not call the reranker")

    monkeypatch.setattr(hybrid_search.embeddings, "embed", _embed)
    monkeypatch.setattr(hybrid_search.store, "knn_search", _knn)
    monkeypatch.setattr(hybrid_search.citations, "record_retrieval_query", _record)
    monkeypatch.setattr(hybrid_search.reranking, "rerank", _never_rerank)

    docs = await hybrid_search.search(
        query="taux livret", language=LanguageCode.FR, corpus="credit_aurore", top_k=2, rerank=False
    )
    assert requested["top_k"] == 2  # no x3 over-fetch: it exists only for the reranker
    assert [d.source for d in docs] == ["a", "b"]  # raw vector order, cut at top_k
    assert docs[0].score == 0.9  # the cosine score serves, not a fused score


async def test_rerank_on_overfetches_for_the_reranker(monkeypatch: pytest.MonkeyPatch) -> None:
    requested: dict[str, Any] = {}

    async def _embed(_texts: list[str]) -> list[list[float]]:
        return [[0.0]]

    async def _knn(**kwargs: Any) -> list[VectorHit]:
        requested.update(kwargs)
        return [_hit("a", 0.9)]

    async def _record(_categories: list[str]) -> None:
        return None

    monkeypatch.setattr(hybrid_search.embeddings, "embed", _embed)
    monkeypatch.setattr(hybrid_search.store, "knn_search", _knn)
    monkeypatch.setattr(hybrid_search.citations, "record_retrieval_query", _record)

    await hybrid_search.search(
        query="taux livret", language=LanguageCode.FR, corpus="credit_aurore", top_k=2
    )
    assert requested["top_k"] == 6  # 2 x _VECTOR_OVERFETCH — the historical truth
