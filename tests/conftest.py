"""Shared pytest fixtures for the Tessera test suite."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tessera.agent.state import AgentState, new_state
from tessera.memory import get_memory_backend
from tessera.settings import LanguageCode, get_settings

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture(autouse=True)
def _isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Force every test to run against a deterministic, isolated settings."""
    monkeypatch.delenv("TESSERA_VERTEX__PROJECT_ID", raising=False)
    monkeypatch.setenv("TESSERA_ENVIRONMENT", "ci")
    monkeypatch.setenv("TESSERA_LLM_PROFILE", "on_prem")
    monkeypatch.setenv("TESSERA_OBS__LOG_FORMAT", "console")
    monkeypatch.setenv("TESSERA_OBS__METRICS_ENABLED", "false")
    monkeypatch.setenv(
        "TESSERA_GUARD__POLICY_PATH",
        str(Path("src/tessera/guard/policy.yaml").resolve()),
    )
    monkeypatch.setenv("TESSERA_GUARD__AUDIT_SINK", "stdout")
    monkeypatch.setenv("TESSERA_MEMORY__CONSENT_DEFAULT", "false")
    monkeypatch.setenv(
        "TESSERA_POSTGRES__DSN",
        "postgresql://tessera:tessera@localhost:5432/tessera_test",
    )
    # Audit reads via API need a file path:
    monkeypatch.setenv("TESSERA_AUDIT_FILE", str(tmp_path / "audit.log"))
    get_settings.cache_clear()
    get_memory_backend.cache_clear()
    yield
    get_settings.cache_clear()
    get_memory_backend.cache_clear()


@pytest.fixture
def fr_state() -> AgentState:
    """A pristine French-language state, ready to enter the graph."""
    return new_state(
        conversation_id=uuid.UUID(int=1),
        turn_id=uuid.UUID(int=2),
        user_input="Quel est le solde de mon compte ?",
        language=LanguageCode.FR,
        language_confidence=1.0,
    )


@pytest.fixture
def de_state() -> AgentState:
    """A pristine German-language state."""
    return new_state(
        conversation_id=uuid.UUID(int=3),
        turn_id=uuid.UUID(int=4),
        user_input="Wie hoch ist mein Kontostand?",
        language=LanguageCode.DE,
        language_confidence=1.0,
    )


@pytest.fixture
def en_state() -> AgentState:
    """A pristine English-language state."""
    return new_state(
        conversation_id=uuid.UUID(int=5),
        turn_id=uuid.UUID(int=6),
        user_input="What is my account balance?",
        language=LanguageCode.EN,
        language_confidence=1.0,
    )
