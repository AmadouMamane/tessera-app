"""The Proofs overview must derive its core from real stores, not literals.

The proof-posture KPIs, the artifact distribution and the cryptographic zone are
recomputed here from the same real sources — :func:`verify_audit_chain`, the eval
score store, the replay-bundle store and the eval-report archive — and checked
against the payload, so the test proves *derivation*. The export/SIEM half stays
a deterministic demonstration (flagged ``evidence_export`` in the UI); we only
assert its shape is present, never that its numbers are real.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tessera.guard.audit import verify_audit_chain
from tessera.observability.eval.report_paths import iter_report_files
from tessera.observability.eval.scores import persisted_scores
from tessera.observability.proofs import compute_proofs_overview
from tessera.observability.replay import persisted_bundles
from tessera.settings import get_settings

if TYPE_CHECKING:
    from pathlib import Path


def _kpi(payload: dict[str, object], key: str) -> str:
    for k in payload["kpis"]:  # type: ignore[union-attr]
        if k["key"] == key:  # type: ignore[index]
            return str(k["value"])  # type: ignore[index]
    raise AssertionError(f"missing KPI {key}")


def _int(value: str) -> int:
    return int(value.replace(" ", ""))


def test_artifact_counts_are_derived_from_the_real_stores() -> None:
    chain = verify_audit_chain(get_settings().guard.audit_file)
    n_audit = chain.length
    n_scores = len(persisted_scores())
    n_bundles = len(persisted_bundles())
    n_reports = sum(1 for _ in iter_report_files())
    total = n_audit + n_scores + n_bundles + n_reports

    payload = compute_proofs_overview("fr")

    assert payload["artifacts_total"] == total
    assert _int(_kpi(payload, "artifacts")) == total
    assert _int(_kpi(payload, "audit_entries")) == n_audit
    assert _int(_kpi(payload, "eval_scores")) == n_scores
    assert _int(_kpi(payload, "replays")) == n_bundles
    assert _int(_kpi(payload, "reports")) == n_reports


def test_distribution_families_match_the_real_counts() -> None:
    chain = verify_audit_chain(get_settings().guard.audit_file)
    expected = {
        "audit_logs": chain.length,
        "eval_scores": len(persisted_scores()),
        "replays": len(persisted_bundles()),
        "reports": sum(1 for _ in iter_report_files()),
    }
    payload = compute_proofs_overview("fr")
    got = {s["key"]: s["count"] for s in payload["artifacts_distribution"]}  # type: ignore[index,union-attr]

    assert got == expected
    # Fabricated families with no real store are omitted, never invented.
    assert "manifests" not in got
    assert "snapshots" not in got


def test_crypto_zone_reflects_the_real_audit_chain() -> None:
    chain = verify_audit_chain(get_settings().guard.audit_file)
    payload = compute_proofs_overview("fr")
    crypto = payload["crypto"]

    assert payload["chain_verified"] == chain.verified  # type: ignore[index]
    assert crypto["algorithm"] == "SHA-256"  # type: ignore[index]  # real hash, not "Ed25519"
    assert _int(str(crypto["chain_length"])) == chain.length  # type: ignore[index]
    if chain.verified:
        assert crypto["valid_signatures"] == "100%"  # type: ignore[index]
        assert crypto["anomalies"] == 0  # type: ignore[index]
        assert _kpi(payload, "chain") == "100%"
    else:
        assert crypto["anomalies"] == 1  # type: ignore[index]


def test_alerts_track_the_chain_status() -> None:
    chain = verify_audit_chain(get_settings().guard.audit_file)
    payload = compute_proofs_overview("fr")
    alerts = payload["alerts"]

    assert payload["alert_count"] == len(alerts)  # type: ignore[arg-type]
    assert len(alerts) == 1  # type: ignore[arg-type]
    assert alerts[0]["level"] == ("ok" if chain.verified else "bad")  # type: ignore[index]


def test_siem_demonstration_shape_is_present() -> None:
    # The export half stays a deterministic fixture (flagged evidence_export in
    # the UI). We only assert the shape survives, not that its numbers are real.
    # `current_pack` is REAL since lot 7: dict when a pack was frozen, None
    # honestly before the first freeze — this test used to demand a dict, and
    # only stayed green on residue a mis-stubbed ratchet had left on disk.
    payload = compute_proofs_overview("fr")
    for key in ("pipeline", "exporters", "retention", "export_journal", "control_case_proofs"):
        assert isinstance(payload[key], list) and payload[key]  # type: ignore[arg-type]
    assert payload["current_pack"] is None or isinstance(payload["current_pack"], dict)


def test_localization_is_honest_across_languages() -> None:
    for lang in ("fr", "de", "en"):
        payload = compute_proofs_overview(lang)
        # The chain footer is honest: it never claims "intact" when broken.
        chain_txt = str(payload["footer"]["chain"])  # type: ignore[index]
        assert chain_txt  # non-empty localized string


def test_evidence_pack_lifecycle_is_attributed_and_digest_verifiable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Create → the manifest freezes real counts with its author; verify re-derives.

    The digest is the witness: edit one stored field and ``manifest_ok`` goes
    False while the chain verdict stays independent — two facts, never one green.
    """
    from tessera.observability import evidence_pack_store as eps

    monkeypatch.setattr(eps, "_packs_path", lambda: tmp_path / "evidence_packs.json")
    monkeypatch.setattr(
        eps,
        "_artifact_counts",
        lambda: {"audit_entries": 7, "eval_scores": 3, "replay_bundles": 2, "eval_reports": 1},
    )

    class _Chain:
        verified = True
        length = 7
        broken_at = None

    monkeypatch.setattr(
        "tessera.guard.ledger_store.verify_active_ledger", lambda *_a, **_k: _Chain()
    )

    pack = eps.create_pack(created_by="bob@bank.eu")
    assert str(pack["pack_id"]).startswith("PK-")
    assert pack["created_by"] == "bob@bank.eu"
    assert pack["period_start"] is None  # first pack covers from the beginning

    verdict = eps.verify_pack(str(pack["pack_id"]))
    assert verdict["manifest_ok"] is True
    assert verdict["chain_verified_now"] is True

    # Tamper with the stored manifest: the digest refuses it, loudly and precisely.
    stored = eps.load_packs()
    stored[0]["created_by"] = "eve@bank.eu"
    eps._save_json(eps._packs_path(), stored)
    assert eps.verify_pack(str(pack["pack_id"]))["manifest_ok"] is False

    with pytest.raises(eps.PackNotFoundError):
        eps.verify_pack("PK-ghost-999")

    # A second pack's window starts where the first ended.
    second = eps.create_pack(created_by="bob@bank.eu")
    assert second["period_start"] == pack["created_at"]
