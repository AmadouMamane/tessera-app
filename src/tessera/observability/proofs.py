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

from tessera.observability.knowledge import _LANG_IDX, _norm_lang

__all__ = ["compute_proofs_overview"]

_ART_COLOR = {
    "audit_logs": "#60a5fa",
    "eval_scores": "#34d399",
    "replays": "#a78bfa",
    "manifests": "#fbbf24",
    "snapshots": "#f472b6",
    "reports": "#64748b",
}

# Localized free-text (fr, de, en). IDs, hashes, dates, names, deployment scopes
# (Prod / Credit Aurore / FR), format codes (JSONL/PDF) and obligation codes
# (DORA/BaFin/RGPD) stay verbatim; only human prose is translated.
_TR: dict[str, tuple[str, str, str]] = {
    "alert_degraded": ("1 destination dégradée", "1 Ziel degradiert", "1 destination degraded"),
    "alert_noloss": ("0 perte de données", "0 Datenverlust", "0 data loss"),
    "u_years": ("{n} ans", "{n} Jahre", "{n} yrs"),
    "u_days": ("{n} j", "{n} T", "{n} d"),
    "dest_s3": ("S3 · Archive souveraine", "S3 · Souveraenes Archiv", "S3 · Sovereign archive"),
    "dest_dataroom": (
        "Data room conformité",
        "Compliance-Datenraum",
        "Compliance data room",
    ),
    "dest_grc": ("GRC / Conformité", "GRC / Compliance", "GRC / Compliance"),
    "dest_partner": ("API partenaire", "Partner-API", "Partner API"),
    "subj_pii": ("Fuite PII & mémoire", "PII- & Speicherleck", "PII & memory leak"),
    "subj_hallu": (
        "Hallucination systématique",
        "Systematische Halluzination",
        "Systematic hallucination",
    ),
    "subj_art50": ("Conformité Art. 50", "Konformitaet Art. 50", "Art. 50 compliance"),
    "pt_audit": ("Logs d'audit", "Audit-Logs", "Audit logs"),
    "pt_packs": ("Evidence packs", "Evidence-Packs", "Evidence packs"),
    "pt_reports": ("Rapports", "Berichte", "Reports"),
    "actor_system": ("Système", "System", "System"),
    "ej_sig_verified": (
        "Signature PK-…041 vérifiée",
        "Signatur PK-…041 verifiziert",
        "Signature PK-…041 verified",
    ),
    "footer_chain": (
        "Chaîne de preuve intacte",
        "Beweiskette intakt",
        "Proof chain intact",
    ),
}


def _t(key: str, lang: str) -> str:
    return _TR[key][_LANG_IDX.get(lang, 0)]


def _years(n: int, lang: str) -> str:
    return _TR["u_years"][_LANG_IDX.get(lang, 0)].format(n=n)


def _days(n: int, lang: str) -> str:
    return _TR["u_days"][_LANG_IDX.get(lang, 0)].format(n=n)


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


def compute_proofs_overview(lang: str = "fr") -> dict[str, object]:
    """Return the full Proofs & exporter overview payload.

    Args:
        lang: UI language (``fr`` / ``de`` / ``en``) for the localized free-text.

    Returns:
        A JSON-serialisable mapping with the proof posture KPIs, the assembly
        pipeline, the current evidence pack, the recent packs, the artifact
        distribution, the exporters & destinations, the cryptographic
        verification, the control-case proofs, the retention obligations and
        the export journal.
    """
    lang = _norm_lang(lang)
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
        {"level": "warn", "label": _t("alert_degraded", lang)},
        {"level": "ok", "label": _t("alert_noloss", lang)},
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
            "by": _t("actor_system", lang),
            "time": "18:47",
            "status": "attente",
        },
        {
            "id": "PK-2026-06-10-038",
            "scope": "Prod · Crédit Aurore · FR",
            "artifacts": "154",
            "signature": "ok",
            "destinations": "5 / 6",
            "by": _t("actor_system", lang),
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
            "retention": _days(365, lang),
        },
        {
            "destination": _t("dest_s3", lang),
            "format": "JSONL",
            "status": "ok",
            "last_push": "10:36",
            "queue": "0",
            "retention": _years(10, lang),
        },
        {
            "destination": _t("dest_dataroom", lang),
            "format": "PDF · CSV",
            "status": "ok",
            "last_push": "10:36",
            "queue": "0",
            "retention": _years(5, lang),
        },
        {
            "destination": _t("dest_grc", lang),
            "format": "ZIP · sig",
            "status": "ok",
            "last_push": "10:21",
            "queue": "0",
            "retention": _years(7, lang),
        },
        {
            "destination": _t("dest_partner", lang),
            "format": "JSON",
            "status": "degraded",
            "last_push": "10:21",
            "queue": "1",
            "retention": _days(180, lang),
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
            "subject": _t("subj_pii", lang),
            "linked": 8,
            "owner": "A. Privacy",
            "status": "ok",
        },
        {
            "case_id": "CC-007",
            "subject": _t("subj_hallu", lang),
            "linked": 5,
            "owner": "M. Engineer",
            "status": "ok",
        },
        {
            "case_id": "CC-004",
            "subject": _t("subj_art50", lang),
            "linked": 4,
            "owner": "A. Compliance",
            "status": "pending",
        },
    ]

    retention = [
        {
            "destination": _t("dest_s3", lang),
            "proof_type": _t("pt_audit", lang),
            "retention": _years(10, lang),
            "obligation": "DORA",
            "coverage": 100,
            "expiry": "—",
        },
        {
            "destination": _t("dest_grc", lang),
            "proof_type": _t("pt_packs", lang),
            "retention": _years(7, lang),
            "obligation": "BaFin",
            "coverage": 100,
            "expiry": "04/2033",
        },
        {
            "destination": _t("dest_dataroom", lang),
            "proof_type": _t("pt_reports", lang),
            "retention": _years(5, lang),
            "obligation": "RGPD",
            "coverage": 96,
            "expiry": "06/2031",
        },
    ]

    export_journal = [
        {"time": "11:54:18", "label": "Pack PK-…042 → SIEM / SOC", "status": "ok"},
        {"time": "11:53:40", "label": "Pack PK-…042 → S3 archive", "status": "ok"},
        {
            "time": "11:52:05",
            "label": f"Pack PK-…041 → {_t('dest_partner', lang)}",
            "status": "degraded",
        },
        {"time": "11:48:31", "label": f"Pack PK-…041 → {_t('dest_grc', lang)}", "status": "ok"},
        {"time": "11:42:12", "label": _t("ej_sig_verified", lang), "status": "ok"},
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
        "footer": {"chain": _t("footer_chain", lang), "source": "YAML · Git"},
    }
