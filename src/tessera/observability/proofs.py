"""Proofs & exporter cockpit overview (page #15).

Composes the "Preuves & exporteurs" overview. The page has two halves:

* **The derivable core is REAL.** The proof posture (artifact counts), the
  artifact distribution and the cryptographic-verification zone are computed
  from the actual durable stores this build owns — the hash-chained audit ledger
  (:func:`verify_audit_chain`), the eval-score store (the reader seam), the
  replay-bundle store (``persisted_bundles``) and the eval-report archive
  (``iter_report_files``). The chain integrity is reported honestly: verified
  when the on-disk chain re-derives, broken (with the first bad index) otherwise.

* **The export / SIEM subsystem is a demonstration.** Evidence-pack assembly,
  signing and export, the exporters & destinations, control-case linkage, the
  retention obligations and the export journal describe a full enterprise
  subsystem that does not exist in this build. Those fields stay a deterministic
  reference fixture, and the frontend marks their zones with the registry-driven
  ``evidence_export`` synthetic notice — never presenting them as live.
"""

from __future__ import annotations

from datetime import UTC, datetime

from tessera.guard.ledger_store import verify_active_ledger
from tessera.observability.eval.report_paths import iter_report_files
from tessera.observability.knowledge import _LANG_IDX, _norm_lang
from tessera.observability.replay import persisted_bundles
from tessera.observability.spine.adapters import read_scores

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
    "alert_chain_ok": (
        "Chaîne d'audit vérifiée",
        "Audit-Kette verifiziert",
        "Audit chain verified",
    ),
    "alert_chain_broken": (
        "Chaîne d'audit rompue à l'entrée {n}",
        "Audit-Kette bei Eintrag {n} unterbrochen",
        "Audit chain broken at entry {n}",
    ),
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
    "footer_chain_broken": (
        "Chaîne de preuve rompue (entrée {n})",
        "Beweiskette unterbrochen (Eintrag {n})",
        "Proof chain broken (entry {n})",
    ),
}


def _t(key: str, lang: str) -> str:
    return _TR[key][_LANG_IDX.get(lang, 0)]


def _years(n: int, lang: str) -> str:
    return _TR["u_years"][_LANG_IDX.get(lang, 0)].format(n=n)


def _days(n: int, lang: str) -> str:
    return _TR["u_days"][_LANG_IDX.get(lang, 0)].format(n=n)


def _fmt_int(n: int) -> str:
    """Group thousands with a thin space (matches the normative's ``1 248``)."""
    return f"{n:,}".replace(",", " ")


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

    The proof-posture KPIs, the artifact distribution and the cryptographic
    verification are derived from real stores (audit ledger, eval scores, replay
    bundles, eval reports); the evidence-pack assembly/export and SIEM chrome are
    a deterministic demonstration flagged ``evidence_export`` in the frontend.

    Args:
        lang: UI language (``fr`` / ``de`` / ``en``) for the localized free-text.

    Returns:
        A JSON-serialisable mapping. ``chain_verified`` reflects the real audit
        chain; the ``crypto`` zone, the ``kpis`` and ``artifacts_distribution``
        are real; the pack/exporter/retention/journal fields are demonstration.
    """
    lang = _norm_lang(lang)
    now = datetime.now(UTC)

    # ── Real derivable core ────────────────────────────────────────────────
    chain = verify_active_ledger()
    n_audit = chain.length
    n_scores = len(read_scores(full=True))
    n_bundles = len(persisted_bundles())
    n_reports = sum(1 for _ in iter_report_files())
    total = n_audit + n_scores + n_bundles + n_reports

    def _pct(n: int) -> int:
        return round(n / total * 100) if total else 0

    def _flat(v: int) -> list[int]:
        # Honest: the current real count, no fabricated trend line.
        return [v] * 7

    # Percentage of the chain that re-derives cleanly (100% when intact; when a
    # break is found at index b, the b entries before it are the intact prefix).
    intact_pct = (
        100
        if chain.verified
        else (round((chain.broken_at or 0) / chain.length * 100) if chain.length else 0)
    )

    kpis = [
        _kpi("artifacts", _fmt_int(total), "0", True, _flat(total)),
        _kpi("audit_entries", _fmt_int(n_audit), "0", True, _flat(n_audit)),
        _kpi("eval_scores", _fmt_int(n_scores), "0", True, _flat(n_scores)),
        _kpi("replays", _fmt_int(n_bundles), "0", True, _flat(n_bundles)),
        _kpi("reports", _fmt_int(n_reports), "0", True, _flat(n_reports)),
        _kpi("chain", f"{intact_pct}%", "0", True, _flat(intact_pct)),
    ]

    if chain.verified:
        alerts = [{"level": "ok", "label": _t("alert_chain_ok", lang)}]
    else:
        alerts = [
            {
                "level": "bad",
                "label": _t("alert_chain_broken", lang).format(n=chain.broken_at),
            }
        ]

    # Real artifact families (durable stores only). manifests/snapshots have no
    # real store in this build, so they are omitted rather than fabricated.
    _families = [
        ("audit_logs", n_audit),
        ("reports", n_reports),
        ("eval_scores", n_scores),
        ("replays", n_bundles),
    ]
    _families.sort(key=lambda kv: kv[1], reverse=True)
    artifacts_distribution = [
        {"key": k, "count": n, "pct": _pct(n), "color": _ART_COLOR[k]} for k, n in _families
    ]

    crypto = {
        "valid_signatures": f"{intact_pct}%",
        "algorithm": "SHA-256",
        "chain_length": _fmt_int(n_audit),
        "anomalies": 0 if chain.verified else 1,
    }

    footer_chain = (
        _t("footer_chain", lang)
        if chain.verified
        else _t("footer_chain_broken", lang).format(n=chain.broken_at)
    )

    # ── SIEM / export subsystem — demonstration (flagged evidence_export) ───
    # These describe evidence-pack assembly, signing, export, destinations,
    # control-case linkage, retention and the export journal: a subsystem this
    # build does not implement. Kept as a deterministic reference fixture; the
    # frontend marks each zone with the registry-driven synthetic notice.
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
        "updated_at": now.strftime("%H:%M:%S"),
        "chain_verified": chain.verified,
        "kpis": kpis,
        "alerts": alerts,
        "alert_count": len(alerts),
        "pipeline": pipeline,
        "current_pack": current_pack,
        "recent_packs": recent_packs,
        "artifacts_distribution": artifacts_distribution,
        "artifacts_total": total,
        "exporters": exporters,
        "crypto": crypto,
        "control_case_proofs": control_case_proofs,
        "retention": retention,
        "export_journal": export_journal,
        "queue": queue,
        "footer": {"chain": footer_chain, "source": "YAML · Git"},
    }
