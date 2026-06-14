"""Proofs & exporter cockpit overview (page #15).

Composes the "Preuves & exporteurs" overview: the proof posture (packs
generated, signed artifacts, export rate, active exporters, latency, retention
coverage), the proof-assembly pipeline, the current evidence pack, the recent
packs, the artifact distribution, the exporters & destinations, the
cryptographic verification, the control-case-linked proofs, the retention
obligations and the live export journal.

The dataset is a deterministic reference fixture (no live proof store in this
build); values are stable across calls so the page never "dances".
"""

from __future__ import annotations

from datetime import UTC, datetime

__all__ = ["compute_proofs_overview"]

_ART_COLOR = {
    "audit_logs": "#60a5fa",
    "eval_scores": "#34d399",
    "replays": "#a78bfa",
    "manifests": "#fbbf24",
    "snapshots": "#f472b6",
    "reports": "#64748b",
}


def _kpi(
    key: str, value: str, delta_label: str, good_is_up: bool, series: list[int]
) -> dict[str, object]:
    return {
        "key": key,
        "value": value,
        "delta_label": delta_label,
        "good_is_up": good_is_up,
        "series": series,
    }


def compute_proofs_overview() -> dict[str, object]:
    """Return the full Proofs & exporter overview payload.

    Returns:
        A JSON-serialisable mapping with the proof posture KPIs, the assembly
        pipeline, the current evidence pack, the recent packs, the artifact
        distribution, the exporters & destinations, the cryptographic
        verification, the control-case proofs, the retention obligations and
        the export journal.
    """
    now = datetime.now(UTC)

    kpis = [
        _kpi("packs", "42", "+16%", True, [30, 33, 35, 37, 39, 40, 42]),
        _kpi("artifacts", "1 248", "+12%", True, [980, 1040, 1100, 1150, 1190, 1220, 1248]),
        _kpi("export_rate", "99.6%", "+0.3 pp", True, [98, 98, 99, 99, 99, 99, 100]),
        _kpi("exporters", "8 / 8", "0", True, [8, 8, 8, 8, 8, 8, 8]),
        _kpi("latency", "18 s", "-8%", False, [24, 23, 22, 21, 20, 19, 18]),
        _kpi("retention", "100%", "0 pp", True, [100, 100, 100, 100, 100, 100, 100]),
    ]

    alerts = [
        {"level": "warn", "label": "1 destination dégradée"},
        {"level": "ok", "label": "0 perte de données"},
    ]

    pipeline = [
        {"key": "collecte", "count": "1 248", "status": "ok"},
        {"key": "normalisation", "count": "1 248", "status": "ok"},
        {"key": "signature", "count": "1 248", "status": "ok"},
        {"key": "pack", "count": "42", "status": "ok"},
        {"key": "export", "count": "41 / 42", "status": "ok"},
    ]

    current_pack = {
        "id": "PK-2026-06-11-042",
        "period": "04/06/2026 → 11/06/2026",
        "scope": "Prod · Crédit Aurore · FR",
        "hash": "sha256: 83fa…9c1e",
        "signer": "Admin / Claire L.",
        "contents": [
            {"key": "audit_logs", "n": 86},
            {"key": "eval_cases", "n": 63},
            {"key": "incidents", "n": 14},
            {"key": "release_manifests", "n": 6},
            {"key": "policy_snapshots", "n": 3},
        ],
    }

    recent_packs = [
        {
            "id": "PK-2026-06-11-042",
            "scope": "Prod · Crédit Aurore · FR",
            "artifacts": "172",
            "signature": "ok",
            "destinations": "6 / 6",
            "by": "Claire L.",
            "time": "11:54",
            "status": "signe",
        },
        {
            "id": "PK-2026-06-11-041",
            "scope": "Prod · Crédit Aurore · FR",
            "artifacts": "168",
            "signature": "ok",
            "destinations": "6 / 6",
            "by": "Amadou D.",
            "time": "10:38",
            "status": "exporte",
        },
        {
            "id": "PK-2026-06-11-040",
            "scope": "Prod · Crédit Aurore · FR",
            "artifacts": "165",
            "signature": "ok",
            "destinations": "5 / 6",
            "by": "Amadou D.",
            "time": "09:12",
            "status": "exporte",
        },
        {
            "id": "PK-2026-06-10-039",
            "scope": "Preprod · Crédit Aurore · FR",
            "artifacts": "158",
            "signature": "ok",
            "destinations": "6 / 6",
            "by": "Système",
            "time": "18:47",
            "status": "attente",
        },
        {
            "id": "PK-2026-06-10-038",
            "scope": "Prod · Crédit Aurore · FR",
            "artifacts": "154",
            "signature": "ok",
            "destinations": "5 / 6",
            "by": "System",
            "time": "16:03",
            "status": "echec",
        },
    ]

    artifacts_distribution = [
        {"key": "audit_logs", "count": 512, "pct": 41, "color": _ART_COLOR["audit_logs"]},
        {"key": "eval_scores", "count": 256, "pct": 21, "color": _ART_COLOR["eval_scores"]},
        {"key": "replays", "count": 192, "pct": 15, "color": _ART_COLOR["replays"]},
        {"key": "manifests", "count": 128, "pct": 10, "color": _ART_COLOR["manifests"]},
        {"key": "snapshots", "count": 96, "pct": 8, "color": _ART_COLOR["snapshots"]},
        {"key": "reports", "count": 64, "pct": 5, "color": _ART_COLOR["reports"]},
    ]

    exporters = [
        {
            "destination": "SIEM / SOC",
            "format": "JSONL",
            "status": "ok",
            "last_push": "11:54",
            "queue": "0",
            "retention": "365 j",
        },
        {
            "destination": "S3 · Archive souveraine",
            "format": "JSONL",
            "status": "ok",
            "last_push": "10:36",
            "queue": "0",
            "retention": "10 ans",
        },
        {
            "destination": "Data room conformité",
            "format": "PDF · CSV",
            "status": "ok",
            "last_push": "10:36",
            "queue": "0",
            "retention": "5 ans",
        },
        {
            "destination": "GRC / Conformité",
            "format": "ZIP · sig",
            "status": "ok",
            "last_push": "10:21",
            "queue": "0",
            "retention": "7 ans",
        },
        {
            "destination": "API partenaire",
            "format": "JSON",
            "status": "degraded",
            "last_push": "10:21",
            "queue": "1",
            "retention": "180 j",
        },
    ]

    crypto = {
        "valid_signatures": "100%",
        "algorithm": "Ed25519",
        "key_rotation": "12/05/2026",
        "anomalies": 0,
    }

    control_case_proofs = [
        {
            "case_id": "CC-012",
            "subject": "Fuite PII & mémoire",
            "linked": 8,
            "owner": "A. Privacy",
            "status": "ok",
        },
        {
            "case_id": "CC-007",
            "subject": "Hallucination systématique",
            "linked": 5,
            "owner": "M. Engineer",
            "status": "ok",
        },
        {
            "case_id": "CC-004",
            "subject": "Conformité Art. 50",
            "linked": 4,
            "owner": "A. Compliance",
            "status": "pending",
        },
    ]

    retention = [
        {
            "destination": "S3 · Archive souveraine",
            "proof_type": "Logs d'audit",
            "retention": "10 ans",
            "obligation": "DORA",
            "coverage": 100,
            "expiry": "—",
        },
        {
            "destination": "GRC / Conformité",
            "proof_type": "Evidence packs",
            "retention": "7 ans",
            "obligation": "BaFin",
            "coverage": 100,
            "expiry": "04/2033",
        },
        {
            "destination": "Data room conformité",
            "proof_type": "Rapports",
            "retention": "5 ans",
            "obligation": "RGPD",
            "coverage": 96,
            "expiry": "06/2031",
        },
    ]

    export_journal = [
        {"time": "11:54:18", "label": "Pack PK-…042 → SIEM / SOC", "status": "ok"},
        {"time": "11:53:40", "label": "Pack PK-…042 → S3 archive", "status": "ok"},
        {"time": "11:52:05", "label": "Pack PK-…041 → API partenaire", "status": "degraded"},
        {"time": "11:48:31", "label": "Pack PK-…041 → GRC / Conformité", "status": "ok"},
        {"time": "11:42:12", "label": "Signature PK-…041 vérifiée", "status": "ok"},
    ]

    queue = {"pending_signature": 2, "pending_export": 3, "verifications": 1}

    return {
        "generated_at": now.isoformat(),
        "period_days": 7,
        "updated_at": "11:54:01",
        "kpis": kpis,
        "alerts": alerts,
        "alert_count": 2,
        "pipeline": pipeline,
        "current_pack": current_pack,
        "recent_packs": recent_packs,
        "artifacts_distribution": artifacts_distribution,
        "artifacts_total": 1248,
        "exporters": exporters,
        "crypto": crypto,
        "control_case_proofs": control_case_proofs,
        "retention": retention,
        "export_journal": export_journal,
        "queue": queue,
        "footer": {"chain": "Chaîne de preuve intacte", "source": "YAML · Git"},
    }
