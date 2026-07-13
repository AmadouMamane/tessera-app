"""The incremental verifier's fold — the part that can silently lie.

The integrity badge no longer re-hashes the whole chain per request (25 634 rows, 1 093 ms). It
verifies only the rows above a persisted checkpoint. That is sound because ``audit_ledger`` has a
BEFORE UPDATE OR DELETE trigger: a verified prefix cannot change.

But "sound in principle" is where verifiers go to die. Everything the checkpoint carries forward
is a chance to carry forward a WRONG answer, and a wrong answer here reads GREEN — the badge says
"integrity verified" and nobody looks again. So the fold is a pure function, and these tests state
each way it could be wrong.

The end-to-end property (incremental == full walk, on a real chain) lives in the integration
suite, which needs a Postgres. These run in the gate.
"""

from __future__ import annotations

from datetime import UTC, datetime

from tessera.guard.ledger_checkpoint import Checkpoint, _Orphan, merge_verdict
from tessera.guard.ledger_store import LedgerForkPoint


def _checkpoint(
    *,
    content_ok: bool = True,
    broken_at: int | None = None,
    attested: bool = False,
    forks: tuple[LedgerForkPoint, ...] = (),
    orphans: tuple[_Orphan, ...] = (),
) -> Checkpoint:
    return Checkpoint(
        verified_seq=100,
        verified_hash="h100",
        verified_count=100,
        content_ok=content_ok,
        broken_at=broken_at,
        attested=attested,
        forks=forks,
        orphans=orphans,
        full_verified_at=datetime(2026, 7, 13, tzinfo=UTC),
        full_verified_seq=100,
    )


def _merge(cp: Checkpoint, **kwargs: object) -> tuple[object, ...]:
    defaults: dict[str, object] = {
        "new_hashes": set(),
        "new_content_ok": True,
        "new_broken_at": None,
        "new_attested": False,
        "touched_forks": (),
        "new_orphans": (),
    }
    defaults.update(kwargs)
    return merge_verdict(cp, **defaults)  # type: ignore[arg-type]


def test_a_broken_prefix_stays_broken_however_clean_the_new_rows_are() -> None:
    """Content integrity is a conjunction. A tampered row does not scroll off the bottom."""
    content_ok, broken_at, _, _, _ = _merge(
        _checkpoint(content_ok=False, broken_at=42), new_content_ok=True
    )
    assert content_ok is False
    assert broken_at == 42


def test_broken_at_keeps_the_first_break_not_the_newest() -> None:
    """An investigator needs where it started, not where it was last noticed."""
    _, broken_at, _, _, _ = _merge(
        _checkpoint(content_ok=False, broken_at=42), new_content_ok=False, new_broken_at=900
    )
    assert broken_at == 42


def test_a_break_in_the_new_rows_alone_is_caught() -> None:
    content_ok, broken_at, _, _, _ = _merge(_checkpoint(), new_content_ok=False, new_broken_at=101)
    assert content_ok is False
    assert broken_at == 101


def test_an_attestation_once_seen_is_never_unseen() -> None:
    _, _, attested, _, _ = _merge(_checkpoint(attested=True), new_attested=False)
    assert attested is True


def test_a_new_row_can_fork_an_old_parent_and_the_delta_is_authoritative() -> None:
    """The trap: a fork point can be created today by a row whose parent is from last month.

    A checkpoint that only ever ADDED forks would miss it. The delta query re-groups every parent
    the new rows touch and its answer WINS over the checkpoint's for those parents.
    """
    cp = _checkpoint(forks=(LedgerForkPoint("old_parent", ("child_a",)),))
    _, _, _, forks, _ = _merge(
        cp, touched_forks=(LedgerForkPoint("old_parent", ("child_a", "child_b")),)
    )
    assert len(forks) == 1
    assert forks[0].children == ("child_a", "child_b")  # not the stale one-child version


def test_an_untouched_fork_survives_untouched() -> None:
    """Append-only means a parent no new row points at cannot have gained a child."""
    cp = _checkpoint(forks=(LedgerForkPoint("p1", ("a", "b")), LedgerForkPoint("p2", ("c", "d"))))
    _, _, _, forks, _ = _merge(cp, touched_forks=(LedgerForkPoint("p2", ("c", "d", "e")),))
    by_parent = {f.prev_hash: f.children for f in forks}
    assert by_parent["p1"] == ("a", "b")
    assert by_parent["p2"] == ("c", "d", "e")


def test_a_new_row_that_is_the_missing_parent_resolves_the_orphan() -> None:
    """The subtle one: an orphan is a completeness gap, and a late write can CLOSE it.

    A verifier that only ever accumulated orphans would keep reporting one forever, and the badge
    would stay amber on a chain that had healed.
    """
    cp = _checkpoint(orphans=(_Orphan(child="lonely", parent="missing_parent"),))
    _, _, _, _, orphans = _merge(cp, new_hashes={"missing_parent"})
    assert orphans == ()


def test_an_orphan_whose_parent_is_still_missing_survives() -> None:
    cp = _checkpoint(orphans=(_Orphan(child="lonely", parent="missing_parent"),))
    _, _, _, _, orphans = _merge(cp, new_hashes={"some_other_hash"})
    assert [o.child for o in orphans] == ["lonely"]


def test_new_orphans_are_added_to_the_surviving_ones() -> None:
    cp = _checkpoint(orphans=(_Orphan(child="old_orphan", parent="still_missing"),))
    _, _, _, _, orphans = _merge(
        cp,
        new_hashes={"h101"},
        new_orphans=(_Orphan(child="new_orphan", parent="also_missing"),),
    )
    assert sorted(o.child for o in orphans) == ["new_orphan", "old_orphan"]


def test_an_empty_delta_changes_nothing() -> None:
    """The commonest case by far: no new rows. The verdict must be the checkpoint's, exactly."""
    cp = _checkpoint(
        content_ok=True,
        attested=True,
        forks=(LedgerForkPoint("p", ("a", "b")),),
        orphans=(_Orphan(child="o", parent="m"),),
    )
    content_ok, broken_at, attested, forks, orphans = _merge(cp)
    assert (content_ok, broken_at, attested) == (True, None, True)
    assert forks == cp.forks
    assert orphans == cp.orphans
