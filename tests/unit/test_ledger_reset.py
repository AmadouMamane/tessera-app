"""Unit tests for the guarded ledger reset (P2).

Covers the two refuse-before-run locks and the empty-proof parse — the pure logic that decides
whether the destructive TRUNCATE may run and whether it actually emptied the tables. The docker /
psql legs are integration-shaped and exercised by `make ledger-reset` against a live container.
"""

from __future__ import annotations

from scripts.ledger_reset import guard, remaining_rows

from tessera.verdict import CannotSay, NotOk


class TestGuard:
    def test_non_local_schema_is_refused(self) -> None:
        # Structural lock: a production schema can never reach the TRUNCATE, even fully confirmed.
        assert isinstance(guard("tessera_prod", "tessera_prod"), NotOk)

    def test_ci_schema_is_refused(self) -> None:
        # `tessera_ci` is not a demo ledger either — only a `_local` one may be wiped.
        assert isinstance(guard("tessera_ci", "tessera_ci"), NotOk)

    def test_missing_confirmation_is_refused(self) -> None:
        assert isinstance(guard("tessera_local", None), CannotSay)

    def test_mismatched_confirmation_is_refused(self) -> None:
        assert isinstance(guard("tessera_local", "yes"), CannotSay)

    def test_named_confirmation_on_local_schema_proceeds(self) -> None:
        assert guard("tessera_local", "tessera_local") is None


class TestRemainingRows:
    def test_parses_a_count(self) -> None:
        assert remaining_rows("0\n") == 0
        assert remaining_rows(" 42 ") == 42

    def test_unparseable_is_none(self) -> None:
        assert remaining_rows("") is None
        assert remaining_rows("not a number") is None
