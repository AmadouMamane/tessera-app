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

#: The SHIPPED cloud-logging transport, bound before the autouse fixture below replaces it with
#: a no-op. Without this, the "no silent degradation" test would assert against the fixture's
#: own stub and pass however the real function behaves.
_REAL_EMIT_CLOUD_LOGGING = audit._emit_cloud_logging


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


class TestNoTransportDegradesSilently:
    """The second half of ADR 0023 #3, and the one a green suite hid: a transport EMITS or FAILS.

    `_emit_postgres` was not the only liar. `_emit_cloud_logging` swallowed a missing provider
    and wrote the entry to **stdout**, under a comment reading *"graceful degradation"* — so an
    operator who configured Cloud Logging (the sink the runbook and the Terraform both select
    for production) got entries in a container's stdout instead, and nothing said so. Every
    dashboard, alert and retention rule built on that sink was quietly empty.

    There is no graceful degradation on an audit path. The distinction ADR 0023 buys is what
    makes failing loudly *cheap*: the sink is a lateral copy, so a dead transport costs an
    observability copy and **not one ledger entry**. Both halves are asserted here.
    """

    def test_a_missing_cloud_logging_provider_raises_instead_of_writing_to_stdout(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The exact regression: the import fails → it must NOT quietly become the stdout sink.

        ``_REAL_EMIT_CLOUD_LOGGING`` is bound at import, *before* the autouse fixture silences
        the transports — otherwise this test would assert against the fixture's own no-op and
        pass no matter what the shipped function does.
        """
        import builtins

        real_import = builtins.__import__

        def _no_google(name: str, *args: Any, **kwargs: Any) -> Any:
            if name.startswith("google"):
                msg = "No module named 'google.cloud'"
                raise ImportError(msg)
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _no_google)

        with pytest.raises(ImportError):
            _REAL_EMIT_CLOUD_LOGGING(_entry())

        assert capsys.readouterr().out == "", (
            "a provider that cannot emit wrote the entry to stdout — that is the 'graceful "
            "degradation' F-6 removed: the operator's chosen sink is silently empty"
        )

    def test_a_dead_transport_still_leaves_the_entry_chained(
        self,
        monkeypatch: pytest.MonkeyPatch,
        spy_enqueue: list[dict[str, Any]],
        tmp_path: Path,
    ) -> None:
        """Why failing loudly is now free: the store does not depend on the transport.

        The transport raises; the sink dispatch records it on stderr; and the opposable entry
        is in the ledger all the same. Before ADR 0023 this scenario had the opposite shape —
        the sink decided whether the chain happened at all.
        """

        def _boom(_e: dict[str, Any]) -> None:
            msg = "cloud logging is down"
            raise RuntimeError(msg)

        monkeypatch.setattr(audit, "_emit_cloud_logging", _boom)
        monkeypatch.setenv("TESSERA_LEDGER_SOURCE", "postgres")
        monkeypatch.setenv("TESSERA_LEDGER_DUAL_WRITE", "1")

        _append_to_chain(_entry(), "cloud_logging", tmp_path / "audit.log")

        assert (
            len(spy_enqueue) == 1
        ), "a dead transport cost a ledger entry — the store must not depend on the sink"


class TestNobodyVerifiesTheChainByReadingTheDeadFile:
    """The symmetric hole: the STORE moved, so a verifier aimed at the old one green-lights air.

    `verify_audit_chain(path)` is the *file* primitive, and on an absent file it answers
    `ChainStatus(verified=True, length=0)` — defensible when the file WAS the store, and a
    loaded gun now that it is not: post-cut (`ledger_source=postgres`, the shipped default) the
    flat file is **never written**, so anything that verifies `guard.audit_file` reports a
    perfect, empty, non-existent chain while the real one — 25k+ opposable rows — goes unread.

    Today no production module does this: every chain-integrity surface goes through the
    store-aware `verify_active_ledger` / `active_ledger_tree_status`, which dispatch on
    `ledger_source()`. This test is what stops the next one from reaching for the primitive,
    because reaching for it is the natural mistake — the function has the obvious name.
    """

    def test_the_file_primitive_still_green_lights_an_absent_file(self, tmp_path: Path) -> None:
        """Stated, not hidden. This is WHY the ban below exists — it is the trap's mechanism."""
        status = audit.verify_audit_chain(tmp_path / "does-not-exist.log")

        assert status.verified is True
        assert status.length == 0

    def test_no_src_module_verifies_the_chain_from_the_configured_audit_file(self) -> None:
        """The ban: chain integrity is read from the ACTIVE STORE, never from the dead file."""
        import pathlib
        import re

        src = pathlib.Path(__file__).resolve().parents[2] / "src" / "tessera"
        # `verify_audit_chain(<anything>.guard.audit_file)` — the exact shape of the mistake.
        offender = re.compile(r"verify_audit_chain\(\s*[^)]*guard\.audit_file")
        guilty = [
            str(f.relative_to(src))
            for f in src.rglob("*.py")
            if offender.search(f.read_text(encoding="utf-8"))
        ]

        assert not guilty, (
            f"{guilty} verifies the audit chain by reading `guard.audit_file` — post-cut that "
            "file is never written, so this reports `verified=True, length=0` on a chain it "
            "never opened. Use verify_active_ledger()/active_ledger_tree_status(), which "
            "dispatch on the active store (ADR 0023)."
        )
