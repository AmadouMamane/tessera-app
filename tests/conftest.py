"""Shared pytest fixtures for the Tessera test suite, and the blind-spot census."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tessera.agent.state import AgentState, new_state
from tessera.memory import get_memory_backend
from tessera.settings import LanguageCode, Settings, get_settings
from tessera.verdict import CannotSay, NotOk, Ok, render
from tests.tooling import BLIND_SPOTS, census, in_gate

if TYPE_CHECKING:
    from collections.abc import Iterator


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """State, at the end of every run, how many tests could NOT look at what they judge.

    Printed even when the count is zero. A census that only speaks up when it has bad news is a
    census a reader learns to stop looking for — and a skipped test that scrolls past in a 1900-test
    run is invisible, which is how `detect-secrets` ran green for weeks while checking nothing
    (F-14). "0 blind spots" has to be **said**.

    Inside the gate the count is not merely reported, it is *enforced*: `gate-web` installs the
    frontend toolchain before `gate-py` runs, so a tooling skip there means the gate is broken, and
    the session goes red rather than green-with-a-hole. See `tests/tooling.py`.
    """
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if reporter is None:  # `-p no:terminal`: no one to tell, so make no claim
        return

    verdict = census(BLIND_SPOTS, in_the_gate=in_gate())
    match verdict:
        case Ok():
            reporter.write_line(f"[tooling] {render(verdict)}", green=True)
        case CannotSay():
            reporter.write_sep("=", "TOOLING BLIND SPOTS — TESTS THAT COULD NOT LOOK", yellow=True)
            reporter.write_line(render(verdict), yellow=True)
        case NotOk():
            reporter.write_sep("=", "TOOLING BLIND SPOTS INSIDE THE GATE", red=True, bold=True)
            reporter.write_line(render(verdict), red=True)
            # The gate's green is withdrawn. A hole the gate stepped over is not a pass.
            session.exitstatus = 1


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
    # Guard audit chain file — the NESTED name is the one settings honour.
    # `TESSERA_AUDIT_FILE` (set here until 2026-07-21) was a dead name: settings
    # ignored it and `guard.audit_file` silently stayed at the machine-shared
    # state-dir default. Nothing leaked in practice — measured 2026-07-21: the
    # `AUDIT_SINK=stdout` pin above was the ONLY thing standing between the unit
    # suite's injection denials and the live ledger. One changed sink default
    # away from a leak, with an isolation line that named nothing (ADR 0026).
    # `test_unit_env_guard_ledger_isolation.py` now interrogates the thing.
    monkeypatch.setenv("TESSERA_GUARD__AUDIT_FILE", str(tmp_path / "audit.log"))
    # The dev .env.local demo override (auto-grant retention consent) must never
    # leak into the suite: governance tests assert the conservative default
    # (no long-term retention without explicit consent).
    monkeypatch.setenv("TESSERA_MEMORY__CONSENT_DEFAULT", "false")
    # The live-payloads cache is a process singleton keyed on the ledger head; a test that
    # drove it to a head must not leave those rows visible to the next test's fresh chain.
    # The chrome memo is a short-TTL singleton (ADR 0044 follow-up): a test that populated it
    # must not serve its stale result to the next test's patched reads.
    from tessera.api.routes.observability.console import reset_timeline_audit_cache
    from tessera.guard.ledger_store import reset_ledger_payloads_cache
    from tessera.observability.chrome import reset_chrome_cache

    reset_ledger_payloads_cache()
    reset_timeline_audit_cache()
    reset_chrome_cache()
    get_settings.cache_clear()
    get_memory_backend.cache_clear()
    yield
    reset_ledger_payloads_cache()
    reset_timeline_audit_cache()
    reset_chrome_cache()
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
