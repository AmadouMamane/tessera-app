"""Dense-vector embeddings with profile-aware backend selection.

Two backends are supported, chosen via :func:`Settings.resolved_llm_profile`:

* **frontier** — Vertex AI's ``text-multilingual-embedding-*`` models.
* **on_prem** — Ollama's locally-served embedding model (default ``bge-m3``).

The choice is invisible to callers — they import :func:`embed` and receive a
list of float vectors. The selected backend's dimension is exposed by
:func:`embedding_dimension` so the pgvector schema can be created with the
correct column width.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from tessera.settings import LLMProfile, get_settings

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["embed", "embedding_dimension", "embedding_model_name"]


_MAX_BATCH: Final[int] = 32


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
    """
    if not texts:
        return []
    settings = get_settings()
    if settings.resolved_llm_profile() is LLMProfile.FRONTIER:
        return await _embed_vertex(texts)
    return await _embed_ollama(texts)
