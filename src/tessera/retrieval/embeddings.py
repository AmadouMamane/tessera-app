"""Dense-vector embeddings with profile-aware backend selection.

Two backends are supported, chosen via :func:`Settings.resolved_llm_profile`:

* **frontier** — Vertex AI's ``text-multilingual-embedding-*`` models.
* **on_prem** — Ollama's locally-served embedding model (default ``bge-m3``).

The choice is invisible to callers — they import :func:`embed` and receive a
list of float vectors. The selected backend's dimension is exposed by
:func:`embedding_dimension` so the pgvector schema can be created with the
correct column width.

Results are memoised per ``(model, text)`` — see :data:`_CACHE_ENTRIES`.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import TYPE_CHECKING, Final

from tessera.settings import LLMProfile, get_settings

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["cache_stats", "embed", "embedding_dimension", "embedding_model_name"]


_MAX_BATCH: Final[int] = 32

#: How many ``(model, text) -> vector`` results to keep, most-recently-used first.
#:
#: The vector of a given text under a given model never changes, so this is a pure memo — and
#: the read paths ask for the SAME texts over and over. `observability_contradictions` embeds
#: every turn of every captured conversation, once per bucket, on a page that polls every 20 s,
#: across three periods and two surfaces.
#:
#: The cost that makes it worth having is not the embedding, it is the model being COLD:
#: measured 2026-08-02 on the on-prem pair, loading ``bge-m3`` into Ollama took **167 s**, while
#: 54 embeds against a warm model took 5.5 s (and 4.5 s batched — which is why this is a cache
#: and not a batching change). Ollama evicts it whenever the machine's other models want the
#: memory, so a cockpit read could land on a 167 s stall at any time; the whole curve payload
#: then blew through its deadline and every trend cell on the page read "pas encore
#: d'historique". Memoised, a text pays that once ever rather than once per eviction.
#:
#: 4096 entries is ~32 MB at bge-m3's 1024 dimensions. Bounded because the retrieval path
#: embeds user queries, which are mostly novel: a cache with no ceiling would grow with traffic
#: while only ever being useful for the repeated reads.
_CACHE_ENTRIES: Final[int] = 4096

_CACHE: OrderedDict[tuple[str, str], list[float]] = OrderedDict()
_HITS = 0
_MISSES = 0


def cache_stats() -> dict[str, int]:
    """Hits, misses and current size — so a caller can prove the memo is working."""
    return {"hits": _HITS, "misses": _MISSES, "size": len(_CACHE)}


def embedding_dimension() -> int:
    """Return the dimensionality of the active embedding backend."""
    settings = get_settings()
    if settings.resolved_llm_profile() is LLMProfile.FRONTIER:
        return settings.vertex.embedding_dimension
    return settings.ollama.embedding_dimension


def embedding_model_name() -> str:
    """Return the model id of the active embedding backend.

    The display name must reflect the backend that actually produced the index
    (Vertex on the frontier profile, Ollama on-prem) - never a hardcoded literal.
    """
    settings = get_settings()
    if settings.resolved_llm_profile() is LLMProfile.FRONTIER:
        return settings.vertex.embedding_model
    return settings.ollama.embedding_model


async def _embed_vertex(texts: Sequence[str]) -> list[list[float]]:
    """Embed via Vertex AI's text-multilingual-embedding model."""
    from vertexai.language_models import TextEmbeddingModel

    settings = get_settings()
    model = TextEmbeddingModel.from_pretrained(settings.vertex.embedding_model)
    out: list[list[float]] = []
    for i in range(0, len(texts), _MAX_BATCH):
        batch = list(texts[i : i + _MAX_BATCH])
        response = await model.get_embeddings_async(batch)  # type: ignore[arg-type]
        out.extend(item.values for item in response)
    return out


async def _embed_ollama(texts: Sequence[str]) -> list[list[float]]:
    """Embed via the local Ollama server."""
    import ollama

    settings = get_settings()
    client = ollama.AsyncClient(host=str(settings.ollama.host))
    out: list[list[float]] = []
    for text in texts:
        response = await client.embeddings(
            model=settings.ollama.embedding_model,
            prompt=text,
        )
        out.append(list(response["embedding"]))
    return out


async def embed(texts: Sequence[str]) -> list[list[float]]:
    """Return the embedding vectors for every text in ``texts``.

    Empty inputs return an empty list. Backend selection happens here so
    callers never branch on ``llm_profile``.

    Already-seen texts are served from the memo (:data:`_CACHE_ENTRIES`) and only the rest
    reach the backend, so a call that repeats an earlier one costs nothing. The key carries the
    MODEL: switching profiles or embedding models must not be answered from vectors the other
    one produced — they are not comparable, and a cosine between them is a number with no
    meaning rather than an error anyone would notice.

    Args:
        texts: The texts to embed, in order.

    Returns:
        One vector per input, in the input's order.
    """
    if not texts:
        return []
    global _HITS, _MISSES
    settings = get_settings()
    frontier = settings.resolved_llm_profile() is LLMProfile.FRONTIER
    model = embedding_model_name()

    known: dict[str, list[float]] = {}
    wanted: list[str] = []
    pending: set[str] = set()
    for text in texts:
        # A text repeated inside one call is resolved once — otherwise a conversation that asks
        # the same question twice pays for it twice, and `wanted` would carry a duplicate.
        if text in known or text in pending:
            continue
        cached = _CACHE.get((model, text))
        if cached is None:
            _MISSES += 1
            wanted.append(text)
            pending.add(text)
        else:
            _HITS += 1
            _CACHE.move_to_end((model, text))
            known[text] = cached

    if wanted:
        fresh = await (_embed_vertex(wanted) if frontier else _embed_ollama(wanted))
        for text, vector in zip(wanted, fresh, strict=True):
            # Held HERE as well as in the cache: a call with more distinct texts than the
            # ceiling would evict its own results before it returned them.
            known[text] = vector
            _CACHE[(model, text)] = vector
            _CACHE.move_to_end((model, text))
        while len(_CACHE) > _CACHE_ENTRIES:
            _CACHE.popitem(last=False)

    return [known[text] for text in texts]
