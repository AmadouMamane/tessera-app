"""Ratchet — the audit chain is persisted independently of the sink. No sink can turn it off.

Audit 2026-07-12, **P1 F-6** (ADR 0023). The opposable ledger is Tessera's central claim, and
it was disablable by a *transport* choice: ``enqueue_ledger_entry`` — the only path into the
chain — ran only ``if sink == "file"``. With the baked default ``ledger_source=postgres`` and
the documented staging sink ``cloud_logging``, every guard decision and business event was
emitted to Cloud Logging and chained *nowhere*. An operator following the staging docs turned
opposability off with no signal.

The invariant this file freezes: **for every sink, an emitted entry either lands in the
opposable ledger, or an exposed deployment refuses to boot with that configuration. There is
no third outcome — no sink emits-without-chaining.**

The sink list is walked from the ``_Sink`` ``Literal`` type, so a sink added later cannot
skip the guarantee without this test failing.
"""

from __future__ import annotations

import typing
from typing import TYPE_CHECKING, Any

import pytest

from tessera.guard import audit
from tessera.guard.audit import (
    _append_to_chain,
    _Sink,
    chain_persists_for,
    validate_audit_chain_config,
)

if TYPE_CHECKING:
    from pathlib import Path

#: Every sink the emitter accepts, taken from the type — not a hand-copied list that could
#: drift. A new sink value forces a decision here.
ALL_SINKS: tuple[str, ...] = typing.get_args(_Sink)


def _entry() -> dict[str, Any]:
    return {
        "type": "tessera.guard.audit",
        "occurred_at": "2026-07-12T00:00:00+00:00",
        "target": "user_input",
        "outcome": "allowed",
    }


