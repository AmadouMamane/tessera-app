"""Unit tests for the Hica external opposability seal (ADR 0015 §Amendment 3 / §Correction 3c).

Hermetic — no database, no network. The real RFC 3161 provider's network/exec path is a Lot 3
integration concern; here a ``FakeProvider`` stands in so the compose logic, the register §9 badge
matrix, the seal cycle, and the honesty invariants are exercised in isolation.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest

from tessera.guard import seal as S  # noqa: N812  module alias
from tessera.guard.audit import LEDGER_ATTESTATION_TYPE, LEDGER_SEAL_TYPE, _hash_core
from tessera.guard.ledger_store import LedgerForkPoint, LedgerTreeStatus

_GENESIS = "0" * 64
_NOW = datetime(2026, 7, 8, 12, 0, tzinfo=UTC)


class FakeProvider:
    """A test double that mints and verifies a trivial token (material == 'GOOD')."""

    name = "fake"

    def __init__(self, *, qualified: bool = True, good: bool = True) -> None:
        self.qualified = qualified
        self._good = good

    def seal(self, head_hash: str) -> S.SealToken:
        return S.SealToken(
            sealed_head=head_hash,
            sealed_at=_NOW.isoformat(),
            provider=self.name,
            qualified=self.qualified,
            tsa="https://fake.tsa",
            material="GOOD",
        )

    def verify(self, token: S.SealToken, head_hash: str) -> S.SealVerification:
        ok = self._good and token.material == "GOOD"
        return S.SealVerification(
            verified=ok,
            qualified=self.qualified and ok,
            provider=self.name,
            sealed_head=token.sealed_head,
            sealed_at=token.sealed_at,
            reason=None if ok else "bad token",
        )


def _chain(*entries: dict[str, Any]) -> list[dict[str, Any]]:
    """Link entries into a content-intact hash chain (like the real writer)."""
    prev = _GENESIS
    out: list[dict[str, Any]] = []
    for raw in entries:
        entry = {**raw, "prev_hash": prev}
        entry["hash"] = _hash_core({k: v for k, v in entry.items() if k != "hash"})
        prev = entry["hash"]
        out.append(entry)
    return out


def _seal_entry(
    sealed_head: str, sealed_at: str, *, material: str = "GOOD", divergence: bool = False
) -> dict[str, Any]:
    return {
        "type": LEDGER_SEAL_TYPE,
        "sealed_head": sealed_head,
        "sealed_at": sealed_at,
        "provider": "fake",
        "qualified": True,
        "token_b64": material,
        "divergence": divergence,
    }


def _tree(
    *, content: bool = True, linear: bool = True, attested: bool = False, forked: bool = False
) -> LedgerTreeStatus:
    forks = (LedgerForkPoint("p", ("a", "b")),) if forked else ()
    return LedgerTreeStatus(
        content_integrity=content,
        linear=linear and not forked,
        forks=forks,
        orphans=(),
        length=3,
        broken_at=None,
        attested=attested,
    )


def _sstat(state: str, *, qualified: bool = True) -> S.SealStatus:
    return S.SealStatus(
        state=state, provider="fake", qualified=qualified, sealed_head="h", sealed_at="t"
    )


# ── Honesty invariant H1: no provider configured ⇒ never a token, never a seal ──


def test_default_provider_is_noop() -> None:
    assert isinstance(S.get_seal_provider(), S.NoOpProvider)


def test_noop_provider_cannot_mint_a_token() -> None:
    with pytest.raises(S.SealUnavailableError):
        S.NoOpProvider().seal("deadbeef")


def test_evaluate_seal_is_absent_under_noop_even_with_a_seal_entry() -> None:
    # A prior seal entry exists, but the provider is now NoOp → no trust root → absent, never green.
    payloads = [_seal_entry("h", _NOW.isoformat())]
    status = S.evaluate_seal(payloads, provider=S.NoOpProvider(), now=_NOW, staleness_budget_s=7200)
    assert status.state == "absent"


def test_rfc3161_provider_when_configured() -> None:
    settings = SimpleNamespace(
        guard=SimpleNamespace(
            seal_provider="rfc3161",
            seal_tsa_url="https://tsa.example",
            seal_tsa_cert=None,
            seal_tsa_qualified=True,
        )
    )
    provider = S.get_seal_provider(settings)  # type: ignore[arg-type]
    assert isinstance(provider, S.Rfc3161Provider)
    assert provider.qualified is True


# ── Register §9 badge matrix (design note §6) ───────────────────────────────────


@pytest.mark.parametrize(
    ("tree", "seal", "expected"),
    [
        (_tree(content=False), _sstat("verified"), "non_scelle"),  # row 1: broken ⇒ non scellé
        (_tree(), _sstat("verified", qualified=True), "scelle_opposable"),  # row 2a
        (_tree(), _sstat("verified", qualified=False), "scelle_non_qualifie"),  # row 2b
        (
            _tree(forked=True, attested=True),
            _sstat("verified"),
            "scelle_opposable",
        ),  # forked+attested
        (_tree(forked=True, attested=False), _sstat("verified"), "integrite_partielle"),  # Q3
        (_tree(), _sstat("absent"), "integrite_partielle"),  # row 4
        (_tree(), _sstat("stale"), "integrite_partielle"),
        (_tree(), _sstat("unverifiable"), "integrite_partielle"),
        (_tree(), _sstat("divergent"), "integrite_partielle"),
    ],
)
def test_seal_badge_matrix(tree: LedgerTreeStatus, seal: S.SealStatus, expected: str) -> None:
    assert S.seal_badge(tree, seal) == expected


# ── evaluate_seal states ────────────────────────────────────────────────────────


def test_evaluate_seal_verified() -> None:
    payloads = [_seal_entry("h", _NOW.isoformat())]
    status = S.evaluate_seal(
        payloads, provider=FakeProvider(qualified=True), now=_NOW, staleness_budget_s=7200
    )
    assert status.state == "verified"
    assert status.qualified is True


def test_evaluate_seal_unverifiable_when_token_fails() -> None:
    payloads = [_seal_entry("h", _NOW.isoformat(), material="BAD")]
    status = S.evaluate_seal(payloads, provider=FakeProvider(), now=_NOW, staleness_budget_s=7200)
    assert status.state == "unverifiable"


def test_evaluate_seal_stale_beyond_budget() -> None:
    old = (_NOW - timedelta(hours=3)).isoformat()
    payloads = [_seal_entry("h", old)]
    status = S.evaluate_seal(payloads, provider=FakeProvider(), now=_NOW, staleness_budget_s=7200)
    assert status.state == "stale"


def test_evaluate_seal_divergent_flag() -> None:
    payloads = [_seal_entry("h", _NOW.isoformat(), divergence=True)]
    status = S.evaluate_seal(payloads, provider=FakeProvider(), now=_NOW, staleness_budget_s=7200)
    assert status.state == "divergent"


def test_evaluate_seal_absent_without_entry() -> None:
    status = S.evaluate_seal([], provider=FakeProvider(), now=_NOW, staleness_budget_s=7200)
    assert status.state == "absent"


def test_latest_seal_entry_respects_as_of() -> None:
    early = _seal_entry("h1", "2026-07-08T10:00:00+00:00")
    late = _seal_entry("h2", "2026-07-08T14:00:00+00:00")
    payloads = [early, late]
    at = datetime(2026, 7, 8, 12, 0, tzinfo=UTC)
    picked = S.latest_seal_entry(payloads, at=at)
    assert picked is not None
    assert picked["sealed_head"] == "h1"  # the 14:00 seal is after T, excluded


# ── head continuity (the §Correction 3c divergence detector) ───────────────────


def test_head_continuity_genesis_and_continuous() -> None:
    chain = _chain({"n": 1}, {"n": 2}, {"n": 3})
    assert S._head_continuity(chain, None, chain[-1]["hash"]) == "genesis"
    assert S._head_continuity(chain, chain[0]["hash"], chain[-1]["hash"]) == "continuous"


def test_head_continuity_rewrite_when_prev_head_missing() -> None:
    chain = _chain({"n": 1}, {"n": 2})
    assert S._head_continuity(chain, "0" * 63 + "1", chain[-1]["hash"]) == "rewrite"


def test_head_continuity_divergent_on_fork() -> None:
    chain = _chain({"n": 1}, {"n": 2})
    child2 = {"n": 99, "prev_hash": chain[0]["hash"]}
    child2["hash"] = _hash_core(child2)
    forked = [*chain, child2]  # chain[0] now has two children ⇒ fork
    assert S._head_continuity(forked, chain[0]["hash"], chain[1]["hash"]) == "divergent"


# ── seal cycle (writer) ─────────────────────────────────────────────────────────


def test_run_seal_cycle_appends_a_seal_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    payloads = _chain({"n": 1}, {"n": 2})
    captured: dict[str, Any] = {}
    monkeypatch.setattr(S, "_read_active_payloads", lambda *_a, **_k: payloads)
    monkeypatch.setattr(S, "emit_ledger_seal", lambda **kw: captured.update(kw))
    result = S.run_seal_cycle(provider=FakeProvider())
    assert result.sealed is True
    assert result.state == "sealed"
    assert result.continuity == "genesis"  # no prior seal
    assert result.head == payloads[-1]["hash"]
    assert captured["sealed_head"] == payloads[-1]["hash"]
    assert captured["prev_sealed_head"] is None
    assert captured["divergence"] is False


def test_run_seal_cycle_unavailable_appends_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """H3 — provider down ⇒ no entry appended (no placeholder, never a fake seal)."""
    payloads = _chain({"n": 1}, {"n": 2})
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(S, "_read_active_payloads", lambda *_a, **_k: payloads)
    monkeypatch.setattr(S, "emit_ledger_seal", lambda **kw: calls.append(kw))
    result = S.run_seal_cycle(provider=S.NoOpProvider())
    assert result.sealed is False
    assert result.state == "unavailable"
    assert calls == []


def test_run_seal_cycle_empty_ledger(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(S, "_read_active_payloads", lambda *_a, **_k: [])
    result = S.run_seal_cycle(provider=FakeProvider())
    assert result.sealed is False
    assert result.state == "empty"


def test_run_seal_cycle_flags_divergence(monkeypatch: pytest.MonkeyPatch) -> None:
    # A prior seal references a head absent from the chain (a lost/rewritten head): the continuity
    # walk cannot reach it ⇒ "rewrite" ⇒ the new seal entry is stamped divergence=True.
    seal_core = _seal_entry("f" * 64, _NOW.isoformat())  # sealed_head not present in the chain
    payloads = _chain(
        {"n": 1}, {"n": 2}, seal_core
    )  # the seal entry is itself chained (has a hash)
    captured: dict[str, Any] = {}
    monkeypatch.setattr(S, "_read_active_payloads", lambda *_a, **_k: payloads)
    monkeypatch.setattr(S, "emit_ledger_seal", lambda **kw: captured.update(kw))
    result = S.run_seal_cycle(provider=FakeProvider())
    assert result.continuity == "rewrite"
    assert captured["divergence"] is True


def test_attestation_type_is_not_a_seal() -> None:
    # Guard against a copy-paste: the two appended-entry families are distinct.
    assert LEDGER_SEAL_TYPE != LEDGER_ATTESTATION_TYPE
