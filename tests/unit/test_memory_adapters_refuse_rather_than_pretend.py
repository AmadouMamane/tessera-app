"""Two external memory backends answered every call, recalled nothing, and never raised.

They were selectable — `MEMORY_BACKEND=zep`, `MEMORY_BACKEND=langmem` — and installing the extra
was treated as configuring the engine. It is not:

* `ZepBackend` built its client with a literal ``api_key=""``, under a comment saying the client
  "reads them itself". An explicit empty string does not defer to the environment, it OVERRIDES
  it. Every call authenticated as nobody, every call failed, and the `except Exception` in
  `load` turned each failure into an empty recall.
* `LangMemBackend` called `create_memory_store_manager(...)` **without** `store=`. The manager
  wrote to its own default store while `load` read `self._store`: writes and reads addressed
  different places, so recall was empty for ever — and nothing raised, because both halves were
  working perfectly. It also hard-coded ``openai:gpt-4o-mini``, a paid model reached outside the
  LLM router, outside the model policy and outside the org-wide daily budget breaker (ADR 0034),
  chosen by a string literal.
* Neither screened a recalled memory or recorded the read, both of which the native
  `PersistentBackend` has done since ADR 0007 and ADR 0024. Text came back from a third-party
  store and went straight into the prompt: unscreened, unmasked, and absent from the audit
  trail. An engine Tessera does not own is *more* exposed to memory poisoning, not less.

These tests do not need the extras installed. They assert what the code says, because that is
what was wrong — and because the failure they guard against is invisible at run time by
construction: it produces a working object that remembers nothing.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Final

import pytest

from tessera.memory.adapters import (
    UnconfiguredMemoryBackendError,
    required_env,
)

_ADAPTERS: Final = Path(__file__).resolve().parents[2] / "src" / "tessera" / "memory" / "adapters"


def _source(name: str) -> str:
    return (_ADAPTERS / f"{name}.py").read_text(encoding="utf-8")


class TestAMissingCredentialIsARefusalAndNotAnEmptyString:
    """`required_env` exists so a credential cannot be defaulted into existence."""

    def test_an_unset_variable_refuses_by_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ZEP_API_KEY", raising=False)

        with pytest.raises(UnconfiguredMemoryBackendError) as caught:
            required_env("ZEP_API_KEY", backend="zep", why="It is the credential.")

        message = str(caught.value)
        assert "ZEP_API_KEY" in message, "it refused without naming what to set"
        assert "window" in message, "it refused without naming a backend that works today"

    def test_whitespace_is_not_a_credential(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ZEP_API_KEY", "   ")

        with pytest.raises(UnconfiguredMemoryBackendError):
            required_env("ZEP_API_KEY", backend="zep", why="It is the credential.")

    def test_a_set_value_is_returned(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ZEP_API_KEY", "zep-live-key")

        assert required_env("ZEP_API_KEY", backend="zep", why="…") == "zep-live-key"


def _string_literals(name: str) -> set[str]:
    """Every string the module's CODE contains — docstrings and comments excluded.

    Read as raw text, this file's own prose would satisfy it: the two literals below are quoted
    in the comments that explain why they are gone, and the first version of these tests failed
    against a fixed module for exactly that reason. A detector that can see its own explanation
    is measuring the wrong thing.
    """
    tree = ast.parse(_source(name))
    docstrings = {
        node.body[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
    }
    return {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node not in docstrings
    }


class TestNoAdapterAuthenticatesAsNobody:
    """The literals that started this — read from the AST, because a run-time test would need
    the extra installed, and the bug's whole nature is that it does not raise."""

    def test_zep_does_not_pass_an_empty_api_key(self) -> None:
        tree = ast.parse(_source("zep"))
        empty_key = [
            keyword
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            for keyword in node.keywords
            if keyword.arg == "api_key"
            and isinstance(keyword.value, ast.Constant)
            and not str(keyword.value.value).strip()
        ]

        assert empty_key == [], (
            'AsyncZep(api_key="") overrides whatever the environment holds and authenticates as '
            "nobody. Every call then fails into the `except Exception` and reads as an empty "
            "memory."
        )
        assert "required_env(" in _source("zep"), "the Zep key is no longer demanded"

    def test_langmem_does_not_hardcode_a_paid_model(self) -> None:
        assert "openai:gpt-4o-mini" not in _string_literals("langmem"), (
            "a paid model is chosen by a string literal, outside the LLM router and outside the "
            "org-wide daily budget breaker (ADR 0034). Nobody decided it and nobody counts it."
        )
        assert "required_env(" in _source("langmem"), "the LangMem model is no longer demanded"


class TestLangMemWritesWhereItReads:
    """The quietest of the three: two working halves, addressing different stores."""

    def test_the_manager_is_given_the_store_the_backend_reads(self) -> None:
        tree = ast.parse(_source("langmem"))
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "create_memory_store_manager"
        ]

        assert calls, "`create_memory_store_manager` is no longer called — has the wiring moved?"
        for call in calls:
            assert any(kw.arg == "store" for kw in call.keywords), (
                "the LangMem manager is built without `store=`, so it writes to its own default "
                "store while `load` reads `self._store`. Recall is empty for ever and nothing "
                "raises, because each half works."
            )


class TestAnExternalStoreIsScreenedLikeTheNativeOne:
    """A store Tessera does not own is more exposed to poisoning, not less."""

    @pytest.mark.parametrize("adapter", ["zep", "langmem"])
    def test_recall_is_screened_before_it_reaches_the_prompt(self, adapter: str) -> None:
        source = _source(adapter)

        assert "governance.screen_memory" in source, (
            f"{adapter} returns third-party text straight into the prompt. An injected "
            f"instruction or a residual PAN stored by another component reaches the model "
            f"unscreened — the exact risk ADR 0007's anti-poisoning read-screen exists for."
        )

    @pytest.mark.parametrize("adapter", ["zep", "langmem"])
    def test_the_read_is_recorded(self, adapter: str) -> None:
        source = _source(adapter)

        assert "governance.audit_memory" in source, (
            f"{adapter} reads a subject's personal data and the audit trail says nothing "
            f"happened. For a product whose thesis is the opposable trail, a read nobody can "
            f"demonstrate is the expensive kind of gap (GDPR Art. 30)."
        )

    @pytest.mark.parametrize("adapter", ["zep", "langmem"])
    def test_the_actors_are_named_and_not_defaulted(self, adapter: str) -> None:
        """ADR 0024: no identity field may carry a default that names somebody."""
        source = _source(adapter)

        assert "_MEMORY_READ_ACTOR" in source
        assert "_TURN_ACTOR" in source