@pytest.fixture(autouse=True)
def _hermetic_transports(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neutralise the sink TRANSPORTS so the ratchet isolates the STORE decision.

    The point of this file is where the entry is *chained*, never where its observability copy
    is *carried* — and one carrier, ``cloud_logging``, would otherwise construct a real
    ``google.cloud.logging.Client()`` and hang on credential/project discovery (~25s, network).
    Silencing stdout/file/cloud_logging keeps the sweep hermetic and fast; ``_emit_postgres``
    is left real, because its no-silent-stdout behaviour is part of what is under test.
    """
    monkeypatch.setattr(audit, "_emit_stdout", lambda _e: None)
    monkeypatch.setattr(audit, "_emit_cloud_logging", lambda _e: None)
    monkeypatch.setattr(audit, "_emit_file", lambda _e, _p: None)


@pytest.fixture
def spy_enqueue(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Capture every entry handed to the ledger, without spooling or a background thread."""
    captured: list[dict[str, Any]] = []
    from tessera.guard import ledger_store

    monkeypatch.setattr(ledger_store, "enqueue_ledger_entry", lambda e: captured.append(dict(e)))
    return captured


def test_the_sink_type_is_the_one_we_reason_about() -> None:
    """If a sink is added or renamed, this list — and the reasoning below — must be revisited."""
    assert set(ALL_SINKS) == {"stdout", "file", "cloud_logging", "postgres"}


@pytest.mark.parametrize("sink", ALL_SINKS)
def test_every_sink_chains_under_the_baked_default(
    sink: str, spy_enqueue: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The fix: with ``ledger_source=postgres`` + dual-write (the shipped default), EVERY sink
    routes the entry into the opposable ledger — not just ``file``.

    Against the pre-fix tree this fails for ``stdout``, ``cloud_logging`` and ``postgres``,
    which is the honest statement of the hole: three of four sinks emitted and chained nothing.
    """
    monkeypatch.setenv("TESSERA_LEDGER_SOURCE", "postgres")
    monkeypatch.setenv("TESSERA_LEDGER_DUAL_WRITE", "1")

    _append_to_chain(_entry(), sink, tmp_path / "audit.log")  # type: ignore[arg-type]

    assert len(spy_enqueue) == 1, (
        f"sink={sink!r} did not enqueue the entry to the opposable ledger — a transport "
        "choice must never skip the chain (ADR 0023)"
    )
    # And the entry carries its position-independent identity, so the drain can chain it.
    assert spy_enqueue[0]["event_id"]


@pytest.mark.parametrize("sink", ALL_SINKS)
def test_no_sink_emits_without_chaining_or_refusing(
    sink: str, spy_enqueue: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """THE ratchet, over the full config space: for every sink, and every ledger config, the
    entry is chained OR an exposed boot refuses that config. Never emitted-and-unchained.

    This walks the same predicate the emitter and the boot check share
    (:func:`chain_persists_for`), so the two can never disagree: whatever it says persists,
    the emitter enqueues; whatever it says does not, an exposed boot rejects.
    """
    for source in ("postgres", "file"):
        for dual_write in ("1", "0"):
            spy_enqueue.clear()
            monkeypatch.setenv("TESSERA_LEDGER_SOURCE", source)
            monkeypatch.setenv("TESSERA_LEDGER_DUAL_WRITE", dual_write)

            persists = chain_persists_for(sink, source, dual_write == "1")

            _append_to_chain(_entry(), sink, tmp_path / "audit.log")  # type: ignore[arg-type]
            enqueued = len(spy_enqueue) == 1

            # The entry is chained IFF the predicate says it persists.
            assert enqueued == persists, (
                f"sink={sink!r} source={source!r} dual_write={dual_write}: "
                f"enqueued={enqueued} but chain_persists_for={persists}"
            )

            # And when it does NOT persist, an EXPOSED deployment must refuse to boot with it —
            # so the only way to reach "emitted, unchained" at runtime is a non-exposed posture.
            if not persists:
                monkeypatch.setenv("TESSERA_ENVIRONMENT", "production")
                with pytest.raises(RuntimeError, match="cannot be persisted"):
                    validate_audit_chain_config()


def test_the_documented_staging_sink_now_chains(
    spy_enqueue: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The exact finding, by name: ``cloud_logging`` + ``ledger_source=postgres`` — the
    configuration ``audit.py``'s own docstring called "used in staging and prod" — chains."""
    monkeypatch.setenv("TESSERA_LEDGER_SOURCE", "postgres")
    monkeypatch.setenv("TESSERA_LEDGER_DUAL_WRITE", "1")

    _append_to_chain(_entry(), "cloud_logging", tmp_path / "audit.log")

    assert len(spy_enqueue) == 1


def test_the_boot_refuses_the_unchainable_staging_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail-closed, symmetric with the three signing-key checks (ADR 0020): an exposed
    deployment whose config cannot persist the chain refuses to start, naming the culprit."""
    from tessera.settings import get_settings

    # ledger_source=file + a non-file sink: the flat file is NOT written, and nothing chains.
    monkeypatch.setenv("TESSERA_ENVIRONMENT", "production")
    monkeypatch.setenv("TESSERA_LEDGER_SOURCE", "file")
    monkeypatch.setenv("TESSERA_GUARD__AUDIT_SINK", "cloud_logging")
    get_settings.cache_clear()

    with pytest.raises(RuntimeError) as excinfo:
        validate_audit_chain_config()

    message = str(excinfo.value)
    assert "audit_sink='cloud_logging'" in message
    assert "TESSERA_LEDGER_SOURCE='file'" in message
    assert "opposable ledger" in message
    get_settings.cache_clear()


def test_dev_and_ci_keep_the_hermetic_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    """The exemption is *not exposed*, drawn as narrowly as the bearer's: dev/CI keep the
    hermetic ``TESSERA_LEDGER_DUAL_WRITE=0`` loop, and the boot check is inert there.

    ``dual_write=0`` is precisely a config that does NOT persist — but in ``local``/``ci`` that
    is the intended hermetic behaviour, not a hole, so the check must not fire.
    """
    from tessera.settings import get_settings

    for environment in ("local", "ci"):
        monkeypatch.setenv("TESSERA_ENVIRONMENT", environment)
        monkeypatch.setenv("TESSERA_LEDGER_SOURCE", "postgres")
        monkeypatch.setenv("TESSERA_GUARD__AUDIT_SINK", "cloud_logging")
        monkeypatch.setenv("TESSERA_LEDGER_DUAL_WRITE", "0")
        get_settings.cache_clear()
        validate_audit_chain_config()  # must NOT raise
    get_settings.cache_clear()


def test_emit_postgres_never_silently_falls_back_to_stdout(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """ADR 0023 #3. The old stub wrote the entry to stdout, so choosing ``postgres`` persisted
    nothing to a table while looking configured. It now writes nothing to stdout — either the
    ledger has the entry (redundant, no-op) or it raises."""
    # chain persisted → the ledger already has it → this sink is a silent-safe no-op.
    audit._emit_postgres(_entry(), chain_persisted=True)
    assert capsys.readouterr().out == ""

    # chain NOT persisted → loud, never a stealth stdout line.
    with pytest.raises(RuntimeError, match="Postgres persistence IS the ledger"):
        audit._emit_postgres(_entry(), chain_persisted=False)
    assert capsys.readouterr().out == ""
