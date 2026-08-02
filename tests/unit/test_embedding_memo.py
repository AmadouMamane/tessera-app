"""A text's vector never changes, so asking for it twice must cost once.

This is a performance memo, but the failure it repairs is not a slow page — it is a page that
stops. `observability_contradictions` embeds every turn of every captured conversation, once
per bucket, on a surface that polls every 20 s across three periods and two pages. Measured on
the on-prem pair on 2026-08-02: with `bge-m3` warm, 54 embeds cost 5.5 s; with the model
evicted from Ollama by the machine's other models, **loading it cost 167 s**, the curve
payload blew through its deadline, and every trend cell on Vue d'ensemble read "pas encore
d'historique" — an empty window, on a window that was full.

So the properties held here are the ones that make the memo safe to rely on rather than the
ones that make it fast:

* the same text, twice, reaches the backend once;
* a DIFFERENT model never answers from another model's vectors — they are not comparable, and
  a cosine between them is a meaningless number rather than an error anyone would notice;
* order and multiplicity of the caller's list survive exactly, including duplicates;
* the cache is bounded, and a call larger than the bound still returns every vector it was
  asked for.
"""

from __future__ import annotations

import pytest

from tessera.retrieval import embeddings as embeddings_mod


@pytest.fixture(autouse=True)
def _empty_cache() -> None:
    """Every test starts from a cold memo — a hit from a neighbour proves nothing."""
    embeddings_mod._CACHE.clear()
    embeddings_mod._HITS = 0
    embeddings_mod._MISSES = 0


class _Backend:
    """Counts what actually reached it, and returns a vector derived from the text."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def __call__(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [[float(len(t)), float(sum(map(ord, t)) % 97)] for t in texts]

    @property
    def embedded(self) -> list[str]:
        return [text for call in self.calls for text in call]


@pytest.fixture
def backend(monkeypatch: pytest.MonkeyPatch) -> _Backend:
    fake = _Backend()
    monkeypatch.setattr(embeddings_mod, "_embed_ollama", fake)
    monkeypatch.setattr(embeddings_mod, "_embed_vertex", fake)
    monkeypatch.setattr(embeddings_mod, "embedding_model_name", lambda: "bge-m3")
    return fake


@pytest.mark.asyncio
async def test_the_same_text_reaches_the_backend_once(backend: _Backend) -> None:
    first = await embeddings_mod.embed(["solde", "virement"])
    second = await embeddings_mod.embed(["solde", "virement"])
    assert first == second
    assert backend.embedded == ["solde", "virement"], "the second read went to the model again"
    assert embeddings_mod.cache_stats() == {"hits": 2, "misses": 2, "size": 2}


@pytest.mark.asyncio
async def test_a_repeat_inside_one_call_is_asked_for_once(backend: _Backend) -> None:
    out = await embeddings_mod.embed(["solde", "virement", "solde"])
    assert backend.embedded == ["solde", "virement"]
    # The caller's list is answered position for position, duplicates included.
    assert len(out) == 3
    assert out[0] == out[2]


@pytest.mark.asyncio
async def test_only_the_texts_it_has_not_seen_reach_the_backend(backend: _Backend) -> None:
    await embeddings_mod.embed(["solde"])
    out = await embeddings_mod.embed(["solde", "iban", "solde"])
    assert backend.calls == [["solde"], ["iban"]], "a cached text was re-embedded"
    assert out[0] == out[2]
    assert out[1] != out[0]


@pytest.mark.asyncio
async def test_another_model_never_answers_from_this_ones_vectors(
    backend: _Backend, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The key carries the model, and this is the assertion that keeps it there.

    Vectors from two models share no space. Serving one from the other would not raise, would
    not look wrong, and would quietly corrupt every cosine downstream — the exact shape of
    defect `embedding_skew` exists to catch at the corpus level.
    """
    await embeddings_mod.embed(["solde"])
    monkeypatch.setattr(embeddings_mod, "embedding_model_name", lambda: "text-embedding-004")
    await embeddings_mod.embed(["solde"])
    assert backend.embedded == ["solde", "solde"], "a second model was served the first's vector"
    assert embeddings_mod.cache_stats()["size"] == 2


@pytest.mark.asyncio
async def test_the_memo_is_bounded_and_evicts_the_least_recently_used(
    backend: _Backend, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The retrieval path embeds user queries, which are mostly novel: unbounded means it grows
    with traffic while only ever paying off on the repeated reads."""
    monkeypatch.setattr(embeddings_mod, "_CACHE_ENTRIES", 3)
    await embeddings_mod.embed(["a", "b", "c"])
    await embeddings_mod.embed(["a"])  # touch "a" so "b" becomes the oldest
    await embeddings_mod.embed(["d"])
    assert embeddings_mod.cache_stats()["size"] == 3
    assert ("bge-m3", "b") not in embeddings_mod._CACHE
    assert ("bge-m3", "a") in embeddings_mod._CACHE


@pytest.mark.asyncio
async def test_a_call_larger_than_the_bound_still_returns_every_vector(
    backend: _Backend, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The results are held by the call as well as by the cache.

    Without that, a call with more distinct texts than the ceiling evicts its own answers
    before returning them — a KeyError on the happy path, reachable only under load.
    """
    monkeypatch.setattr(embeddings_mod, "_CACHE_ENTRIES", 2)
    texts = [f"tour-{i}" for i in range(10)]
    out = await embeddings_mod.embed(texts)
    assert len(out) == 10
    assert all(vector for vector in out)
    assert embeddings_mod.cache_stats()["size"] == 2


@pytest.mark.asyncio
async def test_an_empty_call_touches_neither_the_backend_nor_the_counters(
    backend: _Backend,
) -> None:
    assert await embeddings_mod.embed([]) == []
    assert backend.calls == []
    assert embeddings_mod.cache_stats() == {"hits": 0, "misses": 0, "size": 0}
