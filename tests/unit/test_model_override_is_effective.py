"""The governed model override reaches the client, on every backend that claims it does.

Audit 2026-08-03. ADR 0030 §3 says an ineffective override is unwritable *by construction*:
*"An override that the runtime ignores cannot be written under this design, because the store's
only consumer is the serving path."* On a frontier deployment it was writable and ignored.
``VertexAIBackend`` accepted ``model=`` and threw it away — ``# noqa: ARG002  fixed at init on
the frontier path`` — while memoising one client built from ``settings.vertex.chat_model``.

So a superadmin's override was stored, validated, journalled with its reason, shown as the
active model in the catalogue, stamped on the span, threaded into the eval lineage, and priced
at the requested model's rate — and Gemini served the base model, which was then *recorded* at
the base model's rate. Two costs for one turn, and a lineage naming a model that never ran.

Nothing caught it because nothing asked. The sampling knobs have ``SAMPLING_APPLIED``, a
declaration ``test_sampling_effective.py`` checks against the real calls; the per-call model
had no such table, so its regression was unrepresentable *in the tests* rather than in the
design. These tests interrogate each backend (ADR 0026) rather than trusting the new table.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

import pytest

from tessera.llm.router import MODEL_OVERRIDE_APPLIED

if TYPE_CHECKING:
    from collections.abc import Iterator


class _RecordingGenerativeModel:
    """Stands in for ``vertexai.generative_models.GenerativeModel``, remembering its id."""

    built: ClassVar[list[str]] = []

    def __init__(self, model_name: str) -> None:
        type(self).built.append(model_name)
        self.model_name = model_name

    async def generate_content_async(self, *_a: object, **_k: object) -> Any:
        class _Response:
            candidates: ClassVar[list[object]] = []
            text = ""
            usage_metadata = None

        return _Response()


@pytest.fixture
def vertex_backend(monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    """A ``VertexAIBackend`` whose Vertex SDK is replaced by a recorder."""
    import sys
    import types

    from tessera.llm.frontier import VertexAIBackend

    _RecordingGenerativeModel.built = []
    fake_vertexai = types.ModuleType("vertexai")
    fake_vertexai.init = lambda **_kw: None  # type: ignore[attr-defined]
    fake_models = types.ModuleType("vertexai.generative_models")
    fake_models.GenerativeModel = _RecordingGenerativeModel  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "vertexai", fake_vertexai)
    monkeypatch.setitem(sys.modules, "vertexai.generative_models", fake_models)

    backend = VertexAIBackend()
    backend.model = "gemini-2.0-flash-001"
    backend._project = "a-project"
    yield backend


def test_the_declaration_covers_every_backend_name() -> None:
    """A table that forgets a backend cannot police it."""
    from tessera.llm.router import SAMPLING_APPLIED

    assert set(MODEL_OVERRIDE_APPLIED) == set(SAMPLING_APPLIED)


def test_vertex_builds_the_client_for_the_requested_model(vertex_backend: Any) -> None:
    """THE regression. Before the fix this built ``gemini-2.0-flash-001`` and served it."""
    vertex_backend._ensure_model("gemini-2.0-pro-001")
    assert _RecordingGenerativeModel.built == [
        "gemini-2.0-pro-001"
    ], "Vertex ignored the per-call model and served the one frozen at init"


def test_vertex_falls_back_to_the_configured_model(vertex_backend: Any) -> None:
    vertex_backend._ensure_model(None)
    assert _RecordingGenerativeModel.built == ["gemini-2.0-flash-001"]


def test_vertex_memoises_per_model_not_globally(vertex_backend: Any) -> None:
    """One client per model id — caching by instance is what discarded the override."""
    first = vertex_backend._ensure_model("gemini-2.0-pro-001")
    again = vertex_backend._ensure_model("gemini-2.0-pro-001")
    other = vertex_backend._ensure_model("gemini-2.0-flash-001")
    assert first is again, "a second turn on the same model must reuse its client"
    assert other is not first
    assert _RecordingGenerativeModel.built == ["gemini-2.0-pro-001", "gemini-2.0-flash-001"]


def test_the_local_backend_honours_the_override() -> None:
    """Ollama already threaded it; pinned so the seam cannot silently regress either."""
    import inspect

    from tessera.llm.local import OllamaBackend

    source = inspect.getsource(OllamaBackend)
    assert "effective_model = model or self.model" in source


def test_no_backend_declares_the_override_while_discarding_it() -> None:
    """A ``noqa: ARG002`` on ``model`` is precisely how the frontier defect was written down.

    It is a comment saying "this argument is deliberately unused" — on the argument that
    carries a governed decision. If one reappears, the declaration above has become a claim
    the code contradicts.
    """
    import inspect
    import re

    from tessera.llm import frontier, local, openai_backend

    for module in (frontier, local, openai_backend):
        source = inspect.getsource(module)
        offending = re.findall(
            r"^\s*model: str \| None = None,\s*#\s*noqa: ARG002.*$", source, re.M
        )
        assert not offending, (
            f"{module.__name__} declares the model override applied while discarding it: "
            f"{offending}"
        )
