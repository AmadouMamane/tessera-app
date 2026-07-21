"""Budget accounting regressions for the Vertex streaming backend."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from tessera.llm.frontier import VertexAIBackend
from tessera.llm.router import ChatMessage


@dataclass(slots=True)
class _Usage:
    prompt_token_count: int
    candidates_token_count: int


@dataclass(slots=True)
class _Chunk:
    text: str
    candidates: list[object]
    usage_metadata: _Usage | None = None


class _Stream:
    def __init__(self, chunks: list[_Chunk]) -> None:
        self._chunks = chunks

    def __aiter__(self) -> _Stream:
        return self

    async def __anext__(self) -> _Chunk:
        if not self._chunks:
            raise StopAsyncIteration
        return self._chunks.pop(0)


class _Gemini:
    async def generate_content_async(self, *_args: object, **_kwargs: object) -> _Stream:
        return _Stream(
            [
                _Chunk(text="Bonjour", candidates=[object()]),
                _Chunk(
                    text="",
                    candidates=[object()],
                    usage_metadata=_Usage(prompt_token_count=37, candidates_token_count=11),
                ),
            ]
        )


class _BudgetSpy:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def record(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


@pytest.mark.asyncio
async def test_vertex_stream_records_final_usage_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = VertexAIBackend()
    monkeypatch.setattr(backend, "_ensure_model", lambda: _Gemini())
    budget = _BudgetSpy()
    monkeypatch.setattr("tessera.llm.frontier.get_budget_tracker", lambda: budget)
    usage: dict[str, int] = {}

    tokens = [
        token
        async for token in backend.stream_chat(
            [ChatMessage(role="user", content="Bonjour")],
            usage=usage,
        )
    ]

    assert tokens == ["Bonjour"]
    assert usage == {"input_tokens": 37, "output_tokens": 11}
    assert budget.calls == [
        {
            "backend": "vertex-ai",
            "model": backend.model,
            "input_tokens": 37,
            "output_tokens": 11,
        }
    ]
