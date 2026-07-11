"""Shared pytest fixtures for the Tessera test suite."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tessera.agent.state import AgentState, new_state
from tessera.memory import get_memory_backend
from tessera.settings import LanguageCode, Settings, get_settings

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture(autouse=True)
def _isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Force every test to run against a deterministic, isolated settings."""
    # `Settings` reads a gitignored `.env.local` for local dev; CI has none. A suite that
    # inherits it does not assert the SHIPPED defaults, it asserts the operator's machine —
    # so an operator flipping the ADR 0019 §I4 canary switch ON (the go-and-observe move
    # the flag exists for) turns a green suite red, and a stale `.env.local` can turn a red
    # one green. Cut the file out of the suite: local now resolves settings exactly as CI
    # does, and every non-default below is pinned here, in the open. Tests covering an
    # enabled path pass `Settings` explicitly.
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    monkeypatch.delenv("TESSERA_VERTEX__PROJECT_ID", raising=False)
    monkeypatch.setenv("TESSERA_ENVIRONMENT", "ci")
    monkeypatch.setenv("TESSERA_LLM_PROFILE", "on_prem")
    # Canonical nested form (audit P1.3): TESSERA_OBS__X is silently ignored — the block's own
    # prefix is TESSERA_OBS_ (single _), the composite delimiter needs the field name
    # (observability). These two were dead before; now they actually take effect.
    monkeypatch.setenv("TESSERA_OBSERVABILITY__LOG_FORMAT", "console")
    monkeypatch.setenv("TESSERA_OBSERVABILITY__METRICS_ENABLED", "false")
    monkeypatch.setenv(
        "TESSERA_GUARD__POLICY_PATH",
        str(Path("src/tessera/guard/policy.yaml").resolve()),
    )
    monkeypatch.setenv("TESSERA_GUARD__AUDIT_SINK", "stdout")
    # The owned-store write legs (ADR 0015 §Amend.1-2 + §Corr.2b) are off in the suite:
    # emit_score / record_gating_report must stay hermetic (no insert thread at :18123,
    # no SDK mirror at :3900). The write paths themselves are unit-tested against stubbed
    # clients (opting back in per-test) and proven live by the contract tests.
    monkeypatch.setenv("TESSERA_CLICKHOUSE_SCORES", "0")
    # The ADR 0017 §5 business-event dual-write is off for the same reason (no insert
    # thread at :18123); the write path is unit-tested against a stubbed client.
    monkeypatch.setenv("TESSERA_CLICKHOUSE_BUSINESS_EVENTS", "0")
    monkeypatch.setenv("TESSERA_LANGFUSE_SCORES", "0")
    # The §Amendment 3 ledger dual-write is off too: audit emission in tests must not
    # reach Postgres (and the append-only table could never be cleaned). The promoted
    # ledger is covered by its own unit (pure chain walk) + contract tests.
    monkeypatch.setenv("TESSERA_LEDGER_DUAL_WRITE", "0")
    # Since G5 the flippable facts DEFAULT to the owned stores; the unit suite pins the
    # degraded local source explicitly (tests seed the local stores and must stay offline).
    # The spine sources themselves are covered by the fact-flip unit tests (which drop
    # this pin) and by the live contract tests.
    monkeypatch.setenv("TESSERA_SPINE_SOURCE", "local")
    # H2 step 5 retired the flat audit.log: the ledger source now DEFAULTS to the promoted
    # Postgres table (the cut). The unit suite pins the legacy file source so audit reads +
    # emission stay offline/hermetic; the table read is covered by the ledger contract tests
    # and the seam's postgres branch is unit-tested by monkeypatching the table read.
    monkeypatch.setenv("TESSERA_LEDGER_SOURCE", "file")
    # Eval reports are partitioned per env (ADR 0014, layer 3); the real archive
    # is a local-dev artifact under eval/reports/local. Pin the resolver at it so
    # the report-backed assertions read real data regardless of the test env.
    monkeypatch.setenv("TESSERA_REPORTS_DIR", str(Path("eval/reports/local").resolve()))
    monkeypatch.setenv(
        "TESSERA_POSTGRES__DSN",
        "postgresql://tessera:tessera@localhost:5432/tessera_test",
    )
    # Audit reads via API need a file path:
    monkeypatch.setenv("TESSERA_AUDIT_FILE", str(tmp_path / "audit.log"))
    # The dev .env.local demo override (auto-grant retention consent) must never
    # leak into the suite: governance tests assert the conservative default
    # (no long-term retention without explicit consent).
    monkeypatch.setenv("TESSERA_MEMORY__CONSENT_DEFAULT", "false")
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
