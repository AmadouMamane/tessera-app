"""``verify_active_ledger_checkpointed`` serves the dashboard badge from the incremental verdict.

The Synthèse / Garde-fous chain-integrity dot used to call ``verify_active_ledger`` — a full
re-walk of the whole (65k-row) chain, measured at ~2 s. It now asks the checkpointed incremental
verifier (~15 ms), which the append-only ledger makes exact: a verified prefix can never change.

These tests pin the GLUE this lot added — the ``tree → ChainStatus`` mapping in postgres mode, and
the byte-identical ``verify_audit_chain`` fallback in file mode. The incremental verdict's own
equivalence to a full walk is ``verify_ledger_incremental``'s contract, pinned separately by
``test_ledger_checkpoint_merge``; it is deliberately NOT re-proved here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import tessera.guard.ledger_checkpoint as checkpoint
from tessera.guard import ledger_store
from tessera.guard.audit import ChainStatus
from tessera.guard.ledger_checkpoint import LedgerVerdict
from tessera.guard.ledger_store import (
    LedgerTreeStatus,
    verify_active_ledger,
    verify_active_ledger_checkpointed,
)

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _verdict(tree: LedgerTreeStatus) -> LedgerVerdict:
    return LedgerVerdict(
        tree=tree,
        full_verified_at=None,
        entries_since_full=0,
        entries_verified_now=0,
        checkpoint_used=True,
    )


def test_postgres_maps_the_incremental_tree_to_a_chainstatus(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The badge is the incremental tree's content-integrity, length and break, as a ChainStatus."""
    monkeypatch.setattr(ledger_store, "ledger_source", lambda: "postgres")
    tree = LedgerTreeStatus(
        content_integrity=True, linear=True, forks=(), orphans=(), length=65397, broken_at=None
    )
    monkeypatch.setattr(checkpoint, "verify_ledger_incremental", lambda: _verdict(tree))
    assert verify_active_ledger_checkpointed() == ChainStatus(
        verified=True, length=65397, broken_at=None
    )


def test_a_broken_incremental_tree_reads_as_unverified_at_the_break(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A break the incremental verifier finds surfaces on the badge, as the full walk would."""
    monkeypatch.setattr(ledger_store, "ledger_source", lambda: "postgres")
    tree = LedgerTreeStatus(
        content_integrity=False, linear=False, forks=(), orphans=(), length=10, broken_at=3
    )
    monkeypatch.setattr(checkpoint, "verify_ledger_incremental", lambda: _verdict(tree))
    got = verify_active_ledger_checkpointed()
    assert got.verified is False
    assert got.length == 10
    assert got.broken_at == 3


def test_file_mode_is_the_same_verify_audit_chain_as_the_full_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """No checkpoint in file mode: both the full and checkpointed paths call the SAME
    ``verify_audit_chain`` on the SAME file, so the badge cannot drift from the opposability read.
    """
    monkeypatch.setattr(ledger_store, "ledger_source", lambda: "file")
    sentinel = ChainStatus(verified=True, length=7, broken_at=None)
    seen: dict[str, Path] = {}

    def fake_chain(path: Path) -> ChainStatus:
        seen["path"] = path
        return sentinel

    monkeypatch.setattr(ledger_store, "verify_audit_chain", fake_chain)
    p = tmp_path / "audit.log"
    assert verify_active_ledger_checkpointed(p) is sentinel
    assert seen["path"] == p
    # The full opposability path takes the identical file branch — same object, same file.
    assert verify_active_ledger(p) is sentinel
