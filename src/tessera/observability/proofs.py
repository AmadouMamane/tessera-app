"""Proofs & exporter cockpit overview (page #15).

Composes the "Preuves & exporteurs" overview. The page has two halves:

* **The derivable core is REAL.** The proof posture (artifact counts), the
  artifact distribution and the cryptographic-verification zone are computed
  from the actual durable stores this build owns — the hash-chained audit ledger
  (:func:`~tessera.guard.ledger_store.verify_active_ledger`), the eval-score store (the
  reader seam), the replay-bundle store (``persisted_bundles``) and the eval-report
  archive (``iter_report_files``). The chain integrity is reported honestly: verified
  when the chain re-derives, broken (with the first bad index) otherwise.

  It is read from the **active store**, never from ``guard.audit_file``: post-cut that
  flat file is never written, so verifying it would report a flawless empty chain while
  the real one went unread (ADR 0023; the ban is asserted in
  ``test_audit_chain_independent_of_sink.py``).

* **Evidence packs are REAL** (lot 7): durable manifests frozen by the governed
  create endpoint (:mod:`tessera.observability.evidence_pack_store`) — real
  artifact counts, the chain verdict at freeze time, the verified creator and a
  SHA-256 digest any reader can re-derive. No pack yet → honest empty.

* **The external export / SIEM subsystem stays a demonstration.** Exporters &
  destinations, control-case linkage, retention obligations and the export
  journal describe an enterprise subsystem this build does not implement; those
  zones keep the registry-driven ``evidence_export`` synthetic notice.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from tessera.guard.ledger_store import (
    ledger_length_as_of,
    ledger_source,
    read_ledger_entries,
    verify_active_ledger,
)
from tessera.observability._asof import occurred_before
from tessera.observability.eval.report_paths import iter_report_files
from tessera.observability.evidence_pack_store import load_packs
from tessera.observability.knowledge import _LANG_IDX, _norm_lang
from tessera.observability.replay import persisted_bundles
from tessera.observability.spine.adapters import read_scores
from tessera.settings import get_settings

if TYPE_CHECKING:
    from pathlib import Path

    from tessera.guard.audit import ChainStatus


def _parse_asof(asof: str | None) -> datetime | None:
    """Parse the cockpit's as-of instant; tolerant like État à date's ``_parse_at``.

    A bare instant (no offset) reads as UTC; a malformed hand-edited deep-link
    yields ``None`` (live) rather than crashing the whole payload — the frontend
    temporal state falls back to live on the same garbage, so both agree.
    """
    if not asof:
        return None
    try:
        parsed = datetime.fromisoformat(asof.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _report_time(path: Path) -> datetime:
    """The instant an eval report came to exist — never a bare pass/fail verdict.

    Run reports are named ``<YYYYMMDD>T<HHMMSS>Z_<lang>.json`` — the run instant
    is authoritative. Alias/aggregate files (``latest.json``, ``_model_judge.json``)
    carry no instant in their name and fall back to the file's real mtime (the
    same common-provenance convention as the Configurations history). Only when
    even the stat fails does the file fall open — ``datetime.min`` sorts at or
    before every cutoff, so a bad name never silently drops a real report.
    """
    stem = path.stem.split("_", 1)[0]
    try:
        return datetime.strptime(stem, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
    except ValueError:
        try:
            return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
        except OSError:
            return datetime.min.replace(tzinfo=UTC)


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
    "footer_chain_unknown": (
        "Aucune chaîne de preuve à vérifier",
        "Keine Beweiskette zu pruefen",
        "No proof chain to verify",
    ),
    "alert_chain_unknown": (
        "Aucune chaîne d'audit à vérifier",
        "Keine Audit-Kette zu pruefen",
        "No audit chain to verify",
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


def _ledger_count_at(chain: ChainStatus, at_dt: datetime | None, asof: str | None) -> int:
    """Ledger entries existing at T; live (``at_dt`` None) reads the chain length.

    Postgres counts in SQL on the ``occurred_at`` index (never a 38 MB
    materialisation); file mode (fast CI / on-prem) filters the read seam's
    dicts — both mediums yield the same rows, so the count is medium-agnostic.
    """
    if at_dt is None:
        return chain.length
    if ledger_source() == "postgres":
        return ledger_length_as_of(at_dt)
    # Bounded read (ledger read budget): postgres bounds `until` in SQL; file mode
    # returns the flat journal, so the occurred_before filter stays load-bearing.
    return sum(
        1 for e in read_ledger_entries(until=at_dt) if occurred_before(e.get("occurred_at"), asof)
    )


def _chain_verdict(chain: ChainStatus, n_audit: int) -> tuple[bool, bool, int, str]:
    """Return ``(clean_at_t, unknown, intact_pct, intact_label)`` for the chain at T.

    Content integrity of the full chain implies every prefix is intact; a break at index b
    leaves the b entries before it intact — so the state at T is clean whenever the break sits
    at or after the T-prefix boundary.

    Unless there was no chain to read at all. ``verified`` means "no break was found", which
    is also true of a journal that was never written: this page used to answer "signature
    100 % · OK" and "Chaîne de preuve intacte" over an empty disk. Nothing to attest is
    neither intact nor broken, and the label says so rather than picking one (ADR 0026).
    """
    clean_at_t = chain.verified or (chain.broken_at is not None and chain.broken_at >= n_audit)
    unknown = chain.cannot_say
    intact_pct = (
        100
        if clean_at_t
        else (round(min(chain.broken_at or 0, n_audit) / n_audit * 100) if n_audit else 0)
    )
    return clean_at_t, unknown, intact_pct, ("—" if unknown else f"{intact_pct}%")


def _chain_alerts(
    chain: ChainStatus,
    lang: str,
    *,
    clean_at_t: bool,
    unknown: bool,
) -> list[dict[str, object]]:
    """One alert describing the chain: unknown, intact, or broken at an index."""
    if unknown:
        return [{"level": "unknown", "label": _t("alert_chain_unknown", lang)}]
    if clean_at_t:
        return [{"level": "ok", "label": _t("alert_chain_ok", lang)}]
    return [{"level": "bad", "label": _t("alert_chain_broken", lang).format(n=chain.broken_at)}]


def compute_proofs_overview(lang: str = "fr", asof: str | None = None) -> dict[str, object]:
    """Return the full Proofs & exporter overview payload, live or as-of T.

    The proof-posture KPIs, the artifact distribution and the cryptographic
    verification are derived from real stores (audit ledger, eval scores, replay
    bundles, eval reports); the evidence-pack assembly/export and SIEM chrome are
    a deterministic demonstration flagged ``evidence_export`` in the frontend.

    Args:
        lang: UI language (``fr`` / ``de`` / ``en``) for the localized free-text.
        asof: optional ISO instant T — every real count is then bounded at T
            (ledger prefix, scores/bundles/reports/packs at or before T), so the
            SR-01 command bar's "État au T" reading is REAL, never cosmetic.

    Returns:
        A JSON-serialisable mapping. ``chain_verified`` reflects the real audit
        chain; the ``crypto`` zone, the ``kpis`` and ``artifacts_distribution``
        are real; the pack/exporter/retention/journal fields are demonstration.
    """
    lang = _norm_lang(lang)
    now = datetime.now(UTC)
    at_dt = _parse_asof(asof)
    # A malformed asof reads as live: keep the string in sync so every reader
    # below (occurred_before, read_scores, persisted_bundles) sees the SAME cut.
    asof = at_dt.isoformat() if at_dt is not None else None

    # ── Real derivable core (bounded at T when asof is set) ────────────────
    chain = verify_active_ledger()
    n_audit = _ledger_count_at(chain, at_dt, asof)
    n_scores = len(read_scores(at=asof)) if asof else len(read_scores(full=True))
    n_bundles = len(persisted_bundles(at=asof))
    n_reports = sum(1 for p in iter_report_files() if at_dt is None or _report_time(p) <= at_dt)
    total = n_audit + n_scores + n_bundles + n_reports

    def _pct(n: int) -> int:
        return round(n / total * 100) if total else 0

    def _flat(v: int) -> list[int]:
        # Honest: the current real count, no fabricated trend line.
        return [v] * 7

    clean_at_t, chain_unknown, intact_pct, intact_label = _chain_verdict(chain, n_audit)

    kpis = [
        _kpi("artifacts", _fmt_int(total), "0", True, _flat(total)),
        _kpi("audit_entries", _fmt_int(n_audit), "0", True, _flat(n_audit)),
        _kpi("eval_scores", _fmt_int(n_scores), "0", True, _flat(n_scores)),
        _kpi("replays", _fmt_int(n_bundles), "0", True, _flat(n_bundles)),
        _kpi("reports", _fmt_int(n_reports), "0", True, _flat(n_reports)),
        _kpi("chain", intact_label, "0", True, _flat(0 if chain_unknown else intact_pct)),
    ]

    alerts = _chain_alerts(chain, lang, clean_at_t=clean_at_t, unknown=chain_unknown)

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
        "valid_signatures": intact_label,
        "algorithm": "SHA-256",
        "chain_length": _fmt_int(n_audit),
        "anomalies": 0 if clean_at_t else 1,
    }

    if chain_unknown:
        footer_chain = _t("footer_chain_unknown", lang)
    elif clean_at_t:
        footer_chain = _t("footer_chain", lang)
    else:
        footer_chain = _t("footer_chain_broken", lang).format(n=chain.broken_at)

    # ── REAL evidence packs (lot 7): durable manifests, attributed + digested ─
    # As-of T only the packs frozen at/before T exist (their created_at is real).
    env_label = get_settings().environment.value.capitalize()
    scope_label = f"{env_label} · Crédit Aurore"
    packs = [p for p in load_packs() if occurred_before(p.get("created_at"), asof)]
    n_packs = len(packs)

    def _pack_time(iso: object) -> str:
        try:
            return datetime.fromisoformat(str(iso)).strftime("%d/%m %H:%M")
        except ValueError:
            return "—"

    def _pack_total(pack: dict[str, object]) -> int:
        arts = pack.get("artifacts")
        return sum(int(v) for v in arts.values()) if isinstance(arts, dict) else 0

    recent_packs = [
        {
            "id": str(pack.get("pack_id", "")),
            "scope": scope_label,
            "artifacts": _fmt_int(_pack_total(pack)),
            # The digest is an integrity fingerprint (re-derivable), not a PKI
            # signature; "ok" states its presence, the verify endpoint re-derives.
            "signature": "ok" if pack.get("sha256") else "—",
            "destinations": "—",  # no external export exists in this build
            "by": str(pack.get("created_by", "")),
            "time": _pack_time(pack.get("created_at")),
            "status": "signe",
        }
        for pack in reversed(packs[-5:])
    ]

    latest = packs[-1] if packs else None
    if latest is not None:
        arts = latest.get("artifacts")
        arts = arts if isinstance(arts, dict) else {}
        start = latest.get("period_start")
        current_pack: dict[str, object] | None = {
            "id": str(latest.get("pack_id", "")),
            "period": (
                f"{_pack_time(start) if start else '…'} → "
                f"{_pack_time(latest.get('period_end'))}"
            ),
            "scope": scope_label,
            "hash": f"sha256: {str(latest.get('sha256', ''))[:12]}…",
            "signer": str(latest.get("created_by", "")),
            "contents": [{"key": key, "n": int(n)} for key, n in arts.items()],
        }
    else:
        current_pack = None  # honest: nobody froze a pack yet

    # REAL assembly pipeline: only the stages this build performs. There is no
    # external export stage — the SIEM/exporter chrome below stays demonstration.
    pipeline = [
        {"key": "collecte", "count": _fmt_int(total), "status": "ok"},
        {
            "key": "signature",
            "count": intact_label,
            "status": "unknown" if chain_unknown else ("ok" if chain.verified else "bad"),
        },
        {"key": "pack", "count": str(n_packs), "status": "ok"},
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
