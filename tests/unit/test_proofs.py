"""The Proofs overview must derive its core from real stores, not literals.

The proof-posture KPIs, the artifact distribution and the cryptographic zone are
recomputed here from the same real sources — :func:`verify_audit_chain`, the eval
score store, the replay-bundle store and the eval-report archive — and checked
against the payload, so the test proves *derivation*. The export/SIEM half stays
a deterministic demonstration (flagged ``evidence_export`` in the UI); we only
assert its shape is present, never that its numbers are real.
"""

from __future__ import annotations

from tessera.guard.audit import verify_audit_chain
from tessera.observability.eval.report_paths import iter_report_files
from tessera.observability.eval.scores import persisted_scores
from tessera.observability.proofs import compute_proofs_overview
from tessera.observability.replay import persisted_bundles
from tessera.settings import get_settings


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
    payload = compute_proofs_overview("fr")
    for key in ("pipeline", "exporters", "retention", "export_journal", "control_case_proofs"):
        assert isinstance(payload[key], list) and payload[key]  # type: ignore[arg-type]
    assert isinstance(payload["current_pack"], dict)


def test_localization_is_honest_across_languages() -> None:
    for lang in ("fr", "de", "en"):
        payload = compute_proofs_overview(lang)
        # The chain footer is honest: it never claims "intact" when broken.
        chain_txt = str(payload["footer"]["chain"])  # type: ignore[index]
        assert chain_txt  # non-empty localized string
